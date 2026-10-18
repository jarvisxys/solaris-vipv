"""SUMO traces for the frozen routes (P6): network from OSM, three demand seeds, 1 Hz FCD.

SUMO runs in its own conda env ('sumo': eclipse-sumo, sumolib) through sumo_job.py; this side
fetches the OSM road network around the routes, writes the job, and turns each ego vehicle's
FCD into a trajectory in UTM with heading, speed and the covered flag.
"""

import json
import subprocess
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests

from solaris.core.params import REPO_ROOT
from solaris.geometry.covered import tag_covered
from solaris.geometry.crs import GEOG_CRS, H_CRS, to_utm
from solaris.shading.city import D, ground

SUMO_PY = Path.home() / ".conda" / "envs" / "sumo" / "python.exe"
JOB = Path(__file__).with_name("sumo_job.py")
OVERPASS = "https://overpass-api.de/api/interpreter"
ROAD_TYPES = (
    "motorway",
    "motorway_link",
    "trunk",
    "trunk_link",
    "primary",
    "primary_link",
    "secondary",
    "secondary_link",
    "tertiary",
    "tertiary_link",
)


def fetch_osm(lonlat_bbox, out):
    """OSM XML of the main road network (with signal nodes) in a lon/lat bbox."""
    out = Path(out)
    if out.exists():
        return out
    w, s, e, n = lonlat_bbox
    q = (
        f'[out:xml][timeout:300];(way["highway"~"^({"|".join(ROAD_TYPES)})$"]'
        f"({s},{w},{n},{e}););(._;>;);out body;"
    )
    r = requests.post(OVERPASS, data={"data": q}, timeout=600)
    r.raise_for_status()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(r.content)
    return out


def route_polylines(routes_dir, ids):
    out = {}
    for rid in ids:
        g = gpd.read_file(Path(routes_dir) / f"{rid}.geojson").to_crs(GEOG_CRS)
        out[rid] = [list(c) for c in g.geometry.iloc[0].coords]
    return out


def run_job(job, workdir):
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    jp = workdir / "job.json"
    jp.write_text(json.dumps(job, indent=1), encoding="utf-8")
    r = subprocess.run([str(SUMO_PY), str(JOB), str(jp)], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"SUMO job failed: {r.stdout[-500:]} {r.stderr[-1500:]}")


def osm_way(edge_id):
    """SUMO edge id from an OSM import ('-123#4', '123#0') -> OSM way id ('123')."""
    return str(edge_id).lstrip("-").split("#")[0]


def trajectories(fcd_csv, start_local, covered_polys, ndsm_threshold, bridge_ways):
    """FCD of the egos -> per-vehicle trajectories in UTM with the covered flag.

    z_road is the DEM, or the DSM on a bridge the vehicle drives over (the deck), so the
    deck itself never counts as cover.
    """
    f = pd.read_csv(fcd_csv)
    x, y = to_utm(f["lat"].to_numpy(), f["lon"].to_numpy())
    f = f.assign(x_utm=x, y_utm=y, way=f["edge"].map(osm_way))
    on_bridge = f["way"].isin(bridge_ways).to_numpy()
    dem = ground(x, y)
    deck = ground(x, y, layer="dsm.tif")
    z_road = np.where(on_bridge, deck, dem)
    cov, why = tag_covered(
        x,
        y,
        covered_polys,
        D / "dsm.tif",
        D / "dem.tif",
        ndsm_threshold,
        z_road=z_road,
        own_way=f["way"].to_numpy(),
    )
    f = f.assign(z_road=z_road, covered=cov, covered_reason=why)
    f["time_local"] = pd.Timestamp(start_local) + pd.to_timedelta(f["t"], unit="s")
    return f


def trace_stats(g):
    d = np.hypot(np.diff(g["x_utm"]), np.diff(g["y_utm"])).sum()
    stopped = (g["speed"] < 0.5).to_numpy()
    stops = int(np.sum(stopped[1:] & ~stopped[:-1]))
    return {
        "duration_s": int(g["t"].iloc[-1] - g["t"].iloc[0]),
        "distance_m": round(float(d), 1),
        "mean_speed_kmh": round(float(d / max(1, g["t"].iloc[-1] - g["t"].iloc[0]) * 3.6), 2),
        "stops": stops,
        "stopped_s": int(stopped.sum()),
        "covered_s": int(g["covered"].sum()),
    }


def covered_layer():
    return gpd.read_file(D / "covered.gpkg").to_crs(H_CRS)


def bridge_way_ids(polys):
    return set(polys.loc[polys["kind"] == "bridge", "osm_id"].astype(str))


ROUTE_IDS = ("R-OPEN", "R-DENSE", "R-MIXED", "R-TUNNEL")


def build_traces(cfg, routes_dir, out_dir, table):
    """Run SUMO for every demand seed and write one trajectory per ego vehicle and seed."""
    from shapely import union_all

    from solaris.geometry.sources import lonlat_bounds

    s = cfg["sumo"]
    lines = [
        gpd.read_file(Path(routes_dir) / f"{r}.geojson").to_crs(H_CRS).geometry.iloc[0]
        for r in ROUTE_IDS
    ]
    bbox = lonlat_bounds(union_all([ln.buffer(s["corridor_buffer_m"]) for ln in lines]), pad_deg=0)
    osm = fetch_osm(bbox, REPO_ROOT / "data" / "raw" / "osm" / "sumo_roads.osm.xml")
    start = pd.Timestamp(f"2023-01-01 {s['sim_start_local']}")
    deps = [(pd.Timestamp(f"2023-01-01 {d}") - start).total_seconds() for d in s["departures"]]
    work = D / "sumo"
    job = {
        "osm": str(osm),
        "workdir": str(work),
        "routes": route_polylines(routes_dir, ROUTE_IDS),
        "departures_s": deps,
        "end_s": s["end_s"],
        "step_s": s["step_s"],
        "seeds": s["demand"],
    }
    run_job(job, work)
    polys = covered_layer()
    bridges = bridge_way_ids(polys)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for name in s["demand"]:
        f = trajectories(
            work / f"fcd_{name}.csv", start, polys, cfg["geometry"]["covered_ndsm_m"], bridges
        )
        for veh, g in f.groupby("veh"):
            rid, direction, dep = veh.rsplit("_", 2)
            g = g.sort_values("t")
            g.to_csv(out_dir / f"{veh}_{name}.csv.gz", index=False, float_format="%.3f")
            rows.append(
                {
                    "trip": f"{veh}_{name}",
                    "route": rid,
                    "direction": direction,
                    "departure": (start + pd.Timedelta(seconds=float(dep))).strftime("%H:%M"),
                    "demand": name,
                    **trace_stats(g),
                }
            )
    t = pd.DataFrame(rows).sort_values(["route", "direction", "departure", "demand"])
    Path(table).parent.mkdir(parents=True, exist_ok=True)
    t.to_csv(table, index=False, lineterminator="\n")
    return t
