"""Model cross-checks: production EVs (Table III), satellite climate (Table IV), the gap split,
TMY-release robustness and the design levers on the TMY (conference Secs. IV, V)."""

import dataclasses

import numpy as np

from .climate import gsa_site, load_city_tmy, load_tmy, release_path
from .drive_cycle import consumption_wh_km, whkm, wltp_trace
from .economics import design_mass, pareto
from .metrics import classify
from .params import BASE, Params, Site
from .soc_loop import simulate

# Conference Table III inputs: Cd, Af (m2), mass (kg), Cr, PV kWp, battery-referenced Wh/km
# (usable pack / rated range), claimed solar km/day, PSH used for the claim.
VALIDATION_VEHICLES = {
    "Aptera": (0.13, 2.2, 1000, 0.008, 0.70, 65, 64, 6.0),
    "Lightyear0": (0.175, 2.36, 1575, 0.009, 1.05, 96, 70, 5.0),
}
VALIDATION_ETA_REGEN = 0.65
VALIDATION_KAPPA = 0.80

SCENARIOS = ((50, True, "II 50km"), (100, False, "I 100km"))
SUSPENSION_W = (50, 100, 150, 200)


def validate(p: Params = BASE) -> dict:
    """Apply the platform models to Aptera and Lightyear 0 (WLTP combined cycle)."""
    out = {}
    v = wltp_trace(p=p)
    for name, (cd, af, m, cr, kWp, claim_whkm, claim_km, psh) in VALIDATION_VEHICLES.items():
        pv = dataclasses.replace(p, Cd=cd, Af=af, Cr=cr)
        wh, _, _ = consumption_wh_km(v, m, eta_regen=VALIDATION_ETA_REGEN, p=pv)
        solar_kwh = kWp * psh * VALIDATION_KAPPA
        out[name] = dict(
            model_whkm=round(wh),
            claim_whkm=claim_whkm,
            model_solar_km=round(solar_kwh / (claim_whkm / 1000.0)),
            claim_solar_km=claim_km,
        )
    return out


def real_data_validation(scenarios=SCENARIOS, p: Params = BASE) -> list:
    """Tier 1: rerun with the Global Solar Atlas annual GHI and temperature."""
    out = []
    for km, city, tag in scenarios:
        for loc in p.sites:
            f_assumed = simulate(loc, km, city, p=p)["fss"]
            r = simulate(loc, km, city, site=gsa_site(loc, p), p=p)
            f_real = r["fss"]
            out.append(
                dict(
                    scenario=tag,
                    city=loc,
                    assumed=p.sites[loc].psh,
                    real=gsa_site(loc, p).psh,
                    f_assumed=round(f_assumed, 2),
                    f_real=round(f_real, 2),
                    cls_assumed=classify(f_assumed),
                    cls_real=classify(f_real),
                    class_changed=classify(f_assumed) != classify(f_real),
                    charges=r["charges"],
                )
            )
    return out


def tmy_validation(scenarios=SCENARIOS, p: Params = BASE) -> list:
    """Tier 2: rerun the 8760-h engine on the satellite hourly TMYs (skips absent files)."""
    out = []
    for loc in p.sites:
        tmy = load_city_tmy(loc, p)
        if tmy is None:
            continue
        ghi, T = tmy
        for km, city, tag in scenarios:
            f_syn = simulate(loc, km, city, p=p)["fss"]
            r = simulate(loc, km, city, climate=(ghi, T), p=p)
            r0 = simulate(loc, km, city, climate=(ghi, T), pv_scale=0.0, p=p)
            out.append(
                dict(
                    scenario=tag,
                    city=loc,
                    psh_tmy=round(ghi.sum() / 1000 / 365, 3),
                    ghi_tmy=round(ghi.sum() / 1000, 1),
                    tmean=round(float(T.mean()), 1),
                    f_syn=round(f_syn, 2),
                    f_tmy=round(r["fss"], 2),
                    cls_tmy=classify(r["fss"]),
                    class_changed=classify(f_syn) != classify(r["fss"]),
                    charges=r["charges"],
                    charges_nosolar=r0["charges"],
                    grid=round(r["grid_kwh"]),
                    relief_pct=round(100 * r["relief"]),
                )
            )
    return out


def tmy_robustness(scenarios=SCENARIOS, p: Params = BASE) -> list:
    """Phoenix f_ss across the NSRDB TMY-2022/2023/2024/2025 releases."""
    out = []
    for yr in p.tmy_releases:
        path = release_path(yr, p)
        if not path.exists():
            continue
        ghi, T = load_tmy(path)
        for km, city, tag in scenarios:
            r = simulate("Phoenix", km, city, climate=(ghi, T), p=p)
            out.append(
                dict(
                    release=yr,
                    scenario=tag,
                    psh=round(ghi.sum() / 1000 / 365, 3),
                    fss=round(r["fss"], 3),
                    charges=r["charges"],
                    grid=round(r["grid_kwh"]),
                )
            )
    return out


def gap_decomposition(km=50, city=True, p: Params = BASE) -> dict:
    """Split the synthetic -> TMY f_ss gap into MAGNITUDE (synthetic minus synthetic rescaled
    to the TMY's own annual GHI and mean temperature) and DISTRIBUTION (rescaled synthetic
    minus TMY: the hour-to-hour and day-to-day pattern)."""
    out = {}
    for loc in p.sites:
        tmy = load_city_tmy(loc, p)
        if tmy is None:
            continue
        ghi, T = tmy
        s = p.sites[loc]
        f_syn = simulate(loc, km, city, p=p)["fss"]
        rescaled = Site(s.lat, ghi.sum() / 1000.0 / 365.0, float(T.mean()), s.T_amp)
        f_mag = simulate(loc, km, city, site=rescaled, p=p)["fss"]
        f_t2 = simulate(loc, km, city, climate=tmy, p=p)["fss"]
        out[loc] = dict(
            f_syn=f_syn,
            f_mag=f_mag,
            f_t2=f_t2,
            magnitude=f_syn - f_mag,
            distribution=f_mag - f_t2,
            total=f_syn - f_t2,
        )
    return out


def regen_susp_sensitivity(loc="Phoenix", km=50, city=True, climate=None, p: Params = BASE) -> dict:
    """f_ss for regenerative-suspension output of 50-200 W while driving."""
    return {P: simulate(loc, km, city, climate=climate, P_susp=P, p=p)["fss"] for P in SUSPENSION_W}


def design_levers_tmy(loc="Phoenix", km=50, city=True, p: Params = BASE) -> dict:
    """Sec. V-D on the satellite TMY: kappa sweep, kappa for the quasi tier, eta_regen 0.72,
    suspension sweep, area for f_ss = 1 (mass fed back) and the pack sweep."""
    t = load_city_tmy(loc, p)
    out = {}
    out["kappa"] = {
        c: [
            simulate(c, km, city, kappa=k, climate=load_city_tmy(c, p), p=p)["fss"]
            for k in (0.60, 0.70, 0.80)
        ]
        for c in p.sites
    }
    ks = np.linspace(0.5, 1.2, 29)
    fk = [simulate(loc, km, city, kappa=k, climate=t, p=p)["fss"] for k in ks]
    out["kappa_for_quasi"] = float(np.interp(0.90, fk, ks))
    out["regen_072"] = (
        whkm("P0", city=city, p=p),
        whkm("P0", city=city, eta_regen=0.72, p=p),
        simulate(loc, km, city, climate=t, p=p)["fss"],
        simulate(loc, km, city, eta_regen=0.72, climate=t, p=p)["fss"],
    )
    out["susp"] = regen_susp_sensitivity(loc, km, city, climate=t, p=p)
    A = np.linspace(12, 17, 51)
    cap = p.capacity["P0"]  # v1.1.0: (M_P0 - 541) + 3.5 A + 500
    fA = [
        simulate(loc, km, city, A_over=a, climate=t, m_over=design_mass(a, cap, p), p=p)["fss"]
        for a in A
    ]
    out["area_for_fss1"] = float(np.interp(1.0, fA, A))
    out["pack"] = pareto(loc, km, city, climate=t, areas=(11.6, 15), caps=(150, 200, 250), p=p)
    return out
