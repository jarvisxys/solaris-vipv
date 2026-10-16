"""Freshness check (P3, step 8): what changed along the routes since the 2020-21 lidar.

Candidates come from comparing current Overture footprints with the lidar-epoch building
raster inside each route corridor, for structures tall enough to shade a street
(``min_height_m``):
  added       a current footprint with little lidar building height under it
  demolished  a lidar building blob outside every footprint (grown by the 1-3 m
              lidar/footprint misregistration) and bridge: demolished, or never mapped
              (parking garages often are not), which the author tells apart on imagery
The author confirms each candidate against current imagery in
configs/site/freshness_v1.yaml; confirmed additions are burnt into dsm.tif as
footprint x floors x 3.5 m blocks, confirmed demolitions are lowered to the DEM.
"""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import rasterio.features
import shapely
import yaml
from affine import Affine
from rasterio.windows import from_bounds
from scipy import ndimage
from shapely.geometry import box, shape

from .crs import GEOG_CRS, H_CRS, seed_geometries
from .rasters import BUILDING

COLUMNS = [
    "id",
    "kind",
    "routes",
    "lat_deg",
    "lon_deg",
    "E_m",
    "N_m",
    "area_m2",
    "lidar_built_frac",
    "lidar_ndsm_max_m",
    "overture_id",
    "overture_height_m",
    "overture_num_floors",
    "overture_source",
    "suggested_floors",
    "status",
]


def corridors(cfg) -> gpd.GeoDataFrame:
    w = cfg["geometry"]["freshness"]["corridor_m"]
    seeds = {k: g for k, g in seed_geometries(cfg).items() if k.startswith("R-")}
    return gpd.GeoDataFrame(
        {"route": list(seeds)}, geometry=[g.buffer(w) for g in seeds.values()], crs=H_CRS
    )


def _window(src, bounds, pad=2.0):
    x0, y0, x1, y1 = bounds
    w = from_bounds(x0 - pad, y0 - pad, x1 + pad, y1 + pad, transform=src.transform)
    return w.round_offsets().round_lengths()


def _routes(geom, cor):
    return ";".join(cor.route[cor.intersects(geom)])


def added(cfg, footprints, cor, classes, dsm, dem) -> list[dict]:
    f = cfg["geometry"]["freshness"]
    nmin = cfg["geometry"]["building"]["ndsm_min_m"]
    # Height unknown (3 % of Overture footprints) stays in: it may be a new tower.
    tall = ~(footprints["height_m"] < f["min_height_m"])
    big = footprints.area >= f["min_area_m2"]
    fp = footprints[footprints.intersects(cor.union_all()) & big & tall]
    out = []
    with rasterio.open(classes) as c, rasterio.open(dsm) as d, rasterio.open(dem) as t:
        fp = fp[fp.within(box(*c.bounds))]  # no lidar beyond the raster: no verdict there
        for row in fp.itertuples():
            w = _window(c, row.geometry.bounds)
            mask = rasterio.features.geometry_mask(
                [row.geometry], (w.height, w.width), c.window_transform(w), invert=True
            )
            if not mask.any():
                continue
            ndsm = d.read(1, window=w, boundless=True) - t.read(1, window=w, boundless=True)
            built = (c.read(1, window=w, boundless=True) == BUILDING) & (ndsm > nmin)
            frac = float(built[mask].mean())
            if frac >= f["built_frac_max"]:
                continue
            floors = (
                row.num_floors
                if np.isfinite(row.num_floors)
                else (
                    round(row.height_m / f["floor_height_m"])
                    if np.isfinite(row.height_m)
                    else np.nan
                )
            )
            out.append(
                dict(
                    kind="added",
                    geometry=row.geometry,
                    lidar_built_frac=round(frac, 3),
                    lidar_ndsm_max_m=round(float(np.nanmax(np.where(mask, ndsm, np.nan))), 1),
                    overture_id=row.overture_id,
                    overture_height_m=row.height_m,
                    overture_num_floors=row.num_floors,
                    overture_source=row.source,
                    suggested_floors=floors,
                )
            )
    return out


def demolished(cfg, tiles, footprints, bridges, cor, classes, dsm, dem) -> list[dict]:
    g = cfg["geometry"]
    f, nmin, res = g["freshness"], g["building"]["ndsm_min_m"], g["resolution_m"]
    union = cor.union_all()
    out = []
    with rasterio.open(classes) as c, rasterio.open(dsm) as d, rasterio.open(dem) as t:
        for tile in tiles:
            tb = box(*tile.bounds)
            if not tb.intersects(union):
                continue
            w = _window(c, tile.bounds, pad=50.0)
            tr = c.window_transform(w)
            ndsm = d.read(1, window=w, boundless=True) - t.read(1, window=w, boundless=True)
            built = (c.read(1, window=w, boundless=True) == BUILDING) & (ndsm > nmin)
            # Footprints grown by the lidar-footprint misregistration (1-3 m), so tower edges
            # left outside their footprint do not glue onto neighbouring structures.
            tol = f["footprint_tolerance_m"]
            near = list(
                footprints.geometry.iloc[footprints.sindex.query(tb.buffer(50))].buffer(tol)
            )
            near += list(bridges.geometry.iloc[bridges.sindex.query(tb.buffer(50))])
            if near:
                built &= rasterio.features.geometry_mask(near, built.shape, tr)
            lab, _ = ndimage.label(built, structure=np.ones((3, 3), bool))
            for i, sl in enumerate(ndimage.find_objects(lab), start=1):
                blob = lab[sl] == i
                if blob.sum() * res * res < f["demolished_min_area_m2"]:
                    continue
                if np.percentile(ndsm[sl][blob], 90) < f["min_height_m"]:
                    continue
                sub = tr @ Affine.translation(sl[1].start, sl[0].start)
                parts = rasterio.features.shapes(
                    blob.astype(np.uint8), mask=blob, transform=sub, connectivity=8
                )
                geom = shapely.union_all([shape(p) for p, _ in parts])
                cen = geom.centroid
                if not (tb.contains(cen) and union.contains(cen)):
                    continue  # counted once, by the tile holding its centroid
                out.append(
                    dict(
                        kind="demolished",
                        geometry=geom,
                        lidar_built_frac=1.0,
                        lidar_ndsm_max_m=round(float(ndsm[sl][blob].max()), 1),
                    )
                )
    return out


def candidates(cfg, tiles, footprints, bridges, classes, dsm, dem) -> gpd.GeoDataFrame:
    cor = corridors(cfg)
    rows = added(cfg, footprints, cor, classes, dsm, dem)
    rows += demolished(cfg, tiles, footprints, bridges, cor, classes, dsm, dem)
    gdf = (
        gpd.GeoDataFrame(rows, geometry="geometry", crs=H_CRS)
        if rows
        else gpd.GeoDataFrame(columns=[*COLUMNS, "geometry"], geometry="geometry", crs=H_CRS)
    )
    if len(gdf) == 0:
        return gdf
    cen = gdf.geometry.centroid
    gdf = gdf.assign(_n=-cen.y.round(), _e=cen.x.round()).sort_values(["kind", "_n", "_e"])
    gdf = gdf.drop(columns=["_n", "_e"]).reset_index(drop=True)
    cen = gdf.geometry.centroid
    # Location-based ids survive a rerun, so confirmations stay attached to their candidate.
    gdf["id"] = [
        f"{k[0].upper()}-E{x:.0f}-N{y:.0f}"
        for k, x, y in zip(gdf["kind"], cen.x, cen.y, strict=True)
    ]
    ll = cen.to_crs(GEOG_CRS)
    gdf["routes"] = [_routes(g, cor) for g in gdf.geometry]
    gdf["E_m"], gdf["N_m"] = cen.x.round(1), cen.y.round(1)
    gdf["lat_deg"], gdf["lon_deg"] = ll.y.round(6), ll.x.round(6)
    gdf["area_m2"] = gdf.area.round(1)
    gdf["status"] = "unconfirmed"
    for col in COLUMNS:
        if col not in gdf:
            gdf[col] = np.nan
    return gdf[[*COLUMNS, "geometry"]].reset_index(drop=True)


# ---------------------------------------------------------------- confirmations
def load_confirmations(path) -> dict:
    doc = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return {c["id"]: c for c in doc.get("confirmed") or []}


def apply_confirmed(dsm_epoch, dem, candidates_gpkg, confirmations, out, floor_h) -> dict:
    """dsm.tif = lidar-epoch building DSM with confirmed changes burnt in."""
    import shutil

    shutil.copyfile(dsm_epoch, out)
    conf = load_confirmations(confirmations)
    if not conf:
        return {"applied": 0}
    cand = gpd.read_file(candidates_gpkg).set_index("id")
    unknown = sorted(set(conf) - set(cand.index))
    if unknown:
        raise ValueError(f"confirmed ids not in the candidate list: {unknown}")
    n = 0
    with rasterio.open(out, "r+") as d, rasterio.open(dem) as t:
        for cid, c in conf.items():
            if c.get("status") not in ("added", "demolished"):
                continue
            geom = cand.loc[cid, "geometry"]
            w = _window(d, geom.bounds)
            mask = rasterio.features.geometry_mask(
                [geom], (w.height, w.width), d.window_transform(w), invert=True
            )
            z, ground = d.read(1, window=w), t.read(1, window=w)
            top = ground + float(c["floors"]) * floor_h if c["status"] == "added" else ground
            d.write(np.where(mask, top, z).astype(np.float32), 1, window=w)
            n += 1
    return {"applied": n}


def to_table(gdf) -> pd.DataFrame:
    return pd.DataFrame(gdf.drop(columns="geometry"))
