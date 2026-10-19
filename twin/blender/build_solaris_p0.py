# SOLARIS P0 body for the Unity twin, built in Blender (4.5) around the exact PV facets of
# configs/vehicle/solaris_p0.yaml (placeholder layout, 11.6 m2). Visual model only: E2-E8 use the
# yaml facets, never this mesh; tests/test_vehicle_model.py keeps FACETS equal to the yaml.
# Run: Blender -> Scripting -> Open this file -> Run Script (or send it through blender-mcp);
# then run export_solaris_p0.py to write Assets/SolarisTwin/Models/SOLARIS_P0.glb.
# Body frame: x forward, y left, z up (ground under body centre). Blender local of the root:
# forward -Y, left +X, up +Z  ->  B(x, y, z) = (y, -x, z).
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

COLL = "SOLARIS_SUV"
ROOT_OFFSET = Vector((0.0, 0.0, 0.0))  # set e.g. (3.2, 0, 0) to stand it beside another car
FACETS = [  # id, area, tilt, azimuth_body, centre, across, slope  (solaris_p0.yaml)
    ("roof", 4.4, 2, 0, (-0.10, 0.00, 1.85), 1.6, 2.75),
    ("hood", 1.6, 10, 0, (1.75, 0.00, 1.05), 1.6, 1.0),
    ("tailgate", 0.6, 60, 180, (-2.35, 0.00, 1.45), 1.2, 0.5),
    ("side_left", 2.5, 85, 270, (0.00, 1.00, 1.00), 4.0, 0.625),
    ("side_right", 2.5, 85, 90, (0.00, -1.00, 1.00), 4.0, 0.625),
]
T2, T10 = math.tan(math.radians(2)), math.tan(math.radians(10))


def B(x, y, z):
    return Vector((y, -x, z))


def to_body(v):
    return Vector((-v.y, v.x, v.z))


# ---------------------------------------------------------------- reset
if COLL in bpy.data.collections:
    old = bpy.data.collections[COLL]
    for o in list(old.all_objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.collections.remove(old)
for m in [m for m in bpy.data.meshes if m.users == 0]:
    bpy.data.meshes.remove(m)
coll = bpy.data.collections.new(COLL)
bpy.context.scene.collection.children.link(coll)
root = bpy.data.objects.new("SOLARIS_SUV", None)
root.empty_display_type = "ARROWS"
coll.objects.link(root)


# ---------------------------------------------------------------- materials
def mat(name, base, rough=0.4, metal=0.0, coat=0.0, emit=None, strength=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes.get("Principled BSDF")
    p.inputs["Base Color"].default_value = (*base, 1.0)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    p.inputs["Coat Weight"].default_value = coat
    p.inputs["Coat Roughness"].default_value = 0.03
    if emit is not None:
        p.inputs["Emission Color"].default_value = (*emit, 1.0)
        p.inputs["Emission Strength"].default_value = strength
    return m


PAINT = mat("SOL_Paint_Titanium", (0.40, 0.42, 0.44), rough=0.3, metal=0.75, coat=1.0)
GLOSS = mat("SOL_Gloss_Black", (0.006, 0.006, 0.007), rough=0.12, coat=1.0)
GLASS = mat("SOL_Glass_Tint", (0.006, 0.009, 0.012), rough=0.03, coat=1.0)
CLAD = mat("SOL_Cladding", (0.02, 0.021, 0.023), rough=0.65)
RUBBER = mat("SOL_Tyre", (0.016, 0.016, 0.016), rough=0.88)
RIM = mat("SOL_Rim_Alu", (0.70, 0.71, 0.73), rough=0.2, metal=1.0)
RIM_DARK = mat("SOL_Rim_Dark", (0.05, 0.05, 0.055), rough=0.35, metal=0.8)
FRAME = mat("SOL_PV_Frame", (0.025, 0.025, 0.03), rough=0.3, metal=0.8)
LED_W = mat("SOL_LED_White", (1, 1, 1), rough=0.2, emit=(0.85, 0.93, 1.0), strength=14)
LED_R = mat("SOL_LED_Red", (0.4, 0, 0), rough=0.2, emit=(1.0, 0.02, 0.02), strength=9)
CHROME = mat("SOL_Badge_Chrome", (0.9, 0.9, 0.92), rough=0.06, metal=1.0)
DISC = mat("SOL_Brake", (0.25, 0.25, 0.26), rough=0.45, metal=0.9)
CALIPER = mat("SOL_Caliper", (0.02, 0.25, 0.55), rough=0.35, coat=0.5)


def pv_material():
    m = bpy.data.materials.get("SOL_PV_Cells") or bpy.data.materials.new("SOL_PV_Cells")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    out = nt.nodes["Material Output"]
    p = nt.nodes.new("ShaderNodeBsdfPrincipled")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    br = nt.nodes.new("ShaderNodeTexBrick")
    br.offset, br.squash = 0.0, 1.0
    for k, v in (
        ("Scale", 1.0),
        ("Brick Width", 0.166),
        ("Row Height", 0.166),
        ("Mortar Size", 0.0025),
        ("Mortar Smooth", 0.3),
    ):
        br.inputs[k].default_value = v
    br.inputs["Color1"].default_value = (0.008, 0.016, 0.050, 1)
    br.inputs["Color2"].default_value = (0.011, 0.022, 0.066, 1)
    br.inputs["Mortar"].default_value = (0.16, 0.18, 0.22, 1)
    nt.links.new(tc.outputs["Object"], br.inputs["Vector"])
    nt.links.new(br.outputs["Color"], p.inputs["Base Color"])
    p.inputs["Roughness"].default_value = 0.1
    p.inputs["Metallic"].default_value = 0.2
    p.inputs["Coat Weight"].default_value = 1.0
    p.inputs["Coat Roughness"].default_value = 0.02
    nt.links.new(p.outputs["BSDF"], out.inputs["Surface"])
    return m


PV = pv_material()


# ---------------------------------------------------------------- helpers
def finish(name, bm, materials, smooth=True, angle=40.0, matrix=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    o.parent = root
    if matrix is not None:
        o.matrix_basis = matrix
    for m in materials if isinstance(materials, (list, tuple)) else [materials]:
        me.materials.append(m)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
        try:
            me.set_sharp_from_angle(angle=math.radians(angle))
        except Exception:
            pass
    return o


def bevel(o, width, segs=4, angle=30.0):
    b = o.modifiers.new("Bevel", "BEVEL")
    b.width, b.segments, b.limit_method = width, segs, "ANGLE"
    b.angle_limit = math.radians(angle)
    o.modifiers.new("WeightedNormal", "WEIGHTED_NORMAL").keep_sharp = True


def fillet(keys, k=5):
    """Polyline of (y, z, r) keys -> points with each interior corner rounded by radius r."""
    out = [Vector(keys[0][:2])]
    for i in range(1, len(keys) - 1):
        a, p, c = Vector(keys[i - 1][:2]), Vector(keys[i][:2]), Vector(keys[i + 1][:2])
        r = keys[i][2]
        ua, uc = a - p, c - p
        la, lc = ua.length, uc.length
        if r <= 0:
            out.append(p.copy())  # sharp corner: one point (same key pattern at every station)
            continue
        if la < 1e-6 or lc < 1e-6:
            out += [p.copy() for _ in range(k)]
            continue
        ua.normalize()
        uc.normalize()
        th = math.acos(max(-1.0, min(1.0, ua.dot(uc))))
        d = r / math.tan(th / 2) if th > 1e-3 else 0.0
        d = min(d, 0.45 * la, 0.45 * lc)
        p0, p2 = p + ua * d, p + uc * d
        for j in range(k):
            t = j / (k - 1)
            out.append((1 - t) ** 2 * p0 + 2 * (1 - t) * t * p + t * t * p2)
    out.append(Vector(keys[-1][:2]))
    return out


def loft(name, stations, ring_fn, materials, assign, cap_front=True, cap_rear=True):
    """Stations front->rear; ring_fn(station) -> half ring [(y,z)] from bottom centre to top
    centre (left side). The full ring mirrors it. assign(centre_body, normal_body) -> material
    index per face."""
    bm = bmesh.new()
    rings = []
    for st in stations:
        half = ring_fn(st)
        full = half + [Vector((-p.x, p.y)) for p in reversed(half[1:-1])]
        rings.append([bm.verts.new(B(st["x"], p.x, p.y)) for p in full])
    n = len(rings[0])
    for a, b in zip(rings, rings[1:], strict=False):
        for i in range(n):
            j = (i + 1) % n
            try:
                bm.faces.new([a[i], a[j], b[j], b[i]])
            except ValueError:
                pass
    if cap_front:
        bm.faces.new(rings[0])
    if cap_rear:
        bm.faces.new(list(reversed(rings[-1])))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces:
        f.material_index = assign(to_body(f.calc_center_median()), to_body(f.normal))
    o = finish(name, bm, materials, angle=50)
    o.modifiers.new("WeightedNormal", "WEIGHTED_NORMAL").keep_sharp = True
    return o


def cyl_x(name, c, radius, depth, material, segs=64, bev=0.0, ring=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm, cap_ends=True, segments=segs, radius1=radius, radius2=radius, depth=depth
    )
    bmesh.ops.rotate(
        bm, cent=Vector(), matrix=Matrix.Rotation(math.radians(90), 3, "Y"), verts=bm.verts
    )
    bmesh.ops.translate(bm, vec=B(*c), verts=bm.verts)
    o = finish(name, bm, material, angle=30)
    if bev:
        bevel(o, bev, 4, 40)
    return o


def torus_x(name, c, R, r, material, seg=72, rseg=12):
    bm = bmesh.new()
    rings = []
    for i in range(seg):
        u = 2 * math.pi * i / seg
        ring = []
        for j in range(rseg):
            v = 2 * math.pi * j / rseg
            rr = R + r * math.cos(v)
            ring.append(bm.verts.new((r * math.sin(v), rr * math.cos(u), rr * math.sin(u))))
        rings.append(ring)
    for i in range(seg):
        for j in range(rseg):
            a, b = rings[i], rings[(i + 1) % seg]
            bm.faces.new([a[j], b[j], b[(j + 1) % rseg], a[(j + 1) % rseg]])
    bmesh.ops.translate(bm, vec=B(*c), verts=bm.verts)
    return finish(name, bm, material, angle=80)


def lathe_x(name, c, profile, material, seg=72):
    """Revolve a closed (radius, lateral offset) profile about the body y axis (wheel axle)."""
    bm = bmesh.new()
    rings = []
    for i in range(seg):
        u = 2 * math.pi * i / seg
        rings.append([bm.verts.new((w, r * math.cos(u), r * math.sin(u))) for r, w in profile])
    n = len(profile)
    for i in range(seg):
        a, b = rings[i], rings[(i + 1) % seg]
        for j in range(n):
            bm.faces.new([a[j], b[j], b[(j + 1) % n], a[(j + 1) % n]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.translate(bm, vec=B(*c), verts=bm.verts)
    return finish(name, bm, material, angle=35)


TYRE = [  # 255/50 R18-like section: (radius, lateral), closed loop
    (0.243, 0.098),
    (0.262, 0.112),
    (0.295, 0.118),
    (0.322, 0.113),
    (0.336, 0.100),
    (0.340, 0.050),
    (0.340, -0.050),
    (0.336, -0.100),
    (0.322, -0.113),
    (0.295, -0.118),
    (0.262, -0.112),
    (0.243, -0.098),
]


def box(name, c, size, material, bev=0.01, rot=None):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector((size[1], size[0], size[2])), verts=bm.verts)
    if rot is not None:
        bmesh.ops.rotate(bm, cent=Vector(), matrix=rot, verts=bm.verts)
    bmesh.ops.translate(bm, vec=B(*c), verts=bm.verts)
    o = finish(name, bm, material, smooth=False)
    if bev:
        bevel(o, bev, 3, 60)
    return o


def facet_frame(tilt, az, centre):
    t, a = math.radians(tilt), math.radians(az)
    edge = (math.sin(a), math.cos(a), 0.0)
    up = (-math.cos(t) * math.cos(a), math.cos(t) * math.sin(a), math.sin(t))
    nrm = (math.sin(t) * math.cos(a), -math.sin(t) * math.sin(a), math.cos(t))
    m = Matrix((B(*edge), B(*up), B(*nrm))).transposed().to_4x4()
    m.translation = B(*centre)
    return m


def slab(name, w, h, z0, z1, material, matrix, bev=0.0):
    bm = bmesh.new()
    for z in (z0, z1):
        for x, y in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
            bm.verts.new((x, y, z))
    bm.verts.ensure_lookup_table()
    v = bm.verts
    for f in ((0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)):
        bm.faces.new([v[i] for i in f])
    o = finish(name, bm, material, smooth=False, matrix=matrix)
    if bev:
        bevel(o, bev, 2, 60)
    return o


# ---------------------------------------------------------------- body geometry rules
def side_w(z):  # door skin 12 mm inside the side-panel plane (5 deg lean)
    return 0.988 - 0.0875 * (z - 1.0)


def hood_z(x):  # 15 mm under the hood panel plane (10 deg, rising rearward)
    return 1.05 + (1.75 - x) * T10 - 0.015


def roof_z(x):  # 16 mm under the roof panel plane (2 deg, rising rearward)
    return 1.85 + (-0.10 - x) * T2 - 0.016


def tail_x(z):  # 17 mm inside the tailgate panel plane (60 deg)
    return -2.35 + (z - 1.45) * math.tan(math.radians(30)) + 0.017


LOWER = [  # x, z_bottom, z_belt (fender shoulder), z_hood (centre top), plan scale
    dict(x=2.505, zb=0.36, belt=0.78, hood=0.78, s=0.86),
    dict(x=2.48, zb=0.29, belt=0.88, hood=0.87, s=0.93),
    dict(x=2.42, zb=0.25, belt=1.00, hood=0.925, s=0.975),
    dict(x=2.32, zb=0.24, belt=1.17, hood=hood_z(2.32), s=0.995),
    dict(x=2.20, zb=0.24, belt=1.28, hood=hood_z(2.20), s=1.0),
    dict(x=2.05, zb=0.24, belt=1.32, hood=hood_z(2.05), s=1.0),
    dict(x=1.75, zb=0.24, belt=1.32, hood=hood_z(1.75), s=1.0),
    dict(x=1.45, zb=0.24, belt=1.32, hood=hood_z(1.45), s=1.0),
    dict(x=1.24, zb=0.24, belt=1.32, hood=hood_z(1.24), s=1.0),
    dict(x=1.14, zb=0.24, belt=1.322, hood=1.30, s=1.0),
    dict(x=0.60, zb=0.24, belt=1.327, hood=1.317, s=1.0),
    dict(x=0.00, zb=0.24, belt=1.333, hood=1.323, s=1.0),
    dict(x=-0.80, zb=0.24, belt=1.34, hood=1.33, s=1.0),
    dict(x=-1.60, zb=0.24, belt=1.346, hood=1.336, s=1.0),
    dict(x=-2.10, zb=0.24, belt=1.35, hood=1.34, s=1.0),
    dict(x=tail_x(1.35), zb=0.25, belt=1.35, hood=1.34, s=0.99),
    dict(x=tail_x(1.22), zb=0.27, belt=1.22, hood=1.21, s=0.975),
    dict(x=-2.495, zb=0.30, belt=1.06, hood=1.05, s=0.95),
    dict(x=-2.51, zb=0.36, belt=0.96, hood=0.95, s=0.88),
]


def lower_ring(st):
    s, zb, belt, hood = st["s"], st["zb"], st["belt"], st["hood"]
    zp = min(0.689, belt - 0.06)
    keys = [
        (0.0, zb, 0),
        (0.80 * s, zb, 0.09),
        (side_w(0.62) * s * 0.985, 0.42, 0.07),
        (side_w(zp) * s, zp, 0.0),
        (side_w(belt) * s, belt, 0.03),
        (0.865 * s, belt + 0.012, 0.025),
        (0.815 * s, hood, 0.025),
        (0.0, hood, 0),
    ]
    return fillet(keys)


def lower_assign(c, n):
    if c.z < 0.46:
        return 1  # cladding
    if c.x > 1.15 and abs(c.y) < 0.90 and c.z > 0.85:
        return 2  # hood bay around the hood panel: gloss black, one solar surface
    return 0


body = loft("Body", LOWER, lower_ring, [PAINT, CLAD, GLOSS], lower_assign)

# wheel arches
for i, xw in enumerate((1.50, -1.50)):
    cut = cyl_x(f"ArchCut_{i}", (xw, 0, 0.34), 0.365, 3.0, CLAD, segs=72)
    cut.hide_render = cut.hide_viewport = True
    m = body.modifiers.new(f"Arch_{i}", "BOOLEAN")
    m.operation, m.solver, m.object = "DIFFERENCE", "EXACT", cut
    body.modifiers.move(body.modifiers.find(m.name), i)

# arch liners (inner black)
for i, xw in enumerate((1.50, -1.50)):
    cyl_x(f"ArchLiner_{i}", (xw, 0, 0.34), 0.362, 1.86, CLAD, segs=72)

# greenhouse (glass, pillars, roof)
GH = [dict(x=1.19, top=None)]
for x in (
    0.98,
    0.90,
    0.40,
    0.09,
    0.07,
    -0.06,
    -0.08,
    -0.60,
    -1.04,
    -1.06,
    -1.20,
    -1.22,
    -1.60,
    -1.64,
    -1.66,
    -1.93,
    -1.95,
    -2.06,
):
    GH.append(dict(x=x, top=roof_z(x) if x > -1.52 else roof_z(-1.52) - (-1.52 - x) * 0.04))
GH.append(dict(x=tail_x(1.665), top=1.665))
GH.append(dict(x=tail_x(1.28), top=None))


def gh_ring(st):
    # half ring from the bottom centre (hidden inside the body) to the roof centre
    if st["top"] is None:  # collapsed: windshield base / tailgate base
        z = 1.29
        keys = [
            (0.0, z - 0.01, 0),
            (0.955, z, 0),
            (0.93, z + 0.004, 0.07),
            (0.80, z + 0.006, 0.05),
            (0.0, z + 0.006, 0),
        ]
        return fillet(keys)
    top = st["top"]
    w = 0.94 if st["x"] < -2.1 else 1.0
    keys = [
        (0.0, 1.28, 0),
        (0.955 * w, 1.29, 0),
        (0.86 * w, top - 0.045, 0.08),
        (0.79 * w, top, 0.05),
        (0.0, top, 0),
    ]
    return fillet(keys)


def gh_assign(c, n):
    side = abs(n.y) > 0.55
    if n.z > 0.75 and c.z > 1.6:
        return 2  # roof (gloss black under the panel)
    if c.x > 0.975:
        return 1 if side else 0  # A-pillar paint / windshield
    if c.x < -2.07:
        return 1 if side else 0  # D-pillar paint / rear glass
    if side:
        if -0.08 < c.x < 0.09 or -1.22 < c.x < -1.04:
            return 1  # B, C pillars in body colour
        if c.x > -1.65:
            return 0  # front door, rear door, third-row glass
        return 1  # body-colour rear quarter (D-pillar)
    return 2


loft("Greenhouse", GH, gh_ring, [GLASS, PAINT, GLOSS], gh_assign)

# solar visor: roof skin carried forward over the windshield up to the panel's front edge
slab(
    "Roof_Visor",
    1.74,
    0.40,
    -0.022,
    -0.004,
    PAINT,
    facet_frame(2, 0, (1.14, 0, roof_z(1.14) + 0.016)),
    bev=0.012,
)
slab(
    "Roof_Visor_Under",
    1.70,
    0.36,
    -0.03,
    -0.021,
    GLOSS,
    facet_frame(2, 0, (1.13, 0, roof_z(1.13) + 0.016)),
)

# ---------------------------------------------------------------- PV facets (exact yaml)
for fid, _area, tilt, az, centre, across, slope in FACETS:
    M = facet_frame(tilt, az, centre)
    slab(f"PV_{fid}", across, slope, -0.010, 0.002, PV, M)
    slab(f"PV_{fid}_frame", across + 0.024, slope + 0.024, -0.014, -0.0015, GLOSS, M, bev=0.004)

# ---------------------------------------------------------------- wheels (aero, 20-spoke)
for i, (xw, yw) in enumerate(((1.5, 0.86), (1.5, -0.86), (-1.5, 0.86), (-1.5, -0.86))):
    s = 1 if yw > 0 else -1
    lathe_x(f"Tyre_{i}", (xw, yw, 0.34), [(r, w * s) for r, w in TYRE] if s > 0 else TYRE, RUBBER)
    # recessed dark barrel face, then spokes, lip and hub standing proud of it
    cyl_x(f"RimBarrel_{i}", (xw, yw - 0.03 * s, 0.34), 0.246, 0.15, RIM_DARK, segs=72)
    torus_x(f"RimLip_{i}", (xw, yw + 0.096 * s, 0.34), 0.238, 0.012, RIM)
    cyl_x(f"Disc_{i}", (xw, yw - 0.02 * s, 0.34), 0.20, 0.028, DISC, segs=48)
    box(f"Caliper_{i}", (xw - 0.05, yw + 0.04 * s, 0.53), (0.16, 0.05, 0.07), CALIPER, 0.01)
    cyl_x(f"HubCap_{i}", (xw, yw + 0.10 * s, 0.34), 0.055, 0.016, RIM, segs=32)
    for k in range(10):
        rot = Matrix.Rotation(math.radians(k * 36 + 8), 3, "X")
        box(f"Spoke_{i}_{k}", (xw, yw + 0.088 * s, 0.34), (0.024, 0.018, 0.47), RIM, 0.004, rot=rot)

# ---------------------------------------------------------------- lights, trim, badges
box("Front_Intake", (2.50, 0, 0.47), (0.035, 1.30, 0.17), GLOSS, 0.02)
box("Front_Skid", (2.45, 0, 0.29), (0.10, 1.10, 0.045), RIM, 0.012)
box("LED_Front_Bar", (2.506, 0, 0.745), (0.014, 1.50, 0.022), LED_W, 0.004)
for s in (+1, -1):
    t = "L" if s > 0 else "R"
    box(f"Headlamp_{t}", (2.507, 0.66 * s, 0.665), (0.02, 0.24, 0.045), LED_W, 0.008)
    box(f"Headlamp_Bezel_{t}", (2.498, 0.66 * s, 0.665), (0.03, 0.29, 0.085), GLOSS, 0.015)
    box(f"Mirror_{t}", (1.10, 1.035 * s, 1.40), (0.20, 0.15, 0.11), GLOSS, 0.03)
    box(f"Mirror_Arm_{t}", (1.10, 0.975 * s, 1.36), (0.08, 0.06, 0.03), GLOSS, 0.01)
    box(f"Handle_F_{t}", (0.55, 0.958 * s, 1.345), (0.22, 0.012, 0.022), CHROME, 0.004)
    box(f"Handle_R_{t}", (-0.62, 0.958 * s, 1.35), (0.22, 0.012, 0.022), CHROME, 0.004)
    box(
        f"Belt_Chrome_{t}",
        (-0.48, (side_w(1.338) + 0.004) * s, 1.338),
        (3.20, 0.008, 0.010),
        CHROME,
        0.002,
    )
    box(f"Tail_Corner_{t}", (-2.51, 0.80 * s, 1.03), (0.03, 0.14, 0.10), LED_R, 0.01)
box("LED_Rear_Bar", (-2.515, 0, 1.03), (0.012, 1.40, 0.024), LED_R, 0.004)
box("Rear_Diffuser", (-2.49, 0, 0.36), (0.08, 1.20, 0.10), GLOSS, 0.012)
box("Spoiler", (-2.12, 0, 1.858), (0.16, 1.62, 0.02), GLOSS, 0.008)

cu = bpy.data.curves.new("SOLARIS_badge", "FONT")
cu.body, cu.align_x, cu.size, cu.extrude = "S O L A R I S", "CENTER", 0.075, 0.003
badge = bpy.data.objects.new("Badge_SOLARIS", cu)
coll.objects.link(badge)
badge.parent = root
badge.location = B(-2.53, 0.0, 0.90)
badge.rotation_euler = (math.radians(90), 0, math.radians(180))
badge.data.materials.append(CHROME)
cu2 = cu.copy()
badge2 = bpy.data.objects.new("Badge_SOLARIS_Front", cu2)
coll.objects.link(badge2)
badge2.parent = root
badge2.location = B(2.515, 0.0, 0.60)
badge2.rotation_euler = (math.radians(90), 0, 0)

root.location = ROOT_OFFSET
print("SOLARIS P0 objects", len(coll.all_objects))
