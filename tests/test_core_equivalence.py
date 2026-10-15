"""P1/E0: the refactored solaris.core reproduces the legacy module within 1e-9."""

import contextlib
from pathlib import Path

import numpy as np
import pytest

from solaris import core
from solaris.core.conference import REPO_ROOT, input_path
from solaris.legacy import solaris_v1 as legacy

TOL = 1e-9
FIXTURES = Path(__file__).parent / "fixtures"
LOCS = ("Phoenix", "Lucknow", "London")


def assert_same(a, b, where="value"):
    """Recursive equality: numbers and arrays within TOL, everything else exact."""
    if isinstance(a, dict):
        assert isinstance(b, dict) and set(a) <= set(b), f"{where}: keys {set(a) - set(b)}"
        for k in a:
            assert_same(a[k], b[k], f"{where}[{k!r}]")
    elif isinstance(a, list | tuple):
        assert len(a) == len(b), f"{where}: length {len(a)} != {len(b)}"
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            assert_same(x, y, f"{where}[{i}]")
    elif isinstance(a, str | bool | np.bool_) or a is None:
        assert a == b, f"{where}: {a!r} != {b!r}"
    else:
        np.testing.assert_allclose(b, a, rtol=0, atol=TOL, err_msg=where)


def tmy_phoenix():
    path = input_path("tmy_phoenix")
    if not path.exists():
        pytest.skip("Phoenix TMY not supplied")
    return legacy.load_tmy(str(path))


def test_conference_values_identical(values_legacy, values_core):
    assert set(values_legacy) == set(values_core)
    assert_same(values_legacy, values_core)


def test_constants():
    assert core.HARVEST_HW == legacy.HARVEST_HW
    assert core.M == legacy.M
    assert core.E_TEG == legacy.E_TEG
    assert_same(legacy.TEG, core.TEG)
    assert (core.SYSTEM_COST, core.PV_ONLY_COST) == (legacy.SYSTEM_COST, legacy.PV_ONLY_COST)


@pytest.mark.parametrize("loc", LOCS)
@pytest.mark.parametrize("seed", [0, 1, 2, 3])
def test_synthetic_climate(loc, seed):
    args = legacy.LOCS[loc]
    assert_same(legacy.hourly_climate(*args, seed=seed), core.hourly_climate(*args, seed=seed))


def test_drive_cycle():
    for keys in (tuple(legacy.WLTC), ("Low", "Medium")):
        assert_same(legacy.wltp_trace(keys), core.wltp_trace(keys))
    for variant in ("P0", "PA", "PB"):
        for city in (True, False):
            for eta in (0.60, 0.65, 0.72):
                assert_same(legacy.whkm(variant, city, eta), core.whkm(variant, city, eta))
    assert_same(legacy.wltp_recon_error(), core.wltp_recon_error())


SIM_CASES = [
    dict(loc=loc, daily_km=km, city=city) for loc in LOCS for km, city in ((50, True), (100, False))
] + [
    dict(loc="Phoenix", daily_km=50, city=True, kappa=0.60),
    dict(loc="Phoenix", daily_km=50, city=True, eta_regen=0.72),
    dict(loc="Phoenix", daily_km=50, city=True, pv_scale=0.0),
    dict(loc="Phoenix", daily_km=50, city=True, A_over=15, cap_over=150, seed=2),
    dict(loc="London", daily_km=100, city=False, variant="PA", floor=0.2, recharge_to=0.9),
    dict(loc="Lucknow", daily_km=30, city=True, variant="PB"),
]


@pytest.mark.parametrize("case", SIM_CASES, ids=lambda c: "-".join(map(str, c.values())))
def test_simulate_synthetic(case):
    assert_same(legacy.simulate(**case), core.simulate(**case))


@pytest.mark.parametrize("km,city", [(50, True), (100, False)])
def test_simulate_measured(km, city):
    climate = tmy_phoenix()
    assert_same(
        legacy.load_tmy(str(input_path("tmy_phoenix"))), core.load_tmy(input_path("tmy_phoenix"))
    )
    for kw in ({}, {"kappa": 0.6}, {"pv_scale": 0.0}, {"A_over": 15, "cap_over": 150}):
        assert_same(
            legacy.simulate("Phoenix", km, city, climate=climate, **kw),
            core.simulate("Phoenix", km, city, climate=climate, **kw),
        )


def test_inversion_and_economics():
    for loc in LOCS:
        for km, city in ((50, True), (100, False)):
            assert_same(
                legacy.required_pv_area(km, city, loc), core.required_pv_area(km, city, loc)
            )
            assert_same(legacy.max_selfsuff_km(loc, city), core.max_selfsuff_km(loc, city))
            assert_same(legacy.economics(loc, km, city), core.economics(loc, km, city))
        assert_same(legacy.engine_fT(loc), core.engine_fT(loc))
        assert_same(legacy.engine_Eaux(loc, True, 50), core.engine_Eaux(loc, True, 50))


def test_pareto():
    assert_same(legacy.pareto(), core.pareto())


def test_validation_functions():
    assert_same(legacy.validate(), core.validate())
    assert_same(legacy.real_data_validation(), core.real_data_validation())
    assert_same(legacy.regen_susp_sensitivity(), core.regen_susp_sensitivity())
    assert_same(legacy.teg_tradeoff(), core.teg_tradeoff())
    for f in np.linspace(0.0, 1.2, 25):
        assert legacy.classify(f) == core.classify(f)
    with contextlib.chdir(REPO_ROOT):  # legacy TMY paths are relative to the repo root
        assert_same(legacy.tmy_validation(), core.tmy_validation())
        for loc in LOCS:
            assert_same(legacy.climate_error(loc), core.climate_error(loc))


@pytest.mark.parametrize("case", SIM_CASES, ids=lambda c: "-".join(map(str, c.values())))
def test_simulate_energy_balance_closes(case):
    r = core.simulate(**case)
    stored = r["soc_end_kwh"] - r["soc_start_kwh"]
    assert stored == pytest.approx(r["harvest_used_kwh"] + r["grid_kwh"] - r["ann_dem"], abs=1e-6)
    assert 0.0 <= r["curtailed_kwh"] <= r["ann_harv"]


def test_core_keeps_no_hidden_state():
    before = core.simulate("Phoenix", 50, True)
    core.validate()
    core.regen_susp_sensitivity()
    core.real_data_validation()
    assert_same(before, core.simulate("Phoenix", 50, True))


def test_load_tmy_rejects_utc_timestamps():
    with pytest.raises(ValueError, match="UTC"):
        core.load_tmy(FIXTURES / "nsrdb_tmy_utc.csv")


def test_load_tmy_reads_local_fixture():
    ghi, temp = core.load_tmy(FIXTURES / "nsrdb_tmy_local.csv")
    assert ghi.shape == temp.shape == (8760,)
    assert ghi.max() == 650.0 and temp.min() == 9.5
