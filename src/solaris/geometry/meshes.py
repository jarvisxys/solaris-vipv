"""Heightfield meshes for Unity in the local ENU frame (P3, step 7).

Per 500 m tile: the building DSM (terrain + buildings + bridges) as one surface, and the tree
canopy (DEM + CDSM on tree pixels) as a separate layer Unity can render semi-transparent.
Surfaces are simplified with Delatin to ``max_error_m`` (0.25 m) of vertical error. Each tile
reaches one pixel into its east and south neighbours so tiles meet, and a vertical skirt
of ``skirt_m`` along the tile border hides the residual seams.

Vertices are pixel centres. Faces point up (normals +U). Unity raycasts ignore back faces by
default; visibility queries from below a bridge deck need Physics.queriesHitBackfaces = true.
"""

import json
from pathlib import Path

import numpy as np
import rasterio
import trimesh
from pydelatin import Delatin

from .crs import enu_transformer, to_gltf
from .rasters import tile_window


def heightfield(z, max_error):
    """Delatin triangulation of a 2-D height grid -> (col, row, z) vertices, faces.

    Delatin counts y from the bottom row; it is converted to the array row here.
    """
    h, w = z.shape
    d = Delatin(np.ascontiguousarray(z, np.float32).ravel(), width=w, height=h, max_error=max_error)
    v = np.asarray(d.vertices, float)
    v[:, 1] = (h - 1) - v[:, 1]
    return v, np.asarray(d.triangles, np.int64)


def boundary_edges(faces):
    """Edges used by exactly one face, oriented as in that face."""
    e = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    key = np.sort(e, axis=1)
    _, inv, cnt = np.unique(key, axis=0, return_inverse=True, return_counts=True)
    return e[cnt[inv.ravel()] == 1]


def add_skirt(verts, faces, depth):
    """Hang a vertical wall of ``depth`` below every border edge (verts in metres, z up)."""
    edges = boundary_edges(faces)
    if depth <= 0 or len(edges) == 0:
        return verts, faces
    n = len(verts)
    lower = verts.copy()
    lower[:, 2] -= depth
    a, b = edges[:, 0], edges[:, 1]
    # Faces run a->b counter-clockwise seen from above, so the outside is to the right of
    # a->b; these two triangles face outward.
    skirt = np.concatenate([np.column_stack([b, a, a + n]), np.column_stack([b, a + n, b + n])])
    return np.vstack([verts, lower]), np.vstack([faces, skirt])


def orient_up(verts, faces):
    """Flip faces whose normal points down."""
    v = verts[faces]
    nz = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0])[:, 2]
    faces = faces.copy()
    faces[nz < 0] = faces[nz < 0][:, ::-1]
    return faces


def to_metres(verts, x0, y0, res):
    """Pixel (col, row, z) of a grid whose top-left pixel centre is (x0, y0) -> UTM."""
    return np.column_stack([x0 + verts[:, 0] * res, y0 - verts[:, 1] * res, verts[:, 2]])


def tile_mesh(z, x0, y0, res, max_error, skirt, keep=None):
    """Surface mesh of grid ``z`` in UTM metres. ``keep`` (bool grid) keeps only faces whose
    centroid pixel is True, and no skirt is added (tree layer)."""
    verts, faces = heightfield(z, max_error)
    if keep is not None:
        c = verts[faces].mean(axis=1)
        r = np.clip(np.rint(c[:, 1]).astype(int), 0, z.shape[0] - 1)
        q = np.clip(np.rint(c[:, 0]).astype(int), 0, z.shape[1] - 1)
        faces = faces[keep[r, q]]
        used = np.unique(faces)
        remap = np.full(len(verts), -1)
        remap[used] = np.arange(len(used))
        verts, faces = verts[used], remap[faces]
    verts = to_metres(verts, x0, y0, res)
    faces = orient_up(verts, faces)
    if keep is None:
        verts, faces = add_skirt(verts, faces, skirt)
    return verts, faces


def export_glb(verts_utm, faces, enu, path, name):
    """UTM + NAVD88 vertices -> ENU -> glTF axes, written as binary glTF."""
    e, n, u = enu.transform(verts_utm[:, 0], verts_utm[:, 1], verts_utm[:, 2])
    v = to_gltf(np.column_stack([e, n, u]))
    mesh = trimesh.Trimesh(vertices=v, faces=faces, process=False)
    scene = trimesh.Scene()
    scene.add_geometry(mesh, node_name=name, geom_name=name)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(scene.export(file_type="glb"))
    lo, hi = v.min(axis=0), v.max(axis=0)
    return {
        "file": path.name,
        "vertices": len(v),
        "faces": len(faces),
        "bbox_gltf": [lo.round(2).tolist(), hi.round(2).tolist()],
    }


def _grid(path, tile, res):
    """Tile grid plus one pixel east and south (NaN outside the raster)."""
    with rasterio.open(path) as src:
        w = tile_window(src, tile)
        w = w.__class__(w.col_off, w.row_off, w.width + 1, w.height + 1)
        a = src.read(1, window=w, boundless=True, masked=True, out_dtype="float32")
    return a.filled(np.nan)


def _fill_edge(z, ref):
    """Replace NaN (beyond the AOI edge, DSM nodata) by ``ref``, then by the nearest row/col."""
    z = np.where(np.isnan(z), ref, z)
    if np.isnan(z).any():
        z[-1] = np.where(np.isnan(z[-1]), z[-2], z[-1])
        z[:, -1] = np.where(np.isnan(z[:, -1]), z[:, -2], z[:, -1])
    return z


def build_tile(tile, cfg, paths, out_dir, h0) -> dict:
    g = cfg["geometry"]
    res, me = g["resolution_m"], g["mesh"]
    enu = enu_transformer(cfg, h0)
    dem = _grid(paths["dem"], tile, res)
    dem = _fill_edge(dem, np.nanmedian(dem))
    dsm = _fill_edge(_grid(paths["dsm"], tile, res), dem)
    cdsm = np.nan_to_num(_grid(paths["cdsm"], tile, res), nan=0.0)
    x0, y0 = tile.xmin + res / 2, tile.ymax - res / 2
    out = {"tile": tile.id, "status": "ok", "bounds_utm": list(tile.bounds)}
    v, f = tile_mesh(dsm, x0, y0, res, me["max_error_m"], me["skirt_m"])
    out["surface"] = export_glb(
        v, f, enu, Path(out_dir) / "surface" / f"{tile.id}.glb", f"surface_{tile.id}"
    )
    trees = cdsm > 0
    if trees.any():
        v, f = tile_mesh(dem + cdsm, x0, y0, res, me["max_error_m"], 0, keep=trees)
        out["trees"] = export_glb(
            v, f, enu, Path(out_dir) / "trees" / f"{tile.id}.glb", f"trees_{tile.id}"
        )
    return out


def write_manifest(entries, origin, out):
    out = Path(out)
    doc = {
        "frame": "ENU at enu_origin, glTF axes (x east, y up, z south)",
        "origin": origin,
        "tiles": sorted(entries, key=lambda e: e["tile"]),
    }
    out.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8", newline="\n")
    return out
