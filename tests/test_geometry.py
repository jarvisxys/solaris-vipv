"""P3: frames, tiles, PDAL rasterisation, building/tree split, meshes, covered, freshness, GCPs.

Offline: synthetic point clouds and rasters built in tmp_path. ENU tests need the GEOID18
grid (projsync --file us_noaa_g2018u0.tif) and skip without it.
"""

import geopandas as gpd
import numpy as np
import pdal
import pyproj
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import LineString, box

from solaris.geometry import control, covered, crs, freshness, lidar, meshes, rasters
from solaris.geometry.crs import Tile
from solaris.site import site_config

CFG = site_config()
G = CFG["geometry"]
RES = G["resolution_m"]


def geoid_available():
    try:
        return np.isfinite(crs.ellipsoidal_height(33.4484, -112.074, 300.0))
    except pyproj.exceptions.ProjError:
        return False


needs_geoid = pytest.mark.skipif(not geoid_available(), reason="GEOID18 grid not installed")


def write_raster(path, arr, x0, y1, nodata=None):
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=arr.shape[1],
        height=arr.shape[0],
        count=1,
        dtype=arr.dtype,
        crs=crs.CRS,
        nodata=nodata,
        transform=from_origin(x0, y1, RES, RES),
    ) as dst:
        dst.write(arr, 1)
    return path


# ---------------------------------------------------------------- step 1: AOI and tiles
def test_aoi_covers_every_seed_with_buffer_and_snaps_to_tiles():
    poly = crs.aoi(CFG)
    t = G["tile_m"]
    assert all(v % t == 0 for v in poly.bounds)
    for g in crs.seed_geometries(CFG).values():
        assert poly.contains(g.buffer(CFG["aoi"]["buffer_m"] - 1))


def test_tiles_partition_the_aoi():
    poly = crs.aoi(CFG)
    ts = crs.tiles(CFG, poly)
    assert len({t.id for t in ts}) == len(ts)
    assert sum(box(*t.bounds).area for t in ts) == pytest.approx(poly.area)
    t0 = ts[0]
    assert t0.id == f"E{int(t0.xmin)}_N{int(t0.ymin)}" and t0.xmax - t0.xmin == G["tile_m"]


# ---------------------------------------------------------------- frames
def test_gltf_axes_are_a_rotation():
    assert crs.to_gltf(np.array([[1.0, 2.0, 3.0]])).tolist() == [[1.0, 3.0, -2.0]]
    m = crs.to_gltf(np.eye(3))
    assert np.linalg.det(m) == pytest.approx(1.0)  # winding (face orientation) preserved


def test_meridian_convergence_downtown():
    assert crs.meridian_convergence(33.4484, -112.074) == pytest.approx(-0.592, abs=0.002)


@needs_geoid
def test_geoid18_separation_downtown():
    assert crs.ellipsoidal_height(33.4484, -112.074, 300.0) - 300.0 == pytest.approx(
        -29.92, abs=0.05
    )


@needs_geoid
def test_enu_origin_is_zero_and_axes_point_to_true_north():
    o = CFG["enu_origin"]
    h0 = crs.ellipsoidal_height(o["lat_deg"], o["lon_deg"], 331.0)
    enu = crs.enu_transformer(CFG, h0)
    x, y = crs.to_utm(o["lat_deg"], o["lon_deg"])
    assert np.allclose(enu.transform(x, y, 331.0), 0, atol=1e-6)
    e, n, u = enu.transform(x, y + 100.0, 331.0)  # 100 m grid north
    conv = np.radians(crs.meridian_convergence(o["lat_deg"], o["lon_deg"]))
    assert e == pytest.approx(100 * np.sin(conv), abs=0.02)  # grid north leans west of true north
    assert n == pytest.approx(100, abs=0.05) and abs(u) < 0.01


# ---------------------------------------------------------------- step 2: PDAL
def test_fetch_pipeline_drops_noise_and_withheld():
    tile = Tile("t", 400000.0, 3701500.0, 400500.0, 3702000.0)
    st = lidar.fetch_stages(CFG, tile, "x.laz")
    expr = next(s for s in st if s["type"] == "filters.expression")["expression"]
    pts = np.zeros(
        4, [("X", "f8"), ("Y", "f8"), ("Z", "f8"), ("Classification", "u1"), ("Withheld", "u1")]
    )
    pts["Classification"] = [2, 7, 18, 1]
    pts["Withheld"] = [0, 0, 0, 1]
    p = pdal.Filter.expression(expression=expr).pipeline(pts)
    p.execute()
    assert p.arrays[0]["Classification"].tolist() == [2]
    m = G["tile_margin_m"]
    crop = next(s for s in st if s["type"] == "filters.crop")["bounds"]
    assert crop == f"([{tile.xmin - m}, {tile.xmax + m}], [{tile.ymin - m}, {tile.ymax + m}])"
    rep = next(s for s in st if s["type"] == "filters.reprojection")
    assert (rep["in_srs"], rep["out_srs"]) == ("EPSG:3857", "EPSG:26912")


@pytest.fixture(scope="module")
def synthetic_tile(tmp_path_factory):
    """5 m tile: flat ground at 300 m (class 2, 0.2 m spacing) and one 10 m roof point
    at the centre of the top-left pixel."""
    root = tmp_path_factory.mktemp("pdal")
    cfg = {"geometry": {**G, "tile_margin_m": 1}}
    t = Tile("t", 400000.0, 3700000.0, 400005.0, 3700005.0)
    dt = [("X", "f8"), ("Y", "f8"), ("Z", "f8"), ("Classification", "u1")]
    gx, gy = np.meshgrid(
        np.arange(t.xmin - 1, t.xmax + 1, 0.2), np.arange(t.ymin - 1, t.ymax + 1, 0.2)
    )
    ground = np.zeros(gx.size, dt)
    ground["X"], ground["Y"], ground["Z"], ground["Classification"] = gx.ravel(), gy.ravel(), 300, 2
    roof = np.zeros(1, dt)
    roof["X"], roof["Y"], roof["Z"], roof["Classification"] = t.xmin + 0.25, t.ymax - 0.25, 310, 1
    pdal.Writer.las(filename=str(root / "t.laz"), a_srs=crs.CRS).pipeline(
        np.concatenate([ground, roof])
    ).execute()
    status = lidar.rasterize_tile(cfg, t, root, root / "r")
    out = {}
    for k in lidar.RASTERS:
        with rasterio.open(root / "r" / k / "t.tif") as s:
            out[k] = (s.read(1), s.transform, s.crs)
    return status, out


def test_rasters_sit_on_the_tile_grid(synthetic_tile):
    status, out = synthetic_tile
    assert status["status"] == "ok"
    a, tr, c = out["dsm"]
    assert a.shape == (10, 10) and (tr.c, tr.f, tr.a) == (400000.0, 3700005.0, RES)
    wkt = c.to_wkt()
    assert "UTM zone 12N" in wkt and "NAVD88" in wkt  # compound EPSG:26912+5703


def test_dsm_keeps_roof_in_its_pixel_only(synthetic_tile):
    dsm = synthetic_tile[1]["dsm"][0]
    assert dsm[0, 0] == pytest.approx(310) and dsm[0, 1] == dsm[1, 0] == pytest.approx(300)


def test_dtm_uses_ground_only_and_hag_is_height_above_it(synthetic_tile):
    out = synthetic_tile[1]
    assert np.allclose(out["dtm"][0], 300)
    assert out["hag"][0][0, 0] == pytest.approx(10) and out["hag"][0][5, 5] == pytest.approx(0)


# ---------------------------------------------------------------- steps 3-5
def test_dtm_holes_are_filled(tmp_path):
    a = np.full((40, 40), 300, np.float32)
    a[10:20, 10:20] = lidar.NODATA  # 5 m building, no ground returns
    src = write_raster(tmp_path / "raw.tif", a, 0, 20, nodata=lidar.NODATA)
    out = rasters.fill_dtm(src, tmp_path / "dem.tif", 50, RES)
    with rasterio.open(out) as s:
        assert np.allclose(s.read(1), 300)


def classify(ndsm, ndvi, inside=None, inside_b=None):
    z = np.zeros(ndsm.shape, bool)
    return rasters.classify(
        ndsm,
        ndvi,
        z if inside is None else inside,
        z if inside_b is None else inside_b,
        G,
        RES * RES,
    )


def test_trees_need_height_and_greenness():
    ndsm = np.zeros((20, 20), np.float32)
    ndvi = np.zeros((20, 20), np.float32)
    ndsm[2:8, 2:8], ndvi[2:8, 2:8] = 6, 0.5  # tree
    ndsm[12:18, 2:8], ndvi[12:18, 2:8] = 1.5, 0.5  # lawn/shrub, too low
    c = classify(ndsm, ndvi)
    assert (c[2:8, 2:8] == rasters.TREE).all() and (c[12:18, 2:8] == rasters.GROUND).all()


def test_buildings_from_footprints_or_tall_and_grey():
    ndsm = np.zeros((20, 20), np.float32)
    ndvi = np.full((20, 20), 0.05, np.float32)
    inside = np.zeros((20, 20), bool)
    inside[2:8, 2:8] = True  # footprint, any height
    ndsm[12:18, 12:18] = 8  # no footprint, tall and not green
    c = classify(ndsm, ndvi, inside, inside)
    assert (c[2:8, 2:8] == rasters.BUILDING).all() and (c[12:18, 12:18] == rasters.BUILDING).all()


def test_green_tower_wall_is_building_not_tree():
    ndsm = np.zeros((20, 20), np.float32)
    ndvi = np.full((20, 20), 0.5, np.float32)
    ndsm[2:8, 2:8] = 30  # tall palm
    ndsm[12:18, 12:18] = 60  # tower wall painted green by relief displacement
    c = classify(ndsm, ndvi)
    assert (c[2:8, 2:8] == rasters.TREE).all() and (c[12:18, 12:18] == rasters.BUILDING).all()


def test_tree_next_to_footprint_is_not_a_tree():
    ndsm = np.full((20, 20), 6, np.float32)
    ndvi = np.full((20, 20), 0.5, np.float32)
    buffered = np.zeros((20, 20), bool)
    buffered[:, :10] = True  # within 1 m of a footprint
    c = classify(ndsm, ndvi, inside_b=buffered)
    assert (c[:, :10] != rasters.TREE).all() and (c[:, 10:] == rasters.TREE).all()


def test_blobs_under_4_m2_are_dropped():
    min_px = int(np.ceil(G["min_blob_m2"] / RES**2))  # 16 px
    ndsm = np.zeros((30, 30), np.float32)
    ndvi = np.zeros((30, 30), np.float32)
    ndsm[2:5, 2:7] = 5  # 15 px: car or sign
    ndsm[20:24, 20:24] = 5  # 16 px: kept
    c = classify(ndsm, ndvi)
    assert (c[2:5, 2:7] == rasters.GROUND).all()
    assert (c[20:24, 20:24] == rasters.BUILDING).all() and min_px == 16


def test_model_rasters_follow_the_solweig_convention():
    dem = np.full((4, 4), 300, np.float32)
    dsm = dem + np.array([[20, 20, 6, 0]] * 4, np.float32)
    dsm[3, 0] = np.nan  # no return over a glass roof
    classes = np.array([[1, 1, 2, 0]] * 4, np.uint8)
    b, cdsm, holes = rasters.model_rasters(dsm, dem, classes)
    assert b[0, 0] == 320 and b[0, 2] == 300 and b[3, 0] == 300  # hole not invented
    assert cdsm[0, 2] == 6 and cdsm[0, 0] == 0 and cdsm[0, 3] == 0
    assert holes[3, 0] == 1 and holes.sum() == 1


# ---------------------------------------------------------------- step 6
def test_way_width_rules():
    assert covered.way_width({"width": "12 m"}) == 12
    assert covered.way_width({"lanes": "3"}) == 3 * 3.5 + 2
    assert covered.way_width({"highway": "motorway_link"}) == 16
    assert covered.way_width({"railway": "rail"}) == covered.RAIL_WIDTH_M


def test_culverts_are_not_road_cover():
    ways = gpd.GeoDataFrame(
        {
            "id": ["1", "2", "3"],
            "highway": [None, "primary", "footway"],
            "tunnel": ["culvert", None, None],
            "bridge": [None, "yes", "no"],
        },
        geometry=[LineString([(0, 0), (1, 0)])] * 3,
        crs=crs.H_CRS,
    )
    polys = covered.covered_polygons(ways)
    assert polys.osm_id.tolist() == ["2"] and polys.kind.tolist() == ["bridge"]


@pytest.fixture
def overpass(tmp_path):
    ways = gpd.GeoDataFrame(
        {"id": ["7"], "bridge": ["yes"], "highway": ["primary"]},
        geometry=[LineString([(0, 10), (20, 10)])],
        crs=crs.H_CRS,
    )
    dem = np.full((40, 40), 300, np.float32)
    dsm = dem.copy()
    dsm[:, 30:] = 306  # 6 m overhang at x >= 15
    dsm[8:32, :30] = 307  # the bridge deck itself, 7 m up (y 4-16)
    return (
        covered.covered_polygons(ways),
        write_raster(tmp_path / "dsm.tif", dsm, 0, 20),
        write_raster(tmp_path / "dem.tif", dem, 0, 20),
    )


def test_points_under_bridge_or_tall_cover_are_covered(overpass):
    polys, dsm, dem = overpass
    flag, why = covered.tag_covered(
        [5, 5, 17], [10, 2, 2], polys, dsm, dem, G["covered_ndsm_m"], own_way=["99", "99", "99"]
    )
    assert flag.tolist() == [True, False, True] and why.tolist() == ["osm", "", "ndsm"]


def test_driving_on_the_bridge_is_not_covered(overpass):
    polys, dsm, dem = overpass
    flag, _ = covered.tag_covered(
        [5], [10], polys, dsm, dem, G["covered_ndsm_m"], z_road=[307.0], own_way=["7"]
    )
    assert flag.tolist() == [False]


# ---------------------------------------------------------------- step 7
def test_heightfield_maps_rows_and_columns_to_utm():
    z = np.zeros((5, 7), np.float32)
    z[1, 5] = 10  # row 1, col 5
    v, f = meshes.tile_mesh(z, 100.25, 200.75, RES, 0.01, 0.0)
    peak = v[v[:, 2] > 5]
    assert peak.tolist() == [[100.25 + 5 * RES, 200.75 - 1 * RES, 10.0]]


def test_mesh_error_bound_skirt_and_orientation():
    z = np.zeros((41, 41), np.float32)
    z[10:30, 10:30] = 25  # a 10 m tower
    verts, faces = meshes.heightfield(z, G["mesh"]["max_error_m"])
    from pydelatin import Delatin

    d = Delatin(z.ravel(), width=41, height=41, max_error=G["mesh"]["max_error_m"])
    assert d.error <= G["mesh"]["max_error_m"]
    v, f = meshes.tile_mesh(z, 0.25, 20.25, RES, G["mesh"]["max_error_m"], G["mesh"]["skirt_m"])
    tri = v[f]
    normal = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    top = tri[:, :, 2].min(axis=1) >= -1e-9
    assert (normal[top][:, 2] >= -1e-9).all()  # surface faces point up
    skirt = ~top
    assert skirt.any() and v[:, 2].min() == pytest.approx(-G["mesh"]["skirt_m"])
    centre = np.array([10.25, 10.25])  # skirts face away from the tile centre
    out = tri[skirt].mean(axis=1)[:, :2] - centre
    assert (np.einsum("ij,ij->i", normal[skirt][:, :2], out) > 0).all()


def test_tree_layer_keeps_only_canopy():
    z = np.zeros((21, 21), np.float32)
    keep = np.zeros((21, 21), bool)
    z[5:10, 5:10], keep[5:10, 5:10] = 8, True
    v, f = meshes.tile_mesh(z, 0, 10, RES, 0.25, 0.0, keep=keep)
    c = v[f].mean(axis=1)
    assert len(f) > 0 and (c[:, 0] > 1.5).all() and (c[:, 0] < 5.5).all()


# ---------------------------------------------------------------- step 8
@pytest.fixture
def town(tmp_path):
    """60 x 60 m: a lidar building with a footprint, a lidar building without one
    (demolished?), a footprint over bare ground (added?), all inside the R-OPEN corridor."""
    x0, y0 = crs.to_utm(33.378, -112.050)  # on the R-OPEN seed line
    x0, y1 = float(np.floor(x0)), float(np.floor(y0)) + 30
    n = 120
    dem = np.full((n, n), 340, np.float32)
    dsm = dem.copy()
    cls = np.zeros((n, n), np.uint8)
    dsm[10:40, 10:40] += 12
    cls[10:40, 10:40] = rasters.BUILDING  # existing building, has a footprint
    dsm[70:115, 10:50] += 9
    cls[70:115, 10:50] = rasters.BUILDING  # no current footprint, 450 m2
    paths = {
        k: write_raster(tmp_path / f"{k}.tif", a, x0, y1)
        for k, a in (("dem", dem), ("dsm", dsm), ("classes", cls))
    }
    px = lambda r0, r1, c0, c1: box(x0 + c0 * RES, y1 - r1 * RES, x0 + c1 * RES, y1 - r0 * RES)  # noqa: E731
    fp = gpd.GeoDataFrame(
        {
            "overture_id": ["old", "new"],
            "height_m": [np.nan, 28.0],
            "num_floors": [np.nan, np.nan],
            "source": ["OSM", "Microsoft"],
        },
        geometry=[px(10, 40, 10, 40), px(10, 40, 70, 100)],
        crs=crs.H_CRS,
    )
    tile = Tile("t", x0, y1 - n * RES, x0 + n * RES, y1)
    return paths, fp, tile


def test_freshness_finds_added_and_demolished(town):
    paths, fp, tile = town
    bridges = gpd.GeoDataFrame(geometry=[], crs=crs.H_CRS)
    cand = freshness.candidates(
        CFG, [tile], fp, bridges, paths["classes"], paths["dsm"], paths["dem"]
    )
    assert sorted(cand.kind) == ["added", "demolished"]
    a = cand[cand.kind == "added"].iloc[0]
    assert a.overture_id == "new" and a.suggested_floors == 8 and a.routes == "R-OPEN"
    d = cand[cand.kind == "demolished"].iloc[0]
    assert d.area_m2 == pytest.approx(450, rel=0.01) and d.lidar_ndsm_max_m == pytest.approx(9)
    assert (
        a.id.startswith("A-E") and d.id.startswith("D-E") and (cand.status == "unconfirmed").all()
    )


def test_confirmed_changes_are_burnt_into_the_dsm(town, tmp_path):
    paths, fp, tile = town
    bridges = gpd.GeoDataFrame(geometry=[], crs=crs.H_CRS)
    cand = freshness.candidates(
        CFG, [tile], fp, bridges, paths["classes"], paths["dsm"], paths["dem"]
    )
    cand.to_file(tmp_path / "cand.gpkg", layer="candidates")
    ids = dict(zip(cand.kind, cand.id, strict=True))
    conf = tmp_path / "conf.yaml"
    conf.write_text(
        f"confirmed:\n  - {{id: {ids['added']}, status: added, floors: 8}}\n"
        f"  - {{id: {ids['demolished']}, status: demolished}}\n"
    )
    out = tmp_path / "dsm_now.tif"
    r = freshness.apply_confirmed(
        paths["dsm"],
        paths["dem"],
        tmp_path / "cand.gpkg",
        conf,
        out,
        G["freshness"]["floor_height_m"],
    )
    with rasterio.open(out) as s:
        z = s.read(1)
    assert r == {"applied": 2}
    assert z[25, 85] == pytest.approx(340 + 8 * 3.5)  # new tower
    assert z[85, 25] == pytest.approx(340)  # demolished
    assert z[25, 25] == pytest.approx(352)  # untouched


def test_unknown_confirmation_id_is_rejected(town, tmp_path):
    paths, fp, tile = town
    gpd.GeoDataFrame({"id": ["A-E1-N1"]}, geometry=[box(0, 0, 1, 1)], crs=crs.H_CRS).to_file(
        tmp_path / "c.gpkg", layer="candidates"
    )
    conf = tmp_path / "conf.yaml"
    conf.write_text("confirmed:\n  - {id: A-E9-N9, status: added, floors: 3}\n")
    with pytest.raises(ValueError, match="not in the candidate list"):
        freshness.apply_confirmed(
            paths["dsm"], paths["dem"], tmp_path / "c.gpkg", conf, tmp_path / "o.tif", 3.5
        )


# ---------------------------------------------------------------- ground control
def test_only_adjusted_marks_are_ground_control():
    marks = [
        {
            "pid": "A1",
            "lat": "33.45",
            "lon": "-112.07",
            "orthoHt": "330.1",
            "posSource": "ADJUSTED",
            "vertSource": "ADJUSTED",
        },
        {
            "pid": "S1",
            "lat": "33.45",
            "lon": "-112.07",
            "orthoHt": "330.1",
            "posSource": "SCALED",
            "vertSource": "ADJUSTED",
        },
        {
            "pid": "V1",
            "lat": "33.45",
            "lon": "-112.07",
            "orthoHt": "330.1",
            "posSource": "ADJUSTED",
            "vertSource": "VERTCON3",
        },
        {
            "pid": "N1",
            "lat": "33.45",
            "lon": "-112.07",
            "orthoHt": " ",
            "posSource": "ADJUSTED",
            "vertSource": "ADJUSTED",
        },
    ]
    assert control.good_marks(marks).pid.tolist() == ["A1"]


def test_dem_height_is_bilinear(tmp_path):
    a = np.array([[300, 302], [304, 306]], np.float32)
    p = write_raster(tmp_path / "dem.tif", a, 0, 1)
    h = control.dem_height(p, [0.25, 0.5, 0.25], [0.75, 0.5, 0.25])
    assert h.tolist() == pytest.approx([300, 303, 304])
