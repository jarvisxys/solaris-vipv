"""P8 / E8: Python-Unity exchange and agreement metrics (synthetic data, no Unity)."""

import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from solaris.twin_io import agreement as ag
from solaris.twin_io import export as ex

RESULTS = Path(__file__).resolve().parents[1] / "results" / "e8"


def test_enu_origin_maps_to_zero_and_heading_is_true():
    o = ex.origin()
    tf = ex.enu()
    e, n, u = ex.to_enu(tf, [o["E_m"]], [o["N_m"]], [o["H_navd88_m"]])
    assert abs(e[0]) < 0.01 and abs(n[0]) < 0.01 and abs(u[0]) < 0.01
    # grid bearings differ from true bearings by the meridian convergence (< 1 deg here)
    h = ex.enu_heading(tf, [o["E_m"]], [o["N_m"]], [o["H_navd88_m"]], [0.0, 90.0])
    assert abs(((h[0] + 180) % 360) - 180) < 1.0 and abs(h[1] - 90) < 1.0
    assert (h[1] - h[0]) % 360 == pytest.approx(90, abs=0.01)


def test_trajectory_frame_schema():
    f = pd.DataFrame(
        {
            "x_utm": [400179.648, 400189.648],
            "y_utm": [3701514.105, 3701514.105],
            "z_road": [331.663, 331.663],
            "angle": [90.0, 90.0],
            "speed": [10.0, 10.0],
            "covered": [False, True],
            "time_local": ["2023-01-01 12:00:00", "2023-01-01 12:00:01"],
        }
    )
    meta = {"latitude": 33.45, "longitude": -112.06, "altitude": 340.0}
    t = ex.trajectory_frame(f, "2023-06-21", meta, ex.enu())
    assert list(t.columns) == ex.TRAJ_COLUMNS
    assert t["t_utc"].tolist() == ["2023-06-21T19:00:00Z", "2023-06-21T19:00:01Z"]  # MST = UTC-7
    assert t["x_e"].iloc[1] - t["x_e"].iloc[0] == pytest.approx(10, abs=0.02)
    assert t["covered"].tolist() == [0, 1] and (t["sun_el_deg"] > 70).all()


def test_body_frame_rotation_matches_unity():
    # Unity: local (x right, y up, z fwd) = (-y_body, z_body, x_body), yaw = heading about +Y.
    fwd = ag.body_to_enu(np.array([[1.0, 0, 0], [0, 1.0, 0]]), np.array([90.0]))[0]
    assert np.allclose(fwd[0], [1, 0, 0], atol=1e-12)  # heading east: forward = east
    assert np.allclose(fwd[1], [0, 1, 0], atol=1e-12)  # left = north


def test_states_and_validity():
    traj = pd.DataFrame(
        {"heading_deg": [0.0, 0.0], "sun_az_deg": [180.0, 180.0], "sun_el_deg": [45.0, -5.0]}
    )
    normals = np.array([[0, 0, 1.0], [1.0, 0, 0]])  # roof up; hood-like facing forward (north)
    v = ag.valid_mask(traj, normals)
    assert v.tolist() == [[True, False], [False, False]]
    s = ag.engine_state(
        np.array([[True, False]]), np.array([[True, True]]), np.array([[True, True]])
    )
    assert s.tolist() == [[ag.BUILDING, ag.TREE]]
    u = ag.unity_state(np.array([1, 0, 0, -1]), np.array([0, 1, 0, -1]))
    assert u.tolist() == [ag.BUILDING, ag.TREE, ag.LIT, ag.INVALID]


def test_compare_and_gates():
    rng = np.random.default_rng(0)
    a = rng.choice([ag.LIT, ag.TREE, ag.BUILDING], size=(100, 50))
    r = ag.compare(a, a.copy())
    assert r["agreement"] == 1 and r["lit_diff_pp"] == 0
    b = a.copy()
    b[:2] = np.where(b[:2] == ag.LIT, ag.BUILDING, ag.LIT)  # flip 2 % of the records
    r2 = ag.compare(a, b)
    assert r2["agreement"] == pytest.approx(0.98, abs=1e-9)
    s = ag.summarize([r, r2], "py", "unity")
    assert s["pass_agreement"] and s["sample_records"] == 10000
    b[b == ag.TREE] = ag.INVALID
    assert ag.compare(a, b)["valid_only_one"] == int((b == ag.INVALID).sum())


def test_read_visibility_roundtrip(tmp_path):
    p = tmp_path / "visibility_x.csv.gz"
    with gzip.open(p, "wt", encoding="utf-8", newline="\n") as fh:
        fh.write("t_utc,facet_id,sample_id,beam_building_hit,beam_tree_hit\n")
        for t in ("2023-06-21T19:00:00Z", "2023-06-21T19:00:01Z"):
            for k in range(3):
                fh.write(f"{t},roof,{k},{int(k == 0)},{int(k == 1)}\n")
    t, bld, tree, sid, fid = ag.read_visibility(p, 3)
    assert list(t) == ["2023-06-21T19:00:00Z", "2023-06-21T19:00:01Z"] and sid.tolist() == [0, 1, 2]
    assert ag.unity_state(bld, tree)[0].tolist() == [ag.BUILDING, ag.TREE, ag.LIT]


def test_clusters_rank_by_count():
    x = np.r_[np.full(10, 100.0), np.full(3, 500.0)]
    c = ag.clusters(x, np.zeros(13), np.array(["lit->building"] * 13), np.full(13, 30.0))
    assert c["n"].tolist() == [10, 3] and c["dominant"].iloc[0] == "lit->building"


def test_mesh_probe_on_a_box():
    trimesh = pytest.importorskip("trimesh")
    wall = trimesh.creation.box(extents=(2, 2, 20))
    wall.apply_translation([0, 10, 10])  # 2 m thick wall 10 m north, 20 m tall
    probe = ag.MeshProbe([wall], [])
    traj = pd.DataFrame(
        {
            "x_e": [0.0, 0.0],
            "y_n": [0.0, 0.0],
            "z_u": [0.0, 0.0],
            "heading_deg": [0.0, 0.0],
            "sun_az_deg": [0.0, 180.0],
            "sun_el_deg": [30.0, 30.0],
            "covered": [0, 0],
        }
    )
    st = probe.states(traj, np.array([[0, 0, 1.8]]), np.array([[0, 0, 1.0]]))
    assert st[:, 0].tolist() == [ag.BUILDING, ag.LIT]


def test_e8_unity_gates():
    p = RESULTS / "summary_e8_unity.json"
    if not p.exists():
        pytest.skip("results/e8/summary_e8_unity.json not built (snakemake -c1 e8_twin_agreement)")
    s = json.loads(p.read_text())
    assert s["ground_control"]["pass"]
    assert "python_raster_vs_unity" in s and "embree_vs_unity" in s
