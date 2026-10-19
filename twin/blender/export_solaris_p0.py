# Prepare the SOLARIS model (built by build_solaris_p0.py) for glTF and export it for Unity:
# forward +Z, up +Y, wheels on y = 0. The procedural cell shader becomes a baked texture.
# Set SOLARIS_REPO if the repository lives elsewhere. Then in Unity: SOLARIS -> 8.
import os

import bpy
import numpy as np

REPO = os.environ.get(
    "SOLARIS_REPO", r"C:\Users\Aditya kumar\OneDrive\Desktop\SOLARIS JOURNALS\solaris-vipv"
)
OUT = os.path.join(
    REPO, "twin", "unity", "SOLARIS-Twin", "Assets", "SolarisTwin", "Models", "SOLARIS_P0.glb"
)
CELL, TILE_CELLS, PX = 0.166, 3, 512  # 3 x 3 cells per texture tile
TILE = CELL * TILE_CELLS
coll = bpy.data.collections["SOLARIS_SUV"]
root = bpy.data.objects["SOLARIS_SUV"]

# 1. solar-cell texture (glTF cannot carry the procedural brick shader)
img = bpy.data.images.get("SOL_PV_Cells_Tex") or bpy.data.images.new(
    "SOL_PV_Cells_Tex", PX, PX, alpha=False
)
u = (np.arange(PX) + 0.5) / PX * TILE_CELLS
fx = np.abs(u - np.round(u)) * CELL  # metres from the nearest cell edge
gap = (fx[None, :] < 0.0016) | (fx[:, None] < 0.0016)
ci = np.floor(u).astype(int)
shade = ((ci[None, :] + ci[:, None]) % 2).astype(float)
c1, c2, mortar = (
    np.array([0.008, 0.016, 0.050]),
    np.array([0.011, 0.022, 0.066]),
    np.array([0.16, 0.18, 0.22]),
)
rgb = c1 + (c2 - c1) * shade[..., None]
rgb[gap] = mortar
srgb = np.where(rgb <= 0.0031308, 12.92 * rgb, 1.055 * rgb ** (1 / 2.4) - 0.055)
img.pixels = np.concatenate([srgb, np.ones((PX, PX, 1))], axis=2).ravel().tolist()
img.colorspace_settings.name = "sRGB"
img.pack()

m = bpy.data.materials["SOL_PV_Cells"]
nt = m.node_tree
p = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
for n in [n for n in nt.nodes if n.type in ("TEX_BRICK", "TEX_COORD", "TEX_IMAGE")]:
    nt.nodes.remove(n)
tex = nt.nodes.new("ShaderNodeTexImage")
tex.image = img
nt.links.new(tex.outputs["Color"], p.inputs["Base Color"])

# UVs on the PV slabs: local x / y are the panel's across / slope axes, in metres
for o in coll.all_objects:
    if o.type == "MESH" and o.name.startswith("PV_") and not o.name.endswith("_frame"):
        me = o.data
        uv = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap")
        for poly in me.polygons:
            for li in poly.loop_indices:
                co = me.vertices[me.loops[li].vertex_index].co
                uv.data[li].uv = (co.x / TILE, co.y / TILE)

# 2. badges: text -> mesh
for name in ("Badge_SOLARIS", "Badge_SOLARIS_Front"):
    o = bpy.data.objects.get(name)
    if o is not None and o.type == "FONT":
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
        mo = bpy.data.objects.new(name, me)
        coll.objects.link(mo)
        mo.parent, mo.matrix_basis = root, o.matrix_basis.copy()
        me.materials.clear()
        me.materials.append(bpy.data.materials["SOL_Badge_Chrome"])
        bpy.data.objects.remove(o, do_unlink=True)
        mo.name = name

# 3. export with the root at the origin (it sits 3.2 m aside for the comparison)
offset = root.location.copy()
root.location = (0, 0, 0)
bpy.context.view_layer.update()
for o in bpy.context.view_layer.objects:
    o.select_set(False)
export = [o for o in coll.all_objects if not o.name.startswith("ArchCut")]
for o in export:
    o.select_set(True)
bpy.context.view_layer.objects.active = root
os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format="GLB",
    use_selection=True,
    export_apply=True,
    export_yup=True,
    export_cameras=False,
    export_lights=False,
    export_extras=False,
    export_image_format="AUTO",
)
root.location = offset
bpy.context.view_layer.update()
print("exported", OUT, os.path.getsize(OUT) // 1024, "KB,", len(export), "objects")
