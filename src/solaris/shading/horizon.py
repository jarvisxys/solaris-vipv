"""Raster horizon engine (numba): horizon masks, sky view factor, beam visibility, shadow maps.

A horizon mask holds, per sample point, the horizon elevation in ``n_azimuth`` bins (360 x 1
deg) marched across a surface raster out to ``max_distance_m``; ``bitmask`` expands it to
the 360 azimuth x 0.5 deg elevation boolean mask. Azimuths are true-north based (as pvlib
and the ENU frame are); marching happens on the UTM grid, so every azimuth is rotated by the
point's meridian convergence: grid azimuth = true azimuth - convergence (convergence =
grid north minus true north, about -0.59 deg downtown).

Two surfaces are marched: buildings (dsm.tif, which carries terrain and bridges) and
buildings + canopy (max of dsm and dem + cdsm, trees opaque from the ground up). The
first gives building shading, the difference tree shading.
"""

import math

import numpy as np
import pyproj
from numba import njit, prange

from solaris.geometry.crs import GEOG_CRS, H_CRS


def march_steps(res, max_distance_m, near_m=50.0, growth=0.005):
    """Distances along each ray, in pixels: half-pixel steps out to ``near_m``, then steps of
    ``growth`` x distance (never below half a pixel)."""
    d, out = 0.5 * res, []
    while d <= max_distance_m:
        out.append(d / res)
        d += 0.5 * res if d < near_m else max(0.5 * res, growth * d)
    return np.asarray(out, np.float64)


@njit(parallel=True, cache=True)
def _horizon(surf, rows, cols, z0, az_rad, steps, res):
    n, na = rows.shape[0], az_rad.shape[1]
    nr, nc = surf.shape
    out = np.empty((n, na), np.float32)
    for i in prange(n):
        for k in range(na):
            dx = math.sin(az_rad[i, k])
            dy = -math.cos(az_rad[i, k])  # rows grow southward
            best = -math.pi / 2
            for s in steps:
                r = int(math.floor(rows[i] + dy * s))
                c = int(math.floor(cols[i] + dx * s))
                if r < 0 or c < 0 or r >= nr or c >= nc:
                    break
                z = surf[r, c]
                if z != z:  # NaN: no data, no obstruction
                    continue
                a = math.atan2(z - z0[i], s * res)
                if a > best:
                    best = a
            out[i, k] = math.degrees(best)
    return out


@njit(parallel=True, cache=True)
def _shadow(surf, z0, veg_top, veg_bot, az_rad, el_rad, steps, res):
    nr, nc = surf.shape
    bld = np.zeros((nr, nc), np.bool_)
    veg = np.zeros((nr, nc), np.bool_)
    dx, dy, t = math.sin(az_rad), -math.cos(az_rad), math.tan(el_rad)
    for r0 in prange(nr):
        for c0 in range(nc):
            zr = z0[r0, c0]
            if zr != zr:
                continue
            for s in steps:
                r = int(math.floor(r0 + 0.5 + dy * s))
                c = int(math.floor(c0 + 0.5 + dx * s))
                if r < 0 or c < 0 or r >= nr or c >= nc:
                    break
                z = zr + s * res * t
                if surf[r, c] > z:
                    bld[r0, c0] = True
                    break
                if veg_bot[r, c] <= z <= veg_top[r, c]:  # NaN outside canopy: never true
                    veg[r0, c0] = True
    return bld, veg


@njit(parallel=True, cache=True)
def _beam(surf_b, surf_a, rows, cols, z0, az_rad, el_rad, steps, res, zmax):
    n = rows.shape[0]
    nr, nc = surf_b.shape
    bld = np.zeros(n, np.bool_)
    tree = np.zeros(n, np.bool_)
    for i in prange(n):
        if el_rad[i] <= 0.0:
            bld[i] = True  # sun below the horizontal: no beam
            continue
        dx, dy, t = math.sin(az_rad[i]), -math.cos(az_rad[i]), math.tan(el_rad[i])
        for s in steps:
            z = z0[i] + s * res * t
            if z > zmax:
                break  # above everything in the raster: free
            r = int(math.floor(rows[i] + dy * s))
            c = int(math.floor(cols[i] + dx * s))
            if r < 0 or c < 0 or r >= nr or c >= nc:
                break
            if surf_b[r, c] > z:
                bld[i] = True
                break
            if surf_a[r, c] > z:
                tree[i] = True
    return bld, tree


def beam_points(surf_b, surf_a, transform, x, y, z, sun_az, sun_el, res, steps, convergence):
    """Beam blocked by buildings / by trees only, per point with its own sun position.

    surf_b  building surface (dsm); surf_a  buildings + trees (max of dsm, dem + cdsm)
    sun_az, sun_el  true azimuth and elevation per point (deg); convergence deg per point
    """
    x, y = np.asarray(x, float), np.asarray(y, float)
    col, row = ~transform * (x, y)
    sb = np.ascontiguousarray(surf_b, np.float32)
    sa = np.ascontiguousarray(surf_a, np.float32)
    return _beam(
        sb,
        sa,
        np.asarray(row, float),
        np.asarray(col, float),
        np.asarray(z, float),
        np.radians(np.asarray(sun_az, float) - np.asarray(convergence, float)),
        np.radians(np.asarray(sun_el, float)),
        steps,
        float(res),
        float(np.nanmax(sa)),
    )


def facet_sky_weights(normal_enu, n_azimuth=360, elevation_step=0.5):
    """Weights W (azimuth, elevation bin) = max(0, n . d) cos(el) d_el d_az of the sky
    hemisphere seen by a facet with ENU normal ``normal_enu``. Sum = the facet's view of the
    open sky (pi-normalised later)."""
    az = np.radians(np.arange(n_azimuth) * 360.0 / n_azimuth)
    e0 = np.radians(np.arange(int(round(90 / elevation_step))) * elevation_step)
    el = e0 + np.radians(elevation_step) / 2
    A, E = np.meshgrid(az, el, indexing="ij")
    d = np.stack([np.sin(A) * np.cos(E), np.cos(A) * np.cos(E), np.sin(E)], axis=-1)
    w = np.clip(d @ np.asarray(normal_enu, float), 0.0, None) * np.cos(E)
    return w * np.radians(elevation_step) * 2 * np.pi / n_azimuth


def facet_view(h, weights, elevation_step=0.5, band_deg=None):
    """Visible share of a facet's sky weights above horizons ``h`` (points, azimuth):
    1 = open sky. With ``band_deg``, only the band [0, band_deg) above the horizontal."""
    W = weights if band_deg is None else weights[:, : int(round(band_deg / elevation_step))]
    total = W.sum()
    if total <= 0:
        return np.ones(h.shape[0])
    C = np.concatenate([np.cumsum(W[:, ::-1], axis=1)[:, ::-1], np.zeros((W.shape[0], 1))], axis=1)
    j = np.clip(np.ceil(np.asarray(h, float) / elevation_step).astype(int), 0, W.shape[1])
    vis = C[np.arange(W.shape[0])[None, :], j].sum(axis=1)
    return vis / total


def convergence_deg(x, y):
    """Meridian convergence (grid north minus true north, deg) at UTM points."""
    lon, lat = pyproj.Transformer.from_crs(H_CRS, GEOG_CRS, always_xy=True).transform(x, y)
    return np.asarray(pyproj.Proj(H_CRS).get_factors(lon, lat).meridian_convergence, float)


def azimuth_bins(n_azimuth=360):
    """Bin centres (deg, true north): 0, 1, ..., 359 for 360 bins."""
    return np.arange(n_azimuth) * 360.0 / n_azimuth


def horizon(surf, transform, x, y, z, res, steps, n_azimuth=360, convergence=None):
    """Horizon elevation (deg) per point and true-azimuth bin over a surface raster.

    surf       2-D float32 heights (NaN = no data); transform its rasterio Affine
    x, y, z    UTM points and their eye heights (m)
    convergence  deg per point (default: computed with pyproj; 0 for synthetic grids)
    """
    x, y, z = (np.atleast_1d(np.asarray(v, float)) for v in (x, y, z))
    col, row = ~transform * (x, y)
    conv = convergence_deg(x, y) if convergence is None else np.broadcast_to(convergence, x.shape)
    grid_az = np.radians(azimuth_bins(n_azimuth)[None, :] - np.asarray(conv, float)[:, None])
    return _horizon(
        np.ascontiguousarray(surf, np.float32),
        np.asarray(row, float),
        np.asarray(col, float),
        z,
        np.ascontiguousarray(grid_az),
        steps,
        float(res),
    )


def horizon_at(h, azimuth_deg):
    """Horizon elevation (points, suns) at true azimuths, linear between bins, wrapping 360."""
    n = h.shape[-1]
    f = (np.atleast_1d(np.asarray(azimuth_deg, float)) % 360.0) * n / 360.0
    i0 = np.floor(f).astype(int) % n
    w = f - np.floor(f)
    return (1 - w) * h[:, i0] + w * h[:, (i0 + 1) % n]


def beam_visible(h, azimuth_deg, elevation_deg):
    """True where the sun is above the horizon, shape (points, suns)."""
    return np.atleast_1d(np.asarray(elevation_deg, float))[None, :] > horizon_at(h, azimuth_deg)


def sky_view_factor(h):
    """SVF of a horizontal surface: 1 - mean over azimuth of sin^2(max(h, 0))."""
    hr = np.radians(np.clip(h, 0.0, 90.0))
    return 1.0 - np.mean(np.sin(hr) ** 2, axis=-1)


def bitmask(h, elevation_step=0.5):
    """Boolean mask (points, azimuth, elevation bin): True where the sky cell is blocked.
    Bin j spans [j * step, (j + 1) * step) deg; it is blocked if its centre is below h."""
    centres = (np.arange(int(round(90 / elevation_step))) + 0.5) * elevation_step
    return h[..., None] > centres


def svf_from_mask(mask, elevation_step=0.5):
    """Cosine-weighted SVF of a horizontal surface from a blocked-cell mask."""
    e0 = np.radians(np.arange(mask.shape[-1]) * elevation_step)
    e1 = e0 + np.radians(elevation_step)
    w = (np.sin(e1) ** 2 - np.sin(e0) ** 2) / mask.shape[-2]  # exact per cell, sums to 1
    return 1.0 - np.sum(mask * w, axis=(-2, -1))


def shadow_map(
    surf,
    z0,
    transform,
    res,
    azimuth_deg,
    elevation_deg,
    steps,
    convergence=0.0,
    veg_top=None,
    veg_bottom=None,
):
    """Shaded pixels for one sun position, marching from (pixel centre, z0) toward the sun.

    Returns (building, vegetation) boolean maps when canopy surfaces are given (a ray is
    blocked by vegetation where it passes between ``veg_bottom`` and ``veg_top``, the
    trunk-zone convention of SOLWEIG), else the building map alone. ``surf`` is dsm.tif,
    ``z0`` the receiving surface (dsm.tif too: ground and roofs).
    """
    surf = np.ascontiguousarray(surf, np.float32)
    nan = np.full(surf.shape, np.nan, np.float32)
    top = nan if veg_top is None else np.ascontiguousarray(veg_top, np.float32)
    bot = nan if veg_bottom is None else np.ascontiguousarray(veg_bottom, np.float32)
    bld, veg = _shadow(
        surf,
        np.ascontiguousarray(z0, np.float32),
        top,
        bot,
        math.radians(azimuth_deg - convergence),
        math.radians(elevation_deg),
        steps,
        float(res),
    )
    return bld if veg_top is None else (bld, veg)
