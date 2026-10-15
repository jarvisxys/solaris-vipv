"""P2: NSRDB parsing in America/Phoenix time, the Minute convention and the absence of DST.

Offline: fixtures are whole local days cut from the real downloads with
tests/fixtures/cut_nsrdb.py (TMY: 01-01 03-12 06-21 11-05 12-31; 5-min 2023: 03-12 11-05,
the US DST change dates).
"""

from pathlib import Path

import pandas as pd
import pytest
import requests

from solaris import weather
from solaris.weather import nsrdb

FIX = Path(__file__).parent / "fixtures"
TMY_LOCAL = FIX / "nsrdb_tmy-2023_60min_local.csv"
TMY_UTC = FIX / "nsrdb_tmy-2023_60min_utc.csv"
CONUS = FIX / "nsrdb_2023_5min_local.csv"
CFG = weather.site_config()
DST_2023 = {"start": "2023-03-12", "end": "2023-11-05"}  # US DST, 02:00 local


@pytest.fixture(scope="module", params=[TMY_LOCAL, TMY_UTC, CONUS], ids=lambda p: p.stem)
def parsed(request):
    return weather.read_nsrdb(request.param)


@pytest.fixture(scope="module")
def tmy():
    return weather.read_nsrdb(TMY_LOCAL)


@pytest.fixture(scope="module")
def conus():
    return weather.read_nsrdb(CONUS)


# ---------------------------------------------------------------- time zone
def test_index_is_america_phoenix_utc_minus_7(parsed):
    df, _ = parsed
    assert str(df.index.tz) == "America/Phoenix"
    offsets = (df.index.tz_localize(None) - df.index.tz_convert("UTC").tz_localize(None)).unique()
    assert list(offsets) == [pd.Timedelta(hours=-7)]


def test_utc_and_local_downloads_parse_to_the_same_series(tmy):
    utc, _ = weather.read_nsrdb(TMY_UTC)
    a = weather.to_reference_year(tmy[0], 2023)
    b = weather.to_reference_year(utc, 2023)
    assert a.index.equals(b.index)
    for col in ("ghi", "dni", "dhi", "temp_air", "solar_zenith"):
        assert (a[col] == b[col]).all(), col


def test_reference_year_wraps_utc_tail_to_dec_31():
    utc, _ = weather.read_nsrdb(TMY_UTC)
    assert utc.index[0] == pd.Timestamp("2015-12-31 17:30", tz="America/Phoenix")
    ref = weather.to_reference_year(utc, 2023)
    assert set(ref.index.year) == {2023}
    assert ref.index[-1] == pd.Timestamp("2023-12-31 23:30", tz="America/Phoenix")
    assert ref.index.is_monotonic_increasing


def test_wrong_local_time_zone_is_rejected(tmp_path):
    lines = TMY_LOCAL.read_text(encoding="utf-8").splitlines(keepends=True)
    meta = lines[0].rstrip("\n").split(",")
    values = lines[1].rstrip("\n").split(",")
    values[meta.index("Local Time Zone")] = "-6"
    bad = tmp_path / "denver.csv"
    bad.write_text(lines[0] + ",".join(values) + "\n" + "".join(lines[2:]), encoding="utf-8")
    with pytest.raises(ValueError, match="Local Time Zone"):
        weather.read_nsrdb(bad)


# ---------------------------------------------------------------- Minute convention
def test_tmy_stamps_sit_at_mid_hour(tmy):
    assert set(tmy[0].index.minute) == {30}


def test_5min_stamps_cover_every_5_minutes(conus):
    assert sorted(set(conus[0].index.minute)) == list(range(0, 60, 5))


@pytest.mark.parametrize("which", ["tmy", "conus"])
def test_sun_position_at_stamps_matches_nsrdb_zenith(which, tmy, conus):
    df, meta = {"tmy": tmy, "conus": conus}[which]
    assert weather.check_minute_convention(df, meta) <= nsrdb.ZENITH_TOL_DEG


@pytest.mark.parametrize(
    ("which", "shift"),
    [("tmy", "-30min"), ("tmy", "30min"), ("conus", "-5min"), ("conus", "5min")],
)
def test_shifted_stamps_fail_the_minute_check(which, shift, tmy, conus):
    """Hour-start labels (dropping Minute) or a one-step slip must not pass."""
    df, meta = {"tmy": tmy, "conus": conus}[which]
    shifted = df.set_axis(df.index + pd.Timedelta(shift))
    with pytest.raises(ValueError, match="stamps do not mark"):
        weather.check_minute_convention(shifted, meta)


def test_minute_check_needs_zenith_column(tmy):
    df, meta = tmy
    with pytest.raises(ValueError, match="Solar Zenith"):
        weather.check_minute_convention(df.drop(columns="solar_zenith"), meta)


# ---------------------------------------------------------------- no DST
@pytest.mark.parametrize("change", DST_2023)
def test_no_dst_jump_on_us_change_days(change, conus):
    df, _ = conus
    day = df.loc[DST_2023[change]]
    assert len(day) == 288  # 24 h x 12: no missing (Mar) or repeated (Nov) hour
    weather.check_no_dst(day.index, step="5min")
    two_am = day.loc[f"{DST_2023[change]} 01:55" : f"{DST_2023[change]} 03:00"]
    assert list(two_am.index.hour) == [1] + [2] * 12 + [3]


@pytest.mark.parametrize("change", DST_2023)
def test_denver_time_would_jump(change, conus):
    """Control: the same instants on America/Denver clocks show the DST change."""
    day = conus[0].loc[DST_2023[change]]
    with pytest.raises(ValueError, match="DST present"):
        weather.check_no_dst(day.index.tz_convert("America/Denver"), step="5min")


def test_tmy_reference_year_has_no_dst(tmy):
    ref = weather.to_reference_year(tmy[0], 2023)
    for day in ("2023-03-12", "2023-11-05"):
        weather.check_no_dst(ref.loc[day].index, step="60min")
        assert len(ref.loc[day]) == 24


@pytest.mark.parametrize("drop", [5, None])
def test_check_no_dst_catches_gap_and_repeat(drop, conus):
    idx = conus[0].loc[DST_2023["start"]].index
    idx = idx.delete(drop) if drop is not None else idx.insert(25, idx[24])
    with pytest.raises(ValueError, match="gap or repeat"):
        weather.check_no_dst(idx, step="5min")


# ---------------------------------------------------------------- download (no network)
def test_cache_paths_follow_site_config():
    assert weather.raw_path("tmy", CFG, root=".").as_posix() == (
        "data/raw/nsrdb/33.45_-112.06_tmy-2023_60min.csv"
    )
    assert weather.raw_path("conus_5min", CFG, root=".").as_posix() == (
        "data/raw/nsrdb/33.45_-112.06_2023_5min.csv"
    )


@pytest.mark.parametrize(
    ("kind", "names", "interval"), [("tmy", "tmy-2023", 60), ("conus_5min", "2023", 5)]
)
def test_request_params(kind, names, interval):
    p = nsrdb.request_params(kind, CFG, "KEY", "a@b.c")
    assert p["wkt"] == "POINT(-112.0600 33.4500)"
    assert (p["names"], p["interval"], p["utc"], p["leap_day"]) == (
        names,
        interval,
        "false",
        "false",
    )
    assert "solar_zenith_angle" in p["attributes"].split(",")


def test_cached_file_is_not_downloaded_again(tmp_path, monkeypatch):
    out = tmp_path / "cached.csv"
    out.write_text("cached", encoding="utf-8")
    monkeypatch.setattr(requests, "get", lambda *a, **k: pytest.fail("network used"))
    assert weather.download("tmy", out, CFG) == out


def test_api_key_never_reaches_error_messages(tmp_path, monkeypatch):
    secret = "s3cr3t-key-value"
    monkeypatch.setattr(nsrdb, "api_credentials", lambda: (secret, "a@b.c"))

    def refused(url, params, timeout):
        raise requests.ConnectionError(f"Max retries exceeded with url: {url}?api_key={secret}")

    monkeypatch.setattr(requests, "get", refused)
    with pytest.raises(RuntimeError) as err:
        weather.download("tmy", tmp_path / "x.csv", CFG)
    assert secret not in str(err.value)
    assert not (tmp_path / "x.csv").exists()
