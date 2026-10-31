"""P1/E0: the refactored solaris.core reproduces the conference toolkit v1.1.0 within 1e-9."""

from pathlib import Path

import numpy as np
import pytest

from solaris import core
from solaris.core.conference import input_path, inputs_present

TOL = 1e-9
FIXTURES = Path(__file__).parent / "fixtures"
LOCS = ("Phoenix", "Lucknow", "London")
needs_tmy = pytest.mark.skipif(not inputs_present(), reason="conference TMY files not supplied")


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


def test_conference_values_identical(values_legacy, values_core):
    assert set(values_legacy) == set(values_core)
    assert_same(values_legacy, values_core)


def test_constants(legacy):
    assert core.HARVEST_HW == legacy.HARVEST_HW
    assert core.M == legacy.M
    assert core.E_TEG == legacy.E_TEG
    assert_same(legacy.TEG, core.TEG)
    assert (core.SYSTEM_COST, core.PV_ONLY_COST) == (legacy.SYSTEM_COST, legacy.PV_ONLY_COST)
    assert core.PRICE == legacy.PRICE
    assert core.GSA == legacy.GSA and core.MASS == legacy.MASS


@pytest.mark.parametrize("loc", LOCS)
@pytest.mark.parametrize("seed", [0, 1, 2, 3])
def test_synthetic_climate(legacy, loc, seed):
    args = legacy.LOCS[loc]
    assert_same(legacy.hourly_climate(*args, seed=seed), core.hourly_climate(*args, seed=seed))


def test_drive_cycle(legacy):
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
    dict(loc="Phoenix", daily_km=50, city=True, A_over=15, cap_over=150, m_over=2293.5),
    dict(loc="Phoenix", daily_km=50, city=True, warmup=False),
    dict(loc="London", daily_km=100, city=False, variant="PA", floor=0.2, recharge_to=0.9),
    dict(loc="Lucknow", daily_km=30, city=True, variant="PB"),
]


@pytest.mark.parametrize("case", SIM_CASES, ids=lambda c: "-".join(map(str, c.values())))
def test_simulate_synthetic(legacy, case):
    assert_same(legacy.simulate(**case), core.simulate(**case))


@needs_tmy
@pytest.mark.parametrize("loc", LOCS)
@pytest.mark.parametrize("km,city", [(50, True), (100, False)])
def test_simulate_tmy(legacy, loc, km, city):
    climate = legacy.load_city_tmy(loc)
    assert_same(climate, core.load_city_tmy(loc))
    for kw in (
        {},
        {"kappa": 0.6},
        {"pv_scale": 0.0},
        {"A_over": 15, "cap_over": 150, "m_over": 2293.5},
        {"warmup": False},
    ):
        assert_same(
            legacy.simulate(loc, km, city, climate=climate, **kw),
            core.simulate(loc, km, city, climate=climate, **kw),
        )


def test_inversion_and_economics_synthetic(legacy):
    for loc in LOCS:
        for km, city in ((50, True), (100, False)):
            assert_same(
                legacy.required_pv_area(km, city, loc), core.required_pv_area(km, city, loc)
            )
            assert_same(legacy.max_selfsuff_km(loc, city), core.max_selfsuff_km(loc, city))
            assert_same(
                legacy.max_selfsuff_km(loc, city, A=20), core.max_selfsuff_km(loc, city, A=20)
            )
            assert_same(legacy.economics(loc, km, city), core.economics(loc, km, city))
        assert_same(legacy.engine_fT(loc), core.engine_fT(loc))
        assert_same(legacy.engine_Eaux(loc, True, 50), core.engine_Eaux(loc, True, 50))


@needs_tmy
def test_inversion_and_economics_tmy(legacy):
    for loc in LOCS:
        t = legacy.load_city_tmy(loc)
        for km, city in ((50, True), (100, False)):
            assert_same(
                legacy.required_pv_area(km, city, loc, climate=t),
                core.required_pv_area(km, city, loc, climate=t),
            )
            assert_same(
                legacy.max_selfsuff_km(loc, city, climate=t),
                core.max_selfsuff_km(loc, city, climate=t),
            )
            assert_same(
                legacy.economics(loc, km, city, climate=t), core.economics(loc, km, city, climate=t)
            )
        assert_same(legacy.engine_fT(loc, t), core.engine_fT(loc, t))
        assert_same(legacy.engine_Eaux(loc, True, 50, t), core.engine_Eaux(loc, True, 50, t))


def test_pareto_synthetic(legacy):
    assert_same(legacy.pareto(), core.pareto())


@needs_tmy
def test_pareto_tmy(legacy):
    t = legacy.load_city_tmy("Phoenix")
    assert_same(legacy.pareto(climate=t), core.pareto(climate=t))


def test_validation_functions(legacy):
    assert_same(legacy.validate(), core.validate())
    assert_same(legacy.real_data_validation(), core.real_data_validation())
    assert_same(legacy.regen_susp_sensitivity(), core.regen_susp_sensitivity())
    assert_same(legacy.teg_tradeoff(), core.teg_tradeoff())
    for f in np.linspace(0.0, 1.2, 25):
        assert legacy.classify(f) == core.classify(f)


@needs_tmy
def test_tmy_functions(legacy):
    assert_same(legacy.tmy_validation(), core.tmy_validation())
    assert_same(legacy.tmy_robustness(), core.tmy_robustness())
    assert_same(legacy.gap_decomposition(), core.gap_decomposition())
    assert_same(legacy.design_levers_tmy(), core.design_levers_tmy())
    for loc in LOCS:
        assert_same(legacy.climate_error(loc), core.climate_error(loc))


@pytest.mark.parametrize("case", SIM_CASES, ids=lambda c: "-".join(map(str, c.values())))
def test_simulate_energy_balance_closes(case):
    r = core.simulate(**case)
    stored = r["soc_end_kwh"] - r["soc_start_kwh"]
    assert stored == pytest.approx(r["harvest_used_kwh"] + r["grid_kwh"] - r["ann_dem"], abs=1e-6)
    assert 0.0 <= r["curtailed_kwh"] <= r["ann_harv"]
    assert r["relief"] <= r["fss"] + 1e-12


def test_demand_uses_battery_side_consumption_once():
    """v1.0 divided the battery-side Wh/km by eta_dt a second time."""
    r = core.simulate("Phoenix", 50, True, pv_scale=0.0)
    prop = 50 * 365 * core.whkm("P0", city=True) / 1000.0
    aux = 365 * core.engine_Eaux("Phoenix", True, 50)
    assert r["ann_dem"] == pytest.approx(prop + aux, rel=1e-12)


def test_periodic_year_starts_where_the_warmup_ends():
    a = core.simulate("Phoenix", 50, True, warmup=False)
    b = core.simulate("Phoenix", 50, True)
    assert b["soc_start_kwh"] == pytest.approx(a["soc_end_kwh"], abs=1e-9)
    assert a["soc_start_kwh"] == pytest.approx(0.9 * a["cap"])


def test_core_keeps_no_hidden_state():
    before = core.simulate("Phoenix", 50, True)
    core.validate()
    core.regen_susp_sensitivity()
    core.real_data_validation()
    assert_same(before, core.simulate("Phoenix", 50, True))


def test_load_tmy_rolls_utc_to_local():
    """The UTC fixture is the local fixture with Time Zone 0: rolled by Local Time Zone."""
    ghi_l, t_l = core.load_tmy(FIXTURES / "nsrdb_tmy_local.csv")
    ghi_u, t_u = core.load_tmy(FIXTURES / "nsrdb_tmy_utc.csv")
    assert np.array_equal(ghi_u, np.roll(ghi_l, -7)) and np.array_equal(t_u, np.roll(t_l, -7))
    ghi_o, _ = core.load_tmy(FIXTURES / "nsrdb_tmy_utc.csv", utc_offset=0.0)
    assert np.array_equal(ghi_o, ghi_l)


def test_load_tmy_reads_local_fixture():
    ghi, temp = core.load_tmy(FIXTURES / "nsrdb_tmy_local.csv")
    assert ghi.shape == temp.shape == (8760,)
    assert ghi.max() == 650.0 and temp.min() == 9.5


@needs_tmy
def test_local_time_e0_tmy_equals_the_conference_utc_file():
    """E0/P2 keep the local-time NSRDB download; it is the conference TMY-2023 after the roll."""
    a = core.load_tmy(input_path("tmy_phoenix"))
    b = core.load_city_tmy("Phoenix")
    assert np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1])
