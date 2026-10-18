"""Select and freeze the study routes and parking sites (workflow guide Sec. 3, P6).

    python routes/select_routes.py            # writes routes/v1/ (refuses if it exists)

Routes: every named OSM trunk/primary/secondary arterial in the AOI, sampled every 10 m at
1.8 m above the DEM; SVF and annual sunlit fraction from the E1 raster engine; 8 km
candidate windows; Open = highest mean SVF, Dense = lowest, Mixed = highest SVF variance
among candidates with median-band mean SVF; at least one N-S and one E-W route. The
optional R-TUNNEL (I-10 Deck Park Tunnel) is the shortest drive path between its seed ends.
Parking: P1-P5 chosen from SVF near the seeds (src/solaris/trajectory/parking.py).

Outputs: routes/v1/{R-OPEN,R-DENSE,R-MIXED,R-TUNNEL}.geojson, routes/v1/parking_sites.geojson,
routes/v1/MANIFEST.json (SHA-256 of every file, selection record); results/p6/
table_route_candidates.csv; data/derived/routes/arterial_points.csv.gz.
A frozen version is never edited: a change goes to routes/v2/.
"""

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
import shapely

from solaris.core.params import REPO_ROOT
from solaris.geometry.crs import GEOG_CRS, H_CRS, aoi, seed_geometries
from solaris.geometry.sources import lonlat_bounds
from solaris.pv.model import sun_inputs
from solaris.shading import sky_view_factor
from solaris.shading.city import D, ground, horizons
from solaris.site import site_config
from solaris.trajectory import parking, routes
from solaris.weather import tmy_hourly

ARTERIALS = REPO_ROOT / "data" / "raw" / "osm" / "arterials.gpkg"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def arterials(cfg):
    if not ARTERIALS.exists():
        bb = lonlat_bounds(aoi(cfg), pad_deg=0)
        routes.download_arterials(bb, cfg["routes"]["road_types"]).to_file(ARTERIALS)
    return gpd.read_file(ARTERIALS)


def point_metrics(pts, cfg):
    r, sc = cfg["routes"], cfg["shading"]
    z = ground(pts["x"], pts["y"]) + r["eye_height_m"]
    h_b, h_a = horizons(pts["x"].to_numpy(), pts["y"].to_numpy(), z, sc)
    df, meta = tmy_hourly()
    sun = sun_inputs(df.index, meta["latitude"], meta["longitude"], meta["altitude"])
    day = sun["zenith"] < 90
    return pts.assign(
        z=z,
        svf=sky_view_factor(h_a),
        svf_bld=sky_view_factor(h_b),
        sunlit=routes.sunlit_fraction(
            h_a, sun["azimuth"][day].to_numpy(), 90 - sun["zenith"][day].to_numpy()
        ),
    )


def tunnel_route(cfg):
    """Shortest drive path (freeways included) between the R-TUNNEL seed ends."""
    import osmnx as ox

    (la0, lo0), (la1, lo1) = cfg["aoi"]["seeds"]["R-TUNNEL"]
    pad = 0.01
    G = ox.graph_from_bbox(
        (min(lo0, lo1) - pad, min(la0, la1) - pad, max(lo0, lo1) + pad, max(la0, la1) + pad),
        network_type="drive",
    )
    a = ox.distance.nearest_nodes(G, lo0, la0)
    b = ox.distance.nearest_nodes(G, lo1, la1)
    path = ox.routing.shortest_path(G, a, b, weight="travel_time")
    e = ox.routing.route_to_gdf(G, path).to_crs(H_CRS)
    coords = []
    for gm in e.geometry:
        c = list(gm.coords)
        coords += c if not coords else c[1:]
    return shapely.LineString(coords)


def freeze(out_dir, lines, props, sites, record):
    out_dir.mkdir(parents=True, exist_ok=True)  # main() refuses a folder that has a MANIFEST
    (out_dir / ".gitkeep").unlink(missing_ok=True)
    files = {}
    for rid, line in lines.items():
        g = gpd.GeoDataFrame([props[rid]], geometry=[line], crs=H_CRS).to_crs(GEOG_CRS)
        p = out_dir / f"{rid}.geojson"
        g.to_file(p, driver="GeoJSON")
        files[p.name] = sha256(p)
    p = out_dir / "parking_sites.geojson"
    parking.site_table(sites).to_crs(GEOG_CRS).to_file(p, driver="GeoJSON")
    files[p.name] = sha256(p)
    man = {
        "version": out_dir.name,
        "frozen_utc": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "files": files,
        **record,
    }
    text = json.dumps(man, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    (out_dir / "MANIFEST.json").write_text(text + "\n", encoding="utf-8", newline="\n")
    return man


def main(out_dir=None):
    cfg = site_config()
    r, pc = cfg["routes"], cfg["parking"]
    out_dir = Path(out_dir or REPO_ROOT / "routes" / r["version"])
    if (out_dir / "MANIFEST.json").exists():
        raise SystemExit(f"{out_dir} is frozen; write a new version (routes/v2) instead")
    edges = arterials(cfg)
    pts_path = D / "routes" / f"arterial_points_{r['version']}.csv.gz"
    if pts_path.exists():  # horizons over every arterial point are the slow part
        pts = pd.read_csv(pts_path)
    else:
        pts = point_metrics(
            routes.arterial_points(edges, r["sample_step_m"], r["street_suffix"]), cfg
        )
        pts_path.parent.mkdir(parents=True, exist_ok=True)
        pts.to_csv(pts_path, index=False, float_format="%.4f")
    cands = routes.candidates(pts, r)
    res = REPO_ROOT / "results" / "p6"
    res.mkdir(parents=True, exist_ok=True)
    cands.to_csv(
        res / "table_route_candidates.csv", index=False, lineterminator="\n", float_format="%.5g"
    )
    sel = routes.choose(cands, r["mixed_band"])
    seeds = seed_geometries(cfg)
    lines, props = {}, {}
    for rid, row in sel.items():
        line = routes.route_line(
            edges, row["street"], row["s_from"], row["s_to"], row["orientation"]
        )
        lines[rid] = line
        props[rid] = {
            "id": rid,
            "street": row["street"],
            "orientation": row["orientation"],
            "length_m": round(line.length, 1),
            "window_from_m": float(row["s_from"]),
            "window_to_m": float(row["s_to"]),
            "svf_mean": round(row["svf_mean"], 4),
            "svf_var": round(row["svf_var"], 5),
            "svf_bld_mean": round(row["svf_bld_mean"], 4),
            "sunlit_mean": round(row["sunlit_mean"], 4),
            "seed_overlap": json.dumps(routes.seed_overlap(line, seeds)),
        }
    t = tunnel_route(cfg)
    lines["R-TUNNEL"] = t
    cov = gpd.read_file(D / "covered.gpkg")
    covered_m = t.intersection(cov[cov["kind"] == "tunnel"].union_all()).length
    props["R-TUNNEL"] = {
        "id": "R-TUNNEL",
        "street": "I-10 Deck Park Tunnel (seed)",
        "orientation": "E-W",
        "length_m": round(t.length, 1),
        "tunnel_m": round(covered_m, 1),
        "role": "covered-segment check, outside the E3 matrix",
    }

    sd = {k: to_xy(cfg["aoi"]["seeds"][k][0]) for k in ("P1", "P3")}
    eye, sc = r["eye_height_m"], cfg["shading"]
    fp = gpd.read_file(
        REPO_ROOT / "data" / "raw" / "overture" / "buildings.gpkg",
        bbox=shapely.Point(to_xy(cfg["aoi"]["seeds"]["P2"][0])).buffer(800).bounds,
    )
    sites = {
        "P1": parking.p1_open_lot(sd["P1"], pc, sc, eye),
        "P2": parking.p2_curb(edges, pc, sc, eye),
        "P3": parking.p3_driveway(sd["P3"], pc, sc, eye),
        "P4": parking.p4_garage_deck(to_xy(cfg["aoi"]["seeds"]["P2"][0]), fp, pc, sc, eye),
    }
    p5 = dict(sites["P1"])
    p5["criterion"] = (
        "the P1 stall under a {canopy_height_m} m x {canopy_across_m} x {canopy_along_m} m "
        "shade roof".format(**pc["P5"])
    )
    p5["canopy"] = True
    sites["P5"] = p5
    record = {
        "selection": {k: props[k] for k in ("R-OPEN", "R-DENSE", "R-MIXED")},
        "candidates": int(len(cands)),
        "arterial_points": int(len(pts)),
        "rule": "Open = max mean SVF; Dense = min; Mixed = max SVF variance in the "
        f"{r['mixed_band']} mean-SVF quantile band; >= 1 N-S and >= 1 E-W; distinct streets",
        "parking": {
            k: {kk: (round(vv, 4) if isinstance(vv, float) else vv) for kk, vv in s.items()}
            for k, s in sites.items()
        },
    }
    return freeze(out_dir, lines, props, sites, record)


def to_xy(latlon):
    from solaris.geometry.crs import to_utm

    return to_utm(*latlon)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", help="output folder (default routes/<version>)")
    a = ap.parse_args()
    print(json.dumps(main(a.out), indent=2, default=str))
