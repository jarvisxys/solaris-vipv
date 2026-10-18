"""E2: facet orientation in open sky (workflow guide Sec. 5), on the measured NSRDB TMY.

Cases, each for conference Scenarios II (50 km/day, city) and I (100 km/day, combined):
  2a     conference model: flat GHI on 11.6 m2 (Table B0)
  2b     11.6 m2 horizontal through the new irradiance chain (pvlib Perez G_f at the TMY
         stamps) with the conference cell-temperature rule; must equal 2a within 0.5 %
  2b+F   2b with Faiman cell temperature (wind = ambient + vehicle speed): the thermal step
  2c     placeholder facet skin (configs/vehicle/solaris_p0.yaml), Faiman, 36-heading mean
  2d     roof only, 4.4 m2 at 2 deg, Faiman, heading mean (bound for the unconfirmed layout)
Also: 2c at fixed headings N/E/S/W, 2c with body-bonded Faiman coefficients (sensitivity),
and incident irradiation per facet. F_geo = E_case / E_2b+F isolates geometry.

Outputs: results/e2/table_e2.csv, results/e2/table_e2_facets.csv, results/e2/summary_e2.json.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from solaris import core
from solaris.core.conference import SCENARIOS, input_path
from solaris.core.drive_cycle import mean_speed_kmh
from solaris.core.soc_loop import drive_fraction, drive_mask
from solaris.pv.model import sun_inputs, vehicle_pv
from solaris.vehicle import facets, flat_skin, samples, vehicle_config
from solaris.weather import tmy_hourly

SITE = "Phoenix"
HEADINGS = np.arange(0, 360, 10)
CARDINAL = {"N": 0, "E": 90, "S": 180, "W": 270}
TOL = 0.005


def weather():
    """P2 TMY (all components) after checking it carries the GHI and T behind Table B0."""
    df, meta = tmy_hourly()
    ghi_e0, T_e0 = core.load_tmy(input_path("tmy_phoenix"))
    if not (np.array_equal(df["ghi"].to_numpy(), ghi_e0) and np.allclose(df["temp_air"], T_e0)):
        raise ValueError("P2 TMY differs from the E0 TMY behind Table B0")
    sun = sun_inputs(df.index, meta["latitude"], meta["longitude"], meta["altitude"])
    return df, sun, (ghi_e0, T_e0)


def drive(km, city):
    """Fraction of each hour spent driving and the mean driving speed (m/s)."""
    frac = np.where(drive_mask(), drive_fraction(km, city), 0.0)
    return frac, mean_speed_kmh(city) / 3.6


def pv_conference(climate, p=core.BASE):
    """Conference flat-GHI PV energy per hour (kWh), exactly as core.simulate computes it."""
    ghi, T = climate
    pcell = T + p.cell_temp_rise * (ghi / 1000.0)
    return p.A_skin * p.eta_pv * (ghi / 1000.0) * p.kappa_pv * (1 + p.beta * (pcell - 25))


def heading_mean(fs, wx, sun, pvcfg, frac, v, headings=HEADINGS):
    """Hourly PV energy averaged over headings, and per-facet (poa, kWh) means."""
    tot, per = np.zeros(len(wx)), {}
    for h in headings:
        t, p = vehicle_pv(fs, h, wx, sun, pvcfg, frac, v)
        tot += t / len(headings)
        for k, (poa, e) in p.items():
            a, b = per.get(k, (0.0, 0.0))
            per[k] = (a + poa / len(headings), b + e / len(headings))
    return tot, per


def metrics(r, pv_kwh_yr):
    return {
        "pv_kWh_yr": pv_kwh_yr,
        "fss": r["fss"],
        "grid_kWh": r["grid_kwh"],
        "charges_per_yr": r["charges"],
        "relief_balanced_pct": 100 * r["harvest_used_kwh"] / r["ann_dem"],
        "relief_conference_pct": 100 * (r["ann_dem"] - r["grid_kwh"]) / r["ann_dem"],
    }


def scenario_cases(vcfg, wx, sun, climate, km, city):
    pvcfg = vcfg["pv"]
    conf_t = {**pvcfg, "temperature_model": "conference"}
    skin = facets(vcfg)
    roof = facets(vcfg, only={"roof"})
    flat = flat_skin(sum(f.area_m2 for f in skin))
    frac, v = drive(km, city)
    # 2a runs core.simulate unchanged; its series is only used to report the PV energy.
    cases = {"2a": ("conference flat GHI, 11.6 m2", pv_conference(climate))}
    cases["2b"] = (
        "11.6 m2 horizontal, new irradiance chain, conference T rule",
        vehicle_pv(flat, 0.0, wx, sun, conf_t, frac, v)[0],
    )
    cases["2b+F"] = (
        "2b with Faiman cell temperature",
        vehicle_pv(flat, 0.0, wx, sun, pvcfg, frac, v)[0],
    )
    e2c, per = heading_mean(skin, wx, sun, pvcfg, frac, v)
    cases["2c"] = ("facet skin, Faiman, 36-heading mean", e2c)
    cases["2d"] = (
        "roof only 4.4 m2, Faiman, heading mean",
        heading_mean(roof, wx, sun, pvcfg, frac, v)[0],
    )
    for name, deg in CARDINAL.items():
        cases[f"2c-{name}"] = (
            f"facet skin facing {name}",
            vehicle_pv(skin, deg, wx, sun, pvcfg, frac, v)[0],
        )
    for name, coef in pvcfg["faiman_sensitivity"].items():
        cases[f"2c-{name}"] = (
            f"2c with Faiman u0={coef['u0']}, u1={coef['u1']} ({name})",
            heading_mean(skin, wx, sun, {**pvcfg, "faiman": coef}, frac, v)[0],
        )
    return cases, per, (skin, frac, v)


def main(out_table, out_facets, out_summary):
    vcfg = vehicle_config()
    wx, sun, climate = weather()
    rows, frows = [], []
    summary = {
        "layout": vcfg["status"],
        "area_m2": 11.6,
        "ghi_kWh_m2_yr": round(float(wx["ghi"].sum() / 1000), 1),
    }
    for sc, (km, city) in SCENARIOS.items():
        cases, per, (skin, frac, v) = scenario_cases(vcfg, wx, sun, climate, km, city)
        m = {}
        for case, (_, series) in cases.items():
            kw = {} if case == "2a" else {"pv_kwh": series}
            m[case] = metrics(
                core.simulate(SITE, km, city, climate=climate, **kw), float(series.sum())
            )
        for case, (desc, _) in cases.items():
            rows.append(
                {
                    "scenario": sc,
                    "case": case,
                    "description": desc,
                    **m[case],
                    "F_geo": m[case]["pv_kWh_yr"] / m["2b+F"]["pv_kWh_yr"],
                    "vs_2a_pv": m[case]["pv_kWh_yr"] / m["2a"]["pv_kWh_yr"],
                    "vs_2a_fss": m[case]["fss"] / m["2a"]["fss"],
                }
            )
        d_pv = m["2b"]["pv_kWh_yr"] / m["2a"]["pv_kWh_yr"] - 1
        d_fss = m["2b"]["fss"] / m["2a"]["fss"] - 1
        summary[f"scenario_{sc}"] = {
            "check_2b_vs_2a": {
                "pv_rel": round(d_pv, 5),
                "fss_rel": round(d_fss, 5),
                "tol": TOL,
                "pass": bool(abs(d_pv) <= TOL and abs(d_fss) <= TOL),
            },
            "thermal_step_2bF_vs_2b": round(m["2b+F"]["pv_kWh_yr"] / m["2b"]["pv_kWh_yr"] - 1, 5),
            "F_geo_2c": round(m["2c"]["pv_kWh_yr"] / m["2b+F"]["pv_kWh_yr"], 4),
            "F_geo_2d": round(m["2d"]["pv_kWh_yr"] / m["2b+F"]["pv_kWh_yr"], 4),
            "fss": {k: round(m[k]["fss"], 4) for k in ("2a", "2b", "2b+F", "2c", "2d")},
            "charges_per_yr": {k: m[k]["charges_per_yr"] for k in ("2a", "2c", "2d")},
            "delta_fss_2c_vs_2a": round(m["2c"]["fss"] - m["2a"]["fss"], 4),
            "drive_fraction_in_trip_hours": round(float(frac.max()), 4),
            "drive_speed_mps": round(v, 3),
        }
        if sc == "II":
            frows += facet_rows(skin, per, wx, sun, vcfg["pv"], frac, v)
    summary["pass"] = all(summary[f"scenario_{s}"]["check_2b_vs_2a"]["pass"] for s in SCENARIOS)
    for path in (out_table, out_facets, out_summary):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out_table, index=False, lineterminator="\n", float_format="%.6g")
    pd.DataFrame(frows).to_csv(out_facets, index=False, lineterminator="\n", float_format="%.6g")
    Path(out_summary).write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return summary


def facet_rows(skin, per, wx, sun, pvcfg, frac, v):
    ghi = wx["ghi"].sum()
    out = []
    for f in skin:
        base = {
            "facet": f.id,
            "area_m2": f.area_m2,
            "tilt_deg": f.tilt_deg,
            "azimuth_body_deg": f.azimuth_body_deg,
        }
        poa, e = per[f.id]
        out.append(
            {
                **base,
                "heading": "mean",
                "incident_kWh_m2_yr": poa.sum() / 1000,
                "pv_kWh_yr": e.sum(),
                "vs_ghi": poa.sum() / ghi,
            }
        )
        for name, deg in CARDINAL.items():
            poa_h, e_h = vehicle_pv([f], deg, wx, sun, pvcfg, frac, v)[1][f.id]
            out.append(
                {
                    **base,
                    "heading": name,
                    "incident_kWh_m2_yr": poa_h.sum() / 1000,
                    "pv_kWh_yr": e_h.sum(),
                    "vs_ghi": poa_h.sum() / ghi,
                }
            )
    return out


def write_facet_samples(out):
    """twin/exchange/facet_samples.csv in the guide's exchange schema."""
    vcfg = vehicle_config()
    s = samples(facets(vcfg), vcfg["sample_spacing_m"])
    cols = ["facet_id", "sample_id", "x_body", "y_body", "z_body", "nx", "ny", "nz"]
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    s[cols].to_csv(out, index=False, lineterminator="\n", float_format="%.4f")
    return s


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--table", default="results/e2/table_e2.csv")
    ap.add_argument("--facets", default="results/e2/table_e2_facets.csv")
    ap.add_argument("--summary", default="results/e2/summary_e2.json")
    a = ap.parse_args()
    print(json.dumps(main(a.table, a.facets, a.summary), indent=2))
