# data/

Gitignored. Nothing here is redistributed. Lidar and rasters run to tens of GB:
keep this folder out of OneDrive sync (mark it "Always keep on this device" or
junction it to a local, non-synced folder).

| Path | Source | Fetched by |
|---|---|---|
| `323705_33.45_-112.06_tmy-2023.csv` | NREL NSRDB PSM v4.0.1, GOES TMY, tmy-2023, 33.45/-112.06, **local time** (UTC-7); SHA-256 pinned in `configs/experiments/e0.yaml` | manual download; `src/solaris/weather` from P2 |
| `tmy_51_526_-0_129_2005_2023.csv` | JRC PVGIS 5.2 TMY, London 51.526/-0.129, 2005-2023 (legacy London values; optional) | manual download |
| `raw/nsrdb/323705_33.45_-112.06_tmy-2023_utc.csv` | same TMY-2023 as above in UTC, all 28 columns (albedo, clear-sky, wind direction, pressure) | manual download; input for P2 |
| `raw/nsrdb/` | NSRDB GOES TMY v4 and GOES CONUS v4 5-min (2023) | P2 |
| `raw/lidar/` | USGS 3DEP AZ_MaricopaPinal_2020_B20 (EPT on AWS, public domain) | P3, `geom/` |
| `raw/osm/` | OpenStreetMap Arizona (Geofabrik), Overture buildings | P3, P6 |
| `raw/naip/` | NAIP 0.6 m four-band (Planetary Computer) | P3 |
| `derived/` | `dsm.tif`, `cdsm.tif`, `dem.tif` at 0.5 m, EPSG:26912; `.glb` tiles | P3 |

The fetch commands for each row are added in the phase that first needs the data.
