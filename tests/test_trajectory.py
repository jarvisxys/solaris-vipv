"""P6: route selection rules, trajectory helpers, facet poses, beam and sky-view kernels,
the P5 canopy mask, and the frozen routes/v1 manifest."""

import hashlib
import importlib.util
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from rasterio.transform import from_origin
from shapely.geometry import LineString

from solaris.shading import (
    beam_points,
    facet_sky_weights,
    facet_view,
    march_steps,
    sky_view_factor,
)
from solaris.trajectory import routes
from solaris.trajectory.sumo import osm_way, trace_stats
from solaris.vehicle import body_axes, facets, normal_enu, to_world

ROOT = Path(__file__).resolve().parents[1]
R = {
    "sample_step_m": 10,
    "window_m": 8000,
    "stride_m": 1000,
    "min_m": 6000,
    "max_m": 10000,
    "min_coverage": 0.9,
}


def edges_of(lines):
    return gpd.GeoDataFrame(
        {"name": [n for n, _ in lines]}, geometry=[g for _, g in lines], crs=26912
    )


# ---------------------------------------------------------------- route selection
def test_street_names_drop_direction_prefixes():
    assert routes.street_name("North Central Avenue") == "Central Avenue"
    assert routes.street_name("West Camelback Road") == "Camelback Road"
    assert routes.street_name(None) is None


def test_points_windows_and_coverage():
    e = edges_of(
        [
            ("North Ns Road", LineString([(0, 0), (0, 12000)])),
            ("East Ew Road", LineString([(0, 0), (7000, 0)])),
            ("Gap Road", LineString([(0, 50000), (3000, 50000)])),
        ]
    )
    p = routes.arterial_points(e, 10, "Road$")
    assert set(p["orientation"]) == {"N-S", "E-W"}
    p = p.assign(svf=0.5, svf_bld=0.6, sunlit=0.9)
    c = routes.candidates(p, R)
    ns = c[c["street"] == "Ns Road"]
    # points span 5 m .. 11 995 m: 8 km windows start at 5, 1005, 2005, 3005 m
    assert len(ns) == 4 and (ns["length_m"] == 8000).all()
    assert c[c["street"] == "Ew Road"]["length_m"].tolist() == pytest.approx([7000 - 10], abs=10)
    assert "Gap Road" not in set(c["street"])  # 3 km: too short


def test_choose_open_dense_mixed_on_distinct_streets_and_both_orientations():
    c = pd.DataFrame(
        {
            "street": ["A", "B", "C", "D", "E"],
            "orientation": ["N-S", "N-S", "N-S", "E-W", "N-S"],
            "svf_mean": [0.9, 0.3, 0.6, 0.62, 0.58],
            "svf_var": [0.01, 0.02, 0.01, 0.05, 0.09],
        }
    )
    sel = routes.choose(c, [0.25, 0.75])
    assert sel["R-OPEN"]["street"] == "A" and sel["R-DENSE"]["street"] == "B"
    # the highest-variance band member (E) is N-S like the others, so Mixed goes E-W (D)
    assert sel["R-MIXED"]["street"] == "D"


def test_route_line_runs_north_and_bridges_a_gap():
    e = edges_of(
        [
            ("Ns Road", LineString([(0, 9000), (0, 5000)])),
            ("Ns Road", LineString([(0, 4000), (0, 0)])),
            ("Link Street", LineString([(0, 5000), (300, 4500), (0, 4000)])),
        ]
    )
    ln = routes.route_line(e, "Ns Road", 0, 9000, "N-S")
    assert ln.coords[0] == (0, 0) and ln.coords[-1] == (0, 9000)  # runs north, end to end
    assert ln.length == pytest.approx(8000 + 2 * np.hypot(300, 500), abs=1)  # the gap via the link


def test_seed_overlap():
    ln = LineString([(0, 0), (0, 1000)])
    o = routes.seed_overlap(ln, {"R-X": LineString([(30, 0), (30, 500)]), "P1": LineString()})
    assert o == {"R-X": pytest.approx(0.6, abs=0.01)}


# ---------------------------------------------------------------- trajectories
def test_osm_way_from_sumo_edge_ids():
    assert (
        osm_way("-123456#2") == "123456" and osm_way("98765#0") == "98765" and osm_way(42) == "42"
    )


def test_trace_stats_counts_stops():
    g = pd.DataFrame(
        {
            "t": np.arange(10),
            "x_utm": np.arange(10) * 5.0,
            "y_utm": 0.0,
            "speed": [5, 5, 0, 0, 5, 5, 0, 5, 5, 5],
            "covered": False,
        }
    )
    s = trace_stats(g)
    assert s["stops"] == 2 and s["stopped_s"] == 3 and s["distance_m"] == 45.0


# ---------------------------------------------------------------- vehicle poses
def test_body_axes_and_world_pose():
    fwd, left = body_axes(90.0)  # heading east
    assert np.allclose(fwd, [1, 0, 0]) and np.allclose(left, [0, 1, 0])
    w = to_world(np.array([[1.0, 0.0, 1.8], [0.0, 1.0, 0.0]]), 100.0, 200.0, 330.0, 90.0)
    assert np.allclose(w, [[101, 200, 331.8], [100, 201, 330]])
    side = {f.id: f for f in facets()}["side_right"]
    assert np.allclose(normal_enu(side, 90.0)[:2] / np.sin(np.radians(85)), [0, -1])  # faces south


# ---------------------------------------------------------------- kernels
def test_beam_points_box_shadow():
    res = 0.5
    z = np.zeros((800, 800), np.float32)
    z[380:420, 380:420] = 20.0  # 20 m box; north face at y = 210
    tr = from_origin(0.0, 400.0, res, res)
    L = 20.0 / np.tan(np.radians(30))
    y = np.array([210 + L - 1, 210 + L + 1])
    bld, tree = beam_points(
        z,
        z,
        tr,
        [200.0, 200.0],
        y,
        [0.0, 0.0],
        [180.0, 180.0],
        [30.0, 30.0],
        res,
        march_steps(res, 300.0),
        [0.0, 0.0],
    )
    assert bld.tolist() == [True, False] and not tree.any()


def test_beam_points_tree_only_and_sun_down():
    res = 0.5
    zb = np.zeros((200, 200), np.float32)
    za = zb.copy()
    za[90:110, 90:110] = 15.0  # a tree south of the point, no building
    tr = from_origin(0.0, 100.0, res, res)
    bld, tree = beam_points(
        zb,
        za,
        tr,
        [50.0, 50.0],
        [70.0, 70.0],
        [1.0, 1.0],
        [180.0, 180.0],
        [30.0, -5.0],
        res,
        march_steps(res, 90.0),
        [0.0, 0.0],
    )
    assert tree[0] and not bld[0] and bld[1]  # night counts as no beam


def test_facet_view_matches_svf_for_a_horizontal_facet():
    h = np.zeros((3, 360), np.float32)
    h[1] = 20.0
    h[2, 90:270] = 45.0
    W = facet_sky_weights(np.array([0.0, 0.0, 1.0]))
    assert np.allclose(facet_view(h, W), sky_view_factor(h), atol=0.005)
    assert facet_view(h[:1], W)[0] == pytest.approx(1.0)


def test_vertical_facet_ignores_obstacles_behind_it():
    h = np.zeros((1, 360), np.float32)
    h[0, 135:225] = 60.0  # wall to the south
    W_north = facet_sky_weights(np.array([0.0, 1.0, 0.0]))  # vertical, facing north
    W_south = facet_sky_weights(np.array([0.0, -1.0, 0.0]))
    assert facet_view(h, W_north)[0] == pytest.approx(1.0) and facet_view(h, W_south)[0] < 0.5


def test_canopy_mask_blocks_overhead_not_low_sky():
    spec = importlib.util.spec_from_file_location(
        "e4run", ROOT / "experiments" / "e4_parking" / "run.py"
    )
    e4 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(e4)
    pc5 = {"canopy_height_m": 4.0, "canopy_across_m": 3.0, "canopy_along_m": 6.0}
    m = e4.canopy_mask(np.array([[0.0, 0.0, 1.8]]), 0.0, 0.0, 0.0, 0.0, pc5)
    assert m[0, :, -1].all()  # straight up: under the roof
    assert not m[0, :, :20].any()  # below 10 deg elevation: open
    # along the car (north) the roof reaches 3 m, across (east) only 1.5 m
    el_n = np.argmax(m[0, 0]) * 0.5
    el_e = np.argmax(m[0, 90]) * 0.5
    assert el_n < el_e


# ---------------------------------------------------------------- frozen routes
MAN = ROOT / "routes" / "v1" / "MANIFEST.json"


def test_frozen_routes_match_their_manifest():
    if not MAN.exists():
        pytest.skip("routes/v1 not frozen yet (snakemake -c1 routes_select)")
    man = json.loads(MAN.read_text())
    for name, digest in man["files"].items():
        assert hashlib.sha256((MAN.parent / name).read_bytes()).hexdigest() == digest, name
    sel = man["selection"]
    assert {sel[k]["orientation"] for k in sel} == {"N-S", "E-W"}
    assert sel["R-OPEN"]["svf_mean"] > sel["R-MIXED"]["svf_mean"] > sel["R-DENSE"]["svf_mean"]


def test_e4_solweig_gate():
    p = ROOT / "results" / "e4" / "summary_e4.json"
    if not p.exists():
        pytest.skip("results/e4 not built (snakemake -c1 e4_parking)")
    s = json.loads(p.read_text())
    assert s["pass"] and s["solweig_min_agreement"] >= 0.95
