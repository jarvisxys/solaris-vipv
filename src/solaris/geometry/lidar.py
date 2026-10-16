"""USGS 3DEP lidar -> per-tile point clouds and rasters with PDAL (P3, step 2).

Each 500 m tile is read from the EPT with a margin, reprojected to EPSG:26912 (heights stay
NAVD88, as served), stripped of noise (classes 7, 18) and withheld points, and cached as
LAZ. Rasterisation then writes, on the exact 0.5 m tile grid:
  dsm  max Z of all returns
  dtm  IDW of ground (class 2) points; gaps are filled later on the mosaic (step 3)
  hag  max height above ground (filters.hag_nn)
"""

import json
import time
from pathlib import Path

import numpy as np
import pdal
import pyproj
import rasterio
from rasterio.transform import from_origin

from .crs import CRS, H_CRS

NODATA = -9999.0
RASTERS = ("dsm", "dtm", "hag")


def grid(cfg, tile):
    res = cfg["geometry"]["resolution_m"]
    n = int(round((tile.xmax - tile.xmin) / res))
    return res, n


def fetch_stages(cfg, tile, out) -> list:
    g = cfg["geometry"]
    m = g["tile_margin_m"]
    x0, y0, x1, y1 = tile.xmin - m, tile.ymin - m, tile.xmax + m, tile.ymax + m
    to_merc = pyproj.Transformer.from_crs(H_CRS, "EPSG:3857", always_xy=True)
    bx0, by0, bx1, by1 = to_merc.transform_bounds(x0, y0, x1, y1, densify_pts=21)
    pad = 5.0  # Web Mercator metres; the crop below trims to the exact UTM box
    keep = " && ".join(f"Classification != {c}" for c in g["noise_classes"]) + " && Withheld == 0"
    return [
        {
            "type": "readers.ept",
            "filename": cfg["lidar"]["ept"],
            "bounds": f"([{bx0 - pad}, {bx1 + pad}], [{by0 - pad}, {by1 + pad}])",
            "threads": 4,
        },
        {"type": "filters.expression", "expression": keep},
        {"type": "filters.reprojection", "in_srs": "EPSG:3857", "out_srs": H_CRS},
        {"type": "filters.crop", "bounds": f"([{x0}, {x1}], [{y0}, {y1}])"},
        {
            "type": "writers.las",
            "filename": str(out),
            "a_srs": CRS,
            "minor_version": 4,
            "dataformat_id": 6,
            "scale_x": 0.01,
            "scale_y": 0.01,
            "scale_z": 0.01,
            "offset_x": "auto",
            "offset_y": "auto",
            "offset_z": "auto",
        },
    ]


def raster_stages(cfg, tile, laz, out: dict) -> list:
    res, n = grid(cfg, tile)
    writer = {
        "type": "writers.gdal",
        "resolution": res,
        "origin_x": tile.xmin,
        "origin_y": tile.ymin,
        "width": n,
        "height": n,
        "nodata": NODATA,
        "data_type": "float32",
        "gdaldriver": "GTiff",
        "gdalopts": "COMPRESS=DEFLATE,PREDICTOR=3,TILED=YES",
        "override_srs": CRS,
    }
    # One chain, no branches: python-pdal executes a single leaf, and writers pass points on.
    # DSM and HAG use binmode (each point in its own cell only): the default search radius,
    # res * sqrt(2), would spread roof maxima into the next pixel and fatten buildings.
    return [
        {"type": "readers.las", "filename": str(laz)},
        {"type": "filters.hag_nn"},
        {
            **writer,
            "filename": str(out["dsm"]),
            "dimension": "Z",
            "output_type": "max",
            "binmode": True,
        },
        {
            **writer,
            "filename": str(out["hag"]),
            "dimension": "HeightAboveGround",
            "output_type": "max",
            "binmode": True,
        },
        {"type": "filters.range", "limits": "Classification[2:2]"},
        {**writer, "filename": str(out["dtm"]), "dimension": "Z", "output_type": "idw"},
    ]


def run(stages) -> int:
    return pdal.Pipeline(json.dumps(stages)).execute()


def laz_path(root, tile) -> Path:
    return Path(root) / f"{tile.id}.laz"


def raster_paths(root, tile) -> dict:
    return {k: Path(root) / k / f"{tile.id}.tif" for k in RASTERS}


def fetch_tile(cfg, tile, root, retries=3) -> dict:
    """Cache one tile's cleaned point cloud as LAZ (skipped if present)."""
    out = laz_path(root, tile)
    if out.exists():
        return {"tile": tile.id, "status": "cached"}
    out.parent.mkdir(parents=True, exist_ok=True)
    part = out.with_name(f"{tile.id}.part.laz")
    for attempt in range(1, retries + 1):
        try:
            t0 = time.time()
            n = run(fetch_stages(cfg, tile, part))
            part.replace(out)
            return {"tile": tile.id, "status": "ok", "points": n, "s": round(time.time() - t0)}
        except RuntimeError as e:
            if attempt == retries:
                return {"tile": tile.id, "status": "error", "error": str(e)[:300]}
            time.sleep(10 * attempt)


def _write_empty(path, tile, res, n):
    path.parent.mkdir(parents=True, exist_ok=True)
    profile = dict(
        driver="GTiff",
        width=n,
        height=n,
        count=1,
        dtype="float32",
        nodata=NODATA,
        crs=CRS,
        transform=from_origin(tile.xmin, tile.ymax, res, res),
        compress="deflate",
        predictor=3,
        tiled=True,
    )
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(np.full((1, n, n), NODATA, np.float32))


def rasterize_tile(cfg, tile, laz_root, raster_root) -> dict:
    """DSM, DTM and HAG for one tile from its cached LAZ (skipped if all three exist)."""
    final = raster_paths(raster_root, tile)
    if all(p.exists() for p in final.values()):
        return {"tile": tile.id, "status": "cached"}
    # Write into a scratch folder and move all three at once, so a crash never leaves a
    # partial set that looks cached.
    tmp = Path(raster_root) / ".tmp" / tile.id
    out = {k: tmp / f"{k}.tif" for k in RASTERS}
    tmp.mkdir(parents=True, exist_ok=True)
    laz = laz_path(laz_root, tile)
    res, n = grid(cfg, tile)
    try:
        run(raster_stages(cfg, tile, laz, out))
        status = "ok"
    except RuntimeError as e:
        # No ground points in reach (hag_nn fails): DSM alone, DTM/HAG left to the fill step.
        stages = raster_stages(cfg, tile, laz, out)
        try:
            run([stages[0], stages[2]])
        except RuntimeError:
            _write_empty(out["dsm"], tile, res, n)
        for k in ("dtm", "hag"):
            _write_empty(out[k], tile, res, n)
        status = f"no-ground: {str(e)[:120]}"
    for k, p in final.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        out[k].replace(p)
    tmp.rmdir()
    return {"tile": tile.id, "status": status}
