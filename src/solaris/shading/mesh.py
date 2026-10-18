"""Mesh-ray engine (trimesh + Embree): beam visibility and horizon masks by casting rays.

Works in a local east-north-up frame (x east, y north, z up, true north), so it needs no
meridian-convergence correction. That makes it an independent check of the raster engine.
For the city it loads the P3 .glb tiles (glTF axes, ENU origin in twin/exchange); for
synthetic tests it takes any trimesh meshes in the same frame.
"""

import json
from pathlib import Path

import numpy as np
import trimesh
from trimesh.ray.ray_pyembree import RayMeshIntersector

from solaris.geometry.crs import enu_transformer

from .sun import sun_vector


class MeshEngine:
    """Two layers: buildings (surface tiles: terrain, buildings, bridges) and buildings +
    trees. Each ray asks only 'does anything block it' (Embree any-hit)."""

    def __init__(self, building_meshes, tree_meshes=()):
        bld = trimesh.util.concatenate(list(building_meshes))
        self._bld = RayMeshIntersector(bld)
        trees = list(tree_meshes)
        self._all = (
            RayMeshIntersector(trimesh.util.concatenate([bld, *trees])) if trees else self._bld
        )
        self.faces = len(bld.faces) + sum(len(t.faces) for t in trees)

    def blocked(self, origins, directions, trees=True):
        eng = self._all if trees else self._bld
        return eng.intersects_any(np.asarray(origins, float), np.asarray(directions, float))

    def beam(self, points, azimuth_deg, elevation_deg, trees=True):
        """Blocked flags (points, suns) for rays from ``points`` toward each sun."""
        d = sun_vector(azimuth_deg, elevation_deg).reshape(-1, 3)
        p = np.asarray(points, float)
        o = np.repeat(p, len(d), axis=0)
        dirs = np.tile(d, (len(p), 1))
        return self.blocked(o, dirs, trees).reshape(len(p), len(d))

    def horizon_mask(self, points, n_azimuth=360, elevation_step=0.5, trees=True, batch=16):
        """Boolean mask (points, azimuth, elevation bin): a ray through each cell centre."""
        az = np.arange(n_azimuth) * 360.0 / n_azimuth
        el = (np.arange(int(round(90 / elevation_step))) + 0.5) * elevation_step
        d = sun_vector(*np.meshgrid(az, el, indexing="ij")).reshape(-1, 3)
        p = np.asarray(points, float)
        out = np.empty((len(p), len(az) * len(el)), bool)
        for i in range(0, len(p), batch):
            q = p[i : i + batch]
            o = np.repeat(q, len(d), axis=0)
            dirs = np.tile(d, (len(q), 1))
            out[i : i + len(q)] = self.blocked(o, dirs, trees).reshape(len(q), -1)
        return out.reshape(len(p), len(az), len(el))


# ---------------------------------------------------------------- P3 tiles
def _gltf_to_enu(mesh):
    v = np.asarray(mesh.vertices)
    return trimesh.Trimesh(np.column_stack([v[:, 0], -v[:, 2], v[:, 1]]), mesh.faces, process=False)


def load_tiles(tiles_dir, bounds_utm, layers=("surface", "trees")):
    """P3 .glb tiles whose UTM bounds intersect ``bounds_utm``, as ENU meshes per layer."""
    tiles_dir = Path(tiles_dir)
    man = json.loads((tiles_dir / "MANIFEST.json").read_text(encoding="utf-8"))
    x0, y0, x1, y1 = bounds_utm
    out = {k: [] for k in layers}
    for t in man["tiles"]:
        a, b, c, d = t["bounds_utm"]
        if c <= x0 or a >= x1 or d <= y0 or b >= y1:
            continue
        for k in layers:
            if k in t:
                m = trimesh.load(tiles_dir / k / t[k]["file"], force="mesh", process=False)
                out[k].append(_gltf_to_enu(m))
    return out


def city_engine(cfg, tiles_dir, origin, bounds_utm):
    """MeshEngine over the P3 tiles in ``bounds_utm`` and a UTM+NAVD88 -> ENU converter."""
    layers = load_tiles(tiles_dir, bounds_utm)
    enu = enu_transformer(cfg, origin["h_ellipsoid_m"])

    def to_enu(x, y, z):
        return np.column_stack(enu.transform(np.asarray(x), np.asarray(y), np.asarray(z)))

    return MeshEngine(layers["surface"], layers["trees"]), to_enu
