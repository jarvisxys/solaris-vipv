"""Model cross-checks: production EVs (Table II), measured climate (Table IV), sensitivities."""

import dataclasses

from .climate import gsa_site, load_tmy, tmy_path
from .drive_cycle import consumption_wh_km, wltp_trace
from .metrics import classify
from .params import BASE, Params
from .soc_loop import simulate

# Conference Table II inputs: Cd, Af (m2), mass (kg), Cr, PV kWp, claimed Wh/km,
# claimed solar km/day, PSH used for the claim.
VALIDATION_VEHICLES = {
    "Aptera": (0.13, 2.2, 1000, 0.008, 0.70, 62, 64, 6.0),
    "Lightyear0": (0.175, 2.36, 1575, 0.009, 1.05, 96, 70, 5.0),
}
VALIDATION_ETA_REGEN = 0.65
VALIDATION_KAPPA = 0.80

SCENARIOS = ((50, True, "II 50km"), (100, False, "I 100km"))


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
    """Tier 1: rerun with the measured annual GHI and temperature (Global Solar Atlas)."""
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
    """Tier 2: rerun the 8760-h engine on measured hourly TMY series (skips absent files)."""
    out = []
    for loc in p.tmy_files:
        path = tmy_path(loc, p)
        if not path.exists():
            continue
        ghi, T = load_tmy(path)
        for km, city, tag in scenarios:
            f_syn = simulate(loc, km, city, p=p)["fss"]
            r = simulate(loc, km, city, climate=(ghi, T), p=p)
            out.append(
                dict(
                    scenario=tag,
                    city=loc,
                    psh_tmy=round(ghi.sum() / 1000 / 365, 3),
                    tmean=round(float(T.mean()), 1),
                    f_syn=round(f_syn, 2),
                    f_tmy=round(r["fss"], 2),
                    cls_tmy=classify(r["fss"]),
                    class_changed=classify(f_syn) != classify(r["fss"]),
                    charges=r["charges"],
                    grid=round(r["grid_kwh"]),
                )
            )
    return out


def regen_susp_sensitivity(loc="Phoenix", km=50, city=True, p: Params = BASE) -> dict:
    """f_ss for regenerative-suspension output of 50-200 W while driving."""
    return {P: simulate(loc, km, city, P_susp=P, p=p)["fss"] for P in (50, 100, 150, 200)}
