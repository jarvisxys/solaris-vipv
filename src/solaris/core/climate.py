"""Hourly climate inputs: the conference synthetic generator and measured TMY loaders."""

import csv
from pathlib import Path

import numpy as np

from .params import BASE, REPO_ROOT, Params, Site


def hourly_climate(lat, psh_target, Tmean, Tamp, seed=0):
    """Synthetic 8760-h GHI (W/m2) and air temperature (C), rescaled to the target annual PSH.

    Clear-sky x seasonal-clearness model with daily noise; a Jul-Aug monsoon dip below 30 deg N.
    """
    rng = np.random.default_rng(seed)
    hours = np.arange(8760)
    d = hours // 24
    hod = hours % 24
    decl = np.radians(23.45) * np.sin(2 * np.pi * (284 + d) / 365.0)
    omega = np.radians(15.0 * (hod - 12))
    la = np.radians(lat)
    cosz = np.sin(la) * np.sin(decl) + np.cos(la) * np.cos(decl) * np.cos(omega)
    cosz = np.clip(cosz, 0, None)
    ghi_clear = 1000.0 * cosz**1.15
    Kt = 0.75 + 0.10 * np.cos(2 * np.pi * (d - 172) / 365.0)
    if lat < 30:
        Kt -= 0.20 * np.exp(-((d - 200) ** 2) / (2 * 25**2))
    daily_noise = rng.normal(1.0, 0.18, 366)[d]
    ghi = np.clip(ghi_clear * Kt * daily_noise, 0, None)
    psh_now = ghi.sum() / 1000.0 / 365.0
    ghi *= psh_target / psh_now
    Tseason = Tmean - Tamp * np.cos(2 * np.pi * (d - 200) / 365.0)
    Tdiurnal = 6.0 * (-np.cos(2 * np.pi * (hod - 15) / 24.0))
    return ghi, Tseason + Tdiurnal


def site_climate(site: Site, seed=0):
    return hourly_climate(site.lat, site.psh, site.T_mean, site.T_amp, seed)


def gsa_psh(city: str, p: Params = BASE) -> float:
    """Measured annual GHI from Global Solar Atlas as peak-sun-hours per day (3 d.p.)."""
    return round(p.gsa[city][2] / 365.0, 3)


def gsa_site(city: str, p: Params = BASE) -> Site:
    """Synthetic site rescaled to the measured Global Solar Atlas GHI and temperature (Tier 1)."""
    s = p.sites[city]
    return Site(s.lat, gsa_psh(city, p), p.gsa[city][5], s.T_amp)


def tmy_path(city: str, p: Params = BASE) -> Path:
    return REPO_ROOT / p.tmy_files[city]


def load_tmy(path):
    """Measured 8760-h series -> (GHI W/m2, T_amb C). Auto-detects NSRDB and PVGIS CSVs.

    NSRDB files must carry local-standard-time stamps: a file whose ``Time Zone`` differs
    from its ``Local Time Zone`` (a UTC download) is rejected, because the SoC loop indexes
    hours of the local day.
    """
    raw = Path(path).read_text(encoding="utf-8-sig").splitlines()
    if any(line.startswith("time(UTC)") for line in raw):  # PVGIS
        i = next(i for i, line in enumerate(raw) if line.startswith("time(UTC)"))
        ghi, T = [], []
        for line in raw[i + 1 :]:
            parts = line.split(",")
            if len(parts) < 5 or not parts[0][:4].isdigit():
                break
            T.append(float(parts[1]))
            ghi.append(float(parts[3]))
    else:  # NSRDB
        rows = list(csv.reader(raw))
        meta = dict(zip(rows[0], rows[1], strict=False))
        tz, local_tz = meta.get("Time Zone"), meta.get("Local Time Zone")
        if tz is not None and local_tz is not None and float(tz) != float(local_tz):
            raise ValueError(
                f"{path}: NSRDB timestamps are UTC{float(tz):+g}, not local time "
                f"(UTC{float(local_tz):+g}); download with local time (utc=false)"
            )
        hdr = rows[2]
        gi, ti = hdr.index("GHI"), hdr.index("Temperature")
        ghi = [float(r[gi]) for r in rows[3:] if len(r) > gi]
        T = [float(r[ti]) for r in rows[3:] if len(r) > ti]
    ghi = np.asarray(ghi, float)
    T = np.asarray(T, float)
    if len(ghi) != 8760:
        idx = np.linspace(0, len(ghi) - 1, 8760).astype(int)
        ghi, T = ghi[idx], T[idx]
    return ghi, T


def monthly_psh(ghi):
    """Mean daily PSH per 30.44-day month bucket (conference convention)."""
    mh = np.minimum(((np.arange(8760) // 24) / 30.44).astype(int), 11)
    return np.array([ghi[mh == m].sum() / 1000.0 / (np.sum(mh == m) / 24.0) for m in range(12)])


def climate_error(loc, p: Params = BASE):
    """Annual and monthly error of the synthetic series vs the measured TMY (None if absent)."""
    if loc not in p.tmy_files or not tmy_path(loc, p).exists():
        return None
    meas_ghi, _ = load_tmy(tmy_path(loc, p))
    syn_ghi, _ = site_climate(p.sites[loc])
    meas, syn = monthly_psh(meas_ghi), monthly_psh(syn_ghi)
    return dict(
        ann_err=100 * (syn.mean() - meas.mean()) / meas.mean(),
        monthly_mape=float(np.mean(np.abs(syn - meas) / meas) * 100),
        syn=syn,
        meas=meas,
    )
