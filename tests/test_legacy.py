"""P0: the conference code is byte-identical and configs/base.yaml mirrors it."""

import inspect
from pathlib import Path

import pytest
import yaml

from solaris import integrity

ROOT = Path(__file__).resolve().parents[1]
# SHA-256 of the conference solaris.py v1.1.0 (git blob, LF), recorded 2026-10-29
# (PAPER_CHANGELOG.md). v1.0 (7b30b213...96d5) is at tag v1.0.0-conference.
CONFERENCE_SHA256 = "2603b4b6a2786fbab62f2431873f0498f0ce907c44f55a3aa640510b61807142"
LEGACY_FILE = "solaris_v110.py"


@pytest.fixture(scope="module")
def v1():
    from solaris.core.conference import legacy_module

    return legacy_module()


@pytest.fixture(scope="module")
def base():
    return yaml.safe_load((ROOT / "configs" / "base.yaml").read_text(encoding="utf-8"))


def defaults(func):
    return {
        k: p.default
        for k, p in inspect.signature(func).parameters.items()
        if p.default is not inspect.Parameter.empty
    }


def test_recorded_hash_is_conference_hash():
    assert integrity.recorded_hashes() == {LEGACY_FILE: CONFERENCE_SHA256}


def test_legacy_is_byte_identical():
    assert integrity.verify_legacy() == []


def test_guard_detects_a_one_byte_change(tmp_path, monkeypatch):
    raw = (integrity.LEGACY_DIR / LEGACY_FILE).read_bytes()
    (tmp_path / LEGACY_FILE).write_bytes(raw + b"\n")
    (tmp_path / "SHA256SUMS").write_text(f"{CONFERENCE_SHA256}  {LEGACY_FILE}\n")
    monkeypatch.setattr(integrity, "LEGACY_DIR", tmp_path)
    monkeypatch.setattr(integrity, "SUMS_FILE", tmp_path / "SHA256SUMS")
    assert len(integrity.verify_legacy()) == 1


def test_legacy_has_no_crlf():
    raw = (integrity.LEGACY_DIR / LEGACY_FILE).read_bytes()
    assert b"\r" not in raw


def test_legacy_public_api_imports(v1):
    for name in (
        "simulate",
        "load_tmy",
        "required_pv_area",
        "max_selfsuff_km",
        "economics",
        "pareto",
        "tmy_validation",
        "real_data_validation",
        "load_city_tmy",
        "tmy_robustness",
        "gap_decomposition",
        "design_levers_tmy",
    ):
        assert callable(getattr(v1, name)), name


def test_base_physics_and_pv(v1, base):
    ph, pv = base["physics"], base["pv"]
    assert (ph["g"], ph["rho_air"]) == (v1.g, v1.rho)
    assert (ph["Cd"], ph["Af"], ph["Cr"]) == (v1.Cd, v1.Af, v1.Cr)
    assert ph["eta_dt"] == v1.eta_dt
    assert ph["eta_regen_base"] == v1.ETA_REGEN_BASE
    assert ph["P_susp_W"] == v1.P_SUSP
    assert (pv["A_skin_m2"], pv["eta_pv"], pv["beta_per_K"]) == (v1.A_skin, v1.eta_pv, v1.beta)
    assert pv["kappa_pv_base"] == v1.KAPPA_PV_BASE


def test_base_pack_and_mass(v1, base):
    pk = base["pack"]
    assert pk["E_pack_kWh"] == v1.E_PACK
    assert pk["pack_mass_kg"] == v1.PACK
    assert pk["capacity_kWh"] == v1.CAP
    # order matters: legacy treats the first MASS entry as the glider
    assert list(base["mass_kg"].items()) == list(v1.MASS.items())


def test_base_teg(v1, base):
    assert base["teg"] == defaults(v1.teg_daily_kwh)


def test_base_wltc(v1, base):
    w = base["wltc"]
    for phase, stats in v1.WLTC.items():
        p = w[phase]
        assert (p["distance_km"], p["duration_s"], p["vmax_kmh"], p["n_microtrips"]) == stats
    assert w["build_phase"] == defaults(v1.build_phase)


def test_base_climate_sites(v1, base):
    for city, (lat, psh, tm, ta) in v1.LOCS.items():
        assert base["synthetic_climate"][city] == {
            "lat": lat,
            "psh": psh,
            "T_mean": tm,
            "T_amp": ta,
        }
    for city, row in v1.GSA.items():
        assert tuple(base["global_solar_atlas"][city].values()) == row
    # legacy_module() points v1.1.0's data/ tree at data/conference/
    assert {c: str(ROOT / f) for c, f in base["tmy_files"].items()} == v1.TMY_FILES
    assert {y: str(ROOT / f) for y, f in base["tmy_releases"].items()} == v1.TMY_RELEASES
    assert base["utc_offset_h"] == v1.UTC_OFFSET


def test_base_park_load_and_simulate(v1, base):
    pl = {k: v for k, v in base["park_load"].items() if k != "P_min_W"}
    assert pl == defaults(v1.park_load)
    d = defaults(v1.simulate)
    for key in ("variant", "floor", "recharge_to", "seed", "pv_scale", "warmup"):
        assert base["simulate"][key] == d[key], key
    assert d["kappa"] == base["pv"]["kappa_pv_base"]
    assert d["eta_regen"] == base["physics"]["eta_regen_base"]


def test_base_economics(v1, base):
    from solaris.core.params import prices_usd

    ec = base["economics"]
    assert (ec["fx_inr_per_usd"], ec["fx_usd_per_gbp"]) == (v1.FX_INR_PER_USD, v1.FX_USD_PER_GBP)
    assert prices_usd(ec) == v1.PRICE
    assert list(ec["cost_items_usd"].items()) == list(v1.COST_ITEMS.items())
    pa = defaults(v1.pareto)
    assert tuple(base["pareto"]["areas_m2"]) == pa["areas"]
    assert tuple(base["pareto"]["capacities_kWh"]) == pa["caps"]
