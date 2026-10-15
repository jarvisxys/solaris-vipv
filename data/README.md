# data/

Gitignored. Nothing here is redistributed. Lidar and rasters run to tens of GB:
keep this folder out of OneDrive sync (mark it "Always keep on this device" or
junction it to a local, non-synced folder).

| Path | Source | Fetched by |
|---|---|---|
| `323705_33.45_-112.06_tmy-2023.csv` | NREL NSRDB PSM v4.0.1, GOES TMY, tmy-2023, 33.45/-112.06 (used by the legacy code) | manual download today; `src/solaris/weather` from P2 |
| `raw/nsrdb/` | NSRDB GOES TMY v4 and GOES CONUS v4 5-min (2023) | P2 |
| `raw/lidar/` | USGS 3DEP AZ_MaricopaPinal_2020_B20 (EPT on AWS, public domain) | P3, `geom/` |
| `raw/osm/` | OpenStreetMap Arizona (Geofabrik), Overture buildings | P3, P6 |
| `raw/naip/` | NAIP 0.6 m four-band (Planetary Computer) | P3 |
| `derived/` | `dsm.tif`, `cdsm.tif`, `dem.tif` at 0.5 m, EPSG:26912; `.glb` tiles | P3 |

The fetch commands for each row are added in the phase that first needs the data.
