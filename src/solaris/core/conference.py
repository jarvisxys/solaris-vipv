"""Every number printed in the final conference paper (SOLARIS__Final, toolkit v1.1.0),
computed by a given engine.

``conference_values(api)`` accepts either the frozen legacy module (``legacy_module()``)
or ``solaris.core``; both expose the same function names. The ids match ``expected`` in
configs/experiments/e0.yaml.
"""

import importlib
import inspect
import os
from pathlib import Path

import yaml

from .params import REPO_ROOT

E0_YAML = REPO_ROOT / "configs" / "experiments" / "e0.yaml"
# v1.1.0 reads data/<city>/... next to solaris.py; the files live in data/conference/ here.
LEGACY_DATA = REPO_ROOT / "data" / "conference"
LEGACY_MODULE = "solaris.legacy.solaris_v110"
LOCS = ("Phoenix", "Lucknow", "London")
SCENARIOS = {"II": (50, True), "I": (100, False)}
TABLE2_OTHER = (  # Table II folds these five mass items into one row
    "Thermal management (added pump/HX capacity)",
    "HV wiring / harness (distributed PV+TEG)",
    "Coolant + loops (TEG + pack)",
    "Added structure (roof/panel load paths)",
    "Encapsulation / protective coatings",
)


def e0_config() -> dict:
    return yaml.safe_load(E0_YAML.read_text(encoding="utf-8"))


def input_path(key: str) -> Path:
    return REPO_ROOT / e0_config()["inputs"][key]["path"]


def inputs_present() -> bool:
    return all(input_path(k).exists() for k in e0_config()["inputs"])


def legacy_module():
    """The frozen v1.1.0 module with its TMY paths pointed at data/conference/ (in place,
    on the module's own dicts; the file is untouched)."""
    m = importlib.import_module(LEGACY_MODULE)
    for table in (m.TMY_FILES, m.TMY_RELEASES):
        for k, path in table.items():
            if not str(path).startswith(str(LEGACY_DATA)):
                table[k] = str(LEGACY_DATA / os.path.relpath(path, m.DATA_DIR))
    return m


def _scenario(tag: str) -> str:
    return "II" if tag.startswith("II") else "I"


def conference_values(api) -> dict:
    v = {}
    _audit_and_cycle(api, v)
    _synthetic_and_tier1(api, v)
    if inputs_present():
        _tier2(api, v)
        _design_and_economics(api, v)
    return {k: (x.item() if hasattr(x, "item") else x) for k, x in v.items()}


def _audit_and_cycle(api, v):
    v["mass.harvest_subtotal_kg"] = api.HARVEST_HW
    v["mass.P0_kg"], v["mass.PA_kg"] = api.M["P0"], api.M["PA"]
    v["mass.table2_other_kg"] = sum(api.MASS[k] for k in TABLE2_OTHER)
    d = {k: p.default for k, p in inspect.signature(api.teg_daily_kwh).parameters.items()}
    k_te = d["k_TE"] * d["fill"] / d["leg"]
    v["teg.k_stack_Wm2K"] = 1.0 / (1.0 / k_te + d["R_contact"])
    v["teg.q_through_Wm2"] = api.TEG["q_through"]
    v["teg.dT_leg_K"] = api.TEG["dT_leg"]
    v["teg.P_matched_W"] = api.TEG["P_teg"]
    v["teg.E_kWh_day"] = api.E_TEG
    v["teg.P_opt_W"] = api.TEG["P_opt"]
    t = api.teg_tradeoff()
    v["teg.tradeoff_kWh"], v["teg.tradeoff_years"] = t["kwh_if_battery"], t["years"]

    rec = api.wltp_recon_error()
    v["wltp.total_km"] = rec["TOTAL"]["dist"]
    v["wltp.total_err_pct"] = rec["TOTAL"]["dist_err"]
    v["wltp.vmax_low_pct"] = 100 * (1 - rec["TOTAL"]["vmax"] / rec["TOTAL"]["vmax_off"])
    v["wltp.P0_combined_whkm"] = api.whkm("P0")
    v["wltp.P0_city_whkm"] = api.whkm("P0", city=True)
    for name, d in api.validate().items():
        v[f"table3.{name}.whkm"] = d["model_whkm"]
        v[f"table3.{name}.ratio"] = d["model_whkm"] / d["claim_whkm"]


def _synthetic_and_tier1(api, v):
    for s, (km, city) in SCENARIOS.items():
        for loc in LOCS:
            r = api.simulate(loc, km, city)
            v[f"table4.{s}.{loc}.fss_syn"] = r["fss"]
            v[f"table4.{s}.{loc}.charges_syn"] = r["charges"]
    for row in api.real_data_validation():
        v[f"table4.{_scenario(row['scenario'])}.{row['city']}.fss_t1"] = row["f_real"]
        v[f"sec5b.gsa_psh.{row['city']}"] = row["real"]
    gti = [100 * (g[4] / g[2] - 1) for g in (api.GSA[c] for c in LOCS)]
    v["sec5b.gti_above_ghi_min_pct"], v["sec5b.gti_above_ghi_max_pct"] = min(gti), max(gti)
    for loc in LOCS:
        v[f"inversion.II.{loc}.A_req_syn"] = api.required_pv_area(50, True, loc)


def _tier2(api, v):
    for row in api.tmy_validation():
        key = f"table4.{_scenario(row['scenario'])}.{row['city']}"
        v[f"{key}.fss_t2"] = row["f_tmy"]
        v[f"{key}.charges_t2"] = row["charges"]
        v[f"{key}.charges_nosolar_t2"] = row["charges_nosolar"]
        v[f"{key}.relief_t2_pct"] = row["relief_pct"]
    for loc in LOCS:
        ghi, T = api.load_city_tmy(loc)
        ann = ghi.sum() / 1000.0
        v[f"sec5b.{loc}.tmy_ghi_kWh_m2"] = ann
        v[f"sec5b.{loc}.tmy_vs_gsa_pct"] = 100 * (ann - api.GSA[loc][2]) / api.GSA[loc][2]
        v[f"sec5b.{loc}.monthly_mape_pct"] = api.climate_error(loc)["monthly_mape"]
        if loc == "Lucknow":
            v["sec5b.Lucknow.tmy_mean_T_C"] = float(T.mean())
            v["sec5b.Lucknow.tmy_minus_gsa_T_K"] = float(T.mean()) - api.GSA[loc][5]
    for loc, d in api.gap_decomposition().items():
        for part in ("total", "magnitude", "distribution"):
            v[f"sec5b.{loc}.gap_{part}"] = d[part]
    rob = api.tmy_robustness()
    for s in SCENARIOS:
        f = [r["fss"] for r in rob if _scenario(r["scenario"]) == s]
        v[f"sec5b.releases.{s}.fss_min"], v[f"sec5b.releases.{s}.fss_max"] = min(f), max(f)
    ch = [r["charges"] for r in rob if _scenario(r["scenario"]) == "II"]
    v["sec5b.releases.II.charges_min"], v["sec5b.releases.II.charges_max"] = min(ch), max(ch)
    c0 = v["table4.II.Phoenix.charges_nosolar_t2"]
    c1 = v["table4.II.Phoenix.charges_t2"]
    v["sec5b.Phoenix.plugin_reduction_pct"] = 100 * (c0 - c1) / c0
    v["sec5b.Phoenix.weeks_between_plugins_nosolar"] = 365 / c0 / 7
    v["sec5b.Phoenix.weeks_between_plugins_solar"] = 365 / c1 / 7


def _design_and_economics(api, v):
    tmy = {loc: api.load_city_tmy(loc) for loc in LOCS}
    for loc in LOCS:
        t = tmy[loc]
        v[f"inversion.II.{loc}.A_req_tmy"] = api.required_pv_area(50, True, loc, climate=t)
        v[f"inversion.II.{loc}.D_max_tmy"] = api.max_selfsuff_km(loc, True, climate=t)
        v[f"sec5c.{loc}.E_aux_kWh_day"] = api.engine_Eaux(loc, True, 50, t)
        v[f"sec5c.{loc}.fT_loss_pct"] = 100 * (1 - api.engine_fT(loc, t))
    for loc in ("Phoenix", "London"):
        v[f"inversion.I.{loc}.A_req_tmy"] = api.required_pv_area(100, False, loc, climate=tmy[loc])

    dl = api.design_levers_tmy()
    v["sec5d.area_for_fss1_m2"] = dl["area_for_fss1"]
    pk = {(r["A"], r["cap"]): r for r in dl["pack"]}
    a, b = pk[(11.6, 150)], pk[(11.6, 250)]
    v["sec5d.A11.6.cap150_to_250.mass_kg"] = b["mass"] - a["mass"]
    v["sec5d.A11.6.cap150.fss"], v["sec5d.A11.6.cap250.fss"] = a["fss"], b["fss"]
    v["sec5d.A11.6.cap150.relief_pct"] = 100 * a["relief"]
    v["sec5d.A11.6.cap250.relief_pct"] = 100 * b["relief"]
    v["sec5d.A11.6.cap150_to_250.cost_usd"] = b["cost"] - a["cost"]
    r15 = [r for (A, _), r in pk.items() if A == 15]
    v["sec5d.A15.fss_min"] = min(r["fss"] for r in r15)
    v["sec5d.A15.fss_max"] = max(r["fss"] for r in r15)
    v["sec5d.A15.relief_min_pct"] = 100 * min(r["relief"] for r in r15)
    v["sec5d.A15.relief_max_pct"] = 100 * max(r["relief"] for r in r15)
    v["sec5d.A15.charges_min"] = min(r["charges"] for r in r15)
    v["sec5d.A15.charges_max"] = max(r["charges"] for r in r15)
    for loc, f in dl["kappa"].items():
        v[f"sec5d.kappa060.{loc}.fss"], v[f"sec5d.kappa080.{loc}.fss"] = f[0], f[2]
    v["sec5d.kappa_for_quasi"] = dl["kappa_for_quasi"]
    w0, w1, f0, f1 = dl["regen_072"]
    v["sec5d.regen072.city_whkm_base"], v["sec5d.regen072.city_whkm"] = w0, w1
    v["sec5d.regen072.fss_base"], v["sec5d.regen072.fss"] = f0, f1
    v["sec3c.suspension_50_200.fss_shift"] = dl["susp"][200] - dl["susp"][50]

    v["table5.total_usd"], v["table5.pv_only_usd"] = api.SYSTEM_COST, api.PV_ONLY_COST
    teg_susp = sum(c for k, c in api.COST_ITEMS.items() if k.startswith(("TEG", "Regenerative")))
    v["table5.teg_and_suspension_usd"] = teg_susp
    v["table5.wiring_dropped_usd"] = api.SYSTEM_COST - teg_susp - api.PV_ONLY_COST
    for loc in LOCS:
        e = api.economics(loc, 50, True, climate=tmy[loc])
        v[f"table5.{loc}.relief_pct"] = e["grid_relief_pct"]
        v[f"table5.{loc}.saved_kWh"] = e["saved_kwh"]
        v[f"table5.{loc}.tariff_usd_kWh"] = api.PRICE[loc]
        v[f"table5.{loc}.payback_full_yr"] = e["payback_yr"]
        v[f"table5.{loc}.payback_pvonly_yr"] = e["payback_pvonly"]

    r = api.simulate("Phoenix", 50, True, climate=tmy["Phoenix"])
    v["fig4.listing.fss"], v["fig4.listing.charges"] = round(r["fss"], 2), r["charges"]
