# data/

Gitignored. Nothing here is redistributed. Lidar and rasters run to tens of GB, so
`raw/` and `derived/` are junctions to `D:\solaris-data\{raw,derived}` (external drive,
outside OneDrive). Recreate them on another machine with
`New-Item -ItemType Junction -Path data\raw -Target <folder>` (same for `derived`).

| Path | Source | Fetched by |
|---|---|---|
| `323705_33.45_-112.06_tmy-2023.csv` | NREL NSRDB PSM v4.0.1, GOES TMY, tmy-2023, 33.45/-112.06, **local time** (UTC-7); SHA-256 pinned in `configs/experiments/e0.yaml` | manual download (E0 input) |
| `tmy_51_526_-0_129_2005_2023.csv` | JRC PVGIS 5.2 TMY, London 51.526/-0.129, 2005-2023 (legacy London values; not used, author decision 2026-10-16) | manual download |
| `raw/nsrdb/33.45_-112.06_tmy-2023_60min.csv` | NSRDB GOES TMY v4, tmy-2023, cell 323705, local time, 17 attributes incl. solar zenith; identical GHI/DNI/DHI/T to the E0 file | `snakemake -c1 weather_tmy` |
| `raw/nsrdb/33.45_-112.06_2023_5min.csv` | NSRDB GOES CONUS v4, 2023, 5-min, cell 518064 (33.46/-112.07), local time | `snakemake -c1 weather_conus_5min` |
| `raw/nsrdb/323705_33.45_-112.06_tmy-2023_utc.csv` | same TMY-2023 in UTC, all 28 columns; superseded by the P2 download, kept as the source of the UTC test fixture | manual download |
| `raw/lidar/tiles/` | USGS 3DEP AZ_MaricopaPinal_2020_B20 (EPT on AWS, public domain), one cleaned LAZ per 500 m tile, ~25 GB | `snakemake -c1 geom_lidar_fetch` |
| `raw/naip/2021/` | NAIP 2021 0.6 m four-band COGs (Planetary Computer, public domain), ~6 GB | `geom_naip` |
| `raw/overture/` | Overture Maps buildings (ODbL), release in `MANIFEST.json` | `geom_overture` |
| `raw/osm/` | OSM bridge / tunnel / covered ways via Overpass (ODbL) | `geom_osm` |
| `raw/ngs/` | NGS survey marks in the AOI (datasheet API) | `geom_ground_control` |
| `derived/` | `dsm.tif`, `cdsm.tif`, `dem.tif` at 0.5 m, EPSG:26912 + NAVD88; `tiles/*.glb`; see `geom/README.md` | `snakemake -c1 all` |

The fetch commands for each row are added in the phase that first needs the data.

NSRDB downloads need a free key from https://developer.nlr.gov/signup/, stored once per user:
`[Environment]::SetEnvironmentVariable("NREL_API_KEY", "<key>", "User")`. The request email is
`NREL_API_EMAIL`, else `git config user.email`. A cached CSV is never fetched again; delete
it to refresh. `snakemake -c1 weather_check` writes `results/p2/summary_weather.json`
(SHA-256, cell, row counts, checks).
