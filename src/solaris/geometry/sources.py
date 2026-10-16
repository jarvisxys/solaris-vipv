"""Ancillary downloads for the building/tree split and the freshness check (P3, steps 4, 6, 8).

  NAIP 0.6 m four-band imagery (Planetary Computer, public domain)  -> NDVI
  Overture Maps buildings (ODbL)                                     -> current footprints
  OpenStreetMap bridges, tunnels and covered ways via osmnx (ODbL)   -> covered segments

Every download is cached once under data/raw and described in a MANIFEST.json (release,
date, item ids, SHA-256); delete the folder to refetch.
"""

import datetime as dt
import hashlib
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

from .crs import GEOG_CRS, H_CRS

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"


def lonlat_bounds(polygon_utm, pad_deg=0.002):
    b = gpd.GeoSeries([polygon_utm], crs=H_CRS).to_crs(GEOG_CRS).total_bounds
    return (b[0] - pad_deg, b[1] - pad_deg, b[2] + pad_deg, b[3] + pad_deg)


def _sha256(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def _manifest(folder, **fields):
    folder.mkdir(parents=True, exist_ok=True)
    fields["fetched_utc"] = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    path = folder / "MANIFEST.json"
    path.write_text(json.dumps(fields, indent=2) + "\n", encoding="utf-8", newline="\n")
    return path


# ---------------------------------------------------------------- NAIP
def fetch_naip(polygon_utm, year, folder) -> Path:
    """Download every NAIP COG of ``year`` that intersects the AOI."""
    import planetary_computer
    import pystac_client

    folder = Path(folder)
    cat = pystac_client.Client.open(STAC_URL)
    items = [
        i
        for i in cat.search(collections=["naip"], bbox=lonlat_bounds(polygon_utm)).items()
        if str(i.properties.get("naip:year")) == str(year)
    ]
    if not items:
        raise RuntimeError(f"no NAIP {year} items over the AOI")
    folder.mkdir(parents=True, exist_ok=True)
    files = []
    for it in sorted(items, key=lambda i: i.id):
        out = folder / f"{it.id}.tif"
        for attempt in range(3):
            if out.exists():
                break
            # Sign right before each download: SAS tokens expire within the hour, and a
            # whole AOI takes longer than that.
            href = planetary_computer.sign(it.assets["image"].href)
            part = out.with_suffix(".part")
            try:
                with requests.get(href, stream=True, timeout=600) as r:
                    r.raise_for_status()
                    with open(part, "wb") as f:
                        for block in r.iter_content(1 << 22):
                            f.write(block)
                part.replace(out)
            except requests.RequestException:
                if attempt == 2:
                    raise
        files.append({"id": it.id, "date": str(it.datetime.date()), "sha256": _sha256(out)})
    return _manifest(folder, source="Planetary Computer naip", year=year, items=files)


# ---------------------------------------------------------------- Overture
def fetch_overture_buildings(polygon_utm, out, release=None) -> Path:
    """Overture buildings in the AOI, reprojected to UTM, as a GeoPackage."""
    from overturemaps import core

    release = release or core.get_latest_release()
    gdf = core.geodataframe("building", bbox=lonlat_bounds(polygon_utm), release=release)
    gdf = gdf.set_crs("EPSG:4326", allow_override=True).to_crs(H_CRS)
    gdf = gdf[gdf.geometry.type.isin(["Polygon", "MultiPolygon"])]
    first = gdf["sources"].map(lambda s: s[0] if s is not None and len(s) else {})
    keep = pd.DataFrame(
        {
            "overture_id": gdf["id"],
            "height_m": pd.to_numeric(gdf.get("height"), errors="coerce"),
            "num_floors": pd.to_numeric(gdf.get("num_floors"), errors="coerce"),
            "class": gdf.get("class"),
            "source": first.map(lambda d: d.get("dataset")),
            "source_update": first.map(lambda d: str(d.get("update_time"))),
        }
    )
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    gpd.GeoDataFrame(keep, geometry=gdf.geometry.values, crs=H_CRS).to_file(out, layer="buildings")
    _manifest(
        out.parent,
        source="Overture Maps buildings",
        release=release,
        rows=len(keep),
        sha256=_sha256(out),
    )
    return out


# ---------------------------------------------------------------- OSM
COVER_TAGS = {"bridge": True, "tunnel": True, "covered": "yes"}
DEFAULT_WIDTH_M = {"motorway": 16.0, "trunk": 14.0, "primary": 12.0, "secondary": 10.0}


def fetch_osm_covered(polygon_utm, out) -> Path:
    """OSM ways tagged bridge / tunnel / covered (roads and rails), raw tags kept, in UTM."""
    import osmnx as ox

    w, s, e, n = lonlat_bounds(polygon_utm)
    gdf = ox.features_from_bbox(bbox=(w, s, e, n), tags=COVER_TAGS).reset_index()
    gdf = gdf[gdf["element"] == "way"].to_crs(H_CRS)
    cols = [
        c
        for c in (
            "id",
            "highway",
            "railway",
            "bridge",
            "tunnel",
            "covered",
            "layer",
            "width",
            "lanes",
            "name",
        )
        if c in gdf
    ]
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    gdf[cols + ["geometry"]].astype({c: str for c in cols}).to_file(out, layer="covered_ways")
    _manifest(
        out.parent, source="OpenStreetMap via osmnx/Overpass", rows=len(gdf), sha256=_sha256(out)
    )
    return out
