"""Refactored conference engine: SoC loop, metrics, design inversion, economics.

Output-identical to the conference toolkit v1.1.0 (src/solaris/legacy/solaris_v110.py)
within 1e-9 (tests/test_core_equivalence.py). Every function takes an optional
``p: Params`` (default: configs/base.yaml) instead of reading or mutating module globals.
"""

from .audit import e_teg as _e_teg
from .audit import harvest_hw_kg, teg_base, teg_daily_kwh, teg_tradeoff, vehicle_mass
from .climate import (
    climate_error,
    gsa_site,
    hourly_climate,
    load_city_tmy,
    load_tmy,
    site_climate,
)
from .drive_cycle import build_phase, consumption_wh_km, whkm, wltp_recon_error, wltp_trace
from .economics import economics, pareto, pv_only_cost, system_cost
from .inversion import engine_Eaux, engine_fT, max_selfsuff_km, required_pv_area
from .metrics import classify
from .params import BASE, REPO_ROOT, Params, Site
from .soc_loop import park_load, simulate
from .validation import (
    design_levers_tmy,
    gap_decomposition,
    real_data_validation,
    regen_susp_sensitivity,
    tmy_robustness,
    tmy_validation,
    validate,
)

# Conference constants under their legacy names
HARVEST_HW = harvest_hw_kg()
M = {v: vehicle_mass(v) for v in ("P0", "PA", "PB")}
TEG = teg_base()
E_TEG = _e_teg()
SYSTEM_COST = system_cost()
PV_ONLY_COST = pv_only_cost()
PRICE = dict(BASE.price)
GSA = dict(BASE.gsa)
MASS = dict(BASE.mass)
COST_ITEMS = dict(BASE.cost_items)

__all__ = [
    "BASE",
    "COST_ITEMS",
    "E_TEG",
    "GSA",
    "HARVEST_HW",
    "M",
    "MASS",
    "PRICE",
    "PV_ONLY_COST",
    "REPO_ROOT",
    "SYSTEM_COST",
    "TEG",
    "Params",
    "Site",
    "build_phase",
    "classify",
    "climate_error",
    "consumption_wh_km",
    "design_levers_tmy",
    "economics",
    "engine_Eaux",
    "engine_fT",
    "gap_decomposition",
    "gsa_site",
    "hourly_climate",
    "load_city_tmy",
    "load_tmy",
    "max_selfsuff_km",
    "pareto",
    "park_load",
    "real_data_validation",
    "regen_susp_sensitivity",
    "required_pv_area",
    "simulate",
    "site_climate",
    "teg_daily_kwh",
    "teg_tradeoff",
    "tmy_robustness",
    "tmy_validation",
    "validate",
    "vehicle_mass",
    "whkm",
    "wltp_recon_error",
    "wltp_trace",
]
