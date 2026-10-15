"""Every number printed in the conference paper, computed by a given engine.

``conference_values(api)`` accepts either the frozen legacy module
(``solaris.legacy.solaris_v1``) or ``solaris.core``; both expose the same function
names. The ids match ``expected`` in configs/experiments/e0.yaml.
"""

import contextlib
from pathlib import Path

import yaml

from .params import REPO_ROOT, Site

E0_YAML = REPO_ROOT / "configs" / "experiments" / "e0.yaml"
LOCS = ("Phoenix", "Lucknow", "London")
SCENARIOS = {"II": (50, True), "I": (100, False)}
TMY_INPUT = {"Phoenix": "tmy_phoenix", "London": "tmy_london"}


def e0_config() -> dict:
    return yaml.safe_load(E0_YAML.read_text(encoding="utf-8"))


def input_path(key: str) -> Path:
    return REPO_ROOT / e0_config()["inputs"][key]["path"]


def _is_legacy(api) -> bool:
    return getattr(api, "__name__", "").endswith("legacy.solaris_v1")


def _site(api, loc) -> Site:
    return Site(*api.LOCS[loc]) if _is_legacy(api) else api.BASE.sites[loc]


def _simulate_site(api, loc, site: Site, km, city):
    """simulate() on a rescaled synthetic site (legacy: patch and restore its LOCS table)."""
    if not _is_legacy(api):
        return api.simulate(loc, km, city, site=site)
    saved = api.LOCS[loc]
    api.LOCS[loc] = tuple(site)
    try:
        return api.simulate(loc, km, city)
    finally:
        api.LOCS[loc] = saved


def _scenario(tag: str) -> str:
    return "II" if tag.startswith("II") else "I"


def conference_values(api) -> dict:
    v = {}
    with contextlib.chdir(REPO_ROOT):  # legacy TMY paths are relative to the repo root
        _audit_and_cycle(api, v)
        _climate_runs(api, v)
        _measured(api, v)
        _design_and_economics(api, v)
        _sensitivities(api, v)
    return {k: (x.item() if hasattr(x, "item") else x) for k, x in v.items()}


def _audit_and_cycle(api, v):
    v["mass.harvest_subtotal_kg"] = api.HARVEST_HW
    v["mass.P0_kg"], v["mass.PA_kg"] = api.M["P0"], api.M["PA"]
    v["teg.dT_leg_K"] = api.TEG["dT_leg"]
    v["teg.q_through_Wm2"] = api.TEG["q_through"]
    v["teg.P_matched_W"] = api.TEG["P_teg"]
    v["teg.P_opt_W"] = api.TEG["P_opt"]
    v["teg.E_kWh_day"] = api.E_TEG
    t = api.teg_tradeoff()
    v["teg.tradeoff_kWh"], v["teg.tradeoff_days"] = t["kwh_if_battery"], t["days"]
    v["teg.tradeoff_years"] = t["years"]

    rec = api.wltp_recon_error()
    v["wltp.total_km"] = rec["TOTAL"]["dist"]
    v["wltp.total_err_pct"] = rec["TOTAL"]["dist_err"]
    v["wltp.low_err_pct"] = rec["Low"]["dist_err"]
    v["wltp.medium_err_pct"] = rec["Medium"]["dist_err"]
    v["wltp.vmax_kmh"] = rec["TOTAL"]["vmax"]
    v["wltp.P0_combined_whkm"] = api.whkm("P0")
    v["wltp.P0_city_whkm"] = api.whkm("P0", city=True)
    v["wltp.P0_combined_whkm_regen072"] = api.whkm("P0", eta_regen=0.72)
    for name, d in api.validate().items():
        v[f"table2.{name}.whkm"] = d["model_whkm"]


def _climate_runs(api, v):
    for s, (km, city) in SCENARIOS.items():
        for loc in LOCS:
            r = api.simulate(loc, km, city)
            v[f"table3.{s}.{loc}.fss"] = r["fss"]
            v[f"table3.{s}.{loc}.charges"] = r["charges"]
            v[f"table3.{s}.{loc}.charges_nosolar"] = api.simulate(loc, km, city, pv_scale=0.0)[
                "charges"
            ]
    base, solar = v["table3.II.Phoenix.charges_nosolar"], v["table3.II.Phoenix.charges"]
    v["sec11.Phoenix.charge_reduction_pct"] = 100 * (base - solar) / base
    v["sec18.simulate.fss"] = v["table3.II.Phoenix.fss"]
    v["sec18.simulate.charges"] = v["table3.II.Phoenix.charges"]

    for row in api.real_data_validation():
        v[f"table4.{_scenario(row['scenario'])}.{row['city']}.fss_t1"] = row["f_real"]
        v[f"sec9a.gsa_psh.{row['city']}"] = row["real"]
    for row in api.tmy_validation():
        v[f"table4.{_scenario(row['scenario'])}.{row['city']}.fss_t2"] = row["f_tmy"]


def _measured(api, v):
    for loc, key in TMY_INPUT.items():
        path = input_path(key)
        if not path.exists():
            continue
        ghi, T = api.load_tmy(str(path))
        v[f"sec9a.{loc}.tmy_ghi_kWh_m2"] = ghi.sum() / 1000.0
        v[f"sec9a.{loc}.tmy_psh"] = ghi.sum() / 1000.0 / 365.0
        err = api.climate_error(loc)
        v[f"sec9a.{loc}.synthetic_annual_err_pct"] = err["ann_err"]
        v[f"sec9a.{loc}.synthetic_monthly_mape_pct"] = err["monthly_mape"]
        if loc != "Phoenix":
            continue
        # Sec. IX-A decomposition of the synthetic -> measured-hourly f_ss gap (Scenario II).
        # Magnitude step: synthetic shape rescaled to the TMY's annual PSH and mean T, as
        # reported by tmy_validation() (3 d.p. and 1 d.p.).
        f_syn = api.simulate(loc, 50, True)["fss"]
        f_tmy = api.simulate(loc, 50, True, climate=(ghi, T))["fss"]
        s = _site(api, loc)
        rescaled = Site(s.lat, round(ghi.sum() / 1000 / 365, 3), round(float(T.mean()), 1), s.T_amp)
        f_mag = _simulate_site(api, loc, rescaled, 50, True)["fss"]
        v["sec9a.Phoenix.gap_total"] = f_syn - f_tmy
        v["sec9a.Phoenix.gap_magnitude"] = f_syn - f_mag
        v["sec9a.Phoenix.gap_distribution"] = f_mag - f_tmy


def _design_and_economics(api, v):
    for s, (km, city) in SCENARIOS.items():
        for loc in LOCS:
            v[f"inversion.{s}.{loc}.A_req"] = api.required_pv_area(km, city, loc)
            v[f"inversion.{s}.{loc}.D_max"] = api.max_selfsuff_km(loc, city)
    v["sec18.required_pv_area.London"] = v["inversion.II.London.A_req"]
    v["sec18.max_selfsuff_km.Phoenix"] = v["inversion.II.Phoenix.D_max"]

    v["table5.total_usd"], v["table5.pv_only_usd"] = api.SYSTEM_COST, api.PV_ONLY_COST
    for loc in LOCS:
        e = api.economics(loc, 50, True)
        v[f"table6.{loc}.relief_pct"] = e["grid_relief_pct"]
        v[f"table6.{loc}.saved_kWh"] = e["saved_kwh"]
        v[f"table6.{loc}.payback_full_yr"] = e["payback_yr"]
        v[f"table6.{loc}.payback_pvonly_yr"] = e["payback_pvonly"]

    rows = {(r["A"], r["cap"]): r for r in api.pareto()}
    g150, g250 = rows[(15, 150)]["grid"], rows[(15, 250)]["grid"]
    v["pareto.A15.fss"] = rows[(15, 250)]["fss"]
    v["pareto.A15.cap150.grid_kWh"], v["pareto.A15.cap250.grid_kWh"] = g150, g250
    v["pareto.A15.cap_grid_reduction_pct"] = 100 * (g150 - g250) / g150


def _sensitivities(api, v):
    for loc in LOCS:
        v[f"sens.kappa060.II.{loc}.fss"] = api.simulate(loc, 50, True, kappa=0.60)["fss"]
    susp = api.regen_susp_sensitivity()
    v["sens.suspension_50_200.fss_shift"] = susp[200] - susp[50]
    for s, (km, city) in SCENARIOS.items():
        v[f"sens.eta_regen072.{s}.max_fss_shift"] = max(
            api.simulate(loc, km, city, eta_regen=0.72)["fss"] - api.simulate(loc, km, city)["fss"]
            for loc in LOCS
        )
