"""Refactored conference engine: SoC loop, metrics, design inversion, economics (P1/E0).

Output-identical to src/solaris/legacy/solaris_v1.py within 1e-9
(tests/test_core_equivalence.py). Every function takes an optional ``p: Params``
(default: configs/base.yaml) instead of reading or mutating module globals.
"""

from .audit import e_teg as _e_teg
from .audit import harvest_hw_kg, teg_base, teg_daily_kwh, teg_tradeoff, vehicle_mass
from .climate import climate_error, gsa_site, hourly_climate, load_tmy, site_climate
from .drive_cycle import build_phase, consumption_wh_km, whkm, wltp_recon_error, wltp_trace
from .economics import economics, pareto, pv_only_cost, system_cost
from .inversion import engine_Eaux, engine_fT, max_selfsuff_km, required_pv_area
from .metrics import classify
from .params import BASE, REPO_ROOT, Params, Site
from .soc_loop import park_load, simulate
from .validation import real_data_validation, regen_susp_sensitivity, tmy_validation, validate

# Conference constants under their legacy names
HARVEST_HW = harvest_hw_kg()
M = {v: vehicle_mass(v) for v in ("P0", "PA", "PB")}
TEG = teg_base()
E_TEG = _e_teg()
SYSTEM_COST = system_cost()
PV_ONLY_COST = pv_only_cost()

__all__ = [
    "BASE",
    "E_TEG",
    "HARVEST_HW",
    "M",
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
    "economics",
    "engine_Eaux",
    "engine_fT",
    "gsa_site",
    "hourly_climate",
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
    "tmy_validation",
    "validate",
    "vehicle_mass",
    "whkm",
    "wltp_recon_error",
    "wltp_trace",
]
