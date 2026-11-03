# Blender renders for the README (Blender 4.5, Cycles). Visual only: nothing here feeds a result.
# Run inside Blender (Scripting -> Open -> Run Script, or blender-mcp); set SOLARIS_REPO and
# SOLARIS_RENDERS in the environment if the defaults below do not fit.
# It builds two scenes of its own, README_studio and README_city, and leaves other scenes alone.
#   studio: SOLARIS_SUV from twin/blender/build_solaris_p0.py; beauty shot and facet colours
#   city:   data/derived/tiles/{surface,trees}/*.glb of the 1 km block west of the ENU origin,
#           the lidar points as PLYs (written first by the `points` step below, run outside
#           Blender: python docs/readme/blender_renders.py points OUT) and 28 sun positions
#           on 21 June (pvlib SPA) for the sun_day animation
# Then: python docs/readme/make_figures.py --renders OUT --unity <photo folder>
import json
import math
import os
import sys
import time
from pathlib import Path

REPO = Path(
    os.environ.get(
        "SOLARIS_REPO", Path(__file__).resolve().parents[2] if "__file__" in dir() else "."
    )
)
OUT = Path(os.environ.get("SOLARIS_RENDERS", REPO / "docs" / "readme" / "_renders"))
E0, N0, H0 = 400179.648, 3701514.105, 331.663  # twin/exchange/enu_origin.json
BLOCK = (399500.0, 400500.0, 3701000.0, 3702000.0)  # UTM 12N, 1 km
TILES = ["E399500_N3701000", "E400000_N3701000", "E399500_N3701500", "E400000_N3701500"]
FACET_RGB = {
    "PV_roof": (0.95, 0.62, 0.05),
    "PV_hood": (0.10, 0.45, 0.85),
    "PV_tailgate": (0.55, 0.25, 0.75),
    "PV_side_left": (0.10, 0.65, 0.45),
    "PV_side_right": (0.85, 0.25, 0.25),
}


# ------------------------------------------------------------ outside Blender: inputs


def points(out, target=6_000_000):
    """Lidar points of BLOCK -> pts_height.ply and pts_class.ply (local ENU metres)."""
    import numpy as np
    import pdal
    import rasterio
    import rasterio.windows
    from matplotlib import cm

    x0, x1, y0, y1 = BLOCK
    parts = []
    for t in TILES:
        p = pdal.Pipeline(
            json.dumps(
                [
                    {
                        "type": "readers.las",
                        "filename": str(REPO / "data/raw/lidar/tiles" / f"{t}.laz"),
                    },
                    {
                        "type": "filters.crop",
                        "bounds": f"([{x0}, {x1 - 0.001}], [{y0}, {y1 - 0.001}])",
                    },
                ]
            )
        )
        p.execute()
        a = p.arrays[0]
        parts.append(np.column_stack([a["X"], a["Y"], a["Z"]]))
    xyz = np.concatenate(parts)
    xyz = xyz[np.random.default_rng(0).choice(len(xyz), min(target, len(xyz)), replace=False)]

    def sample(path):
        with rasterio.open(path) as s:
            w = (
                rasterio.windows.from_bounds(x0, y0, x1, y1, s.transform)
                .round_offsets()
                .round_lengths()
            )
            arr, tr = s.read(1, window=w), s.window_transform(w)
        c = ((xyz[:, 0] - tr.c) / tr.a).astype(int)
        r = ((xyz[:, 1] - tr.f) / tr.e).astype(int)
        return arr[np.clip(r, 0, arr.shape[0] - 1), np.clip(c, 0, arr.shape[1] - 1)]

    cls = sample(REPO / "data/derived/classes.tif").astype(int)
    hag = xyz[:, 2] - sample(REPO / "data/derived/dem.tif")
    cls = np.where(
        hag < 2.0, 0, cls
    )  # ground, building, tree as in src/solaris/geometry/rasters.py
    loc = np.column_stack([xyz[:, 0] - E0, xyz[:, 1] - N0, xyz[:, 2] - H0]).astype(np.float32)
    rgb = {
        "height": (cm.turbo(0.08 + 0.9 * np.clip(hag / 60.0, 0, 1) ** 0.6)[:, :3] * 255).astype(
            np.uint8
        ),
        "class": np.array([[150, 140, 128], [214, 120, 60], [70, 160, 70]], np.uint8)[
            np.clip(cls, 0, 2)
        ],
    }
    out.mkdir(parents=True, exist_ok=True)
    for k, col in rgb.items():
        v = np.empty(
            len(loc),
            dtype=[("x", "<f4"), ("y", "<f4"), ("z", "<f4"), ("r", "u1"), ("g", "u1"), ("b", "u1")],
        )
        v["x"], v["y"], v["z"] = loc.T
        v["r"], v["g"], v["b"] = col.T
        head = (
            f"ply\nformat binary_little_endian 1.0\nelement vertex {len(v)}\n"
            "property float x\nproperty float y\nproperty float z\n"
            "property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n"
        )
        with open(out / f"pts_{k}.ply", "wb") as f:
            f.write(head.encode("ascii") + v.tobytes())


def sun_positions(out):
    import pandas as pd
    import pvlib

    t = pd.date_range("2023-06-21 05:45", "2023-06-21 19:15", freq="30min", tz="Etc/GMT+7")
    s = pvlib.solarposition.get_solarposition(t, 33.4484, -112.074)
    rows = [
        [x.strftime("%H:%M"), round(e, 2), round(a, 2)]
        for x, e, a in zip(t, s.apparent_elevation, s.azimuth, strict=True)
    ]
    (out / "sunday").mkdir(parents=True, exist_ok=True)
    (out / "sunday" / "sun.json").write_text(json.dumps(rows))


# ------------------------------------------------------------ inside Blender


def _render(sc, path):
    import bpy

    sc.render.filepath = str(path)
    win = bpy.context.window
    prev, win.scene = win.scene, sc
    try:
        bpy.ops.render.render(write_still=True, scene=sc.name)
    finally:
        win.scene = prev


def _look_at(cam, target, offset):
    from mathutils import Vector

    cam.location = Vector(target) + Vector(offset)
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()


def _sun_dir(el_deg, az_deg):
    from mathutils import Vector

    el, az = math.radians(el_deg), math.radians(az_deg)
    return Vector(
        (math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el))
    )  # x east, y north


def _principled(name, rgb, rough=0.9, emit=0.0):
    import bpy

    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    if emit:
        b.inputs["Emission Color"].default_value = (*rgb, 1)
        b.inputs["Emission Strength"].default_value = emit
    return m


def _sky_world(name, el_deg, az_deg, strength):
    import bpy

    w = bpy.data.worlds.get(name) or bpy.data.worlds.new(name)
    w.use_nodes = True
    nt = w.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_WORLD":
            nt.nodes.remove(n)
    out = next(n for n in nt.nodes if n.type == "OUTPUT_WORLD")
    sky, bg = nt.nodes.new("ShaderNodeTexSky"), nt.nodes.new("ShaderNodeBackground")
    sky.sky_type = "NISHITA"
    sky.sun_elevation, sky.sun_rotation, sky.sun_disc = (
        math.radians(el_deg),
        math.radians(90 - az_deg),
        False,
    )
    bg.inputs["Strength"].default_value = strength
    nt.links.new(sky.outputs[0], bg.inputs[0])
    nt.links.new(bg.outputs[0], out.inputs[0])
    return w


def _cycles(sc, samples, w, h):
    import bpy

    sc.render.engine = "CYCLES"
    sc.cycles.samples, sc.cycles.use_denoising = samples, True
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for t in ("OPTIX", "CUDA", "HIP", "ONEAPI"):
        try:
            prefs.compute_device_type = t
            prefs.get_devices()
            if any(d.type == t for d in prefs.devices):
                for d in prefs.devices:
                    d.use = True
                sc.cycles.device = "GPU"
                break
        except TypeError:
            continue
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.film_transparent = True
    sc.view_settings.view_transform = "AgX"


def studio(out):
    """Beauty shot and facet colours of SOLARIS_SUV on a transparent background."""
    import bmesh
    import bpy

    if "SOLARIS_SUV" not in bpy.data.collections:
        exec(
            compile(
                (REPO / "twin/blender/build_solaris_p0.py").read_text(),
                "build_solaris_p0.py",
                "exec",
            ),
            {},
        )
    sc = bpy.data.scenes.get("README_studio") or bpy.data.scenes.new("README_studio")
    if "SOLARIS_SUV" not in [c.name for c in sc.collection.children]:
        sc.collection.children.link(bpy.data.collections["SOLARIS_SUV"])
    centre = bpy.data.objects["SOLARIS_SUV"].matrix_world.translation.copy()
    if "RD_Ground" not in bpy.data.objects:
        me = bpy.data.meshes.new("RD_Ground")
        bm = bmesh.new()
        bmesh.ops.create_circle(bm, cap_ends=True, radius=40, segments=96)
        bm.to_mesh(me)
        bm.free()
        g = bpy.data.objects.new("RD_Ground", me)
        sc.collection.objects.link(g)
        g.location, g.is_shadow_catcher = centre, True
    if "RD_Sun" not in bpy.data.objects:
        s = bpy.data.objects.new("RD_Sun", bpy.data.lights.new("RD_Sun", "SUN"))
        sc.collection.objects.link(s)
    sun = bpy.data.objects["RD_Sun"]
    sun.data.energy, sun.data.angle = 3.2, math.radians(1.5)
    sun.rotation_euler = (-_sun_dir(38, 215)).to_track_quat("-Z", "Y").to_euler()
    if "RD_Cam" not in bpy.data.objects:
        c = bpy.data.objects.new("RD_Cam", bpy.data.cameras.new("RD_Cam"))
        sc.collection.objects.link(c)
    cam = bpy.data.objects["RD_Cam"]
    cam.data.lens = 60
    sc.camera, sc.world = cam, _sky_world("RD_World", 38, 215, 0.35)
    _cycles(sc, 96, 1600, 900)
    sc.view_settings.exposure, sc.view_settings.look = -0.6, "AgX - Medium High Contrast"
    target = (centre.x, centre.y + 0.2, 0.75)
    _look_at(cam, target, (-7.0, -8.6, 4.6))
    _render(sc, out / "suv_beauty.png")
    saved = {
        n: [(s.link, s.material) for s in bpy.data.objects[n].material_slots] for n in FACET_RGB
    }
    try:
        for n, rgb in FACET_RGB.items():
            m = _principled("RD_" + n, rgb, 0.35, 0.25)
            for s in bpy.data.objects[n].material_slots:
                s.link, s.material = "OBJECT", m
        sc.view_settings.look = "AgX - Punchy"
        for tag, off in (("front", (-7.0, -8.6, 4.6)), ("rear", (7.0, 8.6, 4.6))):
            _look_at(cam, target, off)
            _render(sc, out / f"suv_facets_{tag}.png")
    finally:
        sc.view_settings.look = "AgX - Medium High Contrast"
        for n, sl in saved.items():  # back to the mesh's own materials
            for s, (lk, _mat) in zip(bpy.data.objects[n].material_slots, sl, strict=True):
                s.material, s.link = None, lk


def city(out, sun_frames=True):
    """The 1 km block: points by height and class, bare mesh, mesh + trees, and a day of sun."""
    import bpy

    sc = bpy.data.scenes.get("README_city") or bpy.data.scenes.new("README_city")
    win = bpy.context.window
    prev, win.scene = win.scene, sc
    try:
        for kind in ("surface", "trees"):
            col = bpy.data.collections.get("RC_" + kind) or bpy.data.collections.new("RC_" + kind)
            if col.name not in [c.name for c in sc.collection.children]:
                sc.collection.children.link(col)
            bpy.context.view_layer.active_layer_collection = (
                bpy.context.view_layer.layer_collection.children[col.name]
            )
            for t in TILES:
                if f"RC_{kind}_{t}" in bpy.data.objects:
                    continue
                before = set(bpy.data.objects)
                bpy.ops.import_scene.gltf(
                    filepath=str(REPO / "data/derived/tiles" / kind / f"{t}.glb")
                )
                for o in set(bpy.data.objects) - before:
                    if o.type == "MESH":
                        o.name = f"RC_{kind}_{t}"
        col = bpy.data.collections.get("RC_points") or bpy.data.collections.new("RC_points")
        if col.name not in [c.name for c in sc.collection.children]:
            sc.collection.children.link(col)
        bpy.context.view_layer.active_layer_collection = (
            bpy.context.view_layer.layer_collection.children[col.name]
        )
        for tag in ("height", "class"):
            if f"RC_pts_{tag}" not in bpy.data.objects:
                before = set(bpy.data.objects)
                bpy.ops.wm.ply_import(filepath=str(out / f"pts_{tag}.ply"))
                (set(bpy.data.objects) - before).pop().name = f"RC_pts_{tag}"
    finally:
        win.scene = prev
    clay, leaf = (
        _principled("RC_Clay", (0.62, 0.48, 0.34)),
        _principled("RC_Leaf", (0.16, 0.36, 0.14), 0.8),
    )
    pts_mat = bpy.data.materials.get("RC_PointCol") or bpy.data.materials.new("RC_PointCol")
    pts_mat.use_nodes = True
    nt = pts_mat.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    at = nt.nodes.new("ShaderNodeAttribute")
    at.attribute_name = "Col"
    nt.links.new(at.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(at.outputs["Color"], b.inputs["Emission Color"])
    b.inputs["Emission Strength"].default_value = 0.35
    g = bpy.data.node_groups.get("RC_MeshToPoints")
    if g is None:
        g = bpy.data.node_groups.new("RC_MeshToPoints", "GeometryNodeTree")
        g.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        g.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
        gi, go = g.nodes.new("NodeGroupInput"), g.nodes.new("NodeGroupOutput")
        mp, sm = g.nodes.new("GeometryNodeMeshToPoints"), g.nodes.new("GeometryNodeSetMaterial")
        mp.inputs["Radius"].default_value = 0.32
        sm.inputs["Material"].default_value = pts_mat
        g.links.new(gi.outputs[0], mp.inputs["Mesh"])
        g.links.new(mp.outputs[0], sm.inputs["Geometry"])
        g.links.new(sm.outputs[0], go.inputs[0])
    meshes = [o for o in sc.objects if o.type == "MESH"]
    for o in meshes:
        if o.name.startswith("RC_pts"):
            if "pts" not in o.modifiers:
                o.modifiers.new("pts", "NODES").node_group = g
        else:
            o.data.materials.clear()
            o.data.materials.append(leaf if "trees" in o.name else clay)
    sun = bpy.data.objects.get("RC_Sun")
    if sun is None:
        sun = bpy.data.objects.new("RC_Sun", bpy.data.lights.new("RC_Sun", "SUN"))
        sc.collection.objects.link(sun)
    cam = bpy.data.objects.get("RC_Cam")
    if cam is None:
        cam = bpy.data.objects.new("RC_Cam", bpy.data.cameras.new("RC_Cam"))
        sc.collection.objects.link(cam)
    cam.data.lens, cam.data.clip_end = 42, 5000
    _look_at(cam, (-20.0, 60.0, 15.0), (520, -560, 470))
    sc.camera = cam

    def set_sun(el, az, energy=3.6, rgb=(1, 1, 1)):
        sun.data.energy, sun.data.color, sun.data.angle = energy, rgb, math.radians(0.6)
        sun.rotation_euler = (-_sun_dir(el, az)).to_track_quat("-Z", "Y").to_euler()
        sc.world = _sky_world("RC_World", el, az, 0.18)

    _cycles(sc, 64, 1600, 900)
    sc.view_settings.exposure, sc.view_settings.look = -0.5, "AgX - Medium High Contrast"
    set_sun(22.4, 218.0)  # 21 December, 15:00 MST
    layers = {
        "L1_points_height": lambda o: o.name == "RC_pts_height",
        "L2_points_class": lambda o: o.name == "RC_pts_class",
        "L3_mesh_buildings": lambda o: o.name.startswith("RC_surface"),
        "L4_mesh_trees": lambda o: o.name.startswith(("RC_surface", "RC_trees")),
    }
    try:
        for tag, vis in layers.items():
            for o in meshes:
                o.hide_render = not vis(o)
            _render(sc, out / f"{tag}.png")
        if sun_frames:
            for o in meshes:
                o.hide_render = o.name.startswith("RC_pts")
            _cycles(sc, 32, 960, 540)
            for i, (_, el, az) in enumerate(json.loads((out / "sunday" / "sun.json").read_text())):
                k = max(0.0, min(1.0, (el - 3) / 30))
                set_sun(el, az, 1.2 + 2.6 * k, (1.0, 0.72 + 0.28 * k, 0.5 + 0.5 * k))
                _render(sc, out / "sunday" / f"f{i:02d}.png")
    finally:
        for o in meshes:
            o.hide_render = False


if __name__ == "__main__":
    if (
        len(sys.argv) > 1 and sys.argv[1] == "points"
    ):  # plain Python: python blender_renders.py points OUT
        target = Path(sys.argv[2]) if len(sys.argv) > 2 else OUT
        points(target)
        sun_positions(target)
    else:  # inside Blender
        OUT.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        studio(OUT)
        city(OUT)
        print(f"README renders in {OUT} ({time.time() - t0:.0f} s)")
