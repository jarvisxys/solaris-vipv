# geom/ — Phoenix 3D city model (P3)

Builds `data/derived/` from public data, following workflow guide Sec. 2, steps 1–8. The code
is `src/solaris/geometry/`; each step is a Snakemake rule. Parameters live under `aoi:` and
`geometry:` in `configs/site/phoenix.yaml`.

| Step | Rule | Output (`data/derived/` unless noted) |
|---|---|---|
| 1 AOI | `geom_aoi` | `aoi.geojson`, `tiles.csv` (952 tiles of 500 m, 238 km²) |
| 2 PDAL | `geom_lidar_fetch` | `data/raw/lidar/tiles/*.laz` (EPT → EPSG:26912, NAVD88, classes 7/18 and withheld dropped) |
| 2 PDAL | `geom_lidar_rasters` | `lidar/{dsm,dtm,hag}/` per tile; `lidar/dsm_lidar.vrt`, `lidar/hag_lidar.vrt`, `lidar/dtm_raw.tif` |
| 3 fill | `geom_dem` | `dem.tif` (FillNodata; DSM holes stay flagged) |
| 4 split | `geom_naip`, `geom_overture`, `geom_model` | `classes.tif` (0 ground, 1 building, 2 tree), `ndvi.vrt` |
| 5 model | `geom_model`, `geom_dsm` | `dsm_lidar_epoch.tif`, **`dsm.tif`**, **`cdsm.tif`**, **`dem.tif`**, `dsm_holes.tif` |
| 6 covered | `geom_osm`, `geom_covered` | `covered.gpkg` (bridges, tunnels, covered ways); point test in `geometry.covered` |
| 7 meshes | `geom_enu_origin`, `geom_meshes` | `twin/exchange/enu_origin.json`; `tiles/surface/*.glb`, `tiles/trees/*.glb`, `tiles/MANIFEST.json` |
| 8 freshness | `geom_freshness`, `geom_dsm` | `results/p3/table_freshness.csv`, `freshness_candidates.gpkg` |
| control | `geom_ground_control` | `results/p3/table_ground_control.csv` (NGS marks in every frame) |
| summary | `geom_summary` | `results/p3/summary_geometry.json` |

Every engine reads exactly `dsm.tif`, `cdsm.tif` and `dem.tif`: 0.5 m, EPSG:26912 + NAVD88
(EPSG:5703), float32, tiled and compressed.

## Running

```
snakemake -c1 geom_lidar_fetch      # ~3 billion points, several hours, ~25 GB on D:
snakemake -c1 all                   # everything else
```

Per-tile steps run in worker processes (`python -m solaris.geometry fetch|rasterize|model|meshes
[--workers N] [--tiles ID ...]`), log to `data/derived/logs/<step>.jsonl` and skip tiles that are
already done, so an interrupted run resumes. A step's tile cache is cleared when its settings
change (`PARAMS.json` in the cache folder). Set `SOLARIS_DATA` to build into another folder
(trial runs on a few tiles).

## Visual check and freshness review in QGIS

```
"C:\Program Files\QGIS 3.44.15\bin\python-qgis-ltr.bat" geom\qgis_review.py
```

This writes `data/derived/p3_review.qgz` with these layers:
- Esri World Imagery (current) as the basemap.
- `dsm.tif` and `dem.tif` as hillshades.
- Classes and canopy height.
- DSM holes.
- The AOI outline.
- The NGS marks.
- The freshness candidates, labelled by id: blue for added, magenta for demolished.

## Frames

- Analysis: NAD83 / UTM 12N + NAVD88. The EPT is served in EPSG:3857 with NAVD88 heights;
  PDAL reprojects horizontally only (null NAD83–WGS84 shift, as PROJ does by default).
- Unity: ENU at `enu_origin` (Central Ave & Washington St), heights lifted to the GRS80
  ellipsoid with GEOID18 (`projsync --file us_noaa_g2018u0.tif`). ENU axes point to true
  north; UTM grid north is −0.59° from it here. `.glb` files use glTF axes (x east, y up,
  z south); Unity's importer turns them into (east, up, north).
- Meshes face up. Raycasts from under a bridge deck need `Physics.queriesHitBackfaces = true`.

## Building/tree split (step 4)

- Trees: nDSM > 2 m, NDVI > 0.2 (NAIP 2021), outside footprints buffered 1 m.
- Buildings: inside an Overture footprint, or nDSM > 2.5 m with NDVI < 0.15.
- Blobs under 4 m² are dropped.
- The lidar has no building class (classes 1, 2, 7 only), so footprints and NDVI do the split.

## Freshness (step 8)

`geom_freshness` lists candidates inside a 250 m corridor around each seed route:
- **added:** a current Overture footprint with less than 30 % lidar building height under it.
- **demolished:** a lidar building blob of 50 m² or more, outside current footprints and bridges.

The author checks each candidate against current imagery (QGIS + an XYZ basemap, or Google
Earth). Verdicts go in `configs/site/freshness_v1.yaml` by candidate id. `geom_dsm` then
burns confirmed additions as footprint × floors × 3.5 m and lowers confirmed demolitions to
the DEM.
