# SOLARIS-Twin

Trajectory- and parking-resolved assessment of a solar-assisted heavy EV in a
lidar-built 3D Phoenix. This is the journal extension of the SOLARIS conference
paper (*SOLARIS: A First-Principles, Drive-Cycle- and Climate-Resolved Methodology
and Open Toolkit for Assessing Solar-Assisted Heavy Electric Vehicles*). The
conference code is kept byte-identical in `src/solaris/legacy/solaris_v1.py`.

Python produces every reported number. The Unity + Cesium twin and SOLWEIG are
independent cross-checks only.

## Setup

Everything runs natively on Windows 11. Install
[Miniforge](https://conda-forge.org/download/), then from a Miniforge Prompt in the repo:

```bat
conda env create -f environment.yml
conda activate solaris
pre-commit install
```

PDAL and GDAL come from conda-forge; `snakemake` and `embreex` have no win-64
conda builds and are installed by pip inside the same environment.

## Reproduce

```bash
pytest -q          # regression and verification tests
snakemake -n       # dry run of the DAG
snakemake -c8 all  # rebuild every table and figure
```

Input data is not redistributed; `data/README.md` lists the fetch commands.

## Layout

| Path | Contents |
|---|---|
| `configs/` | `base.yaml` (conference parameters, frozen), site, vehicle, schedules, experiments |
| `src/solaris/` | `legacy/` (conference code), `core/`, `weather/`, `geometry/`, `vehicle/`, `trajectory/`, `shading/`, `pv/`, `twin_io/` |
| `geom/` | scripts that build `data/derived/` from lidar |
| `routes/v1/` | frozen route and parking GeoJSON with `MANIFEST.json` |
| `twin/` | Unity project and the Python-Unity exchange schema |
| `experiments/` | `e0_reproduce/` ... `e8_validation/` |
| `results/` | outputs (only summary tables are committed) |
| `paper/` | journal LaTeX; figures written by Snakemake |

Paper-affecting decisions are logged in `PAPER_CHANGELOG.md`.

## Licence

MIT. SOLWEIG/UMEP (GPL-3) are only ever called as external tools.
