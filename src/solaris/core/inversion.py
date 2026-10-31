"""Design inversion for self-sufficiency, Eqs. (3)-(4) of the conference paper (v1.1.0).

    A_req = (D c + E_aux) / (eta_pv PSH kappa_pv f_T)
    D_max = (A eta_pv PSH kappa_pv f_T - E_aux) / c

c is the battery-side consumption (eta_dt is already inside it). PSH, f_T and E_aux are
annual means of one hourly climate: the idealized synthetic climate with ``climate=None``,
or a satellite (GHI, T) series, e.g. ``load_city_tmy(loc)``.
"""

import numpy as np

from .climate import site_climate
from .drive_cycle import whkm
from .params import BASE, Params
from .soc_loop import aux_power_W

D_MAX_AUX_KM = 50  # conference convention: D_max uses the 50 km/day auxiliary schedule


def _climate(loc, climate, p: Params):
    return site_climate(p.sites[loc]) if climate is None else climate


def fT_from_series(ghi, Tamb, p: Params = BASE) -> float:
    """Irradiance-weighted annual mean PV temperature factor."""
    Pcell = Tamb + p.cell_temp_rise * (ghi / 1000.0)
    w = ghi > 0
    return float(np.sum(ghi[w] * (1 + p.beta * (Pcell[w] - 25))) / np.sum(ghi[w]))


def engine_fT(loc, climate=None, p: Params = BASE) -> float:
    return fT_from_series(*_climate(loc, climate, p), p)


def engine_Eaux(loc, city, daily_km, climate=None, p: Params = BASE) -> float:
    """Annual-mean daily auxiliary energy (kWh/day)."""
    _, Tamb = _climate(loc, climate, p)
    return float(aux_power_W(Tamb, daily_km, city, p).sum() / 1000.0 / 365.0)


def required_pv_area(daily_km, city, loc, climate=None, p: Params = BASE) -> float:
    """Minimum PV skin area (m2) for f_ss = 1 (TEG and suspension neglected)."""
    ghi, T = _climate(loc, climate, p)
    psh = ghi.sum() / 1000.0 / 365.0
    c = whkm("P0", city=city, p=p) / 1000.0
    fT = engine_fT(loc, (ghi, T), p)
    E_aux = engine_Eaux(loc, city, daily_km, (ghi, T), p)
    return float((daily_km * c + E_aux) / (p.eta_pv * psh * p.kappa_pv * fT))


def max_selfsuff_km(loc, city=True, climate=None, A=None, p: Params = BASE) -> float:
    """Maximum self-sufficient daily distance (km/day) with PV area A (default: 11.6 m2)."""
    A = p.A_skin if A is None else A
    ghi, T = _climate(loc, climate, p)
    psh = ghi.sum() / 1000.0 / 365.0
    c = whkm("P0", city=city, p=p) / 1000.0
    fT = engine_fT(loc, (ghi, T), p)
    E_aux = engine_Eaux(loc, city, D_MAX_AUX_KM, (ghi, T), p)
    E_pv = A * p.eta_pv * psh * p.kappa_pv * fT
    return float((E_pv - E_aux) / c)
