"""Grid relief, payback and the PV-area x pack-size sweep (conference Secs. V-D, V-E)."""

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


def pv_cost_per_m2(p: Params = BASE) -> float:
    """PV skin cost per m2 on the economics() basis (~264 USD/m2)."""
    return p.cost_items[PV_SKIN] / p.A_skin


def design_mass(A, cap_kwh, p: Params = BASE) -> float:
    """Vehicle mass (kg) with PV area A and pack capacity cap_kwh at the audit's areal and
    specific masses (Pareto mass feedback)."""
    base = vehicle_mass("P0", p) - p.pack_mass["P0"] - p.mass[PV_MASS_ITEM]
    return base + A * PV_AREAL_MASS + cap_kwh * PACK_KG_PER_KWH


def economics(loc, km, city, cost=None, climate=None, kappa=None, p: Params = BASE) -> dict:
    """Grid relief (harvest actually used / demand) and simple payback on the saved energy."""
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
        grid_relief_pct=100 * r["relief"],
    )


def pareto(
    loc="Phoenix", km=50, city=True, climate=None, areas=None, caps=None, p: Params = BASE
) -> list:
    """Sweep PV area and pack capacity with mass fed back into consumption; return
    (grid, mass, cost, f_ss, relief) per design.

    climate=None: synthetic climate, grid energy averaged over the seeds.
    climate=(ghi, T): one satellite TMY year (no seed averaging).
    """
    rows = []
    for A in p.pareto_areas if areas is None else areas:
        for capk in p.pareto_caps if caps is None else caps:
            mass = design_mass(A, capk, p)
            kw = dict(A_over=A, cap_over=capk, m_over=mass, p=p)
            if climate is None:
                grids = [
                    simulate(loc, km, city, seed=sd, **kw)["grid_kwh"] for sd in p.pareto_seeds
                ]
            r = simulate(loc, km, city, climate=climate, **kw)
            if climate is not None:
                grids = [r["grid_kwh"]]
            rows.append(
                dict(
                    A=A,
                    cap=capk,
                    grid=float(np.mean(grids)),
                    charges=r["charges"],
                    mass=mass,
                    cost=A * pv_cost_per_m2(p) + capk * p.pareto_pack_cost,
                    fss=r["fss"],
                    relief=r["relief"],
                )
            )
    return rows
