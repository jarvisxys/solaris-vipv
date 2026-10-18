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


def compare_tile(tile, days, hours, buffer_m, transmissivity_pct, trunk_pct, work, root, res=0.5):
    """Pixel agreement of our shadow map with SOLWEIG on ``tile`` (UTM bounds) at local
    standard times; both run on the same clipped rasters (tile + buffer), and the comparison
    covers the tile itself. Returns one dict per time."""
    import pandas as pd
    import pyproj

    from solaris.geometry.crs import GEOG_CRS, H_CRS

    from .horizon import convergence_deg, march_steps, shadow_map
    from .sun import sun_position

    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    big = (tile[0] - buffer_m, tile[1] - buffer_m, tile[2] + buffer_m, tile[3] + buffer_m)
    dsm, tr = clip(Path(root) / "dsm.tif", big, work / "dsm.tif")
    cdsm, _ = clip(Path(root) / "cdsm.tif", big, work / "cdsm.tif")
    dem, _ = clip(Path(root) / "dem.tif", big, work / "dem.tif")
    canopy = cdsm > 0
    top = np.where(canopy, dem + cdsm, np.nan)
    bot = np.where(canopy, dem + trunk_pct / 100.0 * cdsm, np.nan)
    # cached SOLWEIG maps are valid only for the exact rasters they were made from
    import hashlib

    key = hashlib.sha256(
        dsm.tobytes() + cdsm.tobytes() + f"{transmissivity_pct},{trunk_pct}".encode()
    ).hexdigest()
    stamp = work / "inputs.sha256"
    if not stamp.exists() or stamp.read_text().strip() != key:
        for old in work.glob("solweig_*.tif"):
            old.unlink()
        stamp.write_text(key + "\n")
    k = int(round(buffer_m / res))
    inner = (slice(k, dsm.shape[0] - k), slice(k, dsm.shape[1] - k))
    cx, cy = (tile[0] + tile[2]) / 2, (tile[1] + tile[3]) / 2
    conv = float(convergence_deg(np.array([cx]), np.array([cy]))[0])
    lon, lat = pyproj.Transformer.from_crs(H_CRS, GEOG_CRS, always_xy=True).transform(cx, cy)
    steps = march_steps(res, float(np.hypot(*dsm.shape) * res))
    out = []
    for d in days:
        for hr in hours:
            when = pd.Timestamp(f"{d} {hr:02d}:00")
            path = work / f"solweig_{when:%Y%m%d_%H%M}.tif"
            if path.exists():
                with rasterio.open(path) as s:
                    ref = s.read(1)
            else:
                ref = shadow(
                    work / "dsm.tif", work / "cdsm.tif", when, path, transmissivity_pct, trunk_pct
                )
            sp = sun_position([when.tz_localize("America/Phoenix")], lat, lon, altitude=331.0).iloc[
                0
            ]
            bld, veg = shadow_map(
                dsm, dsm, tr, res, sp.azimuth, sp.elevation, steps, conv, top, bot
            )
            ours, theirs = (bld | veg)[inner], (ref < 0.5)[inner]
            out.append(
                {
                    "time": f"{when:%Y-%m-%d %H:%M}",
                    "sun_el": round(float(sp.elevation), 2),
                    "agreement": float(np.mean(ours == theirs)),
                    "shaded_ours": round(float(ours.mean()), 4),
                    "shaded_solweig": round(float(theirs.mean()), 4),
                }
            )
    return out
