"""City-scale helpers over the P3 rasters: horizons for many points (blocked by area so only a
few km2 of raster sit in memory at a time), and ground heights."""

import numpy as np
import rasterio
from rasterio.windows import from_bounds

from solaris.core.params import REPO_ROOT

from .horizon import horizon, march_steps

D = REPO_ROOT / "data" / "derived"
RES = 0.5


def read_window(path, bounds):
    with rasterio.open(path) as s:
        w = from_bounds(*bounds, transform=s.transform).round_offsets().round_lengths()
        a = s.read(1, window=w, boundless=True, masked=True, out_dtype="float32").filled(np.nan)
        return a, s.window_transform(w)


def surfaces(bounds, root=D):
    """Building surface (dsm), buildings + trees (max of dsm and dem + cdsm), dem; transform."""
    dsm, tr = read_window(root / "dsm.tif", bounds)
    dem, _ = read_window(root / "dem.tif", bounds)
    cdsm, _ = read_window(root / "cdsm.tif", bounds)
    return dsm, np.fmax(dsm, dem + np.nan_to_num(cdsm)), dem, tr


def ground(x, y, root=D, layer="dem.tif"):
    """Raster height (nearest pixel) at UTM points."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    with rasterio.open(root / layer) as s:
        return np.array([v[0] for v in s.sample(list(zip(x, y, strict=True)))], float)


def horizons(x, y, z, shading_cfg, block_m=2000.0, root=D):
    """(h_buildings, h_all) per point, deg, n_azimuth bins; points processed by blocks."""
    x, y, z = (np.asarray(v, float) for v in (x, y, z))
    sh = shading_cfg
    dmax = sh["max_distance_m"]
    steps = march_steps(RES, dmax, sh["near_m"], sh["growth"])
    n = sh["n_azimuth"]
    h_b = np.empty((len(x), n), np.float32)
    h_a = np.empty((len(x), n), np.float32)
    bx, by = np.floor(x / block_m).astype(int), np.floor(y / block_m).astype(int)
    for kx, ky in sorted(set(zip(bx, by, strict=True))):
        idx = np.nonzero((bx == kx) & (by == ky))[0]
        b = (
            kx * block_m - dmax,
            ky * block_m - dmax,
            (kx + 1) * block_m + dmax,
            (ky + 1) * block_m + dmax,
        )
        dsm, allv, _, tr = surfaces(b, root)
        h_b[idx] = horizon(dsm, tr, x[idx], y[idx], z[idx], RES, steps, n)
        h_a[idx] = horizon(allv, tr, x[idx], y[idx], z[idx], RES, steps, n)
    return h_b, h_a
