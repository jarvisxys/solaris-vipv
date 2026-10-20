"""Visual-only data for the Unity Playback scene (P8-visual). Never feeds a reported number.

Writes twin/exchange/visual/hud_<trip>_<date>.csv (gitignored) for every exported trajectory:
    t_utc, pv_W, trip_Wh, pv_<facet>_W ..., street
Per-second PV is E3 case C (buildings + trees, tau base) on the matching TMY day, the same
arithmetic as the E8 render overlay (experiments/e8_validation/run.py: render_overlay). Street
names come from the trace's OSM way ids and the raw OSM tiles of the SUMO network. This
script only reads the frozen code and data.

    python twin/visual/export_visual.py            # all 120 R-DENSE trip-dates
    python twin/visual/export_visual.py --trip R-DENSE_fwd_1800_medium
    python twin/visual/export_visual.py --streets  # street names only, into existing files
"""

import argparse
import importlib.util
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from solaris.pv import series  # noqa: E402
from solaris.pv.model import cell_temperature, pv_energy  # noqa: E402
from solaris.site import site_config  # noqa: E402
from solaris.twin_io import export as ex  # noqa: E402
from solaris.vehicle import vehicle_config  # noqa: E402
from solaris.weather import tmy_hourly  # noqa: E402

OUT = REPO / "twin" / "exchange" / "visual"


def e3_module():
    p = REPO / "experiments" / "e3_driving" / "run.py"
    spec = importlib.util.spec_from_file_location("e3_driving_run", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def trip_day_pv(e3m, geo, f, day, e3, vcfg, wx, meta):
    """Per-second PV power (W), total and per facet, case C on the TMY day."""
    times, sp = e3m.day_inputs(f, day, meta)
    bld, tree = geo.beam(sp["azimuth"].to_numpy(), sp["apparent_elevation"].to_numpy())
    ghi, dni, dhi = e3m.irradiance(
        times, "tmy", wx, meta["latitude"], meta["longitude"], meta["altitude"]
    )
    sun = series.sun_at((times - series.YEAR_START).total_seconds().to_numpy(), meta)
    hour = (times.dayofyear - 1) * 24 + times.hour
    T = wx["temp_air"].to_numpy()[hour]
    wind = wx["wind_speed"].to_numpy()[hour] + f["speed"].to_numpy()
    tau, fa = e3["tree_transmissivity"], vcfg["pv"]["faiman"]
    w = {"ghi": ghi, "dni": dni, "dhi": dhi}
    cols = {}
    for fct in geo.fs:
        k = geo.sid == fct.id
        caz = (geo.heading + fct.azimuth_body_deg) % 360
        beam, iso, hzc, ground_r, _ = series.facet_terms(
            fct.tilt_deg, caz, sun, w, vcfg["pv"]["albedo"]
        )
        v = geo.views[fct.id]
        vb = np.where(bld[:, k], 0.0, np.where(tree[:, k], tau, 1.0)).mean(axis=1)
        svf = v["svf_a"] + tau * (v["svf_b"] - v["svf_a"])
        vhz = v["hz_a"] + tau * (v["hz_b"] - v["hz_a"])
        g = np.where(geo.cov, 0.0, vb * beam + svf * iso + vhz * hzc + ground_r)
        tc = cell_temperature(g, T, wind, "faiman", fa["u0"], fa["u1"])
        cols[f"pv_{fct.id}_W"] = pv_energy(fct.area_m2, g, tc) * 1000.0
    pv = sum(cols.values())
    df = pd.DataFrame(
        {
            "t_utc": times.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
            "pv_W": pv,
            "trip_Wh": np.cumsum(pv) / 3600.0,
            **cols,
        }
    )
    return df


def main(route="R-DENSE", only=None):
    e3 = yaml.safe_load((REPO / "configs" / "experiments" / "e3.yaml").read_text(encoding="utf-8"))
    cfg, vcfg = site_config(), vehicle_config()
    wx, meta = tmy_hourly()
    e3m = e3_module()
    trips = [t for t in ex.trip_names(route) if only is None or t == only]
    data = {t: e3m.load_trip(t) for t in trips}
    hz = e3m.position_horizons(data, cfg, e3["position_round_m"])
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    for i, trip in enumerate(trips):
        f = data[trip]
        geo = e3m.TripGeometry(f, hz[trip], e3, cfg, vcfg)
        streets = trip_streets(f, osm_street_names())
        for day in e3["days"]:
            df = trip_day_pv(e3m, geo, f, day, e3, vcfg, wx, meta)
            df["street"] = streets
            df.to_csv(
                OUT / f"hud_{trip}_{day}.csv", index=False, lineterminator="\n", float_format="%.3f"
            )
        del geo
        print(f"[visual] {i + 1}/{len(trips)} {trip} ({time.time() - t0:.0f} s)", flush=True)


# ---------------------------------------------------------------- street names (feature 2)
_NAMES = None


def osm_street_names():
    """OSM way id -> street name, from the raw OSM tiles behind the frozen SUMO network."""
    global _NAMES
    if _NAMES is None:
        import xml.etree.ElementTree as ET

        _NAMES = {}
        for fn in sorted((REPO / "data" / "raw" / "osm").glob("sumo_roads_v2.osm_*.xml")):
            for _, el in ET.iterparse(fn):
                if el.tag == "way":
                    tags = {t.get("k"): t.get("v") for t in el.findall("tag")}
                    name = tags.get("name") or tags.get("ref") or ""
                    _NAMES[el.get("id")] = name.replace(",", " ").strip()
                    el.clear()
    return _NAMES


def trip_streets(f, names):
    """Street name per trace second; junction seconds (no OSM way) keep the last street."""
    way = f["way"].astype(str).str.replace(r"\.0$", "", regex=True)
    s = way.map(lambda w: names.get(w, "")).replace("", np.nan)
    return s.ffill().bfill().fillna("").to_numpy()


def add_streets(route="R-DENSE"):
    """Add or refresh the street column of existing HUD files without recomputing PV."""
    e3 = yaml.safe_load((REPO / "configs" / "experiments" / "e3.yaml").read_text(encoding="utf-8"))
    names = osm_street_names()
    n = 0
    for trip in ex.trip_names(route):
        streets = trip_streets(ex.load_trip(trip), names)
        for day in e3["days"]:
            p = OUT / f"hud_{trip}_{day}.csv"
            df = pd.read_csv(p, dtype={"t_utc": str})
            if len(df) != len(streets):
                raise ValueError(f"{p}: {len(df)} rows, trace has {len(streets)}")
            df["street"] = streets
            df.to_csv(p, index=False, lineterminator="\n", float_format="%.3f")
            n += 1
    print(f"[visual] street names added to {n} HUD files")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--route", default="R-DENSE")
    ap.add_argument("--trip", default=None)
    ap.add_argument(
        "--streets", action="store_true", help="only add street names to existing files"
    )
    a = ap.parse_args()
    if a.streets:
        add_streets(a.route)
    else:
        main(a.route, a.trip)
