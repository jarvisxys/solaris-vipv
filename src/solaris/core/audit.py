"""Systems mass audit and the TEG 1-D thermal-network model (conference Secs. V, VI-B)."""

from .params import BASE, Params

GLIDER = "Glider (body, chassis, 2 motors, interior, 7 seats, HVAC)"


def harvest_hw_kg(p: Params = BASE) -> int:
    """Harvesting + integration hardware: every mass entry except the glider."""
    return sum(v for k, v in p.mass.items() if k != GLIDER)


def vehicle_mass(variant: str, p: Params = BASE) -> int:
    pack = 500 if variant == "PB" else p.pack_mass.get(variant, 500)
    return p.mass[GLIDER] + harvest_hw_kg(p) + pack


def teg_daily_kwh(
    A_teg=2.0,
    alpha=0.90,
    G=700.0,
    h_loss=15.0,
    k_TE=1.2,
    leg=0.004,
    fill=0.5,
    R_contact=1e-3,
    S_mod=0.051,
    R_int=3.0,
    mod_per_m2=625,
    hours=5.0,
):
    """Flux-limited TEG output from a series thermal network. Energies in kWh/day."""
    k_TE_area = k_TE * fill / leg  # W/m2K of TE legs
    k_stack = 1.0 / (1.0 / k_TE_area + R_contact)  # + contact resistance
    dT_skin = alpha * G / (h_loss + k_stack)
    q_through = k_stack * dT_skin  # W/m2 through module
    dT_leg = q_through / k_TE_area  # K across TE legs
    Voc = S_mod * dT_leg
    P_mod = Voc**2 / (4 * R_int)  # matched load, W/module
    P_teg = P_mod * mod_per_m2 * A_teg
    P_opt = 0.01 * q_through * A_teg  # purpose-built high-R TEG bound
    return dict(
        dT_leg=dT_leg,
        q_through=q_through,
        P_teg=P_teg,
        P_opt=P_opt,
        E_teg=P_teg * hours / 1000.0,
        E_teg_opt=P_opt * hours / 1000.0,
    )


def teg_base(p: Params = BASE) -> dict:
    return teg_daily_kwh(**p.teg)


def e_teg(p: Params = BASE) -> float:
    """Adopted commercial-module TEG output, kWh/day (rounded as in the paper)."""
    return round(teg_base(p)["E_teg"], 3)


def teg_tradeoff(p: Params = BASE) -> dict:
    """Energy the 35 kg TEG mass would store as 500 Wh/kg pack, and days for the TEG to make it."""
    kwh_if_battery = 35 * 500 / 1000.0
    days = kwh_if_battery / e_teg(p)
    return dict(kwh_if_battery=kwh_if_battery, days=days, years=days / 365.0)
