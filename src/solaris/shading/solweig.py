"""SOLWEIG (UMEP for Processing) shadow maps as an external reference (E1, E4).

UMEP is GPL-3. It runs only as a separate process (``qgis_process``), on rasters this module
writes, and nothing of its code enters this repository (CLAUDE.md).

Install (QGIS 3.44 LTR, UMEP for processing 3.0):
  1. Plugin "UMEP for processing" into the QGIS profile (Plugin Manager, or the zip from
     plugins.qgis.org into %APPDATA%\\QGIS\\QGIS3\\profiles\\default\\python\\plugins).
  2. For QGIS's Python: ``pip install --user umep-reqs supy numba rioxarray pydantic
     jaydebeapi`` (python-qgis-ltr.bat -m pip ...), then
     ``qgis_process plugins enable processing_umep``.
  3. UMEP 3.0 fails under numpy >= 2.4 (QGIS 3.44 ships 2.4.6): functions/dailyshading.py
     lines 93-94 assign size-1 arrays to scalars. Local fix: take ``.reshape(-1)[0]`` of
     ``sun['zenith']`` and ``sun['azimuth']`` (original kept as dailyshading.py.orig).
"""

import shutil
import subprocess
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import from_bounds

QGIS_PROCESS = Path(r"C:\Program Files\QGIS 3.44.15\bin\qgis_process-qgis-ltr.bat")
ALGORITHM = "umep:Solar Radiation: Shadow Generator"
UTC_MINUS_7 = 6  # index of UTC-07:00 in the algorithm's UTC enum


def available(qgis_process=QGIS_PROCESS) -> bool:
    return Path(qgis_process).exists()


def clip(src_path, bounds, out_path):
    """Clip a raster to UTM bounds as a plain EPSG:26912 float32 GeoTIFF (SOLWEIG reads the
    horizontal CRS to find latitude and longitude; it does not need the vertical datum)."""
    with rasterio.open(src_path) as src:
        w = from_bounds(*bounds, transform=src.transform).round_offsets().round_lengths()
        a = src.read(1, window=w, masked=True).filled(0).astype(np.float32)
        prof = dict(
            driver="GTiff",
            width=a.shape[1],
            height=a.shape[0],
            count=1,
            dtype="float32",
            crs="EPSG:26912",
            transform=src.window_transform(w),
        )
    with rasterio.open(out_path, "w", **prof) as dst:
        dst.write(a, 1)
    return a, prof["transform"]


def shadow(
    dsm_tif,
    cdsm_tif,
    when,
    out_tif,
    transmissivity_pct=3.0,
    trunk_pct=25.0,
    qgis_process=QGIS_PROCESS,
):
    """One SOLWEIG shadow map at local standard time ``when`` (pandas Timestamp, MST).
    Returns the array: 1 sunlit, 0 shaded by buildings, in between under vegetation."""
    out_tif = Path(out_tif)
    out_dir = out_tif.parent / (out_tif.stem + "_dir")
    out_dir.mkdir(parents=True, exist_ok=True)
    args = [
        str(qgis_process),
        "run",
        ALGORITHM,
        "--",
        f"INPUT_DSM={dsm_tif}",
        f"INPUT_CDSM={cdsm_tif}",
        f"TRANS_VEG={transmissivity_pct}",
        f"INPUT_THEIGHT={trunk_pct}",
        f"UTC={UTC_MINUS_7}",
        "DST=0",
        # UMEP parses these strings itself: '%Y-%m-%d' and '%H:%M:%S.%f'
        f"DATEINI={when:%Y-%m-%d}",
        f"TIMEINI={when:%H:%M}:00.000",
        "ONE_SHADOW=1",  # booleans are 1/0 for qgis_process; "true" is ignored
        "ITERTIME=30",
        f"OUTPUT_DIR={out_dir}",
        f"OUTPUT_FILE={out_tif}",
    ]
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0 or not out_tif.exists():
        raise RuntimeError(f"SOLWEIG shadow failed ({r.returncode}): {r.stderr[-800:]}")
    shutil.rmtree(out_dir, ignore_errors=True)
    with rasterio.open(out_tif) as s:
        return s.read(1)
