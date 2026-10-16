"""NSRDB PSM v4 downloads (GOES TMY, GOES CONUS 5-min) and parsing in America/Phoenix time.

Timestamp convention. NSRDB stamps each row Year-Month-Day Hour:Minute, and the Minute is
the instant the row's values represent: :30 for the hourly TMY (mid-hour), :00, :05, ...
for the 5-min CONUS series. The parsed index keeps the minute, so pvlib SPA evaluated at the
index gives the sun position for each irradiance value. ``check_minute_convention`` proves
it against the solar zenith NSRDB ships in the file. Labelling hour-averaged values at the
hour start instead misplaces low-sun shadows by up to 30 minutes.

Arizona keeps no daylight saving time. Every index is America/Phoenix (MST, UTC-7 all year);
America/Denver would shift the summer by an hour. A file stamped in UTC (utc=true) and the
same file in local time parse to the same index.
"""

import hashlib
import os
import subprocess
from pathlib import Path

import pandas as pd
import pvlib
import requests
from pvlib.iotools import psm4

from solaris.core.params import REPO_ROOT
from solaris.site import site_config

TZ = "America/Phoenix"
UTC_OFFSET = pd.Timedelta(hours=-7)
RAW_SUBDIR = Path("data") / "raw" / "nsrdb"
DATASETS = {"tmy": psm4.PSM4_TMY_URL, "conus_5min": psm4.PSM4_CON_URL}
# NSRDB zenith vs pvlib SPA at the stamps. Correct stamps agree within 0.06 deg, except that
# the TMY's last local hours of some months come from another source day (NSRDB stitches TMY
# months in UTC): up to 0.24 deg on 32 of 8760 rows. A 5-min slip moves the sun >= 1.5 deg,
# a 30-min slip >= 6.8 deg.
ZENITH_TOL_DEG = 0.3


def dataset_name(kind, cfg) -> str:
    """NSRDB ``names`` parameter: the TMY release, or the calendar year of the 5-min series."""
    d = cfg["nsrdb"][kind]
    return d["name"] if kind == "tmy" else str(d["sensitivity_year"])


def raw_path(kind, cfg=None, root=REPO_ROOT) -> Path:
    """Cache file for one dataset, e.g. data/raw/nsrdb/33.45_-112.06_tmy-2023_60min.csv.

    Named by the requested point, not the cell: the CONUS 5-min grid cell nearest the site
    (518064) is not the TMY cell (323705). summary() records each file's cell.
    """
    cfg = cfg or site_config()
    n = cfg["nsrdb"]
    name = f"{n['lat']}_{n['lon']}_{dataset_name(kind, cfg)}_{n[kind]['interval_min']}min.csv"
    return Path(root) / RAW_SUBDIR / name


# ---------------------------------------------------------------- download
def _user_env(name):
    """Environment variable, falling back on Windows to the user-level value in the registry
    (set with [Environment]::SetEnvironmentVariable(name, value, "User")), which processes
    started before it was set do not inherit."""
    value = os.environ.get(name)
    if not value and os.name == "nt":
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                value = winreg.QueryValueEx(key, name)[0]
        except OSError:
            value = None
    return value or None


def api_credentials():
    """(api_key, email) from NREL_API_KEY and NREL_API_EMAIL (email defaults to git user.email)."""
    key = _user_env("NREL_API_KEY")
    if not key:
        raise RuntimeError(
            "NREL_API_KEY is not set. Get a free key at https://developer.nlr.gov/signup/ and "
            'store it with [Environment]::SetEnvironmentVariable("NREL_API_KEY", "<key>", "User")'
        )
    email = _user_env("NREL_API_EMAIL")
    if not email:
        git = subprocess.run(
            ["git", "config", "user.email"], cwd=REPO_ROOT, capture_output=True, text=True
        )
        email = git.stdout.strip()
    if not email:
        raise RuntimeError("NREL_API_EMAIL is not set and git has no user.email")
    return key, email


def request_params(kind, cfg, api_key, email) -> dict:
    """Query string for the NSRDB v4 CSV endpoint (same fields as pvlib's get_nsrdb_psm4_*)."""
    n = cfg["nsrdb"]
    return {
        "api_key": api_key,
        "email": email,
        "full_name": "SOLARIS-Twin",
        "affiliation": "SOLARIS-Twin",
        "reason": "research",
        "mailing_list": "false",
        "wkt": f"POINT({n['lon']:.4f} {n['lat']:.4f})",
        "names": dataset_name(kind, cfg),
        "attributes": ",".join(n["attributes"]),
        "interval": n[kind]["interval_min"],
        "utc": str(n["utc"]).lower(),
        "leap_day": "false",
    }


def download(kind, out=None, cfg=None, timeout=900, force=False) -> Path:
    """Fetch one dataset into data/raw/nsrdb. An existing file is the cache and is kept."""
    cfg = cfg or site_config()
    out = Path(out) if out else raw_path(kind, cfg)
    if out.exists() and not force:
        return out
    key, email = api_credentials()
    params = request_params(kind, cfg, key, email)
    # The request URL carries the key: never let it reach an error message or a log.
    try:
        r = requests.get(DATASETS[kind], params=params, timeout=timeout)
    except requests.RequestException as e:
        raise RuntimeError(f"NSRDB {kind} request failed: {str(e).replace(key, '***')}") from None
    if not r.ok:
        body = r.content.decode("utf-8", "replace")[:500].replace(key, "***")
        raise RuntimeError(f"NSRDB {kind} request failed: HTTP {r.status_code}: {body}")
    if not r.content.startswith(b"Source,Location ID"):
        body = r.content[:300].decode("utf-8", "replace").replace(key, "***")
        raise RuntimeError(f"NSRDB {kind}: response is not an NSRDB CSV: {body}")
    out.parent.mkdir(parents=True, exist_ok=True)
    part = out.with_name(out.name + ".part")
    part.write_bytes(r.content)
    try:
        _, meta = read_nsrdb(part)
        n = cfg["nsrdb"]
        if abs(meta["latitude"] - n["lat"]) > 0.02 or abs(meta["longitude"] - n["lon"]) > 0.02:
            raise ValueError(
                f"NSRDB {kind}: cell at ({meta['latitude']}, {meta['longitude']}), "
                f"site is ({n['lat']}, {n['lon']})"
            )
    except Exception:
        part.unlink()
        raise
    part.replace(out)
    return out


# ---------------------------------------------------------------- parsing
def read_nsrdb(path, tz=TZ):
    """NSRDB PSM v4 CSV -> (DataFrame on a tz-aware America/Phoenix index, metadata dict).

    Columns use pvlib names (ghi, dni, dhi, temp_air, solar_zenith, ...). Stamps keep the
    Minute column. Files stamped in UTC are converted.
    """
    df, meta = psm4.read_nsrdb_psm4(str(path), map_variables=True)
    local = pd.Timedelta(hours=meta["Local Time Zone"])
    if local != pd.Timestamp("2023-07-01", tz=tz).utcoffset():
        raise ValueError(f"{path}: Local Time Zone is UTC{meta['Local Time Zone']:+d}, not {tz}")
    df.index = df.index.tz_convert(tz)
    return df, meta


def to_reference_year(df, year):
    """Relabel TMY rows (each month drawn from a different year) onto one calendar year.

    Local month, day and time are kept. In a UTC download the last 7 local hours of the year
    come first, stamped in the previous year; they move to Dec 31 of the reference year.
    """
    t = df.index
    stamps = pd.to_datetime(
        pd.DataFrame(
            {"year": year, "month": t.month, "day": t.day, "hour": t.hour, "minute": t.minute}
        )
    )
    return df.set_axis(pd.DatetimeIndex(stamps).tz_localize(t.tz)).sort_index()


def check_no_dst(index, step=None):
    """Raise unless every stamp is UTC-7 and consecutive stamps are exactly ``step`` apart.

    A DST zone shows up as a changed offset, a missing hour in March or a repeated one in
    November.
    """
    wall = index.tz_localize(None)
    utc = index.tz_convert("UTC").tz_localize(None)
    offsets = (wall - utc).unique()
    if len(offsets) != 1 or offsets[0] != UTC_OFFSET:
        hours = sorted(o / pd.Timedelta(hours=1) for o in offsets)
        raise ValueError(f"UTC offsets {hours} h, expected [-7.0] h all year: DST present")
    if step is not None:
        steps = (index[1:] - index[:-1]).unique()
        if len(steps) != 1 or steps[0] != pd.Timedelta(step):
            raise ValueError(f"stamp steps {sorted(steps)} != {pd.Timedelta(step)}: gap or repeat")


def zenith_residual(df, meta):
    """NSRDB solar zenith minus pvlib SPA apparent zenith at the parsed stamps (deg)."""
    sp = pvlib.solarposition.get_solarposition(
        df.index, meta["latitude"], meta["longitude"], altitude=meta["altitude"]
    )
    return df["solar_zenith"] - sp["apparent_zenith"]


def check_minute_convention(df, meta, tol_deg=ZENITH_TOL_DEG) -> float:
    """Raise unless the stamps are the instants NSRDB computed its own zenith for.

    Returns the largest |zenith difference| in degrees.
    """
    if "solar_zenith" not in df:
        raise ValueError("file has no Solar Zenith Angle column; request solar_zenith_angle")
    worst = float(zenith_residual(df, meta).abs().max())
    if not worst <= tol_deg:
        raise ValueError(
            f"NSRDB zenith differs from SPA at the parsed stamps by {worst:.2f} deg "
            f"(> {tol_deg}): stamps do not mark the instant the values represent"
        )
    return worst


# ---------------------------------------------------------------- loaders
def tmy_hourly(path=None, cfg=None):
    """Checked 8760-h TMY on the reference year, America/Phoenix, stamps at :30."""
    cfg = cfg or site_config()
    df, meta = read_nsrdb(path or raw_path("tmy", cfg))
    check_minute_convention(df, meta)
    df = to_reference_year(df, cfg["nsrdb"]["tmy"]["reference_year"])
    check_no_dst(df.index, step="60min")
    if len(df) != 8760:
        raise ValueError(f"TMY has {len(df)} rows, expected 8760")
    return df, meta


def conus_5min(path=None, cfg=None):
    """Checked 5-min CONUS year, America/Phoenix, stamps at :00, :05, ..."""
    cfg = cfg or site_config()
    df, meta = read_nsrdb(path or raw_path("conus_5min", cfg))
    check_minute_convention(df, meta)
    step = cfg["nsrdb"]["conus_5min"]["interval_min"]
    check_no_dst(df.index, step=f"{step}min")
    expected = 365 * 24 * 60 // step  # downloads drop Feb 29 (leap_day=false)
    if len(df) != expected:
        raise ValueError(f"5-min series has {len(df)} rows, expected {expected}")
    return df, meta


def sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def summary(tmy_path, conus_path, e0_tmy_path, cfg=None) -> dict:
    """Provenance and checks for both downloads (rule weather_check).

    The downloaded TMY must reproduce the GHI and temperature of the TMY pinned for E0.
    """
    cfg = cfg or site_config()
    out = {"timezone": TZ, "utc_offset_h": UTC_OFFSET / pd.Timedelta(hours=1)}
    for kind, path, (df, meta) in (
        ("tmy", tmy_path, tmy_hourly(tmy_path, cfg)),
        ("conus_5min", conus_path, conus_5min(conus_path, cfg)),
    ):
        raw, _ = read_nsrdb(path)
        dt_h = cfg["nsrdb"][kind]["interval_min"] / 60
        out[kind] = {
            "file": Path(path).name,
            "sha256": sha256(path),
            "dataset": cfg["nsrdb"][kind]["dataset"],
            "names": dataset_name(kind, cfg),
            "version": meta["Version"],
            "location_id": int(meta["Location ID"]),
            "lat": meta["latitude"],
            "lon": meta["longitude"],
            "elevation_m": meta["altitude"],
            "rows": len(df),
            "first": str(df.index[0]),
            "last": str(df.index[-1]),
            "minutes": sorted(int(m) for m in pd.unique(df.index.minute)),
            "max_abs_zenith_residual_deg": round(float(zenith_residual(raw, meta).abs().max()), 4),
            "ghi_kWh_m2": round(float(df["ghi"].sum() * dt_h / 1000), 1),
            "dni_kWh_m2": round(float(df["dni"].sum() * dt_h / 1000), 1),
            "temp_air_mean_C": round(float(df["temp_air"].mean()), 2),
        }
    tmy, _ = tmy_hourly(tmy_path, cfg)
    e0, _ = read_nsrdb(e0_tmy_path)
    e0 = to_reference_year(e0, cfg["nsrdb"]["tmy"]["reference_year"])
    diff = {c: float((tmy[c] - e0[c]).abs().max()) for c in ("ghi", "dni", "dhi", "temp_air")}
    out["tmy_vs_e0_pinned"] = {"file": Path(e0_tmy_path).name, "max_abs_diff": diff}
    if any(diff.values()):
        raise ValueError(f"downloaded TMY differs from the E0 pinned TMY: {diff}")
    return out
