"""Design inversion for self-sufficiency, Eq. (2) of the conference paper.

    A_req = (D c / eta_dt + E_aux) / (eta_pv PSH kappa_pv f_T)
    D_max = eta_dt (A_skin eta_pv PSH kappa_pv f_T - E_aux) / c

f_T and E_aux are annual means from the same hourly engine. With ``climate=None`` the
conference synthetic climate (and its nominal PSH) is used, as in the paper; pass a
measured (GHI, T) series to invert on measured data.
"""

import numpy as np

from .climate import site_climate
from .drive_cycle import whkm
from .params import BASE, Params
from .soc_loop import aux_power_W

D_MAX_AUX_KM = 50  # conference convention: D_max uses the 50 km/day auxiliary schedule


def _climate(loc, climate, p: Params):
    return site_climate(p.sites[loc]) if climate is None else climate


def _psh(loc, climate, p: Params) -> float:
    if climate is None:
        return p.sites[loc].psh
    return climate[0].sum() / 1000.0 / 365.0


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
    """Minimum PV skin area (m2) for f_ss = 1."""
    c = whkm("P0", city=city, p=p) / 1000.0
    fT = engine_fT(loc, climate, p)
    E_aux = engine_Eaux(loc, city, daily_km, climate, p)
    return (daily_km * c / p.eta_dt + E_aux) / (p.eta_pv * _psh(loc, climate, p) * p.kappa_pv * fT)


def max_selfsuff_km(loc, city=True, climate=None, p: Params = BASE) -> float:
    """Maximum self-sufficient daily distance (km/day) with the as-built skin."""
    c = whkm("P0", city=city, p=p) / 1000.0
    fT = engine_fT(loc, climate, p)
    E_aux = engine_Eaux(loc, city, D_MAX_AUX_KM, climate, p)
    E_pv = p.A_skin * p.eta_pv * _psh(loc, climate, p) * p.kappa_pv * fT
    return p.eta_dt * (E_pv - E_aux) / c
