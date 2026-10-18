"""E6: electrical partial shading (workflow guide Sec. 5).

Each facet is one module on its own MPPT input (configs/vehicle/electrical_p0.yaml): cells
(= facet samples) in three bypass-diode substrings, string I-V from pvlib bishop88 with
reverse-bias breakdown, MPP per input
(src/solaris/pv/electrical.py). Per facet and instant:

    F_mm = P_mpp(per-cell irradiance) / P_mpp(every cell at the facet's mean irradiance)

Data: every R-DENSE trip of E3 (30 traces x 4 days x clear / TMY sky, 1 s) and the parked
sites P2 and P3 at their E5 headings (every daylight 5-min step of the TMY year). A cell
gets v_b * beam + diffuse, v_b = 0 behind buildings, tau behind trees, 1 open. F_mm is fitted
against the beam-shaded area fraction s = 1 - mean(v_b):  F_mm = 1 - k s^alpha (1 - s)^beta,
energy-weighted within driving and parking, the two sources weighted equally. E5 applies
the fit as its last waterfall step. Gate: uniform light gives F_mm = 1 within 1e-3.

Outputs: results/e6/table_e6.csv (binned), fit_fmm.json, summary_e6.json, fig11_fmm.png/.pdf;
all rows in data/derived/e6/rows.csv.gz.
"""

import argparse
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pvlib
import yaml

from solaris.core.params import REPO_ROOT
from solaris.pv import electrical as el
from solaris.pv import series
from solaris.pv.model import cell_temperature, pv_energy
from solaris.shading import parked
from solaris.shading.city import D
from solaris.site import site_config
from solaris.trajectory.schedules import schedules_config
from solaris.vehicle import facets, samples, vehicle_config
from solaris.weather import tmy_hourly

E6_YAML = REPO_ROOT / "configs" / "experiments" / "e6.yaml"
E3_YAML = REPO_ROOT / "configs" / "experiments" / "e3.yaml"
E4_YAML = REPO_ROOT / "configs" / "experiments" / "e4.yaml"
HEADING_DEG = {"N": 0, "E": 90, "S": 180, "W": 270}


def e3_module():
    p = REPO_ROOT / "experiments" / "e3_driving" / "run.py"
    spec = importlib.util.spec_from_file_location("e3_driving_run", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def facet_rows(vb, beam, diffuse, T, wind, facet, area, ec, dt_s, labels):
    """Rows (s, F_mm, energy Wh) for the sunny instants of one facet."""
    s = 1.0 - vb.mean(axis=1)
    g_mean = (1.0 - s) * beam + diffuse
    fa = vehicle_config()["pv"]["faiman"]
    tc = cell_temperature(g_mean, T, wind, "faiman", fa["u0"], fa["u1"])
    f = np.ones(len(s))
    nonuni = vb.max(axis=1) > vb.min(axis=1)
    if nonuni.any():
        f[nonuni] = el.mismatch(vb[nonuni], beam[nonuni], diffuse[nonuni], tc[nonuni], area, ec)
    wh = pv_energy(facet.area_m2, g_mean, tc) * 1000.0 * dt_s / 3600.0
    return pd.DataFrame(
        {**labels, "facet": facet.id, "s": s, "F_mm": f, "Wh": wh, "nonuniform": nonuni}
    )


def driving_rows(e6, vcfg, ec, tau):
    e3m = e3_module()
    e3 = yaml.safe_load(E3_YAML.read_text(encoding="utf-8"))
    cfg = site_config()
    wx, meta = tmy_hourly()
    trips = e3m.trip_ids(e3, routes=e6["driving"]["routes"])
    data = {t[0]: e3m.load_trip(t[0]) for t in trips}
    hz = e3m.position_horizons(data, cfg, e3["position_round_m"])
    lat, lon, alt = meta["latitude"], meta["longitude"], meta["altitude"]
    albedo = vcfg["pv"]["albedo"]
    out = []
    for trip, *_ in trips:
        f = data[trip]
        geo = e3m.TripGeometry(f, hz[trip], e3, cfg, vcfg)
        speed = f["speed"].to_numpy()
        cov = geo.cov
        for day in e3["days"]:
            times, sp = e3m.day_inputs(f, day, meta)
            bld, tree = geo.beam(sp["azimuth"].to_numpy(), sp["apparent_elevation"].to_numpy())
            zen = sp["apparent_zenith"].to_numpy()
            sun = {
                "zen": zen,
                "az": sp["azimuth"].to_numpy(),
                "el": sp["apparent_elevation"].to_numpy(),
                "extra": pvlib.irradiance.get_extra_radiation(times).to_numpy(),
                "am": np.asarray(pvlib.atmosphere.get_relative_airmass(zen), float),
            }
            hour = (times.dayofyear - 1) * 24 + times.hour
            T = wx["temp_air"].to_numpy()[hour]
            wind = wx["wind_speed"].to_numpy()[hour] + speed
            for sky in e6["driving"]["skies"]:
                ghi, dni, dhi = e3m.irradiance(times, sky, wx, lat, lon, alt)
                w = {"ghi": ghi, "dni": dni, "dhi": dhi}
                for fct in geo.fs:
                    k = geo.sid == fct.id
                    caz = (geo.heading + fct.azimuth_body_deg) % 360
                    beam, iso, hzc, ground, sunny = series.facet_terms(
                        fct.tilt_deg, caz, sun, w, albedo
                    )
                    v = geo.views[fct.id]
                    svf = v["svf_a"] + tau * (v["svf_b"] - v["svf_a"])
                    vhz = v["hz_a"] + tau * (v["hz_b"] - v["hz_a"])
                    vb = np.where(bld[:, k], 0.0, np.where(tree[:, k], tau, 1.0))
                    vb[cov] = 0.0
                    diffuse = np.where(cov, 0.0, svf * iso + vhz * hzc + ground)
                    sel = sunny & (beam > 0)
                    if not sel.any():
                        continue
                    out.append(
                        facet_rows(
                            vb[sel],
                            beam[sel],
                            diffuse[sel],
                            T[sel],
                            wind[sel],
                            fct,
                            el.cell_area(fct, vcfg),
                            ec,
                            1.0,
                            {"source": "driving", "case": f"{trip}|{day}|{sky}"},
                        )
                    )
        del geo
    return pd.concat(out, ignore_index=True)


def parking_rows(e6, vcfg, ec, tau):
    e4 = yaml.safe_load(E4_YAML.read_text(encoding="utf-8"))
    wtmy, meta = series.load_weather("tmy")
    step = e6["parking"]["step_min"] * 60
    t_s = np.arange(0, series.YEAR_S, step)
    sun = series.sun_at(t_s, meta, offset_s=step / 2)
    day = sun["el"] > 0
    t_s = t_s[day]
    sun = {k: a[day] for k, a in sun.items()}
    w = wtmy.at(t_s + step / 2)
    albedo = vcfg["pv"]["albedo"]
    out = []
    for site in e6["parking"]["sites"]:
        for hname in schedules_config()["headings"][site]:
            hdeg = HEADING_DEG[hname]
            mb, ma = parked.load_masks(site, hdeg)
            views = parked.facet_views(mb, ma, vcfg, hdeg, tau, e4["horizon_band_deg"])
            for v in views.values():
                fct = v["facet"]
                caz = (hdeg + fct.azimuth_body_deg) % 360
                beam, iso, hzc, ground, sunny = series.facet_terms(
                    fct.tilt_deg, caz, sun, w, albedo
                )
                sel = sunny & (beam > 0)
                vb = parked.sample_vb(mb, ma, v["idx"], sun["az"][sel], sun["el"][sel], tau)
                diffuse = v["svf"] * iso + v["vhz"] * hzc + ground
                out.append(
                    facet_rows(
                        vb,
                        beam[sel],
                        diffuse[sel],
                        w["temp_air"][sel],
                        w["wind_speed"][sel],
                        fct,
                        el.cell_area(fct, vcfg),
                        ec,
                        float(step),
                        {"source": "parking", "case": f"{site}-{hname}"},
                    )
                )
    return pd.concat(out, ignore_index=True)


def uniform_gate(vcfg, ec, g):
    """Uniform light: the substring/bypass string model must equal n_cells x the single-cell
    bishop88 MPP (the averaged model), and F_mm must be 1."""
    worst = 0.0
    for f in facets(vcfg):
        k = len(samples([f], vcfg["sample_spacing_m"]))
        a = el.cell_area(f, vcfg)
        G = np.repeat(np.asarray(g["irradiance"], float), len(g["temperature"]))
        T = np.tile(np.asarray(g["temperature"], float), len(g["irradiance"]))
        fm = el.mismatch(np.ones((len(G), k)), G, np.zeros(len(G)), T, a, ec)
        counts = np.zeros((len(G), ec["substrings_per_module"], 1))
        counts[:, :, 0] = np.bincount(el.substring_index(k, ec["substrings_per_module"]))
        p = el.module_mpp(G[:, None], counts, T, a, ec)
        ref = k * pvlib.singlediode.bishop88_mpp(*el.cell_params(G, T, a, ec))[2]
        worst = max(worst, float(np.max(np.abs(fm - 1))), float(np.max(np.abs(p / ref - 1))))
    return {"max_abs_dev": worst, "tol": g["tol"], "pass": bool(worst <= g["tol"])}


def fit_weights(rows):
    w = rows["Wh"].to_numpy().copy()
    for src in rows["source"].unique():
        m = (rows["source"] == src).to_numpy()
        w[m] /= w[m].sum()
    return w


def binned(rows, n_bins):
    edges = np.linspace(0, 1, n_bins + 1)
    out = []
    for src, g in [("all", rows), *rows.groupby("source")]:
        zero = g["s"] <= 0
        groups = [("0", 0.0, 0.0, g[zero])]
        b = np.clip(np.digitize(g["s"], edges[1:-1], right=True), 0, n_bins - 1)
        for i in range(n_bins):
            groups.append((str(i + 1), edges[i], edges[i + 1], g[~zero & (b == i)]))
        tot = g["Wh"].sum()
        for name, lo, hi, gg in groups:
            if len(gg) == 0:
                continue
            out.append(
                {
                    "source": src,
                    "bin": name,
                    "s_lo": lo,
                    "s_hi": hi,
                    "rows": len(gg),
                    "energy_share": gg["Wh"].sum() / tot,
                    "s_mean": np.average(gg["s"], weights=gg["Wh"])
                    if gg["Wh"].sum() > 0
                    else gg["s"].mean(),
                    "F_mm_mean": np.average(gg["F_mm"], weights=gg["Wh"])
                    if gg["Wh"].sum() > 0
                    else gg["F_mm"].mean(),
                    "F_mm_p10": gg["F_mm"].quantile(0.1),
                    "F_mm_p90": gg["F_mm"].quantile(0.9),
                }
            )
    return pd.DataFrame(out)


def figure(table, fit, stem):
    from solaris import figures

    plt = figures.style()
    fig, ax = plt.subplots(figsize=(4.6, 3.2))
    s = np.linspace(0, 1, 201)
    p = {k: fit[k] for k in ("k", "alpha", "beta")}
    ax.plot(s, el.fmm(s, **p), color=figures.INK, lw=1.5, zorder=3)
    ax.annotate(
        f"fit  1 − {p['k']:.2f} s^{p['alpha']:.2f} (1 − s)^{p['beta']:.2f}   R² {fit['r2']:.2f}",
        xy=(0.62, el.fmm(0.62, **p)),
        xytext=(0.28, 0.62),
        textcoords="axes fraction",
        fontsize=8,
        color=figures.INK2,
        arrowprops={"arrowstyle": "-", "color": figures.MUTED, "lw": 0.6},
    )
    for i, src in enumerate(("driving", "parking")):
        g = table[(table["source"] == src) & (table["bin"] != "0")]
        c = figures.SERIES[i]
        ax.plot(
            g["s_mean"],
            g["F_mm_mean"],
            "o",
            ms=4,
            color=c,
            mec=figures.SURFACE,
            mew=0.8,
            label={"driving": "R-DENSE trips (1 s)", "parking": "P2, P3 parked (5 min)"}[src],
        )
    ax.set_xlim(0, 1)
    ax.set_xlabel("Beam-shaded fraction of the facet, s")
    ax.set_ylabel("Mismatch factor F_mm")
    ax.legend(loc="upper center", fontsize=8)
    ax.set_title("Electrical mismatch vs shaded fraction (energy-weighted bin means)", loc="left")
    figures.save(fig, stem)
    plt.close(fig)


def main(out_table, out_fit, out_summary, out_fig):
    e6 = yaml.safe_load(E6_YAML.read_text(encoding="utf-8"))
    vcfg = vehicle_config()
    ec = el.electrical_config()
    tau = e6["tree_transmissivity"]
    gate = uniform_gate(vcfg, ec, e6["uniform_gate"])
    rows = pd.concat(
        [driving_rows(e6, vcfg, ec, tau), parking_rows(e6, vcfg, ec, tau)], ignore_index=True
    )
    w = fit_weights(rows)
    params, r2 = el.fit_fmm(rows["s"], rows["F_mm"], w)
    per_source = {}
    for src, g in rows.groupby("source"):
        ps, pr2 = el.fit_fmm(g["s"], g["F_mm"], g["Wh"])
        per_source[src] = {
            **{k: round(v, 5) for k, v in ps.items()},
            "r2": round(pr2, 4),
            "rows": len(g),
            "nonuniform_rows": int(g["nonuniform"].sum()),
            "F_mm_energy_weighted": round(float(np.average(g["F_mm"], weights=g["Wh"])), 5),
            "F_fit_energy_weighted": round(
                float(np.average(el.fmm(g["s"], **params), weights=g["Wh"])), 5
            ),
        }
    for case, g in rows[rows.source == "parking"].groupby("case"):
        per_source[f"parking|{case}"] = {
            "F_mm_energy_weighted": round(float(np.average(g["F_mm"], weights=g["Wh"])), 5)
        }
    table = binned(rows, e6["s_bins"])
    fit = {
        "form": el.FMM_FORM,
        **params,
        "r2": r2,
        "s": "beam-shaded area fraction of the facet, 1 - mean(v_b), while the beam reaches it",
        "weights": e6["fit_weights"],
    }
    for p in (out_table, out_fit, out_summary, out_fig):
        Path(p).parent.mkdir(parents=True, exist_ok=True)
    (D / "e6").mkdir(parents=True, exist_ok=True)
    rows.to_csv(D / "e6" / "rows.csv.gz", index=False, float_format="%.6g")
    table.to_csv(out_table, index=False, lineterminator="\n", float_format="%.6g")
    Path(out_fit).write_text(json.dumps(fit, indent=2) + "\n", encoding="utf-8", newline="\n")
    summary = {
        "uniform_gate": gate,
        "fit": {k: round(v, 5) if isinstance(v, float) else v for k, v in fit.items()},
        "by_source": per_source,
        "pass": gate["pass"],
    }
    Path(out_summary).write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    figure(table, fit, str(Path(out_fig).with_suffix("")))
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--table", default="results/e6/table_e6.csv")
    ap.add_argument("--fit", default="results/e6/fit_fmm.json")
    ap.add_argument("--summary", default="results/e6/summary_e6.json")
    ap.add_argument("--fig", default="results/e6/fig11_fmm.png")
    a = ap.parse_args()
    print(json.dumps(main(a.table, a.fit, a.summary, a.fig), indent=2))
