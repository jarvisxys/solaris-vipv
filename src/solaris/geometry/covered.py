"""Bridges and tunnels (P3, step 6).

Overpasses stay in the DSM because they shade. A trajectory point is *covered* (beam and sky
both blocked) when it is inside an OSM tunnel or covered way, under an OSM bridge it is not
driving on, or where the DSM stands more than ``covered_ndsm_m`` (4.5 m) above the road
surface. The road surface is the DEM for at-grade roads; for a point on a bridge deck the
caller passes the deck height (P6), so the deck itself never counts as cover.
"""

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio

from .sources import DEFAULT_WIDTH_M

RAIL_WIDTH_M = 6.0
OTHER_WIDTH_M = 8.0
LANE_M = 3.5
NULLS = {"", "no", "none", "nan", "<na>", "null"}


def tagged(ways, col) -> pd.Series:
    """True where an OSM tag is present and not 'no'."""
    if col not in ways:
        return pd.Series(False, index=ways.index)
    s = ways[col]
    return s.notna() & ~s.astype(str).str.strip().str.lower().isin(NULLS)


def way_width(row) -> float:
    w = pd.to_numeric(str(row.get("width", "")).replace("m", "").strip(), errors="coerce")
    if np.isfinite(w) and w > 0:
        return float(w)
    lanes = pd.to_numeric(str(row.get("lanes", "")).split(";")[0], errors="coerce")
    if np.isfinite(lanes) and lanes > 0:
        return float(lanes) * LANE_M + 2.0
    hw = str(row.get("highway", "")).replace("_link", "")
    if hw in DEFAULT_WIDTH_M:
        return DEFAULT_WIDTH_M[hw]
    if str(row.get("railway", "")).strip().lower() not in NULLS:
        return RAIL_WIDTH_M
    return OTHER_WIDTH_M


def covered_polygons(ways: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Road and rail ways tagged tunnel / covered / bridge -> polygons (lines buffered by half
    their width). Waterway culverts (tunnel=culvert without highway/railway) are dropped."""
    ways = ways[tagged(ways, "highway") | tagged(ways, "railway")]
    kind = np.select(
        [tagged(ways, "tunnel"), tagged(ways, "covered"), tagged(ways, "bridge")],
        ["tunnel", "covered", "bridge"],
        default="",
    )
    ways = ways[kind != ""]
    kind = kind[kind != ""]
    widths = ways.apply(way_width, axis=1)
    geom = [
        g if g.geom_type in ("Polygon", "MultiPolygon") else g.buffer(w / 2, cap_style="flat")
        for g, w in zip(ways.geometry, widths, strict=True)
    ]
    ids = ways["id"].astype(str).values if "id" in ways else np.full(len(ways), "")
    return gpd.GeoDataFrame(
        {"kind": kind, "width_m": widths.values, "osm_id": ids}, geometry=geom, crs=ways.crs
    )


def tag_covered(x, y, polygons, dsm_path, dem_path, threshold, z_road=None, own_way=None):
    """Covered flag and reason ('osm' | 'ndsm' | '') for UTM points.

    z_road   road-surface height per point (default: DEM, at-grade)
    own_way  OSM way id each point drives on; a bridge with that id does not cover it
    """
    n = len(x)
    pts = gpd.GeoSeries(gpd.points_from_xy(x, y), crs=polygons.crs)
    pi, qi = polygons.sindex.query(pts, predicate="intersects")
    kind = polygons["kind"].to_numpy()[qi]
    own = np.full(n, "", object) if own_way is None else np.asarray(own_way, str)
    ok = (kind != "bridge") | (polygons["osm_id"].to_numpy()[qi] != own[pi])
    hit = np.zeros(n, bool)
    hit[pi[ok]] = True
    xy = list(zip(x, y, strict=True))
    with rasterio.open(dsm_path) as d, rasterio.open(dem_path) as t:
        dsm = np.array([a[0] for a in d.sample(xy)], float)
        base = (
            np.array([b[0] for b in t.sample(xy)], float) if z_road is None else np.asarray(z_road)
        )
    over = dsm - base > threshold
    reason = np.where(hit, "osm", np.where(over, "ndsm", ""))
    return hit | over, reason
