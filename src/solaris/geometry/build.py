"""P3 build steps behind the Snakemake geom_* rules; data layout under data/ (see geom/README.md).

Per-tile steps (fetch, rasterize, model, meshes) run in worker processes through
``python -m solaris.geometry <step>`` and cache per tile, so an interrupted or repeated run
only redoes missing tiles.
"""

import csv
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import geopandas as gpd

from solaris.core.params import REPO_ROOT
from solaris.site import site_config

from . import control, covered, freshness, lidar, meshes, rasters, sources
from .crs import H_CRS, Tile, aoi, tiles

# SOLARIS_DATA points the whole build at another root (trial runs on a few tiles).
D = Path(os.environ.get("SOLARIS_DATA", REPO_ROOT / "data"))
P = {
    "aoi": D / "derived" / "aoi.geojson",
    "tiles": D / "derived" / "tiles.csv",
    "laz": D / "raw" / "lidar" / "tiles",
    "lidar": D / "derived" / "lidar",
    "dtm_raw": D / "derived" / "lidar" / "dtm_raw.tif",
    "dsm_lidar": D / "derived" / "lidar" / "dsm_lidar.vrt",
    "dem": D / "derived" / "dem.tif",
    "naip": D / "raw" / "naip",
    "naip_vrt": D / "derived" / "naip.vrt",
    "overture": D / "raw" / "overture" / "buildings.gpkg",
    "osm": D / "raw" / "osm" / "covered_ways.gpkg",
    "model": D / "derived" / "model",
    "classes": D / "derived" / "classes.tif",
    "dsm_epoch": D / "derived" / "dsm_lidar_epoch.tif",
    "cdsm": D / "derived" / "cdsm.tif",
    "holes": D / "derived" / "dsm_holes.tif",
    "dsm": D / "derived" / "dsm.tif",
    "covered": D / "derived" / "covered.gpkg",
    "candidates": D / "derived" / "freshness_candidates.gpkg",
    "meshes": D / "derived" / "tiles",
    "ngs": D / "raw" / "ngs" / "marks.json",
    "logs": D / "derived" / "logs",
    "origin": (REPO_ROOT / "twin" / "exchange" if "SOLARIS_DATA" not in os.environ else D)
    / "enu_origin.json",
    "confirmations": REPO_ROOT / "configs" / "site" / "freshness_v1.yaml",
}
MODEL_LAYERS = ("classes", "dsm", "cdsm", "holes", "ndvi")
WORKERS = {"fetch": 6, "rasterize": 4, "model": 4, "meshes": 4}
CACHE = {"fetch": P["laz"], "rasterize": P["lidar"], "model": P["model"], "meshes": P["meshes"]}


def step_params(step, cfg=None) -> dict:
    """Settings each cached step depends on. Snakemake reruns a rule when they change
    (params trigger), and run_tiles clears that step's tile cache when they differ from
    the ones it was built with."""
    cfg = cfg or site_config()
    g = cfg["geometry"]
    common = {"res": g["resolution_m"], "tile_m": g["tile_m"], "margin": g["tile_margin_m"]}
    return {
        "aoi": {**cfg["aoi"], "tile_m": g["tile_m"]},
        "fetch": {"ept": cfg["lidar"]["ept"], "noise": g["noise_classes"], **common},
        "rasterize": common,
        "dem": {"fill_m": g["dtm_fill_max_m"], **common},
        "naip": {"year": g["naip_year"]},
        "model": {k: g[k] for k in ("tree", "building", "min_blob_m2", "naip_year")} | common,
        "freshness": g["freshness"] | {"ndsm_min": g["building"]["ndsm_min_m"]},
        "meshes": {**g["mesh"], **common, "origin": cfg["enu_origin"]},
        "covered": {"ndsm_m": g["covered_ndsm_m"]},
    }[step]


def reset_cache(step, cfg=None):
    """Empty a step's tile cache if its stamp records other settings. A cache without a
    stamp is adopted, never deleted."""
    import shutil

    folder, params = CACHE[step], step_params(step, cfg)
    stamp = folder / "PARAMS.json"
    if stamp.exists() and json.loads(stamp.read_text()) != params:
        shutil.rmtree(folder)
    folder.mkdir(parents=True, exist_ok=True)
    stamp.write_text(json.dumps(params, indent=1) + "\n", encoding="utf-8", newline="\n")


def write_json(path, doc):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8", newline="\n")


# ---------------------------------------------------------------- step 1
def step_aoi(cfg=None):
    cfg = cfg or site_config()
    poly = aoi(cfg)
    P["aoi"].parent.mkdir(parents=True, exist_ok=True)
    gpd.GeoDataFrame({"name": ["aoi"]}, geometry=[poly], crs=H_CRS).to_file(P["aoi"])
    ts = tiles(cfg, poly)
    with open(P["tiles"], "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(Tile._fields)
        w.writerows(ts)
    return {"area_km2": round(poly.area / 1e6, 2), "tiles": len(ts), "bounds_utm": poly.bounds}


def load_tiles(path=None) -> list[Tile]:
    with open(path or P["tiles"], newline="", encoding="utf-8") as f:
        return [Tile(r["id"], *(float(r[k]) for k in Tile._fields[1:])) for r in csv.DictReader(f)]


# ---------------------------------------------------------------- per-tile workers
def _footprints():
    fp = gpd.read_file(P["overture"])
    _ = fp.sindex  # build the spatial index once per worker
    return fp


_FP = None


def _work(step, tile, cfg, h0):
    global _FP
    if step == "fetch":
        return lidar.fetch_tile(cfg, tile, P["laz"])
    if step == "rasterize":
        return lidar.rasterize_tile(cfg, tile, P["laz"], P["lidar"])
    if step == "model":
        if _FP is None:
            _FP = _footprints()
        paths = {"dsm_lidar": P["dsm_lidar"], "dem": P["dem"], "naip": P["naip_vrt"]}
        dirs = {k: P["model"] / k for k in MODEL_LAYERS}
        return rasters.model_tile(tile, cfg, paths, _FP, dirs)
    if step == "meshes":
        paths = {"dem": P["dem"], "dsm": P["dsm"], "cdsm": P["cdsm"]}
        return meshes.build_tile(tile, cfg, paths, P["meshes"], h0)
    raise ValueError(step)


def run_tiles(step, workers=None, only=None) -> list[dict]:
    """Run one per-tile step over all tiles (or ``only`` ids) in worker processes."""
    cfg = site_config()
    reset_cache(step, cfg)
    ts = [t for t in load_tiles() if only is None or t.id in only]
    h0 = json.loads(P["origin"].read_text())["h_ellipsoid_m"] if step == "meshes" else None
    log = P["logs"] / f"{step}.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    results, t0 = [], time.time()
    mode = "w" if step == "meshes" else "a"  # meshes are rebuilt whole; the log is the manifest
    with ProcessPoolExecutor(workers or WORKERS[step]) as pool, open(log, mode) as lf:
        futs = {pool.submit(_work, step, t, cfg, h0): t for t in ts}
        for i, fut in enumerate(as_completed(futs), start=1):
            try:
                r = fut.result()
            except Exception as e:  # keep going; failures are listed at the end
                r = {"tile": futs[fut].id, "status": "error", "error": repr(e)[:300]}
            results.append(r)
            lf.write(json.dumps(r) + "\n")
            lf.flush()
            if i % 10 == 0 or i == len(ts):
                el = time.time() - t0
                print(
                    f"{step}: {i}/{len(ts)} tiles, {el / 60:.1f} min, "
                    f"eta {el / i * (len(ts) - i) / 60:.0f} min",
                    flush=True,
                )
    return results


def run_step_subprocess(step, workers=None):
    """Called from Snakemake: run a per-tile step in a fresh interpreter (spawned workers
    then never import Snakemake's main module)."""
    env = dict(os.environ, PYTHONPATH=str(REPO_ROOT / "src"), GDAL_CACHEMAX="256")
    share = Path(sys.prefix) / "Library" / "share"
    env.setdefault("GDAL_DATA", str(share / "gdal"))
    env.setdefault("PROJ_DATA", str(share / "proj"))
    cmd = [sys.executable, "-m", "solaris.geometry", step]
    if workers:
        cmd += ["--workers", str(workers)]
    subprocess.run(cmd, check=True, env=env, cwd=REPO_ROOT)


def check_results(step, results):
    bad = [r for r in results if r["status"] == "error"]
    if bad:
        raise RuntimeError(f"{step}: {len(bad)} tiles failed, e.g. {bad[0]}")


# ---------------------------------------------------------------- mosaics and global steps
def step_lidar_mosaics():
    ts = load_tiles()
    for k in lidar.RASTERS:
        paths = [lidar.raster_paths(P["lidar"], t)[k] for t in ts]
        if k == "dtm":
            rasters.mosaic(paths, P["dtm_raw"])
        else:
            rasters.mosaic(paths, P["lidar"] / f"{k}_lidar.tif", vrt_only=True)


def step_dem(cfg=None):
    cfg = cfg or site_config()
    g = cfg["geometry"]
    rasters.fill_dtm(P["dtm_raw"], P["dem"], g["dtm_fill_max_m"], g["resolution_m"])


def step_naip(cfg=None):
    cfg = cfg or site_config()
    year = cfg["geometry"]["naip_year"]
    folder = P["naip"] / str(year)
    if not (folder / "MANIFEST.json").exists():
        sources.fetch_naip(aoi(cfg), year, folder)
    rasters.mosaic(sorted(folder.glob("*.tif")), P["naip_vrt"], vrt_only=True)


def step_model_mosaics():
    ts = load_tiles()
    out = {"classes": P["classes"], "dsm": P["dsm_epoch"], "cdsm": P["cdsm"], "holes": P["holes"]}
    for k in MODEL_LAYERS:
        paths = [P["model"] / k / f"{t.id}.tif" for t in ts]
        if k == "ndvi":
            rasters.mosaic(paths, D / "derived" / "ndvi.tif", vrt_only=True)
        else:
            rasters.mosaic(paths, out[k])


def step_covered(cfg=None):
    ways = gpd.read_file(P["osm"])
    covered.covered_polygons(ways).to_file(P["covered"], layer="covered")


def step_freshness(table_out, cfg=None):
    cfg = cfg or site_config()
    fp = _footprints()
    br = gpd.read_file(P["covered"])
    cand = freshness.candidates(cfg, load_tiles(), fp, br, P["classes"], P["dsm_epoch"], P["dem"])
    cand.to_file(P["candidates"], layer="candidates")
    Path(table_out).parent.mkdir(parents=True, exist_ok=True)
    freshness.to_table(cand).to_csv(table_out, index=False, lineterminator="\n")


def step_dsm(cfg=None):
    cfg = cfg or site_config()
    return freshness.apply_confirmed(
        P["dsm_epoch"],
        P["dem"],
        P["candidates"],
        P["confirmations"],
        P["dsm"],
        cfg["geometry"]["freshness"]["floor_height_m"],
    )


def step_enu_origin(cfg=None):
    cfg = cfg or site_config()
    o = control.enu_origin(cfg, P["dem"])
    write_json(P["origin"], o)
    return o


def step_ground_control(table_out, cfg=None):
    cfg = cfg or site_config()
    if not P["ngs"].exists():
        control.fetch_ngs(aoi(cfg), P["ngs"])
    marks = json.loads(P["ngs"].read_text(encoding="utf-8"))
    origin = json.loads(P["origin"].read_text(encoding="utf-8"))
    gcp = control.ground_control(cfg, marks, P["dem"], origin)
    Path(table_out).parent.mkdir(parents=True, exist_ok=True)
    gcp.to_csv(table_out, index=False, lineterminator="\n")
    return control.control_summary(gcp)


def _blocks(path, fn):
    """Fold ``fn(block, acc)`` over a raster's internal blocks."""
    import rasterio

    acc = {}
    with rasterio.open(path) as src:
        for _, w in src.block_windows(1):
            fn(src.read(1, window=w, masked=True), acc)
    return acc


def _count_values(block, acc):
    import numpy as np

    v, c = np.unique(block.compressed(), return_counts=True)
    for k, n in zip(v.tolist(), c.tolist(), strict=True):
        acc[k] = acc.get(k, 0) + n


def _count_valid(block, acc):
    acc["valid"] = acc.get("valid", 0) + int(block.count())
    acc["all"] = acc.get("all", 0) + block.size


def _log(step):
    path = P["logs"] / f"{step}.jsonl"
    if not path.exists():
        return {}
    latest = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["status"] != "cached" or r["tile"] not in latest:
            latest[r["tile"]] = r
    return latest


def step_summary(gcp_csv, freshness_csv, out):
    """results/p3/summary_geometry.json: provenance and the checks behind P3's done-when."""
    import pandas as pd

    cfg = site_config()
    res = cfg["geometry"]["resolution_m"]
    poly = aoi(cfg)
    fetch = _log("fetch")
    pts = sum(r.get("points", 0) for r in fetch.values())
    raw_valid = _blocks(P["dtm_raw"], _count_valid)
    cls = _blocks(P["classes"], _count_values)
    total = sum(cls.values())
    holes = _blocks(P["holes"], _count_values)
    man = json.loads((P["meshes"] / "MANIFEST.json").read_text(encoding="utf-8"))
    tiles_ = man["tiles"]
    cov = gpd.read_file(P["covered"])
    fresh = pd.read_csv(freshness_csv)
    gcp = pd.read_csv(gcp_csv)
    src = {
        k: json.loads((P[k].parent / "MANIFEST.json").read_text(encoding="utf-8"))
        for k in ("overture", "osm")
    }
    naip = json.loads((P["naip"] / str(cfg["geometry"]["naip_year"]) / "MANIFEST.json").read_text())
    doc = {
        "crs": "EPSG:26912+5703 (NAD83 / UTM 12N + NAVD88)",
        "resolution_m": res,
        "aoi": {
            "area_km2": round(poly.area / 1e6, 2),
            "bounds_utm": list(poly.bounds),
            "tiles": len(load_tiles()),
        },
        "lidar": {
            "ept": cfg["lidar"]["ept"],
            "points_kept": pts,
            "points_per_m2": round(pts / poly.area, 2),
            "tiles_ok": sum(r["status"] == "ok" for r in fetch.values()),
        },
        "dtm_ground_coverage_pct": round(100 * raw_valid["valid"] / raw_valid["all"], 2),
        "classes_pct": {
            name: round(100 * cls.get(v, 0) / total, 2)
            for v, name in ((0, "ground"), (1, "building"), (2, "tree"))
        },
        "dsm_holes_pct": round(100 * holes.get(1, 0) / total, 3),
        "sources": {
            "overture_release": src["overture"]["release"],
            "overture_buildings": src["overture"]["rows"],
            "osm_fetched_utc": src["osm"]["fetched_utc"],
            "naip": [i["id"] for i in naip["items"]],
        },
        "covered_polygons": cov["kind"].value_counts().to_dict(),
        "meshes": {
            "tiles": len(tiles_),
            "surface_faces": sum(t["surface"]["faces"] for t in tiles_),
            "tree_tiles": sum("trees" in t for t in tiles_),
            "tree_faces": sum(t.get("trees", {}).get("faces", 0) for t in tiles_),
        },
        "enu_origin": man["origin"],
        "ground_control": control.control_summary(gcp),
        "freshness_candidates": fresh["kind"].value_counts().to_dict(),
        "freshness_confirmed": pd.Series(
            [c["status"] for c in freshness.load_confirmations(P["confirmations"]).values()]
        )
        .value_counts()
        .to_dict(),
    }
    write_json(out, doc)
    return doc


def step_mesh_manifest():
    entries = [json.loads(line) for line in (P["logs"] / "meshes.jsonl").read_text().splitlines()]
    latest = {e["tile"]: e for e in entries if "surface" in e}
    origin = json.loads(P["origin"].read_text(encoding="utf-8"))
    return meshes.write_manifest(list(latest.values()), origin, P["meshes"] / "MANIFEST.json")
