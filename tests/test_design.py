"""P9 / E7: shading-aware design inversion (extended Eq. (2)) and the E7 results."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from solaris import core, design
from solaris.trajectory import schedules as sch

RESULTS = Path(__file__).resolve().parents[1] / "results" / "e7"


@pytest.fixture(scope="module")
def climate():
    return core.hourly_climate(33.4, 6.3, 24, 12)


@pytest.mark.parametrize("km,city", [(50, True), (100, False), (20, True)])
def test_unit_factors_reduce_to_the_conference_inversion(climate, km, city):
    a = design.required_area(km, city, climate)
    b = core.required_pv_area(km, city, "Phoenix", climate=climate)
    assert a == pytest.approx(b, rel=1e-12)


def test_factors_and_kappa_divide_the_area(climate):
    a0 = design.required_area(50, True, climate)
    f = {"F_geo": 0.8, "F_sh": 0.7, "F_mm": 0.95}
    a1 = design.required_area(50, True, climate, kappa=0.6, **f)
    assert a1 == pytest.approx(a0 * 0.8 / 0.6 / (0.8 * 0.7 * 0.95), rel=1e-12)


def test_archetype_trip_hours_enter_the_aux_load(climate):
    p = sch.archetype_params("A4")
    a = design.required_area(100, False, climate, p=p)
    assert a == pytest.approx(core.required_pv_area(100, False, "Phoenix", climate, p), rel=1e-12)


@pytest.mark.parametrize("A", [8.0, 11.6, 30.0])
def test_max_distance_inverts_required_area(climate, A):
    f = {"F_geo": 0.8, "F_sh": 0.7, "F_mm": 0.95}
    d = design.max_distance(A, True, climate, **f)
    assert d > 0
    assert design.required_area(d, True, climate, **f) == pytest.approx(A, rel=1e-9)


def test_max_distance_is_zero_below_the_parked_load(climate):
    a_aux = design.required_area(0.0, True, climate)
    assert design.max_distance(0.5 * a_aux, True, climate) == 0.0


def test_loss_factors():
    f = design.loss_factors({"chain": 100.0, "facets": 80.0, "trees": 60.0, "mismatch": 57.0})
    assert f == pytest.approx({"F_geo": 0.8, "F_sh": 0.75, "F_mm": 0.95})


def test_allocation_scales_area_proportionally():
    per = {"roof": np.full(8760, 2.0), "hood": np.full(8760, 1.0), "side": np.full(8760, 5.0)}
    areas = {"roof": 4.4, "hood": 1.6, "side": 2.5}
    s = design.allocation_series(per, ["roof", "hood"], areas, 12.0)
    assert np.allclose(s, (2.0 + 1.0) * 12.0 / 6.0)
    assert np.allclose(design.allocation_series(per, ["roof"], areas, 4.4), 2.0)


def test_design_mass_is_anchored_on_the_audited_vehicle():
    p = core.BASE
    assert design.design_mass(p.A_skin, p) == core.vehicle_mass("P0", p)
    assert design.design_mass(p.A_skin + 2.0, p) - design.design_mass(p.A_skin, p) == 7.0


# ---------------------------------------------------------------- E7 results
def _summary():
    path = RESULTS / "summary_e7.json"
    if not path.exists():
        pytest.skip("results/e7/summary_e7.json not built (snakemake -c1 e7_inversion)")
    return json.loads(path.read_text(encoding="utf-8"))


def test_e7_facets_reproduce_e5():
    s = _summary()
    assert s["facet_sum_vs_e5"]["pass"]
    assert s["facet_sum_vs_e5"]["max_rel_annual"] <= 1e-5  # table_e5.csv has 6 digits


def test_e7_closed_form_within_gate():
    s = _summary()
    assert s["closed_form_check"]["pass"]
    t = pd.read_csv(RESULTS / "table_e7_inversion.csv")
    assert (t["rel_err"].abs() <= s["closed_form_check"]["tol"]).all()


def test_e7_base_case_is_the_e5_archetype():
    _summary()
    sweep = pd.read_csv(RESULTS / "table_e7_sweep.csv")
    e5 = pd.read_csv(RESULTS.parent / "e5" / "table_e5.csv")
    e5 = e5[(e5.weather == "tmy") & (e5.step == "mismatch")].set_index("archetype")
    base = sweep[
        (sweep.allocation == "full_skin") & (sweep.A_m2 == 11.6) & (sweep.kappa == 0.8)
    ].set_index("archetype")
    for a, row in base.iterrows():
        assert row.fss == pytest.approx(e5.loc[a, "fss"], rel=1e-5)
