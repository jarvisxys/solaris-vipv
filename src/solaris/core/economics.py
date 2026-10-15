"""Grid relief, payback and the PV-area x pack-size sweep (conference Secs. XI, XII)."""

import numpy as np

from .audit import vehicle_mass
from .params import BASE, Params
from .soc_loop import simulate

PV_SKIN = "PV skin (2.55 kWp @ ~$1.2/Wp incl. integration)"
MPPT = "Multi-input MPPT / power electronics"
WIRING = "HV wiring / structure / coatings"
PV_MASS_ITEM = "PV skin (11.6 m^2 VIPV laminate @3.5 kg/m^2)"
PV_AREAL_MASS = 3.5  # kg/m2 VIPV laminate
PACK_KG_PER_KWH = 2.0  # 500 Wh/kg


def system_cost(p: Params = BASE) -> float:
    """Full as-specified add-on cost (USD)."""
    return sum(p.cost_items.values())


def pv_only_cost(p: Params = BASE) -> float:
    """PV skin + MPPT + half the wiring/structure: TEG and regenerative suspension dropped."""
    return p.cost_items[PV_SKIN] + p.cost_items[MPPT] + p.cost_items[WIRING] * 0.5


def economics(loc, km, city, cost=None, climate=None, kappa=None, p: Params = BASE) -> dict:
    """Grid-energy relief and simple payback. Relief counts demand not met from the grid."""
    r = simulate(loc, km, city, climate=climate, kappa=kappa, p=p)
    saved_kwh = r["solar_used"]
    saved_usd = saved_kwh * p.price[loc]
    c = system_cost(p) if cost is None else cost
    payback = c / saved_usd if saved_usd > 0 else float("inf")
    return dict(
        fss=r["fss"],
        grid_kwh=r["grid_kwh"],
        saved_kwh=saved_kwh,
        saved_usd=saved_usd,
        payback_yr=payback,
        payback_pvonly=pv_only_cost(p) / saved_usd if saved_usd > 0 else float("inf"),
        grid_relief_pct=100 * saved_kwh / r["ann_dem"],
    )


def pareto(loc="Phoenix", km=50, city=True, climate=None, p: Params = BASE) -> list:
    """Sweep PV area and pack capacity; return (grid, mass, cost, f_ss) per design.

    Grid energy is averaged over the synthetic-climate seeds; a measured climate has no
    seed, so every seed gives the same run.
    """
    rows = []
    for A in p.pareto_areas:
        for capk in p.pareto_caps:
            grids = [
                simulate(loc, km, city, A_over=A, cap_over=capk, seed=sd, climate=climate, p=p)[
                    "grid_kwh"
                ]
                for sd in p.pareto_seeds
            ]
            r = simulate(loc, km, city, A_over=A, cap_over=capk, climate=climate, p=p)
            mass = (
                (vehicle_mass("P0", p) - p.pack_mass["P0"] - p.mass[PV_MASS_ITEM])
                + A * PV_AREAL_MASS
                + capk * PACK_KG_PER_KWH
            )
            cost = A * p.pareto_pv_cost + capk * p.pareto_pack_cost
            rows.append(
                dict(
                    A=A,
                    cap=capk,
                    grid=float(np.mean(grids)),
                    charges=r["charges"],
                    mass=mass,
                    cost=cost,
                    fss=r["fss"],
                )
            )
    return rows
