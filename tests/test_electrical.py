"""P7 / E6: bishop88 cell, substring and module model; mismatch factor and its fit."""

import json
from pathlib import Path

import numpy as np
import pvlib
import pytest

from solaris.pv import electrical as el
from solaris.vehicle import facets, samples, vehicle_config

CFG = vehicle_config()
EC = el.electrical_config()
SUMMARY = Path(__file__).resolve().parents[1] / "results" / "e6" / "summary_e6.json"


def test_substrings_are_contiguous_and_near_equal():
    sub = el.substring_index(77, 3)
    assert sub.tolist() == sorted(sub.tolist())
    n = np.bincount(sub)
    assert n.sum() == 77 and n.max() - n.min() <= 1 and len(n) == 3


def test_cell_area_matches_the_samples():
    s = samples(facets(CFG), CFG["sample_spacing_m"])
    for f in facets(CFG):
        g = s[s.facet_id == f.id]
        assert el.cell_area(f, CFG) == pytest.approx(g.area_m2.iloc[0])


def test_uniform_light_reproduces_the_averaged_model():
    """Series cells under one irradiance: module MPP = n_cells x cell MPP (bishop88_mpp)."""
    n = 28
    counts = np.zeros((1, 3, 3))
    counts[0, :, 0] = np.bincount(el.substring_index(n, 3))
    for G, T in ((1000.0, 25.0), (300.0, 55.0), (60.0, 15.0)):
        p = el.module_mpp(np.array([[G, 0.0, 0.0]]), counts, np.array([T]), 0.057, EC)[0]
        cell = el.cell_params(np.array([G]), np.array([T]), 0.057, EC)
        ref = pvlib.singlediode.bishop88_mpp(*cell)[2][0] * n
        assert p == pytest.approx(ref, rel=1e-4)


def test_mismatch_is_one_under_uniform_light_for_every_facet():
    for f in facets(CFG):
        k = len(samples([f], CFG["sample_spacing_m"]))
        a = el.cell_area(f, CFG)
        for G in (50.0, 400.0, 1000.0):
            for T in (10.0, 40.0, 70.0):
                vb = np.ones((1, k))
                f_mm = el.mismatch(vb, np.array([G]), np.array([0.0]), np.array([T]), a, EC)[0]
                assert abs(f_mm - 1) <= 1e-3


def test_one_dark_cell_bypasses_its_substring():
    """A fully dark cell sends its substring through the bypass diode: about 2/3 power left."""
    k = 30
    vb = np.ones((1, k))
    vb[0, 3] = 0.0
    beam, diffuse = np.array([1000.0]), np.array([0.0])
    p_mixed, p_lit = el.mismatch_powers(vb, beam, diffuse, np.array([25.0]), 0.057, EC)
    full = el.mismatch_powers(np.ones((1, k)), beam, diffuse, np.array([25.0]), 0.057, EC)[0]
    assert p_mixed[0] / full[0] == pytest.approx(2 / 3, abs=0.03)
    assert p_mixed[0] < p_lit[0]  # the averaged model would lose only 1/30


def test_mismatch_never_exceeds_one():
    rng = np.random.default_rng(0)
    k = 48
    vb = rng.choice([0.0, 0.03, 1.0], size=(40, k))
    beam = rng.uniform(100, 900, 40)
    dif = rng.uniform(30, 200, 40)
    T = rng.uniform(10, 60, 40)
    f = el.mismatch(vb, beam, dif, T, 0.052, EC)
    assert np.all(f <= 1 + 1e-9) and np.all(f > 0)


def test_fit_form_is_one_at_both_ends_and_recovers_its_coefficients():
    s = np.linspace(0, 1, 101)
    y = el.fmm(s, 1.4, 0.45, 0.6)
    assert y[0] == 1 and y[-1] == 1 and y[50] < 1
    assert y[3] < 0.75  # steep shoulder: a few percent shaded already costs a quarter
    p, r2 = el.fit_fmm(s, y, np.ones_like(s))
    assert (p["k"], p["alpha"], p["beta"]) == pytest.approx((1.4, 0.45, 0.6), rel=1e-4)
    assert r2 == pytest.approx(1)


def test_e6_gate():
    if not SUMMARY.exists():
        pytest.skip("results/e6/summary_e6.json not built (snakemake -c1 e6_mismatch)")
    s = json.loads(SUMMARY.read_text())
    assert s["uniform_gate"]["pass"] and s["uniform_gate"]["max_abs_dev"] <= 1e-3
