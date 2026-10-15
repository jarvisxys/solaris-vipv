"""WLTP Class 3b reconstruction and road-load integration (conference Sec. VI-C)."""

import numpy as np

from .audit import vehicle_mass
from .params import BASE, Params

ALL_PHASES = ("Low", "Medium", "High", "ExtraHigh")
CITY_PHASES = ("Low", "Medium")


def phases(city: bool) -> tuple:
    return CITY_PHASES if city else ALL_PHASES


def build_phase(D_km, T_s, vmax_kmh, n, a_acc=1.0, a_dec=1.2):
    """1 Hz speed trace (m/s) of n identical trapezoidal micro-trips matching D and T."""
    D, vpk = D_km * 1000, vmax_kmh / 3.6
    best = None
    for vc in np.linspace(0.35 * vpk, 0.95 * vpk, 60):
        ta, td = vc / a_acc, vc / a_dec
        da, dd = 0.5 * a_acc * ta**2, 0.5 * a_dec * td**2
        if da + dd > D / n:
            continue
        dc = D / n - da - dd
        tc = dc / vc
        ti = (T_s - n * (ta + tc + td)) / n
        if ti < 0:
            continue
        best = (vc, ta, tc, td, ti)
    vc, ta, tc, td, ti = best
    v = []
    for _ in range(n):
        v += [min(vc, a_acc * t) for t in np.arange(0, ta, 1)]
        v += [vc] * int(tc)
        v += [max(0, vc - a_dec * t) for t in np.arange(0, td, 1)]
        v += [0.0] * int(ti)
    return np.array(v)


def wltp_trace(keys=ALL_PHASES, p: Params = BASE):
    return np.concatenate([build_phase(*p.wltc[k], a_acc=p.a_acc, a_dec=p.a_dec) for k in keys])


def consumption_wh_km(v_ms, m, eta_regen=None, p: Params = BASE):
    """Battery-side consumption (Wh/km), distance (km) and mean speed (km/h) of a 1 Hz trace."""
    eta_regen = p.eta_regen if eta_regen is None else eta_regen
    a = np.diff(v_ms, prepend=v_ms[0])
    F = p.Cr * m * p.g * (v_ms > 0.1) + 0.5 * p.rho * p.Cd * p.Af * v_ms**2 + m * a
    P = F * v_ms
    E_pos = np.sum(np.clip(P, 0, None)) / 3.6e6
    E_neg = np.sum(np.clip(P, None, 0)) / 3.6e6
    E_batt = E_pos / p.eta_dt + E_neg * eta_regen * p.eta_dt
    dist = np.sum(v_ms) / 1000.0
    return E_batt / dist * 1000.0, dist, np.mean(v_ms) * 3.6


def whkm(variant, city=False, eta_regen=None, p: Params = BASE):
    v = wltp_trace(phases(city), p)
    return consumption_wh_km(v, vehicle_mass(variant, p), eta_regen, p)[0]


def mean_speed_kmh(city: bool, p: Params = BASE) -> float:
    return wltp_trace(phases(city), p).mean() * 3.6


def wltp_recon_error(p: Params = BASE) -> dict:
    """Per-phase and total distance error and peak speed of the reconstruction vs WLTC 3b."""
    rows = {}
    for k in ALL_PHASES:
        ph = p.wltc[k]
        v = build_phase(*ph, a_acc=p.a_acc, a_dec=p.a_dec)
        dist = v.sum() / 1000.0
        rows[k] = dict(
            dist=dist,
            dist_err=100 * (dist - ph.distance_km) / ph.distance_km,
            vmax=v.max() * 3.6,
            vmax_off=ph.vmax_kmh,
        )
    vfull = wltp_trace(ALL_PHASES, p)
    tot = vfull.sum() / 1000.0
    off = p.official_total_km
    rows["TOTAL"] = dict(
        dist=tot,
        dist_err=100 * (tot - off) / off,
        vmax=vfull.max() * 3.6,
        vmax_off=p.wltc["ExtraHigh"].vmax_kmh,
    )
    return rows
