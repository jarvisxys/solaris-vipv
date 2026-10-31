"""E0: Table B0, the conference metrics on the satellite-derived hourly TMY for Phoenix,
Lucknow and London (conference toolkit v1.1.0 semantics).

Every later experiment compares against this table. Columns:
  printed_synthetic / printed_tmy  value printed in the final conference paper (e0.yaml)
  synthetic                        idealized synthetic climate, reproduced (historical row)
  tmy                              satellite hourly TMY -- the journal baseline

relief_pct is the harvest actually used (harvest - curtailed) / demand, on the periodic
year (the second of two passes), so relief <= f_ss and the pack balance closes.
Phoenix runs on the local-time NSRDB TMY-2023 (tmy_phoenix), asserted identical to the
conference UTC file after its roll; Lucknow and London on the files shipped with v1.1.0.

Outputs: results/e0/table_b0.csv, table_b0_pareto.csv (Phoenix, Scenario II, mass fed back)
and summary_b0.json (inputs, gap split, TMY-release spread, design levers on the TMY).

Run by Snakemake (rule e0_measured) or directly:
  python experiments/e0_reproduce/run.py --table <csv> --pareto <csv> --summary <json>
"""

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

from solaris import core
from solaris.core.conference import SCENARIOS, e0_config, input_path

# metric -> (unit, e0.yaml id printed for the synthetic run, id printed for the TMY run).
# {s} is the scenario, {c} the city; an id without {s} was printed for Scenario II only.
METRICS = {
    "psh": ("kWh/m2/day", None, None),
    "ghi_kWh_m2": ("kWh/m2/yr", None, "sec5b.{c}.tmy_ghi_kWh_m2"),
    "T_mean_C": ("C", None, None),
    "fss": ("-", "table4.{s}.{c}.fss_syn", "table4.{s}.{c}.fss_t2"),
    "fss_class": ("-", None, None),
    "charges_per_yr": ("1/yr", "table4.{s}.{c}.charges_syn", "table4.{s}.{c}.charges_t2"),
    "charges_nosolar_per_yr": ("1/yr", None, "table4.{s}.{c}.charges_nosolar_t2"),
    "charge_reduction_pct": ("%", None, "sec5b.{c}.plugin_reduction_pct"),
    "demand_kWh": ("kWh/yr", None, None),
    "harvest_kWh": ("kWh/yr", None, None),
    "grid_kWh": ("kWh/yr", None, None),
    "curtailed_kWh": ("kWh/yr", None, None),
    "solar_used_kWh": ("kWh/yr", None, "table5.{c}.saved_kWh"),
    "relief_pct": ("%", None, "table4.{s}.{c}.relief_t2_pct"),
    "soc_end_minus_start_kWh": ("kWh", None, None),
    "saved_usd_per_yr": ("USD/yr", None, None),
    "payback_full_yr": ("yr", None, "table5.{c}.payback_full_yr"),
    "payback_pvonly_yr": ("yr", None, "table5.{c}.payback_pvonly_yr"),
    "fT": ("-", None, None),
    "E_aux_kWh_day": ("kWh/day", None, "sec5c.{c}.E_aux_kWh_day"),
    "A_req_m2": ("m2", "inversion.{s}.{c}.A_req_syn", "inversion.{s}.{c}.A_req_tmy"),
    "D_max_km_day": ("km/day", None, "inversion.{s}.{c}.D_max_tmy"),
    "fss_kappa060": ("-", None, "sec5d.kappa060.{c}.fss"),
    "fss_kappa070": ("-", None, None),
}
SCENARIO_FREE = {"ghi_kWh_m2"}  # printed once, same value in both scenarios


def metrics(city, km, s_city, climate) -> dict:
    """Conference metrics for one city and scenario on one climate (None = synthetic)."""
    r = core.simulate(city, km, s_city, climate=climate)
    r0 = core.simulate(city, km, s_city, climate=climate, pv_scale=0.0)
    e = core.economics(city, km, s_city, climate=climate)
    ghi, T = core.site_climate(core.BASE.sites[city]) if climate is None else climate
    return {
        "psh": r["psh"],
        "ghi_kWh_m2": float(ghi.sum() / 1000.0),
        "T_mean_C": float(T.mean()),
        "fss": r["fss"],
        "fss_class": core.classify(r["fss"]),
        "charges_per_yr": r["charges"],
        "charges_nosolar_per_yr": r0["charges"],
        "charge_reduction_pct": 100 * (r0["charges"] - r["charges"]) / r0["charges"],
        "demand_kWh": r["ann_dem"],
        "harvest_kWh": r["ann_harv"],
        "grid_kWh": r["grid_kwh"],
        "curtailed_kWh": r["curtailed"],
        "solar_used_kWh": r["solar_used"],
        "relief_pct": 100 * r["relief"],
        "soc_end_minus_start_kWh": r["soc_change"],
        "saved_usd_per_yr": e["saved_usd"],
        "payback_full_yr": e["payback_yr"],
        "payback_pvonly_yr": e["payback_pvonly"],
        "fT": core.engine_fT(city, climate),
        "E_aux_kWh_day": core.engine_Eaux(city, s_city, km, climate),
        "A_req_m2": core.required_pv_area(km, s_city, city, climate),
        "D_max_km_day": core.max_selfsuff_km(city, s_city, climate),
        "fss_kappa060": core.simulate(city, km, s_city, climate=climate, kappa=0.60)["fss"],
        "fss_kappa070": core.simulate(city, km, s_city, climate=climate, kappa=0.70)["fss"],
    }


def printed(cfg, metric, template, scenario, city):
    if template is None:
        return ""
    if "{s}" not in template and scenario != "II" and metric not in SCENARIO_FREE:
        return ""
    key = template.format(s=scenario, c=city)
    return {e["id"]: e["printed"] for e in cfg["expected"]}.get(key, "")


def fmt(x):
    if isinstance(x, str):
        return x
    return format(float(x), ".10g") if isinstance(x, float) or hasattr(x, "item") else str(x)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_inputs(cfg) -> dict:
    """Every e0.yaml input present with its pinned SHA-256; returns {key: sha256}."""
    out = {}
    for key, spec in cfg["inputs"].items():
        actual = sha256(input_path(key))
        if actual != spec["sha256"]:
            raise ValueError(f"{spec['path']}: sha256 {actual} does not match e0.yaml")
        out[key] = actual
    return out


def climates(cfg) -> dict:
    """City -> (GHI, T) in local standard time. Phoenix: the E0/P2 local-time file, which must
    equal the conference UTC TMY-2023 after its roll."""
    out = {c: core.load_city_tmy(c) for c in cfg["b0"]["sites"]}
    local = core.load_tmy(input_path("tmy_phoenix"))
    if not all(np.array_equal(a, b) for a, b in zip(local, out["Phoenix"], strict=True)):
        raise ValueError("local-time Phoenix TMY differs from the conference TMY-2023")
    out["Phoenix"] = local
    return out


def main(out_table, out_pareto, out_summary):
    cfg = e0_config()
    shas = check_inputs(cfg)
    clim = climates(cfg)
    rows = []
    for city in cfg["b0"]["sites"]:
        for s in cfg["b0"]["scenarios"]:
            km, s_city = SCENARIOS[s]
            syn, tmy = metrics(city, km, s_city, None), metrics(city, km, s_city, clim[city])
            for m, (unit, id_syn, id_tmy) in METRICS.items():
                rows.append(
                    [
                        city,
                        s,
                        m,
                        unit,
                        printed(cfg, m, id_syn, s, city),
                        fmt(syn[m]),
                        printed(cfg, m, id_tmy, s, city),
                        fmt(tmy[m]),
                    ]
                )
    header = ["city", "scenario", "metric", "unit"]
    header += ["printed_synthetic", "synthetic", "printed_tmy", "tmy"]
    _write(out_table, header, rows)

    site = cfg["b0"]["pareto_site"]
    syn = core.pareto(site, 50, True)
    tmy = core.pareto(site, 50, True, climate=clim[site])
    cols = ("A", "cap", "mass", "cost")
    pairs = ("fss", "grid", "charges", "relief")
    prow = [
        [fmt(a[k]) for k in cols] + [fmt(x[k]) for k in pairs for x in (a, b)]
        for a, b in zip(syn, tmy, strict=True)
    ]
    pheader = ["A_m2", "cap_kWh", "mass_kg", "cost_usd"]
    pheader += [f"{k}_{c}" for k in pairs for c in ("synthetic_4seed", "tmy")]
    _write(out_pareto, pheader, prow)

    Path(out_summary).write_text(
        json.dumps(summary(cfg, shas, clim), indent=2) + "\n", encoding="utf-8", newline="\n"
    )


def summary(cfg, shas, clim) -> dict:
    gsa = core.BASE.gsa
    dl = core.design_levers_tmy()
    w0, w1, f0, f1 = dl["regen_072"]
    return {
        "baseline": "conference toolkit v1.1.0 (SOLARIS__Final), satellite hourly TMY",
        "inputs": {k: {"path": cfg["inputs"][k]["path"], "sha256": v} for k, v in shas.items()},
        "climate": {
            c: {
                "ghi_kWh_m2": round(float(g.sum() / 1000), 1),
                "psh": round(float(g.sum() / 1000 / 365), 3),
                "T_mean_C": round(float(T.mean()), 2),
                "ghi_vs_gsa_pct": round(100 * (g.sum() / 1000 - gsa[c][2]) / gsa[c][2], 2),
            }
            for c, (g, T) in clim.items()
        },
        "gap_decomposition_II": {
            c: {k: round(x, 4) for k, x in d.items()} for c, d in core.gap_decomposition().items()
        },
        "tmy_releases_phoenix": core.tmy_robustness(),
        "design_levers_phoenix_II": {
            "kappa_060_070_080": {c: [round(x, 4) for x in f] for c, f in dl["kappa"].items()},
            "kappa_for_quasi": round(dl["kappa_for_quasi"], 3),
            "eta_regen_072": {
                "city_whkm": [round(w0, 2), round(w1, 2)],
                "fss": [round(f0, 4), round(f1, 4)],
            },
            "suspension_W_fss": {str(k): round(x, 4) for k, x in dl["susp"].items()},
            "area_for_fss1_m2": round(dl["area_for_fss1"], 3),
            "pack": [
                {k: round(float(r[k]), 4) for k in ("A", "cap", "mass", "fss", "relief", "grid")}
                | {"charges": r["charges"]}
                for r in dl["pack"]
            ],
        },
    }


def _write(path, header, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--table", default="results/e0/table_b0.csv")
    ap.add_argument("--pareto", default="results/e0/table_b0_pareto.csv")
    ap.add_argument("--summary", default="results/e0/summary_b0.json")
    a = ap.parse_args()
    main(a.table, a.pareto, a.summary)
