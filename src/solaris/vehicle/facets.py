"""Vehicle PV facets and their sample points (P5): configs/vehicle/solaris_p0.yaml.

Body frame x forward, y left, z up. A facet faces ``azimuth_body_deg`` clockwise from the
vehicle's forward direction, so on the road its compass azimuth (pvlib convention, 180 =
south) is heading + azimuth_body. Samples sit on a ``sample_spacing_m`` grid over each
rectangle; each carries an equal share of the facet's area.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from solaris.core.params import REPO_ROOT

VEHICLE_YAML = REPO_ROOT / "configs" / "vehicle" / "solaris_p0.yaml"


@dataclass(frozen=True)
class Facet:
    id: str
    area_m2: float
    tilt_deg: float
    azimuth_body_deg: float
    centre_m: tuple
    across_m: float
    slope_m: float

    def compass_azimuth(self, heading_deg):
        return (np.asarray(heading_deg, float) + self.azimuth_body_deg) % 360.0

    def normal_body(self):
        t, a = np.radians(self.tilt_deg), np.radians(self.azimuth_body_deg)
        return np.array([np.sin(t) * np.cos(a), -np.sin(t) * np.sin(a), np.cos(t)])


def vehicle_config(path=VEHICLE_YAML) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def facets(cfg=None, only=None) -> list[Facet]:
    cfg = cfg or vehicle_config()
    out = [
        Facet(
            f["id"],
            float(f["area_m2"]),
            float(f["tilt_deg"]),
            float(f["azimuth_body_deg"]),
            tuple(f["centre_m"]),
            float(f["across_m"]),
            float(f["slope_m"]),
        )
        for f in cfg["facets"]
    ]
    return [f for f in out if only is None or f.id in only]


def flat_skin(area_m2) -> list[Facet]:
    """One horizontal facet of the given area (E2 case 2b, the conference geometry)."""
    side = float(np.sqrt(area_m2))
    return [Facet("flat", float(area_m2), 0.0, 0.0, (0.0, 0.0, 1.85), side, side)]


def samples(fs, spacing=0.25) -> pd.DataFrame:
    """Sample points on every facet: body position, unit normal, represented area."""
    rows = []
    for f in fs:
        n = f.normal_body()
        a = np.radians(f.azimuth_body_deg)
        t = np.radians(f.tilt_deg)
        edge = np.array([np.sin(a), np.cos(a), 0.0])  # horizontal, along the facet
        up = np.array([-np.cos(t) * np.cos(a), np.cos(t) * np.sin(a), np.sin(t)])  # up-slope
        nu = max(1, int(np.ceil(f.across_m / spacing - 1e-9)))
        nv = max(1, int(np.ceil(f.slope_m / spacing - 1e-9)))
        cu = (np.arange(nu) + 0.5) / nu * f.across_m - f.across_m / 2
        cv = (np.arange(nv) + 0.5) / nv * f.slope_m - f.slope_m / 2
        k = 0
        for v in cv:
            for u in cu:
                p = np.asarray(f.centre_m) + u * edge + v * up
                rows.append(
                    dict(
                        facet_id=f.id,
                        sample_id=k,
                        x_body=p[0],
                        y_body=p[1],
                        z_body=p[2],
                        nx=n[0],
                        ny=n[1],
                        nz=n[2],
                        area_m2=f.area_m2 / (nu * nv),
                    )
                )
                k += 1
    return pd.DataFrame(rows)
