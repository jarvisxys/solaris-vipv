"""8760-h state-of-charge loop (conference Secs. VI, IX)."""

import numpy as np

from .audit import e_teg
from .climate import site_climate
from .drive_cycle import consumption_wh_km, mean_speed_kmh, phases, whkm, wltp_trace
from .params import BASE, Params, Site

PARK_DEADBAND_K = 2.0  # parked HVAC idles below setpoint - 2 K


def park_load(Tamb, setpt=30.0, UA=25.0, COP=2.2, soak=15.0, P_min=50.0):
    """Parked thermal-management power (W) from a lumped UA*dT/COP model."""
    return np.where(
        Tamb <= setpt - PARK_DEADBAND_K,
        P_min,
        np.maximum(P_min, UA * ((Tamb - setpt) + soak) / COP),
    )


def park_load_p(Tamb, p: Params = BASE):
    return park_load(Tamb, p.park_setpt, p.park_UA, p.park_COP, p.park_soak, p.park_P_min)


def drive_mask(p: Params = BASE):
    """True in the hourly buckets that contain a commute trip."""
    return np.isin(np.arange(8760) % 24, list(p.drive_hours))


def drive_fraction(daily_km, city, p: Params = BASE) -> float:
    """Fraction of each trip bucket spent driving, prorated by the cycle's mean speed."""
    trips = float(len(p.drive_hours))
    return min(1.0, (daily_km / mean_speed_kmh(city, p)) / trips)


def aux_power_W(Tamb, daily_km, city, p: Params = BASE):
    """Auxiliary power per hour: 250 W while driving, parked load for the rest of the hour."""
    drive = drive_mask(p)
    frac = drive_fraction(daily_km, city, p)
    park = park_load_p(Tamb, p)
    return np.where(drive, p.P_aux_driving * frac + park * (1 - frac), park)


def simulate(
    loc,
    daily_km,
    city,
    variant="P0",
    kappa=None,
    eta_regen=None,
    floor=None,
    recharge_to=None,
    seed=0,
    pv_scale=1.0,
    A_over=None,
    cap_over=None,
    climate=None,
    site: Site | None = None,
    P_susp=None,
    p: Params = BASE,
    pv_kwh=None,
    m_over=None,
    warmup=None,
):
    """Run one year hour by hour and return f_ss, grid energy, charge events and the SoC trace.

    ``climate`` is a satellite (GHI W/m2, T C) series; otherwise the synthetic climate of
    ``site`` (default: the conference site for ``loc``) is generated with ``seed``.
    Demand uses the battery-side Wh/km as is (eta_dt is already inside it). With ``warmup``
    (default: configs/base.yaml) the year runs twice and the second pass, which starts from
    the first pass's end-of-year SoC, is reported. relief = (harvest - curtailed) / demand.
    ``m_over`` replaces the vehicle mass in the consumption (Pareto mass feedback).
    ``pv_kwh`` (journal extension, P5) replaces the conference flat-GHI PV model with an
    8760-h PV energy series (kWh per hour, before ``pv_scale``), e.g. the facet model.
    """
    kappa = p.kappa_pv if kappa is None else kappa
    floor = p.floor if floor is None else floor
    recharge_to = p.recharge_to if recharge_to is None else recharge_to
    P_susp = p.P_susp if P_susp is None else P_susp
    warmup = p.warmup if warmup is None else warmup
    if climate is None:
        ghi, Tamb = site_climate(site if site is not None else p.sites[loc], seed)
    else:
        ghi, Tamb = climate
    if m_over is None:
        wh = whkm(variant, city=city, eta_regen=eta_regen, p=p)
    else:
        wh = consumption_wh_km(wltp_trace(phases(city), p), m_over, eta_regen, p)[0]
    A = A_over if A_over is not None else p.A_skin
    drive = drive_mask(p)
    trip_km = daily_km / float(len(p.drive_hours))
    frac = drive_fraction(daily_km, city, p)
    E_prop_h = np.where(drive, wh * trip_km / 1000.0, 0.0)
    E_susp_h = np.where(drive, P_susp * frac / 1000.0, 0.0)
    Pcell = Tamb + p.cell_temp_rise * (ghi / 1000.0)
    if pv_kwh is None:
        E_pv_h = pv_scale * A * p.eta_pv * (ghi / 1000.0) * kappa * (1 + p.beta * (Pcell - 25))
    else:
        E_pv_h = pv_scale * np.asarray(pv_kwh, float)
    E_aux_h = aux_power_W(Tamb, daily_km, city, p) / 1000.0
    E_teg_h = e_teg(p) / 24.0
    harv = E_pv_h + E_susp_h + E_teg_h
    dem = E_prop_h + E_aux_h
    cap = cap_over if cap_over is not None else p.capacity[variant]

    s0 = p.soc_initial_frac * cap
    if warmup:
        s0 = _year(s0, harv, dem, cap, floor, recharge_to)[0][-1]
    soc, grid, charges, curtailed = _year(s0, harv, dem, cap, floor, recharge_to)

    ann_harv = harv.sum()
    ann_dem = dem.sum()
    used = ann_harv - curtailed  # closes the pack: soc_end - soc_start = used + grid - demand
    return dict(
        soc=soc / cap * 100,
        fss=float(ann_harv / ann_dem),
        grid_kwh=float(grid),
        charges=int(charges),
        ann_dem=float(ann_dem),
        ann_harv=float(ann_harv),
        curtailed=float(curtailed),
        solar_used=float(used),
        relief=float(used / ann_dem),
        soc_change=float(soc[-1] - soc[0]),
        psh=float(ghi.sum() / 1000.0 / 365.0),
        whkm=float(wh),
        cap=float(cap),
        curtailed_kwh=float(curtailed),
        harvest_used_kwh=float(used),
        soc_start_kwh=float(soc[0]),
        soc_end_kwh=float(soc[-1]),
    )


def _year(s0, harv, dem, cap, floor, recharge_to):
    """One pass over the 8760 h: plug in below floor (refill to recharge_to), curtail above cap."""
    soc = np.zeros(8761)
    soc[0] = s0
    grid = 0.0
    charges = 0
    curtailed = 0.0
    for h in range(8760):
        s = soc[h] + harv[h] - dem[h]
        if s < floor * cap:
            grid += recharge_to * cap - s
            s = recharge_to * cap
            charges += 1
        if s > cap:
            curtailed += s - cap
            s = cap
        soc[h + 1] = s
    return soc, grid, charges, curtailed
