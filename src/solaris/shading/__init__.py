"""Shading engines (P4): raster horizon masks (numba), SVF, beam visibility, covered flag,
and a trimesh/Embree mesh-ray engine used as the cross-check (E1)."""

from solaris.geometry.covered import tag_covered

from .horizon import (
    azimuth_bins,
    beam_visible,
    bitmask,
    convergence_deg,
    horizon,
    horizon_at,
    march_steps,
    shadow_map,
    sky_view_factor,
    svf_from_mask,
)
from .mesh import MeshEngine, city_engine, load_tiles
from .sun import sun_position, sun_vector

__all__ = [
    "MeshEngine",
    "azimuth_bins",
    "beam_visible",
    "bitmask",
    "city_engine",
    "convergence_deg",
    "horizon",
    "horizon_at",
    "load_tiles",
    "march_steps",
    "shadow_map",
    "sky_view_factor",
    "sun_position",
    "sun_vector",
    "svf_from_mask",
    "tag_covered",
]
