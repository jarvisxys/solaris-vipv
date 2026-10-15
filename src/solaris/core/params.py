"""Conference parameters, loaded once from configs/base.yaml into an immutable object.

Variants (validation vehicles, sensitivities) are made with ``dataclasses.replace``;
nothing in solaris.core mutates module state.
"""

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import NamedTuple

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
BASE_YAML = REPO_ROOT / "configs" / "base.yaml"


class Site(NamedTuple):
    """Synthetic-climate site: latitude, annual PSH, mean and seasonal amplitude of T."""

    lat: float
    psh: float
    T_mean: float
    T_amp: float


class Phase(NamedTuple):
    distance_km: float
    duration_s: int
    vmax_kmh: float
    n_microtrips: int


@dataclass(frozen=True)
class Params:
    # physics
    g: float
    rho: float
    Cd: float
    Af: float
    Cr: float
    eta_dt: float
    eta_regen: float
    P_susp: float
    # PV
    A_skin: float
    eta_pv: float
    beta: float
    kappa_pv: float
    cell_temp_rise: float
    # pack and mass
    E_pack: float
    pack_mass: MappingProxyType
    capacity: MappingProxyType
    mass: MappingProxyType
    teg: MappingProxyType
    # drive cycle
    wltc: MappingProxyType
    a_acc: float
    a_dec: float
    official_total_km: float
    # climate
    sites: MappingProxyType
    gsa: MappingProxyType
    tmy_files: MappingProxyType
    # auxiliary load and schedule
    park_setpt: float
    park_UA: float
    park_COP: float
    park_soak: float
    park_P_min: float
    drive_hours: tuple
    P_aux_driving: float
    # SoC loop
    floor: float
    recharge_to: float
    soc_initial_frac: float
    # economics and Pareto sweep
    price: MappingProxyType
    cost_items: MappingProxyType
    pareto_pv_cost: float
    pareto_pack_cost: float
    pareto_areas: tuple
    pareto_caps: tuple
    pareto_seeds: tuple

    @classmethod
    def from_yaml(cls, path=BASE_YAML):
        y = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        ph, pv, pk, wl = y["physics"], y["pv"], y["pack"], y["wltc"]
        ro = MappingProxyType
        return cls(
            g=ph["g"],
            rho=ph["rho_air"],
            Cd=ph["Cd"],
            Af=ph["Af"],
            Cr=ph["Cr"],
            eta_dt=ph["eta_dt"],
            eta_regen=ph["eta_regen_base"],
            P_susp=ph["P_susp_W"],
            A_skin=pv["A_skin_m2"],
            eta_pv=pv["eta_pv"],
            beta=pv["beta_per_K"],
            kappa_pv=pv["kappa_pv_base"],
            cell_temp_rise=pv["cell_temp_rise_K_per_kWm2"],
            E_pack=pk["E_pack_kWh"],
            pack_mass=ro(dict(pk["pack_mass_kg"])),
            capacity=ro(dict(pk["capacity_kWh"])),
            mass=ro(dict(y["mass_kg"])),
            teg=ro(dict(y["teg"])),
            wltc=ro({k: Phase(**wl[k]) for k in ("Low", "Medium", "High", "ExtraHigh")}),
            a_acc=wl["build_phase"]["a_acc"],
            a_dec=wl["build_phase"]["a_dec"],
            official_total_km=wl["official_total_km"],
            sites=ro(
                {
                    c: Site(v["lat"], v["psh"], v["T_mean"], v["T_amp"])
                    for c, v in y["synthetic_climate"].items()
                }
            ),
            gsa=ro({c: tuple(v.values()) for c, v in y["global_solar_atlas"].items()}),
            tmy_files=ro(dict(y["tmy_files"])),
            park_setpt=y["park_load"]["setpt"],
            park_UA=y["park_load"]["UA"],
            park_COP=y["park_load"]["COP"],
            park_soak=y["park_load"]["soak"],
            park_P_min=y["park_load"]["P_min_W"],
            drive_hours=tuple(y["schedule"]["drive_hours"]),
            P_aux_driving=y["schedule"]["P_aux_driving_W"],
            floor=y["simulate"]["floor"],
            recharge_to=y["simulate"]["recharge_to"],
            soc_initial_frac=y["simulate"]["soc_initial_frac"],
            price=ro(dict(y["economics"]["price_usd_per_kWh"])),
            cost_items=ro(dict(y["economics"]["cost_items_usd"])),
            pareto_pv_cost=y["pareto"]["pv_cost_usd_per_m2"],
            pareto_pack_cost=y["pareto"]["pack_cost_usd_per_kWh"],
            pareto_areas=tuple(y["pareto"]["areas_m2"]),
            pareto_caps=tuple(y["pareto"]["capacities_kWh"]),
            pareto_seeds=tuple(y["pareto"]["seeds"]),
        )


BASE = Params.from_yaml()
