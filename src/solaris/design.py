"""Shading-aware design inversion: the conference Eq. (2) with three journal factors (E7).

    A_req = (D c + E_aux) / (eta_pv PSH kappa_pv f_T F_geo F_sh F_mm)

c is the battery-side consumption (v1.1.0: eta_dt is already inside it); PSH, f_T and E_aux
come from one hourly climate as in core.required_pv_area, which this reduces to when all
three factors are 1. From the E5 loss chain of one archetype (annual PV energy per step):

    F_geo = E_facets / E_chain       facet orientation, open sky (as in E2)
    F_sh  = E_trees / E_facets       parking and driving shade, trajectory-weighted
    F_mm  = E_mismatch / E_trees     electrical mismatch (E6 fit)
"""

import numpy as np
from scipy.optimize import brentq

from .core import engine_Eaux, engine_fT, vehicle_mass, whkm
from .core.params import BASE, Params

PV_AREAL_MASS = 3.5  # kg/m2 VIPV laminate (mass audit, core.economics)


def loss_factors(e: dict) -> dict:
    """F_geo, F_sh, F_mm from annual PV energy at the chain, facets, trees and mismatch steps."""
    return {
        "F_geo": e["facets"] / e["chain"],
        "F_sh": e["trees"] / e["facets"],
        "F_mm": e["mismatch"] / e["trees"],
    }


def required_area(
    daily_km,
    city,
    climate,
    F_geo=1.0,
    F_sh=1.0,
    F_mm=1.0,
    kappa=None,
    loc="Phoenix",
    p: Params = BASE,
) -> float:
    """PV area (m2) at which the annual harvest equals the annual demand (f_ss = 1)."""
    ghi, T = climate
    kappa = p.kappa_pv if kappa is None else kappa
    psh = ghi.sum() / 1000.0 / 365.0
    c = whkm("P0", city=city, p=p) / 1000.0
    fT = engine_fT(loc, (ghi, T), p)
    E_aux = engine_Eaux(loc, city, daily_km, (ghi, T), p)
    return float((daily_km * c + E_aux) / (p.eta_pv * psh * kappa * fT * F_geo * F_sh * F_mm))


def max_distance(A, city, climate, km_max=2000.0, **kw) -> float:
    """Daily distance (km/day) that area A makes self-sufficient: the inverse of
    required_area, with the auxiliary load evaluated at that distance (0 if A cannot
    even cover the parked load)."""
    if required_area(0.0, city, climate, **kw) >= A:
        return 0.0
    return float(brentq(lambda d: required_area(d, city, climate, **kw) - A, 0.0, km_max))


def allocation_series(per_facet: dict, ids, base_areas: dict, A) -> np.ndarray:
    """Hourly PV of the facets in ``ids`` with their areas scaled together to total A."""
    a0 = sum(base_areas[i] for i in ids)
    return (A / a0) * sum(np.asarray(per_facet[i], float) for i in ids)


def design_mass(A, p: Params = BASE) -> float:
    """P0 mass with PV area A instead of the 11.6 m2 skin (pack unchanged)."""
    return vehicle_mass("P0", p) + PV_AREAL_MASS * (A - p.A_skin)
