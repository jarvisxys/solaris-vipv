"""E0: Table B0, the conference metrics rerun on the measured NSRDB TMY (Phoenix).

Every later experiment compares against this table. Columns:
  printed_synthetic / printed_measured  value printed in the conference paper (from e0.yaml)
  synthetic                             conference synthetic climate, reproduced (historical row)
  measured_b0                           measured hourly TMY -- the journal baseline

grid_relief_pct is the conference definition (demand - grid) / demand; it credits the
pack's net discharge over the year as solar. grid_relief_balanced_pct uses the harvest
actually delivered, so the pack energy balance closes. The journal reports the balanced
definition (author decision, 2026-10-16); the *_balanced paybacks follow from it.

Run by Snakemake (rule e0_measured, which calls main()) or directly:
  python experiments/e0_reproduce/run.py --tmy <csv> --table <csv> --pareto <csv>
"""

import argparse
import csv
import hashlib
from pathlib import Path

from solaris import core
from solaris.core.conference import SCENARIOS, e0_config

SITE = "Phoenix"

# metric -> (unit, e0.yaml id printed for the synthetic run, id printed for the measured run);
# {s} is the scenario tag. Only ids that exist in e0.yaml are filled in.
METRICS = {
    "psh": ("kWh/m2/day", None, "sec9a.Phoenix.tmy_psh"),
    "fss": ("-", "table3.{s}.Phoenix.fss", "table4.{s}.Phoenix.fss_t2"),
    "fss_class": ("-", None, None),
    "charges_per_yr": ("1/yr", "table3.{s}.Phoenix.charges", None),
    "charges_nosolar_per_yr": ("1/yr", "table3.{s}.Phoenix.charges_nosolar", None),
    "charge_reduction_pct": ("%", "sec11.Phoenix.charge_reduction_pct", None),
    "demand_kWh": ("kWh/yr", None, None),
    "harvest_kWh": ("kWh/yr", None, None),
    "grid_kWh": ("kWh/yr", None, None),
    "grid_relief_kWh": ("kWh/yr", "table6.Phoenix.saved_kWh", None),
    "grid_relief_pct": ("%", "table6.Phoenix.relief_pct", None),
    "soc_end_minus_start_kWh": ("kWh", None, None),
    "curtailed_kWh": ("kWh/yr", None, None),
    "harvest_used_kWh": ("kWh/yr", None, None),
    "grid_relief_balanced_pct": ("%", None, None),
    "saved_usd_per_yr": ("USD/yr", None, None),
    "payback_full_yr": ("yr", "table6.Phoenix.payback_full_yr", None),
    "payback_pvonly_yr": ("yr", "table6.Phoenix.payback_pvonly_yr", None),
    "saved_usd_balanced_per_yr": ("USD/yr", None, None),
    "payback_full_balanced_yr": ("yr", None, None),
    "payback_pvonly_balanced_yr": ("yr", None, None),
    "fT": ("-", None, None),
    "E_aux_kWh_day": ("kWh/day", None, None),
    "A_req_m2": ("m2", "inversion.{s}.Phoenix.A_req", None),
    "D_max_km_day": ("km/day", "inversion.{s}.Phoenix.D_max", None),
    "fss_kappa060": ("-", "sens.kappa060.{s}.Phoenix.fss", None),
    "fss_kappa070": ("-", None, None),
}
# Table VI, the charge reduction and the kappa sweep were printed for Scenario II only.
SCENARIO_II_ONLY = ("table6.", "sec11.", "sens.kappa060.")


def metrics(km, city, climate) -> dict:
    """Conference metrics for one scenario on one climate (None = synthetic)."""
    r = core.simulate(SITE, km, city, climate=climate)
    r0 = core.simulate(SITE, km, city, climate=climate, pv_scale=0.0)
    e = core.economics(SITE, km, city, climate=climate)
    saved_usd_balanced = r["harvest_used_kwh"] * core.BASE.price[SITE]
    return {
        "psh": r["psh"],
        "fss": r["fss"],
        "fss_class": core.classify(r["fss"]),
        "charges_per_yr": r["charges"],
        "charges_nosolar_per_yr": r0["charges"],
        "charge_reduction_pct": 100 * (r0["charges"] - r["charges"]) / r0["charges"],
        "demand_kWh": r["ann_dem"],
        "harvest_kWh": r["ann_harv"],
        "grid_kWh": r["grid_kwh"],
        "grid_relief_kWh": e["saved_kwh"],
        "grid_relief_pct": e["grid_relief_pct"],
        "soc_end_minus_start_kWh": r["soc_end_kwh"] - r["soc_start_kwh"],
        "curtailed_kWh": r["curtailed_kwh"],
        "harvest_used_kWh": r["harvest_used_kwh"],
        # solar share of demand with the pack's year-end change in stored energy counted
        "grid_relief_balanced_pct": 100 * r["harvest_used_kwh"] / r["ann_dem"],
        "saved_usd_per_yr": e["saved_usd"],
        "payback_full_yr": e["payback_yr"],
        "payback_pvonly_yr": e["payback_pvonly"],
        "saved_usd_balanced_per_yr": saved_usd_balanced,
        "payback_full_balanced_yr": core.SYSTEM_COST / saved_usd_balanced,
        "payback_pvonly_balanced_yr": core.PV_ONLY_COST / saved_usd_balanced,
        "fT": core.engine_fT(SITE, climate),
        "E_aux_kWh_day": core.engine_Eaux(SITE, city, km, climate),
        "A_req_m2": core.required_pv_area(km, city, SITE, climate),
        "D_max_km_day": core.max_selfsuff_km(SITE, city, climate),
        "fss_kappa060": core.simulate(SITE, km, city, climate=climate, kappa=0.60)["fss"],
        "fss_kappa070": core.simulate(SITE, km, city, climate=climate, kappa=0.70)["fss"],
    }


def printed(cfg, template, scenario):
    if template is None:
        return ""
    key = template.format(s=scenario)
    if scenario != "II" and key.startswith(SCENARIO_II_ONLY):
        return ""
    return {e["id"]: e["printed"] for e in cfg["expected"]}.get(key, "")


def fmt(x):
    if isinstance(x, str):
        return x
    return format(float(x), ".10g") if isinstance(x, float) or hasattr(x, "item") else str(x)


def check_tmy(path, cfg):
    expected = cfg["inputs"]["tmy_phoenix"]["sha256"]
    actual = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError(f"{path}: sha256 {actual} does not match e0.yaml ({expected})")


def main(tmy, out_table, out_pareto):
    cfg = e0_config()
    check_tmy(tmy, cfg)
    climate = core.load_tmy(tmy)
    rows = []
    for s in cfg["b0"]["scenarios"]:
        km, city = SCENARIOS[s]
        syn, meas = metrics(km, city, None), metrics(km, city, climate)
        for m, (unit, id_syn, id_meas) in METRICS.items():
            rows.append(
                [
                    s,
                    m,
                    unit,
                    printed(cfg, id_syn, s),
                    fmt(syn[m]),
                    printed(cfg, id_meas, s),
                    fmt(meas[m]),
                ]
            )
    _write(
        out_table,
        [
            "scenario",
            "metric",
            "unit",
            "printed_synthetic",
            "synthetic",
            "printed_measured",
            "measured_b0",
        ],
        rows,
    )

    syn = core.pareto(SITE, 50, True)
    meas = core.pareto(SITE, 50, True, climate=climate)
    prow = [
        [
            fmt(a["A"]),
            fmt(a["cap"]),
            fmt(a["mass"]),
            fmt(a["cost"]),
            fmt(a["fss"]),
            fmt(b["fss"]),
            fmt(a["grid"]),
            fmt(b["grid"]),
            fmt(a["charges"]),
            fmt(b["charges"]),
        ]
        for a, b in zip(syn, meas, strict=True)
    ]
    _write(
        out_pareto,
        [
            "A_m2",
            "cap_kWh",
            "mass_kg",
            "cost_usd",
            "fss_synthetic",
            "fss_measured",
            "grid_kWh_synthetic_4seed",
            "grid_kWh_measured",
            "charges_synthetic",
            "charges_measured",
        ],
        prow,
    )


def _write(path, header, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tmy", required=True)
    ap.add_argument("--table", required=True)
    ap.add_argument("--pareto", required=True)
    a = ap.parse_args()
    main(a.tmy, a.table, a.pareto)
