"""P5 / E2: vehicle facets, samples, the facet PV model and the simulate(pv_kwh=) hook."""

import json
from pathlib import Path

import numpy as np
import pytest

from solaris import core
from solaris.pv.model import cell_temperature, pv_energy
from solaris.vehicle import facets, flat_skin, samples, vehicle_config

CFG = vehicle_config()
SKIN = facets(CFG)
SUMMARY = Path(__file__).resolve().parents[1] / "results" / "e2" / "summary_e2.json"


def test_placeholder_layout_totals_the_conference_area():
    assert {f.id for f in SKIN} == {"roof", "hood", "tailgate", "side_left", "side_right"}
    assert sum(f.area_m2 for f in SKIN) == pytest.approx(core.BASE.A_skin)
    for f in SKIN:
        assert f.across_m * f.slope_m == pytest.approx(f.area_m2)


def test_normals_and_compass_azimuth():
    by = {f.id: f for f in SKIN}
    assert np.allclose(by["side_left"].normal_body()[:2] / np.sin(np.radians(85)), [0, 1])
    assert np.allclose(by["side_right"].normal_body()[:2] / np.sin(np.radians(85)), [0, -1])
    assert by["tailgate"].normal_body()[0] < 0 < by["hood"].normal_body()[0]
    # heading east (90): the right side faces south, the left side north
    assert by["side_right"].compass_azimuth(90) == 180 and by["side_left"].compass_azimuth(90) == 0


def test_samples_cover_each_facet_in_its_plane():
    s = samples(SKIN, CFG["sample_spacing_m"])
    for f in SKIN:
        g = s[s.facet_id == f.id]
        assert g.area_m2.sum() == pytest.approx(f.area_m2)
        d = g[["x_body", "y_body", "z_body"]].to_numpy() - np.asarray(f.centre_m)
        assert np.allclose(d @ f.normal_body(), 0, atol=1e-9)  # samples lie on the facet
        assert len(g) >= f.area_m2 / CFG["sample_spacing_m"] ** 2 - 1e-9
    assert set(s.columns) >= {
        "facet_id",
        "sample_id",
        "x_body",
        "y_body",
        "z_body",
        "nx",
        "ny",
        "nz",
    }


def test_flat_skin_is_one_horizontal_facet():
    (f,) = flat_skin(11.6)
    assert f.tilt_deg == 0 and f.area_m2 == 11.6 and np.allclose(f.normal_body(), [0, 0, 1])


def test_simulate_pv_hook_is_bit_identical_to_the_conference_model():
    ghi, T = core.hourly_climate(33.4, 6.3, 24, 12)
    p = core.BASE
    pcell = T + p.cell_temp_rise * (ghi / 1000.0)  # same operation order as core.simulate
    pv = p.A_skin * p.eta_pv * (ghi / 1000.0) * p.kappa_pv * (1 + p.beta * (pcell - 25))
    a = core.simulate("Phoenix", 50, True, climate=(ghi, T))
    b = core.simulate("Phoenix", 50, True, climate=(ghi, T), pv_kwh=pv)
    for k in ("fss", "grid_kwh", "charges", "ann_harv", "curtailed_kwh"):
        assert a[k] == b[k]
    assert np.array_equal(a["soc"], b["soc"])


def test_conference_temperature_rule_reproduces_the_core_pv_formula():
    g = np.array([0.0, 300.0, 900.0])
    T = np.array([10.0, 25.0, 40.0])
    tc = cell_temperature(g, T, np.zeros(3), model="conference")
    p = core.BASE
    ref = 11.6 * p.eta_pv * g / 1000 * p.kappa_pv * (1 + p.beta * (T + 25 * g / 1000 - 25))
    assert np.allclose(pv_energy(11.6, g, tc), ref)


def test_vehicle_speed_cools_the_cells():
    g, T = np.array([900.0]), np.array([40.0])
    park = cell_temperature(g, T, np.array([2.0]))
    drive = cell_temperature(g, T, np.array([2.0 + 13.0]))
    assert drive[0] < park[0] - 10


def test_e2_gate():
    """2b (flat skin, new irradiance chain, conference T rule) equals 2a within 0.5 %."""
    if not SUMMARY.exists():
        pytest.skip("results/e2/summary_e2.json not built (snakemake -c1 e2_facets)")
    s = json.loads(SUMMARY.read_text())
    for sc in ("scenario_II", "scenario_I"):
        c = s[sc]["check_2b_vs_2a"]
        assert c["pass"] and abs(c["pv_rel"]) <= 0.005 and abs(c["fss_rel"]) <= 0.005
