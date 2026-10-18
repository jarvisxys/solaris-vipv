"""P7 / E5: hourly aggregation into the 8760-h SoC loop and the energy-balance checks."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from solaris import annual, core

RESULTS = Path(__file__).resolve().parents[1] / "results"


def test_bin_hourly_conserves_energy():
    rng = np.random.default_rng(1)
    t = rng.integers(0, 8760 * 3600, 100_000)
    e = rng.uniform(0, 1e-3, t.size)
    h = annual.bin_hourly(t, e)
    assert h.shape == (8760,)
    assert h.sum() == pytest.approx(e.sum(), rel=1e-12)
    assert h[t[0] // 3600] >= e[0]


def test_bin_hourly_rejects_samples_outside_the_year():
    with pytest.raises(ValueError):
        annual.bin_hourly(np.array([0, 8760 * 3600]), np.array([1.0, 1.0]))


def test_closure_check():
    annual.assert_closure(100.0, 100.05, "pv")
    with pytest.raises(AssertionError):
        annual.assert_closure(100.0, 100.2, "pv")


def test_time_closure():
    drive = np.zeros(8760)
    drive[8::24] = 3000
    annual.assert_time_closure(drive, 3600 - drive)
    with pytest.raises(AssertionError):
        annual.assert_time_closure(drive, np.full(8760, 3600.0))


@pytest.mark.parametrize("km,city", [(50, True), (100, False)])
def test_pack_balance_closes_in_the_soc_loop(km, city):
    ghi, T = core.hourly_climate(33.4, 6.3, 24, 12)
    r = core.simulate("Phoenix", km, city, climate=(ghi, T))
    assert abs(annual.pack_balance(r)) < 1e-9
    r2 = core.simulate("Phoenix", km, city, climate=(ghi, T), pv_kwh=np.full(8760, 0.5))
    assert abs(annual.pack_balance(r2)) < 1e-9


def test_e5_closes_and_starts_at_b0():
    s_path = RESULTS / "e5" / "summary_e5.json"
    if not s_path.exists():
        pytest.skip("results/e5/summary_e5.json not built (snakemake -c1 e5_annual)")
    s = json.loads(s_path.read_text())
    assert s["energy_balance"]["pass"] and s["energy_balance"]["max_rel"] <= 1e-3
    t = pd.read_csv(RESULTS / "e5" / "table_e5.csv")
    t = t[t.weather == "tmy"]
    b0 = pd.read_csv(RESULTS / "e0" / "table_b0.csv").set_index(["scenario", "metric"])
    sched = {"A1": "II", "A2": "II", "A3": "II", "A4": "I"}
    for arch, sc in sched.items():
        row = t[(t.archetype == arch) & (t.step == "B0")].iloc[0]
        ref = b0.loc[sc, "measured_b0"]
        assert row.fss == pytest.approx(float(ref["fss"]), rel=1e-5)
        assert row.grid_kWh == pytest.approx(float(ref["grid_kWh"]), rel=1e-5)
    assert (t["energy_closure_rel"] <= 1e-3).all() and (t["pack_balance_rel"] <= 1e-3).all()
