"""E7: design sensitivity and shading-aware inversion (workflow guide Sec. 5).

Two stages.

facet_series (long, ~E5 run time): the E5 machinery run one facet at a time on the TMY, so
every archetype has an 8760-h PV series per facet and per waterfall step. Driving reuses
E5's drive_segment with a one-facet vehicle; parking repeats E5's park_site loop keyed by
facet (the E4 masks are indexed over all samples). The facet sums must reproduce E5.

inversion (fast): from those series,
  - sweep: area (8, 11.6, 15, 20 m2) x allocation (roof, roof + hood, full skin) x kappa_pv
    (0.60-0.80) x archetype through the SoC loop, area scaled over the allocated facets,
    mass fed back;
  - extended Eq. (2): A_req = (D c + E_aux) / (eta_pv PSH kappa f_T F_geo F_sh F_mm) per
    archetype and allocation, checked against the area at which the full simulation
    reaches f_ss = 1 (gate 3 %);
  - Fig. 12 nomograph: A_req vs daily distance, one curve per archetype, and f_ss vs area.

Outputs: results/e7/table_e7_facet_hourly.csv.gz, table_e7_facets.csv, table_e7_sweep.csv,
table_e7_inversion.csv, table_e7_nomograph.csv, summary_e7.json, fig12_nomograph.png/.pdf.
"""

import argparse
import importlib.util
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy.optimize import brentq

from solaris import core, design
from solaris.core.conference import SCENARIOS
from solaris.core.params import REPO_ROOT
from solaris.pv import electrical as el
from solaris.pv import series
from solaris.pv.model import pv_energy
from solaris.shading import parked
from solaris.site import site_config
from solaris.trajectory import schedules as sch
from solaris.vehicle import facets, vehicle_config

E7_YAML = REPO_ROOT / "configs" / "experiments" / "e7.yaml"
E5_YAML = REPO_ROOT / "configs" / "experiments" / "e5.yaml"
E5_TABLE = REPO_ROOT / "results" / "e5" / "table_e5.csv"
E5_HOURLY = REPO_ROOT / "results" / "e5" / "table_e5_hourly.csv.gz"
SITE = "Phoenix"
STEPS = ("chain", "facets", "parking", "buildings", "trees", "mismatch")


def log(msg):
    print(f"[e7 {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def load_yaml(path):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def e5_module():
    p = REPO_ROOT / "experiments" / "e5_annual" / "run.py"
    spec = importlib.util.spec_from_file_location("e5_annual_run", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ---------------------------------------------------------------- stage 1: facet series
def park_site_facets(site, headings, vcfg, wname, W, meta, step_s, tau, band_deg, fit, e5m):
    """e5.park_site for every day, with the energy kept per facet: {facet id: {(weather,
    case): 5-min series}}; the facet sum is park_site's output."""
    t_s = np.arange(e5m.N_STEPS) * step_s
    sun = series.sun_at(t_s, meta, offset_s=step_s / 2)
    day = sun["el"] > 0
    sun_d = {k: a[day] for k, a in sun.items()}
    albedo = vcfg["pv"]["albedo"]
    dt_h = step_s / 3600.0
    w = W.at(t_s[day] + step_s / 2)
    T, wind = w["temp_air"], w["wind_speed"]
    fs = facets(vcfg)
    acc = {f.id: {c: np.zeros(day.sum()) for c in e5m.PARK_CASES} for f in fs}
    b, i_, h_, g_, _ = series.facet_terms(0.0, 180.0, sun_d, w, albedo)
    g = b + i_ + h_ + g_
    for f in fs:
        acc[f.id]["flat"] = pv_energy(f.area_m2, g, e5m.faiman(g, T, wind, vcfg)) * dt_h
    for hname in headings:
        hdeg = e5m.HEADING_DEG[hname]
        mb, ma = parked.load_masks(site, hdeg)
        views = parked.facet_views(mb, ma, vcfg, hdeg, tau, band_deg)
        for fid, v in views.items():
            fc = v["facet"]
            caz = (hdeg + fc.azimuth_body_deg) % 360
            beam, iso, hzc, ground, sunny = series.facet_terms(fc.tilt_deg, caz, sun_d, w, albedo)
            vb = parked.sample_vb(mb, ma, v["idx"], sun_d["az"], sun_d["el"], tau).mean(axis=1)
            g_open = beam + iso + hzc + ground
            g_site = vb * beam + v["svf"] * iso + v["vhz"] * hzc + ground
            e_open = pv_energy(fc.area_m2, g_open, e5m.faiman(g_open, T, wind, vcfg)) * dt_h
            e_site = pv_energy(fc.area_m2, g_site, e5m.faiman(g_site, T, wind, vcfg)) * dt_h
            s = np.where(sunny & (beam > 0), 1.0 - vb, 0.0)
            acc[fid]["open"] += e_open / len(headings)
            acc[fid]["site"] += e_site / len(headings)
            acc[fid]["sitemm"] += e_site * el.fmm(s, **fit) / len(headings)
    out = {}
    for fid, cases in acc.items():
        out[fid] = {}
        for c, a in cases.items():
            full = np.zeros(e5m.N_STEPS)
            full[day] = a
            out[fid][(wname, c)] = full
    return out


def check_against_e5(per, archs, tol=1e-5):
    """Facet sums vs E5: annual totals (table_e5.csv, 6 significant digits) and hourly
    series (table_e5_hourly.csv.gz, 5 significant digits)."""
    t = pd.read_csv(E5_TABLE)
    t = t[t.weather == "tmy"].set_index(["archetype", "step"])["pv_kWh_yr"]
    h = pd.read_csv(E5_HOURLY, index_col="hour")
    worst_a, worst_h = 0.0, 0.0
    for a in archs:
        for st in STEPS:
            s = sum(per[(a, fid, st)] for fid in {k[1] for k in per if k[0] == a})
            worst_a = max(worst_a, abs(s.sum() / t.loc[(a, st)] - 1))
            ref = h[f"{a}|{st}|pv_kWh"].to_numpy()
            worst_h = max(worst_h, float(np.max(np.abs(s - ref) / np.maximum(np.abs(ref), 1e-3))))
    return {
        "max_rel_annual": worst_a,
        "max_rel_hourly": worst_h,
        "tol_annual": tol,
        "tol_hourly": 1e-4,
        "pass": bool(worst_a <= tol and worst_h <= 1e-4),
    }


def facet_series(out_hourly, out_facets, out_check, day_stride=1):
    """day_stride > 1 is for development only: it skips the check against E5."""
    e5m = e5_module()
    e7, e5 = load_yaml(E7_YAML), load_yaml(E5_YAML)
    e3, e4 = load_yaml(e5m.E3_YAML), load_yaml(e5m.E4_YAML)
    scfg = sch.schedules_config()
    cfg, vcfg = site_config(), vehicle_config()
    fit_all = json.loads(e5m.FIT.read_text(encoding="utf-8"))
    fit = {k: fit_all[k] for k in ("k", "alpha", "beta")}
    tau = e5["tree_transmissivity"]
    days = np.arange(0, 365, day_stride)
    wname = e7["weather"]
    W, meta = series.load_weather(wname)
    archs = e7["archetypes"]
    for a in archs:
        if SCENARIOS[scfg["archetypes"][a]["scenario"]] != sch.scenario(a):
            raise ValueError(a)
    e3m = e5m.e3_module()
    segs = sorted({s for a in archs for s in sch.segments(a)}, key=lambda s: (s.start_s, s.route))
    frames = e5m.segment_frames(segs, e3m, scfg["demand_seed"])
    hz = e3m.position_horizons(frames, cfg, e3["position_round_m"])
    log(f"{len(segs)} driving segments, {len(days)} days")
    fs = facets(vcfg)
    drive_h, drive_fine, drive_secs = {f.id: {} for f in fs}, {f.id: {} for f in fs}, {}
    for f_raw, f in zip(vcfg["facets"], fs, strict=True):
        one = {**vcfg, "facets": [f_raw]}
        t0 = time.time()
        for seg in segs:
            drive_h[f.id][seg], drive_fine[f.id][seg], drive_secs[seg] = e5m.drive_segment(
                seg, frames[seg], hz[seg], e3m, e3, cfg, one, {wname: W}, meta, days, tau, fit
            )
        log(f"driving, facet {f.id}: {time.time() - t0:.0f} s")
    sites = sorted({s for a in archs for s in sch.sites_used(a)})
    park = {f.id: {} for f in fs}
    for site in sites:
        t0 = time.time()
        by_f = park_site_facets(
            site,
            scfg["headings"][site],
            vcfg,
            wname,
            W,
            meta,
            e5["step_min"] * 60,
            tau,
            e4["horizon_band_deg"],
            fit,
            e5m,
        )
        for fid, d in by_f.items():
            park[fid][site] = d
        log(f"parked {site}: {time.time() - t0:.0f} s")

    per, rows = {}, []
    for a in archs:
        for f in fs:
            r, tr, _ = e5m.run_archetype(
                a, wname, W, e5["steps"], drive_h[f.id], drive_fine[f.id], drive_secs,
                park[f.id], days, e5,
            )  # fmt: skip
            for row in r:
                if row["step"] in STEPS:
                    rows.append(
                        {
                            "archetype": a,
                            "facet": f.id,
                            "area_m2": f.area_m2,
                            "step": row["step"],
                            "pv_kWh_yr": row["pv_kWh_yr"],
                            "pv_drive_kWh": row["pv_drive_kWh"],
                            "pv_park_kWh": row["pv_park_kWh"],
                        }
                    )
            for st in STEPS:
                per[(a, f.id, st)] = tr[st][0]
    check = check_against_e5(per, archs) if day_stride == 1 else {"pass": None, "dev": day_stride}
    log(f"facet sums vs E5: {check}")
    if check["pass"] is False:
        raise AssertionError(f"facet sums do not reproduce E5: {check}")
    for p in (out_hourly, out_facets, out_check):
        Path(p).parent.mkdir(parents=True, exist_ok=True)
    keep = ("chain", "facets", "trees", "mismatch")
    hourly = {f"{a}|{fid}|{st}": v for (a, fid, st), v in per.items() if st in keep}
    pd.DataFrame(hourly).rename_axis("hour").to_csv(out_hourly, float_format="%.6g")
    pd.DataFrame(rows).to_csv(out_facets, index=False, lineterminator="\n", float_format="%.6g")
    Path(out_check).write_text(json.dumps(check, indent=2) + "\n", encoding="utf-8", newline="\n")
    return check


# ---------------------------------------------------------------- stage 2: inversion
def conference_pv_per_m2(climate, p=core.BASE):
    ghi, T = climate
    pcell = T + p.cell_temp_rise * (ghi / 1000.0)
    return float((p.eta_pv * (ghi / 1000.0) * p.kappa_pv * (1 + p.beta * (pcell - 25))).sum())


class Archetype:
    """One archetype's demand side and per-facet final PV, ready for the SoC loop."""

    def __init__(self, a, H, areas, climate, e7):
        self.a = a
        self.km, self.city = sch.scenario(a)
        self.p = sch.archetype_params(a)
        self.climate = climate
        self.areas = areas
        self.mass_feedback = e7["mass_feedback"]
        steps = e7["loss_steps"]
        self.series = {
            k: {f: H[f"{a}|{f}|{st}"].to_numpy() for f in areas} for k, st in steps.items()
        }

    def energy(self, ids):
        return {k: float(sum(s[f].sum() for f in ids)) for k, s in self.series.items()}

    def simulate(self, ids, A, kappa, mass_feedback=None):
        mf = self.mass_feedback if mass_feedback is None else mass_feedback
        pv = design.allocation_series(self.series["mismatch"], ids, self.areas, A)
        return core.simulate(
            SITE,
            self.km,
            self.city,
            climate=self.climate,
            p=self.p,
            pv_kwh=pv * kappa / self.p.kappa_pv,
            m_over=design.design_mass(A, self.p) if mf else None,
        )

    def area_for_fss1(self, ids, kappa, mass_feedback=None, A_max=1000.0):
        """Area at which the SoC loop reaches f_ss = 1 (NaN if not below A_max: with mass
        fed back, f_ss saturates as the area grows)."""

        def gap(A):
            return self.simulate(ids, A, kappa, mass_feedback)["fss"] - 1.0

        if gap(A_max) < 0:
            return float("nan")
        return float(brentq(gap, 0.5, A_max, xtol=1e-6))


def inversion(
    hourly,
    out_sweep,
    out_inversion,
    out_nomograph,
    out_summary,
    out_fig,
    check_path=None,
    out_fss_area=None,
):
    e7 = load_yaml(E7_YAML)
    W, _ = series.load_weather(e7["weather"])
    climate = W.hourly_climate()
    H = pd.read_csv(hourly, index_col="hour")
    areas = {f.id: f.area_m2 for f in facets(vehicle_config())}
    conf_m2 = conference_pv_per_m2(climate)
    p0 = core.BASE
    sweep, inv, factors = [], [], {}
    archs = {a: Archetype(a, H, areas, climate, e7) for a in e7["archetypes"]}
    for a, X in archs.items():
        factors[a] = {}
        for alloc, ids in e7["allocations"].items():
            a0 = sum(areas[i] for i in ids)
            e = X.energy(ids)
            F = design.loss_factors(e)
            factors[a][alloc] = {
                "area_m2": a0,
                **{k: round(v, 4) for k, v in F.items()},
                "F_chain": round(e["chain"] / (a0 * conf_m2), 4),
                "pv_final_kWh_m2_yr": round(e["mismatch"] / a0, 2),
            }
            for kappa in e7["kappa"]:
                A_cf = design.required_area(X.km, X.city, climate, kappa=kappa, p=X.p, **F)
                A_sim = X.area_for_fss1(ids, kappa)
                A_fix = X.area_for_fss1(ids, kappa, mass_feedback=False)
                inv.append(
                    {
                        "archetype": a,
                        "allocation": alloc,
                        "kappa": kappa,
                        "km_day": X.km,
                        "city": X.city,
                        **F,
                        "A_req_closed_m2": A_cf,
                        "A_fss1_sim_m2": A_sim,
                        "rel_err": A_cf / A_sim - 1,
                        "A_fss1_sim_fixed_mass_m2": A_fix,
                        "rel_err_fixed_mass": A_cf / A_fix - 1,
                        "D_max_km_day_11p6": design.max_distance(
                            p0.A_skin, X.city, climate, kappa=kappa, p=X.p, **F
                        ),
                    }
                )
                for A in e7["areas_m2"]:
                    r = X.simulate(ids, A, kappa)
                    sweep.append(
                        {
                            "archetype": a,
                            "allocation": alloc,
                            "A_m2": A,
                            "kappa": kappa,
                            "mass_kg": design.design_mass(A, X.p),
                            "fss": r["fss"],
                            "grid_kWh": r["grid_kwh"],
                            "charges_per_yr": r["charges"],
                            "relief_pct": 100 * r["relief"],
                            "curtailed_kWh": r["curtailed_kwh"],
                        }
                    )
        log(f"{a}: sweep and inversion done")
    inv_t, sweep_t = pd.DataFrame(inv), pd.DataFrame(sweep)

    nm = e7["nomograph"]
    ids = e7["allocations"][nm["allocation"]]
    kms = np.arange(nm["km"][0], nm["km"][1] + 1e-9, nm["km"][2])
    A_grid = np.arange(nm["area_m2"][0], nm["area_m2"][1] + 1e-9, nm["area_m2"][2])
    nomo = []
    for a, X in archs.items():
        F = design.loss_factors(X.energy(ids))
        for d in kms:
            nomo.append(
                {
                    "curve": a,
                    "km_day": d,
                    "A_req_m2": design.required_area(
                        d, X.city, climate, kappa=nm["kappa"], p=X.p, **F
                    ),
                }
            )
    for sc, (_km, city) in SCENARIOS.items():
        for d in kms:
            nomo.append(
                {
                    "curve": f"B0-{sc}",
                    "km_day": d,
                    "A_req_m2": design.required_area(d, city, climate, kappa=nm["kappa"]),
                }
            )
    nomo_t = pd.DataFrame(nomo)
    fss_vs_A = {
        a: [X.simulate(ids, A, nm["kappa"])["fss"] for A in A_grid] for a, X in archs.items()
    }

    tol = e7["gate_rel"]
    worst = float(inv_t["rel_err"].abs().max())
    sel = inv_t[(inv_t.allocation == nm["allocation"]) & (inv_t.kappa == nm["kappa"])]
    summary = {
        "weather": e7["weather"],
        "allocation_base": nm["allocation"],
        "kappa_base": nm["kappa"],
        "mass_feedback": e7["mass_feedback"],
        "factors": factors,
        "base_case": {
            r.archetype: {
                "km_day": float(r.km_day),
                "A_req_closed_m2": round(r.A_req_closed_m2, 2),
                "A_fss1_sim_m2": round(r.A_fss1_sim_m2, 2),
                "rel_err": round(r.rel_err, 4),
                "D_max_km_day_11p6": round(r.D_max_km_day_11p6, 1),
            }
            for r in sel.itertuples()
        },
        "B0_A_req_m2": {
            sc: round(design.required_area(km, city, climate), 2)
            for sc, (km, city) in SCENARIOS.items()
        },
        "closed_form_check": {
            "max_abs_rel_err": round(worst, 4),
            "max_abs_rel_err_fixed_mass": round(float(inv_t["rel_err_fixed_mass"].abs().max()), 4),
            "tol": tol,
            "n": int(len(inv_t)),
            "pass": bool(worst <= tol),
        },
    }
    if check_path is not None:
        summary["facet_sum_vs_e5"] = json.loads(Path(check_path).read_text(encoding="utf-8"))
    summary["pass"] = (
        summary["closed_form_check"]["pass"]
        and summary.get("facet_sum_vs_e5", {"pass": True})["pass"]
    )
    for p in (out_sweep, out_inversion, out_nomograph, out_summary, out_fig):
        Path(p).parent.mkdir(parents=True, exist_ok=True)
    kw = dict(index=False, lineterminator="\n", float_format="%.6g")
    sweep_t.to_csv(out_sweep, **kw)
    inv_t.to_csv(out_inversion, **kw)
    nomo_t.to_csv(out_nomograph, **kw)
    out_fss_area = out_fss_area or Path(out_nomograph).with_name("table_e7_fss_area.csv")
    pd.DataFrame(
        [
            {"archetype": a, "A_m2": A, "fss": f}
            for a, fs in fss_vs_A.items()
            for A, f in zip(A_grid, fs, strict=True)
        ]
    ).to_csv(out_fss_area, **kw)
    Path(out_summary).write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    fig_nomograph(nomo_t, sel, A_grid, fss_vs_A, str(Path(out_fig).with_suffix("")))
    return summary


def fig_nomograph(nomo, sel, A_grid, fss_vs_A, stem):
    from solaris import figures

    plt = figures.style()
    names = sch.schedules_config()["archetypes"]
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(7.0, 3.1))
    for i, a in enumerate(fss_vs_A):
        c = nomo[nomo.curve == a]
        ax.plot(c.km_day, c.A_req_m2, color=figures.SERIES[i], label=f"{a} {names[a]['name']}")
        r = sel[sel.archetype == a].iloc[0]
        ax.plot(r.km_day, r.A_fss1_sim_m2, "o", ms=4, mfc="none", color=figures.SERIES[i])
        bx.plot(A_grid, fss_vs_A[a], color=figures.SERIES[i])
    for sc, ls in (("II", "--"), ("I", ":")):
        c = nomo[nomo.curve == f"B0-{sc}"]
        ax.plot(
            c.km_day, c.A_req_m2, ls, color=figures.MUTED, lw=1.0, label=f"Table B0, Scen. {sc}"
        )
    ax.axhline(11.6, color=figures.AXIS, lw=0.8)
    ax.text(1, 12.2, "11.6 m² skin", fontsize=7, color=figures.INK2)
    ax.set_xlabel("Daily distance D, km/day")
    ax.set_ylabel("PV area for f_ss = 1, m²")
    ax.set_ylim(0, None)
    ax.set_title("(a) Shading-aware Eq. (2); circles: full simulation", loc="left", fontsize=8.5)
    ax.legend(fontsize=6.5, loc="upper left")
    bx.axhline(1.0, color=figures.AXIS, lw=0.8)
    bx.axvline(11.6, color=figures.AXIS, lw=0.8)
    bx.set_xlabel("PV area A, m² (full skin, scaled)")
    bx.set_ylabel("Solar self-sufficiency f_ss")
    bx.set_title("(b) Full simulation, mass fed back", loc="left", fontsize=8.5)
    fig.tight_layout()
    figures.save(fig, stem)
    plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("stage", choices=["facets", "inversion"])
    ap.add_argument("--hourly", default="results/e7/table_e7_facet_hourly.csv.gz")
    ap.add_argument("--facets", default="results/e7/table_e7_facets.csv")
    ap.add_argument("--check", default="results/e7/check_e7_facets.json")
    ap.add_argument("--sweep", default="results/e7/table_e7_sweep.csv")
    ap.add_argument("--inversion", default="results/e7/table_e7_inversion.csv")
    ap.add_argument("--nomograph", default="results/e7/table_e7_nomograph.csv")
    ap.add_argument("--summary", default="results/e7/summary_e7.json")
    ap.add_argument("--fig", default="results/e7/fig12_nomograph.png")
    ap.add_argument("--day-stride", type=int, default=1)
    a = ap.parse_args()
    if a.stage == "facets":
        print(json.dumps(facet_series(a.hourly, a.facets, a.check, a.day_stride), indent=2))
    else:
        out = inversion(a.hourly, a.sweep, a.inversion, a.nomograph, a.summary, a.fig, a.check)
        print(json.dumps(out, indent=2))
