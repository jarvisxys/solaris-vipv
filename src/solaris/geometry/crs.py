"""Coordinate frames, the area of interest and the 500 m tile grid (P3, step 1).

Analysis frame: EPSG:26912 (NAD83 / UTM 12N) with NAVD88 heights (EPSG:5703). Unity frame:
local east-north-up (ENU) at configs/site/phoenix.yaml ``enu_origin``, built with PROJ's
topocentric conversion after GEOID18 lifts NAVD88 heights to the GRS80 ellipsoid. ENU axes
point to true north, so the UTM meridian convergence (about -0.59 deg here) is absorbed.
"""

from functools import lru_cache
from typing import NamedTuple

import numpy as np
import pyproj
import shapely
from shapely.geometry import LineString, Point, box

H_CRS = "EPSG:26912"
V_CRS = "EPSG:5703"
CRS = f"{H_CRS}+{V_CRS}"
GEOG_CRS = "EPSG:4269"  # NAD83; the seeds and the ENU origin are given in it
GEOID_GRID = "us_noaa_g2018u0.tif"  # GEOID18, fetched with `projsync --file us_noaa_g2018u0.tif`


class Tile(NamedTuple):
    id: str
    xmin: float
    ymin: float
    xmax: float
    ymax: float

    @property
    def bounds(self):
        return (self.xmin, self.ymin, self.xmax, self.ymax)


@lru_cache(maxsize=1)
def _to_utm():
    return pyproj.Transformer.from_crs(GEOG_CRS, H_CRS, always_xy=True)


def to_utm(lat, lon):
    return _to_utm().transform(lon, lat)


def seed_geometries(cfg) -> dict:
    """Route and parking seeds in UTM: LineString for routes, Point for sites."""
    out = {}
    for name, pts in cfg["aoi"]["seeds"].items():
        xy = [to_utm(lat, lon) for lat, lon in pts]
        out[name] = LineString(xy) if len(xy) > 1 else Point(xy[0])
    return out


def aoi(cfg):
    """AOI polygon in UTM: seeds buffered by ``buffer_m``; with shape=bbox, their envelope,
    snapped outward to the tile grid."""
    a = cfg["aoi"]
    buffered = shapely.union_all([g.buffer(a["buffer_m"]) for g in seed_geometries(cfg).values()])
    if a.get("shape", "bbox") != "bbox":
        return buffered
    t = cfg["geometry"]["tile_m"]
    x0, y0, x1, y1 = buffered.bounds
    return box(np.floor(x0 / t) * t, np.floor(y0 / t) * t, np.ceil(x1 / t) * t, np.ceil(y1 / t) * t)


def tile_id(xmin, ymin) -> str:
    return f"E{int(round(xmin))}_N{int(round(ymin))}"


def tiles(cfg, polygon=None) -> list[Tile]:
    """Tiles of ``tile_m``, aligned to multiples of it, that intersect the AOI; south-west first."""
    t = cfg["geometry"]["tile_m"]
    poly = aoi(cfg) if polygon is None else polygon
    x0, y0, x1, y1 = poly.bounds
    out = []
    for y in np.arange(np.floor(y0 / t) * t, y1, t):
        for x in np.arange(np.floor(x0 / t) * t, x1, t):
            if box(x, y, x + t, y + t).intersection(poly).area > 0:
                out.append(Tile(tile_id(x, y), float(x), float(y), float(x + t), float(y + t)))
    return out


# ---------------------------------------------------------------- ENU (Unity frame)
def enu_pipeline(lat0, lon0, h0) -> str:
    """PROJ pipeline: UTM 12N + NAVD88 height -> ENU metres at (lat0, lon0, h0 ellipsoidal)."""
    return (
        "+proj=pipeline"
        " +step +inv +proj=utm +zone=12 +ellps=GRS80"
        f" +step +proj=vgridshift +grids={GEOID_GRID} +multiplier=1"
        " +step +proj=cart +ellps=GRS80"
        f" +step +proj=topocentric +lat_0={lat0} +lon_0={lon0} +h_0={h0} +ellps=GRS80"
    )


def enu_transformer(cfg, h0=None):
    o = cfg["enu_origin"]
    h0 = o["h_ellipsoid_m"] if h0 is None else h0
    if h0 is None:
        raise ValueError("enu_origin.h_ellipsoid_m is not set (rule geom_enu_origin)")
    return pyproj.Transformer.from_pipeline(enu_pipeline(o["lat_deg"], o["lon_deg"], h0))


def ellipsoidal_height(lat, lon, h_navd88) -> float:
    """NAVD88 orthometric height -> GRS80 ellipsoidal height with GEOID18."""
    t = pyproj.Transformer.from_pipeline(enu_pipeline(lat, lon, 0.0))
    x, y = to_utm(lat, lon)
    return float(t.transform(x, y, h_navd88)[2])


def to_gltf(enu):
    """ENU (x east, y north, z up) -> glTF axes (x east, y up, z south); glTF importers in
    Unity flip z, which gives Unity's (east, up, north)."""
    enu = np.asarray(enu)
    return np.column_stack([enu[:, 0], enu[:, 2], -enu[:, 1]])


def meridian_convergence(lat, lon) -> float:
    """Grid north minus true north (deg) for EPSG:26912 at a point."""
    return float(pyproj.Proj(H_CRS).get_factors(lon, lat).meridian_convergence)
