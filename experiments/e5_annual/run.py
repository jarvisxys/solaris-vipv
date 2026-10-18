"""E5: annual integration, the headline loss waterfall (workflow guide Sec. 5).

Archetypes A1-A4 (configs/schedules/archetypes.yaml) drive their trip hours every day on
replays of the frozen SUMO traces and park at their sites otherwise. Driving energy is
computed per second (E3 machinery: per-sample beam rays over the P3 rasters, facet sky
and horizon views from the roof-centre horizon, Faiman with wind + vehicle speed), parked
energy per 5-min step (E4 horizon masks, heading-averaged). Both are binned into the 8760
hours of the conference SoC loop (core.simulate, pv_kwh=), whose demand is the B0 scenario
with the archetype's trip hours.

Waterfall (configs/experiments/e5.yaml), each step changing only the harvest:
  B0 -> trip hours -> Perez chain + Faiman (11.6 m2 flat) -> facets (open sky)
  -> parking shade -> driving buildings -> driving trees -> electrical mismatch (E6 fit).
Energy balance, asserted for every archetype x weather x step (tolerance 0.1 %):
binned = fine-resolution energy, driving + parked seconds = 3600 per hour, and the SoC
loop's pack balance. Sensitivity for A1, A2: NSRDB 2023 hourly vs 5-min.

Outputs: results/e5/table_e5.csv, table_e5_hourly.csv.gz, summary_e5.json,
fig10_waterfall.png/.pdf, fig9_soc.png/.pdf.
"""

import argparse
import importlib.util
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from solaris import annual, core
from solaris.core.conference import SCENARIOS
from solaris.core.params import REPO_ROOT
from solaris.pv import electrical as el
from solaris.pv import series
from solaris.pv.model import cell_temperature, pv_energy
from solaris.shading import parked
from solaris.site import site_config
from solaris.trajectory import schedules as sch
from solaris.vehicle import facets, vehicle_config

E5_YAML = REPO_ROOT / "configs" / "experiments" / "e5.yaml"
E3_YAML = REPO_ROOT / "configs" / "experiments" / "e3.yaml"
E4_YAML = REPO_ROOT / "configs" / "experiments" / "e4.yaml"
FIT = REPO_ROOT / "results" / "e6" / "fit_fmm.json"
SITE = "Phoenix"
HEADING_DEG = {"N": 0, "E": 90, "S": 180, "W": 270}
DRIVE_CASES = ("flat", "open", "B", "C", "Cmm")
PARK_CASES = ("flat", "open", "site", "sitemm")
N_STEPS = 365 * 288


def log(msg):
    print(f"[e5 {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def e3_module():
    p = REPO_ROOT / "experiments" / "e3_driving" / "run.py"
    spec = importlib.util.spec_from_file_location("e3_driving_run", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def faiman(g, T, wind, vcfg):
    fa = vcfg["pv"]["faiman"]
    return cell_temperature(g, T, wind, "faiman", fa["u0"], fa["u1"])


# ---------------------------------------------------------------- driving, 1 s
def segment_frames(segs, e3m, demand):
    out = {}
    for seg in segs:
        traces = {
            d: e3m.load_trip(sch.trace_id(seg.route, d, seg.departure, demand))
            for d in ("fwd", "rev")
        }
        out[seg] = sch.replay(seg, traces.__getitem__)
    return out


def drive_segment(seg, f, hz, e3m, e3, cfg, vcfg, weathers, meta, days, tau, fit):
    """Hourly (8760) driving energy per (weather, case) of one segment over ``days``, the
    fine-resolution totals, and the driving seconds per hour."""
    geo = e3m.TripGeometry(f, hz, e3, cfg, vcfg)
    n = len(f)
    t_s = (days[:, None] * 86400 + f["clock_s"].to_numpy()[None, :]).ravel()
    sun = series.sun_at(t_s, meta)
    nd = len(days)
    vbB = {fc.id: np.zeros((nd, n)) for fc in geo.fs}
    vbC = {fc.id: np.zeros((nd, n)) for fc in geo.fs}
    az, elv = sun["az"].reshape(nd, n), sun["el"].reshape(nd, n)
    for i in range(nd):
        if not (elv[i] > 0).any():
            continue
        bld, tree = geo.beam(az[i], elv[i])
        for fc in geo.fs:
            k = geo.sid == fc.id
            vbB[fc.id][i] = (~bld[:, k]).mean(axis=1)
            vbC[fc.id][i] = np.where(bld[:, k], 0.0, np.where(tree[:, k], tau, 1.0)).mean(axis=1)
    cov = np.tile(geo.cov, nd)
    heading = np.tile(geo.heading, nd)
    speed = np.tile(f["speed"].to_numpy(), nd)
    albedo = vcfg["pv"]["albedo"]
    area_flat = sum(fc.area_m2 for fc in geo.fs)
    hourly, fine = {}, {}
    for wname, W in weathers.items():
        w = W.at(t_s)
        T, wind = w["temp_air"], w["wind_speed"] + speed
        e = {c: np.zeros(len(t_s)) for c in DRIVE_CASES}
        b, i_, h_, g_, _ = series.facet_terms(0.0, 180.0, sun, w, albedo)
        g = b + i_ + h_ + g_
        e["flat"] = pv_energy(area_flat, g, faiman(g, T, wind, vcfg)) / 3600.0
        for fc in geo.fs:
            caz = (heading + fc.azimuth_body_deg) % 360
            beam, iso, hzc, ground, sunny = series.facet_terms(fc.tilt_deg, caz, sun, w, albedo)
            v = {k: np.tile(a, nd) for k, a in geo.views[fc.id].items()}
            ground_c = np.where(cov, 0.0, ground)
            vb_b = np.where(cov, 0.0, vbB[fc.id].ravel())
            vb_c = np.where(cov, 0.0, vbC[fc.id].ravel())
            svf_c = v["svf_a"] + tau * (v["svf_b"] - v["svf_a"])
            hz_c = v["hz_a"] + tau * (v["hz_b"] - v["hz_a"])
            gs = {
                "open": beam + iso + hzc + ground,
                "B": vb_b * beam
                + np.where(cov, 0, v["svf_b"]) * iso
                + np.where(cov, 0, v["hz_b"]) * hzc
                + ground_c,
                "C": vb_c * beam
                + np.where(cov, 0, svf_c) * iso
                + np.where(cov, 0, hz_c) * hzc
                + ground_c,
            }
            for c, gg in gs.items():
                ec = pv_energy(fc.area_m2, gg, faiman(gg, T, wind, vcfg)) / 3600.0
                e[c] += ec
                if c == "C":
                    s = np.where(sunny & (beam > 0), 1.0 - vb_c, 0.0)
                    e["Cmm"] += ec * el.fmm(s, **fit)
        for c in DRIVE_CASES:
            hourly[(wname, c)] = annual.bin_hourly(t_s, e[c])
            fine[(wname, c)] = float(e[c].sum())
    secs = annual.bin_hourly(t_s, np.ones(len(t_s)))
    del geo
    return hourly, fine, secs


# ---------------------------------------------------------------- parked, 5 min
def park_site(site, headings, vcfg, weathers, meta, step_s, tau, band_deg, fit, keep):
    """Per 5-min step of the year (N_STEPS), heading-averaged parked energy (kWh) per
    (weather, case) for one site; zero at night and on days not in ``keep``."""
    t_s = np.arange(N_STEPS) * step_s
    sun = series.sun_at(t_s, meta, offset_s=step_s / 2)
    day = (sun["el"] > 0) & keep
    sun_d = {k: a[day] for k, a in sun.items()}
    albedo = vcfg["pv"]["albedo"]
    dt_h = step_s / 3600.0
    out = {}
    for wname, W in weathers.items():
        w = W.at(t_s[day] + step_s / 2)
        T, wind = w["temp_air"], w["wind_speed"]
        acc = {c: np.zeros(day.sum()) for c in PARK_CASES}
        b, i_, h_, g_, _ = series.facet_terms(0.0, 180.0, sun_d, w, albedo)
        g = b + i_ + h_ + g_
        acc["flat"] = (
            pv_energy(sum(f.area_m2 for f in facets(vcfg)), g, faiman(g, T, wind, vcfg)) * dt_h
        )
        for hname in headings:
            hdeg = HEADING_DEG[hname]
            mb, ma = parked.load_masks(site, hdeg)
            views = parked.facet_views(mb, ma, vcfg, hdeg, tau, band_deg)
            for v in views.values():
                fc = v["facet"]
                caz = (hdeg + fc.azimuth_body_deg) % 360
                beam, iso, hzc, ground, sunny = series.facet_terms(
                    fc.tilt_deg, caz, sun_d, w, albedo
                )
                vb = parked.sample_vb(mb, ma, v["idx"], sun_d["az"], sun_d["el"], tau).mean(axis=1)
                g_open = beam + iso + hzc + ground
                g_site = vb * beam + v["svf"] * iso + v["vhz"] * hzc + ground
                e_open = pv_energy(fc.area_m2, g_open, faiman(g_open, T, wind, vcfg)) * dt_h
                e_site = pv_energy(fc.area_m2, g_site, faiman(g_site, T, wind, vcfg)) * dt_h
                s = np.where(sunny & (beam > 0), 1.0 - vb, 0.0)
                acc["open"] += e_open / len(headings)
                acc["site"] += e_site / len(headings)
                acc["sitemm"] += e_site * el.fmm(s, **fit) / len(headings)
        for c in PARK_CASES:
            full = np.zeros(N_STEPS)
            full[day] = acc[c]
            out[(wname, c)] = full
    return out


def archetype_parking(arch, days, step_min):
    """Per 5-min step of the year: site and parked fraction (0 on days not in ``days``)."""
    site = np.empty(N_STEPS, object)
    frac = np.zeros(N_STEPS)
    steps = {w: sch.day_steps(arch, w, step_min) for w in (False, True)}
    for d in days:
        wk = (series.YEAR_START + pd.Timedelta(days=int(d))).weekday() >= 5
        s = steps[wk]
        site[d * 288 : (d + 1) * 288] = s["site"].to_numpy()
        frac[d * 288 : (d + 1) * 288] = s["parked_frac"].to_numpy()
    return site, frac


# ---------------------------------------------------------------- SoC loop
def pv_conference(climate, p=core.BASE):
    """Annual conference flat-GHI PV (kWh), as core.simulate computes it."""
    ghi, T = climate
    pcell = T + p.cell_temp_rise * (ghi / 1000.0)
    return float(
        (p.A_skin * p.eta_pv * (ghi / 1000.0) * p.kappa_pv * (1 + p.beta * (pcell - 25))).sum()
    )


def metrics(r):
    return {
        "fss": r["fss"],
        "grid_kWh": r["grid_kwh"],
        "charges_per_yr": r["charges"],
        "relief_conference_pct": 100 * (r["ann_dem"] - r["grid_kwh"]) / r["ann_dem"],
        "relief_balanced_pct": 100 * r["harvest_used_kwh"] / r["ann_dem"],
        "demand_kWh": r["ann_dem"],
        "curtailed_kWh": r["curtailed_kwh"],
    }


def run_archetype(arch, wname, W, steps, drive_h, drive_fine, drive_secs, park, days, e5):
    km, city = sch.scenario(arch)
    p = sch.archetype_params(arch)
    climate = W.hourly_climate()
    segs = sch.segments(arch)
    site_arr, frac = archetype_parking(arch, days, e5["step_min"])
    step_s = e5["step_min"] * 60
    t_steps = np.arange(N_STEPS) * step_s
    secs_drive = sum(drive_secs[s] for s in segs)
    secs_park = annual.bin_hourly(t_steps, frac * step_s)
    hours = (days[:, None] * 24 + np.arange(24)[None, :]).ravel()
    annual.assert_time_closure(secs_drive[hours], secs_park[hours])
    rows, traces, max_rel = [], {}, 0.0
    for st in steps:
        if st["drive"] is None:
            r = core.simulate(
                SITE, km, city, climate=climate, p=core.BASE if st["id"] == "B0" else p
            )
            pv_h, pv_fine, e_drive, e_park = None, np.nan, np.nan, np.nan
        else:
            d_h = sum(drive_h[s][(wname, st["drive"])] for s in segs)
            d_fine = sum(drive_fine[s][(wname, st["drive"])] for s in segs)
            e_steps = np.zeros(N_STEPS)
            for site in set(site_arr[frac > 0]):
                m = site_arr == site
                e_steps[m] = frac[m] * park[site][(wname, st["park"])][m]
            p_h = annual.bin_hourly(t_steps, e_steps)
            pv_h = d_h + p_h
            pv_fine = d_fine + float(e_steps.sum())
            rel = annual.assert_closure(
                pv_fine, pv_h, f"{arch} {wname} {st['id']}", e5["closure_tol"]
            )
            max_rel = max(max_rel, rel)
            e_drive, e_park = float(d_h.sum()), float(p_h.sum())
            r = core.simulate(SITE, km, city, climate=climate, p=p, pv_kwh=pv_h)
        pack = annual.assert_pack_balance(r, f"{arch} {wname} {st['id']}", e5["closure_tol"])
        max_rel = max(max_rel, pack)
        rows.append(
            {
                "archetype": arch,
                "weather": wname,
                "step": st["id"],
                "label": st["label"],
                "pv_kWh_yr": float(pv_h.sum()) if pv_h is not None else pv_conference(climate),
                "pv_drive_kWh": e_drive,
                "pv_park_kWh": e_park,
                **metrics(r),
                "energy_closure_rel": annual.rel(pv_fine, pv_h.sum()) if pv_h is not None else 0.0,
                "pack_balance_rel": pack,
            }
        )
        traces[st["id"]] = (pv_h, r["soc"])
    return rows, traces, max_rel


# ---------------------------------------------------------------- figures
def fig_waterfall(table, steps, stem):
    from solaris import figures

    plt = figures.style()
    t = table[table["weather"] == "tmy"]
    archs = list(dict.fromkeys(t["archetype"]))
    fig, axes = plt.subplots(1, len(archs), figsize=(3.0 * len(archs), 3.6), sharey=False)
    labels = [s["label"] for s in steps] + ["Archetype"]
    for ax, a in zip(np.atleast_1d(axes), archs, strict=True):
        f = t[t["archetype"] == a].set_index("step")["fss"]
        vals = [f[s["id"]] for s in steps]
        x = np.arange(len(labels))
        ax.bar(0, vals[0], color=figures.SERIES[0], width=0.7)
        for i in range(1, len(vals)):
            d = vals[i] - vals[i - 1]
            ax.bar(
                i,
                d,
                bottom=vals[i - 1],
                width=0.7,
                color=figures.SERIES[1] if d < 0 else figures.SERIES[2],
            )
            if abs(d) >= 0.005:
                ax.text(
                    i,
                    max(vals[i], vals[i - 1]) + 0.012,
                    f"{d:+.3f}",
                    ha="center",
                    va="bottom",
                    fontsize=6.5,
                    color=figures.INK2,
                )
        ax.bar(len(vals), vals[-1], color=figures.SERIES[0], width=0.7)
        ax.text(0, vals[0] + 0.012, f"{vals[0]:.3f}", ha="center", fontsize=7, color=figures.INK)
        ax.text(
            len(vals),
            vals[-1] + 0.012,
            f"{vals[-1]:.3f}",
            ha="center",
            fontsize=7,
            color=figures.INK,
        )
        ax.set_xticks(x, labels, rotation=60, ha="right", fontsize=7)
        ax.set_ylim(0, max(vals) * 1.15)
        ax.grid(axis="x", visible=False)
        name = sch.schedules_config()["archetypes"][a]["name"]
        ax.set_title(f"{a} {name}", loc="left", fontsize=8.5)
    np.atleast_1d(axes)[0].set_ylabel("Solar self-sufficiency f_ss")
    fig.suptitle(
        "Loss waterfall from Table B0 to each archetype (Phoenix, measured TMY)",
        x=0.01,
        ha="left",
        fontsize=10,
        color=figures.INK,
    )
    fig.tight_layout()
    figures.save(fig, stem)
    plt.close(fig)


def fig_soc(traces, stem):
    from solaris import figures

    plt = figures.style()
    archs = list(traces)
    fig, axes = plt.subplots(len(archs), 1, figsize=(6.4, 1.6 * len(archs)), sharex=True)
    days = np.arange(365)
    for ax, a in zip(np.atleast_1d(axes), archs, strict=True):
        for i, (key, lab) in enumerate((("B0", "Table B0"), ("mismatch", "Archetype, all losses"))):
            soc = traces[a][key][1][1:].reshape(365, 24).min(axis=1)
            ax.plot(days, soc, color=figures.SERIES[i], lw=1.0, label=lab)
        ax.set_ylim(0, 100)
        ax.set_ylabel("Daily min SoC, %", fontsize=7.5)
        ax.set_title(a, loc="left", fontsize=8.5)
    np.atleast_1d(axes)[-1].set_xlabel("Day of year")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    handles, labels = np.atleast_1d(axes)[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right", ncol=2, fontsize=7.5)
    fig.suptitle("Daily minimum SoC, Table B0 vs archetype", x=0.01, ha="left", fontsize=10)
    figures.save(fig, stem)
    plt.close(fig)


# ---------------------------------------------------------------- main
def main(out_table, out_hourly, out_summary, out_fig_waterfall, out_fig_soc, day_stride=None):
    e5 = yaml.safe_load(E5_YAML.read_text(encoding="utf-8"))
    e3 = yaml.safe_load(E3_YAML.read_text(encoding="utf-8"))
    e4 = yaml.safe_load(E4_YAML.read_text(encoding="utf-8"))
    scfg = sch.schedules_config()
    cfg, vcfg = site_config(), vehicle_config()
    fit_all = json.loads(FIT.read_text(encoding="utf-8"))
    fit = {k: fit_all[k] for k in ("k", "alpha", "beta")}
    tau = e5["tree_transmissivity"]
    stride = day_stride or e5["day_stride"]
    days = np.arange(0, 365, stride)
    keep = np.zeros(N_STEPS, bool)
    for d in days:
        keep[d * 288 : (d + 1) * 288] = True
    archs = e5["archetypes"]
    wnames = [e5["weather"], *e5["sensitivity"]["weather"]]
    weathers, meta = {}, None
    for w in wnames:
        weathers[w], m = series.load_weather(w)
        meta = meta or m
    for a in archs:
        if SCENARIOS[scfg["archetypes"][a]["scenario"]] != sch.scenario(a):
            raise ValueError(a)

    e3m = e3_module()
    segs = sorted({s for a in archs for s in sch.segments(a)}, key=lambda s: (s.start_s, s.route))
    frames = segment_frames(segs, e3m, scfg["demand_seed"])
    log(
        f"{len(segs)} driving segments, {sum(len(f) for f in frames.values())} s per day, "
        f"{len(days)} days"
    )
    hz = e3m.position_horizons(frames, cfg, e3["position_round_m"])
    drive_h, drive_fine, drive_secs = {}, {}, {}
    for i, seg in enumerate(segs):
        t0 = time.time()
        drive_h[seg], drive_fine[seg], drive_secs[seg] = drive_segment(
            seg, frames[seg], hz[seg], e3m, e3, cfg, vcfg, weathers, meta, days, tau, fit
        )
        log(
            f"segment {i + 1}/{len(segs)} {seg.route} {seg.first} @{seg.start_s / 3600:.2f} h "
            f"{seg.duration_s} s: {time.time() - t0:.0f} s"
        )
    sites = sorted({s for a in archs for s in sch.sites_used(a)})
    park = {}
    for site in sites:
        t0 = time.time()
        park[site] = park_site(
            site,
            scfg["headings"][site],
            vcfg,
            weathers,
            meta,
            e5["step_min"] * 60,
            tau,
            e4["horizon_band_deg"],
            fit,
            keep,
        )
        log(f"parked {site}: {time.time() - t0:.0f} s")

    rows, traces, worst = [], {}, 0.0
    for a in archs:
        for w in wnames:
            if w != e5["weather"] and a not in e5["sensitivity"]["archetypes"]:
                continue
            r, tr, mr = run_archetype(
                a, w, weathers[w], e5["steps"], drive_h, drive_fine, drive_secs, park, days, e5
            )
            rows += r
            worst = max(worst, mr)
            if w == e5["weather"]:
                traces[a] = tr
    table = pd.DataFrame(rows)
    table["delta_fss"] = table.groupby(["archetype", "weather"])["fss"].diff()

    hourly = {}
    for a, tr in traces.items():
        for s, (pv, _soc) in tr.items():
            if pv is not None:
                hourly[f"{a}|{s}|pv_kWh"] = pv
        hourly[f"{a}|B0|soc_pct"] = tr["B0"][1][1:]
        hourly[f"{a}|mismatch|soc_pct"] = tr["mismatch"][1][1:]
    for p in (out_table, out_hourly, out_summary, out_fig_waterfall, out_fig_soc):
        Path(p).parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(out_table, index=False, lineterminator="\n", float_format="%.6g")
    pd.DataFrame(hourly).rename_axis("hour").to_csv(out_hourly, float_format="%.5g")

    base = table[table.weather == e5["weather"]]
    summary = {
        "days": int(len(days)),
        "energy_balance": {
            "max_rel": worst,
            "tol": e5["closure_tol"],
            "pass": bool(worst <= e5["closure_tol"]),
        },
        "fss": {
            a: {s: round(float(v), 4) for s, v in g.set_index("step")["fss"].items()}
            for a, g in base.groupby("archetype")
        },
        "charges_per_yr": {
            a: {s: int(v) for s, v in g.set_index("step")["charges_per_yr"].items()}
            for a, g in base.groupby("archetype")
        },
        "fmm_fit": {k: fit_all[k] for k in ("form", "k", "alpha", "beta", "r2")},
    }
    sens = {}
    for a in e5["sensitivity"]["archetypes"]:
        g = table[table.archetype == a].pivot(index="step", columns="weather", values="fss")
        h, m = e5["sensitivity"]["weather"]
        sens[a] = {
            "fss_final": {w: round(float(g.loc["mismatch", w]), 4) for w in g.columns},
            "year_effect_tmy_minus_2023_hourly": round(
                float(g.loc["mismatch", e5["weather"]] - g.loc["mismatch", h]), 4
            ),
            "resolution_effect_5min_minus_hourly": round(
                float(g.loc["mismatch", m] - g.loc["mismatch", h]), 4
            ),
            "resolution_effect_by_step": {
                s: round(float(g.loc[s, m] - g.loc[s, h]), 4) for s in g.index
            },
        }
    summary["sensitivity_subhourly"] = sens
    summary["pass"] = summary["energy_balance"]["pass"]
    Path(out_summary).write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    fig_waterfall(table, e5["steps"], str(Path(out_fig_waterfall).with_suffix("")))
    fig_soc(traces, str(Path(out_fig_soc).with_suffix("")))
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--table", default="results/e5/table_e5.csv")
    ap.add_argument("--hourly", default="results/e5/table_e5_hourly.csv.gz")
    ap.add_argument("--summary", default="results/e5/summary_e5.json")
    ap.add_argument("--waterfall", default="results/e5/fig10_waterfall.png")
    ap.add_argument("--soc", default="results/e5/fig9_soc.png")
    ap.add_argument("--day-stride", type=int, default=None)
    a = ap.parse_args()
    print(
        json.dumps(main(a.table, a.hourly, a.summary, a.waterfall, a.soc, a.day_stride), indent=2)
    )
