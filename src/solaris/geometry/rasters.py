"""Mosaics, gap filling, the building/tree split and the three model rasters (P3, steps 3-5).

Every engine reads exactly three rasters, 0.5 m, EPSG:26912 + NAVD88:
  dsm.tif   building DSM = DTM + nDSM on building pixels, DTM elsewhere (bridges included)
  cdsm.tif  canopy height = nDSM on tree pixels, else 0 (SOLWEIG convention)
  dem.tif   DTM, gaps filled
DSM holes (no lidar return: water, glass roofs) are not invented: they take the DTM in
dsm.tif and are flagged in dsm_holes.tif.
"""

from pathlib import Path

import numpy as np
import rasterio
import rasterio.features
import rasterio.warp
from osgeo import gdal
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.windows import Window, from_bounds
from scipy import ndimage
from shapely.geometry import box

from .crs import CRS
from .lidar import NODATA

gdal.UseExceptions()

GROUND, BUILDING, TREE = 0, 1, 2
GTIFF = dict(
    driver="GTiff",
    compress="deflate",
    tiled=True,
    blockxsize=512,
    blockysize=512,
    BIGTIFF="IF_SAFER",
    num_threads="all_cpus",
)


def mosaic(paths, out, vrt_only=False) -> Path:
    """VRT over tile rasters; with vrt_only=False also a tiled, compressed GeoTIFF."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    vrt = out.with_suffix(".vrt")
    gdal.BuildVRT(str(vrt), [str(p) for p in paths]).FlushCache()
    if vrt_only:
        return vrt
    ds = gdal.Open(str(vrt))
    pred = 3 if ds.GetRasterBand(1).DataType == gdal.GDT_Float32 else 2
    opts = [
        "TILED=YES",
        "BLOCKXSIZE=512",
        "BLOCKYSIZE=512",
        "COMPRESS=DEFLATE",
        f"PREDICTOR={pred}",
        "BIGTIFF=IF_SAFER",
        "NUM_THREADS=ALL_CPUS",
    ]
    gdal.Translate(str(out), ds, creationOptions=opts).FlushCache()
    return out


def fill_dtm(src, dst, max_dist_m, res) -> Path:
    """Step 3: gdal FillNodata on the DTM mosaic (ground under buildings, sparse returns)."""
    gdal.Translate(
        str(dst),
        str(src),
        creationOptions=["TILED=YES", "COMPRESS=DEFLATE", "PREDICTOR=3", "BIGTIFF=IF_SAFER"],
    ).FlushCache()
    ds = gdal.Open(str(dst), gdal.GA_Update)
    band = ds.GetRasterBand(1)
    gdal.FillNodata(band, None, maxSearchDist=int(max_dist_m / res), smoothingIterations=0)
    band.FlushCache()
    ds = None
    return Path(dst)


# ---------------------------------------------------------------- windows
def tile_window(src, tile, margin_px=0) -> Window:
    w = from_bounds(*tile.bounds, transform=src.transform).round_offsets().round_lengths()
    return Window(
        w.col_off - margin_px,
        w.row_off - margin_px,
        w.width + 2 * margin_px,
        w.height + 2 * margin_px,
    )


def read(path, tile, margin_px=0, fill=np.nan, resampling=None, res=None):
    """Tile (+ margin) as float32 with nodata -> ``fill``. With ``resampling``, warp the
    source onto the tile grid at ``res`` (used for NAIP, 0.6 m)."""
    with rasterio.open(path) as src:
        if resampling is None:
            a = src.read(
                1,
                window=tile_window(src, tile, margin_px),
                boundless=True,
                fill_value=src.nodata if src.nodata is not None else 0,
                out_dtype="float32",
                masked=True,
            )
            return a.filled(fill)
        m = margin_px * res
        x0, y1 = tile.xmin - m, tile.ymax + m
        n = int(round((tile.xmax - tile.xmin) / res)) + 2 * margin_px
        out = np.full((src.count, n, n), fill, np.float32)
        rasterio.warp.reproject(
            rasterio.band(src, list(range(1, src.count + 1))),
            out,
            dst_transform=from_origin(x0, y1, res, res),
            dst_crs=src.crs,
            resampling=resampling,
            dst_nodata=fill,
        )
        return out


def ndvi_tile(naip_vrt, tile, res, margin_px=0):
    """NDVI on the tile grid from NAIP bands (1 red, 4 NIR), bilinear from 0.6 m."""
    b = read(naip_vrt, tile, margin_px, fill=np.nan, resampling=Resampling.bilinear, res=res)
    red, nir = b[0], b[3]
    with np.errstate(invalid="ignore", divide="ignore"):
        return (nir - red) / (nir + red)


def rasterize(geoms, tile, res, margin_px=0):
    m = margin_px * res
    n = int(round((tile.xmax - tile.xmin) / res)) + 2 * margin_px
    if len(geoms) == 0:
        return np.zeros((n, n), bool)
    return rasterio.features.rasterize(
        ((g, 1) for g in geoms),
        out_shape=(n, n),
        dtype="uint8",
        transform=from_origin(tile.xmin - m, tile.ymax + m, res, res),
    ).astype(bool)


# ---------------------------------------------------------------- step 4
def remove_small(mask, min_px):
    """Drop 8-connected blobs smaller than ``min_px`` pixels."""
    lab, n = ndimage.label(mask, structure=np.ones((3, 3), bool))
    if n == 0:
        return mask
    sizes = np.bincount(lab.ravel())
    keep = sizes >= min_px
    keep[0] = False
    return keep[lab]


def classify(ndsm, ndvi, inside, inside_buffered, p, px_area):
    """Step 4. Trees: nDSM > 2 m, NDVI > 0.2, outside footprints buffered by 1 m.
    Buildings: inside footprints, or nDSM > 2.5 m with NDVI < 0.15. Blobs < 4 m2 dropped.
    Added to the guide: nothing above ``tree.ndsm_max_m`` (35 m) is a tree; such pixels are
    tower walls that NAIP's relief displacement paints green, and they count as building.
    NaN nDSM (no return) or NDVI (no image) never satisfies a threshold."""
    t, b = p["tree"], p["building"]
    with np.errstate(invalid="ignore"):
        too_tall = ndsm > t["ndsm_max_m"]
        tree = (ndsm > t["ndsm_min_m"]) & ~too_tall & (ndvi > t["ndvi_min"]) & ~inside_buffered
        by_height = (ndsm > b["ndsm_min_m"]) & (ndvi < b["ndvi_max"])
    # Added to the guide: structures narrower than min_width_m (overhead power lines, poles,
    # signal arms) are not buildings. An opening of (by_height | inside) removes them but
    # keeps strips joined to a footprint (lidar/footprint misregistration at tower edges).
    k = max(1, int(np.ceil(b["min_width_m"] / np.sqrt(px_area))))
    wide = ndimage.binary_opening(by_height | inside, structure=np.ones((k, k), bool))
    building = inside | too_tall | (by_height & wide)
    min_px = int(np.ceil(p["min_blob_m2"] / px_area))
    building = remove_small(building, min_px)
    tree = remove_small(tree & ~building, min_px)
    out = np.full(ndsm.shape, GROUND, np.uint8)
    out[building] = BUILDING
    out[tree] = TREE
    return out


def model_rasters(dsm_lidar, dem, classes):
    """Step 5: (building DSM, CDSM, holes flag) from lidar DSM, filled DTM and classes."""
    ndsm = dsm_lidar - dem
    holes = np.isnan(dsm_lidar)
    bld = (classes == BUILDING) & ~holes
    dsm = np.where(bld, dem + np.maximum(ndsm, 0), dem).astype(np.float32)
    cdsm = np.where((classes == TREE) & ~holes, np.maximum(ndsm, 0), 0).astype(np.float32)
    return dsm, cdsm, holes.astype(np.uint8)


def write_tile(path, arr, tile, res, nodata=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if nodata is not None and not np.isnan(nodata):
        arr = np.where(np.isnan(arr), nodata, arr).astype(arr.dtype)
    n = arr.shape[0]
    profile = dict(
        GTIFF,
        width=n,
        height=n,
        count=1,
        dtype=arr.dtype,
        crs=CRS,
        nodata=nodata,
        transform=from_origin(tile.xmin, tile.ymax, res, res),
        predictor=3 if arr.dtype == np.float32 else 2,
    )
    profile.pop("BIGTIFF")
    part = path.with_name(path.stem + ".part.tif")
    with rasterio.open(part, "w", **profile) as dst:
        dst.write(arr, 1)
    part.replace(path)


def model_tile(tile, cfg, paths, footprints, out_dirs) -> dict:
    """Steps 4-5 for one tile; ``footprints`` is a GeoDataFrame in UTM with a spatial index."""
    g = cfg["geometry"]
    res = g["resolution_m"]
    margin = int(np.ceil(np.sqrt(g["min_blob_m2"]) / res)) + 2  # whole small blobs in view
    final = {k: Path(d) / f"{tile.id}.tif" for k, d in out_dirs.items()}
    if all(p.exists() for p in final.values()):
        return {"tile": tile.id, "status": "cached"}
    dsm_l = read(paths["dsm_lidar"], tile, margin)
    dem = read(paths["dem"], tile, margin)
    ndvi = ndvi_tile(paths["naip"], tile, res, margin)
    m = margin * res
    near = footprints.iloc[
        footprints.sindex.query(box(tile.xmin - m, tile.ymin - m, tile.xmax + m, tile.ymax + m))
    ]
    inside = rasterize(list(near.geometry), tile, res, margin)
    buf = g["tree"]["footprint_buffer_m"]
    inside_b = rasterize(list(near.geometry.buffer(buf)), tile, res, margin)
    classes = classify(dsm_l - dem, ndvi, inside, inside_b, g, res * res)
    dsm, cdsm, holes = model_rasters(dsm_l, dem, classes)
    c = slice(margin, -margin)
    write_tile(final["classes"], classes[c, c], tile, res)
    write_tile(final["dsm"], dsm[c, c], tile, res, nodata=NODATA)
    write_tile(final["cdsm"], cdsm[c, c], tile, res)
    write_tile(final["holes"], holes[c, c], tile, res)
    write_tile(final["ndvi"], ndvi[c, c].astype(np.float32), tile, res, nodata=np.nan)
    return {"tile": tile.id, "status": "ok"}
