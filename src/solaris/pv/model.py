"""Facet PV energy per hour (P5 / E2): G_f, cell temperature, conference electrical model.

    E_f = A_f * eta * G_f / 1000 * kappa * (1 + beta (T_cell - 25))      [kWh per hour]

eta, kappa and beta are the conference values (configs/base.yaml), so a horizontal 11.6 m2
skin reproduces the conference harvest (E2 case 2b). G_f comes from pv.irradiance with
pvlib Perez components at the TMY's own stamps (:30, solar position from pvlib SPA). T_cell
is pvlib Faiman with wind = ambient wind + vehicle speed while driving. In an hour that is
part driving, energy is the time-weighted mix of the parked and driving parts.
"""

import numpy as np
import pandas as pd
import pvlib

from solaris.core.params import BASE, Params

from .irradiance import facet_irradiance


def sun_inputs(index, lat, lon, altitude):
    """Solar geometry and Perez inputs at the weather stamps."""
    sp = pvlib.solarposition.get_solarposition(index, lat, lon, altitude=altitude)
    return pd.DataFrame(
        {
            "zenith": sp["apparent_zenith"],
            "azimuth": sp["azimuth"],
            "dni_extra": pvlib.irradiance.get_extra_radiation(index),
            "airmass": pvlib.atmosphere.get_relative_airmass(sp["apparent_zenith"]),
        },
        index=index,
    )


def facet_poa(facet_tilt, facet_azimuth, wx, sun, albedo, **visibility):
    """G_f (W/m2) for one facet orientation; ``visibility`` = v_b, svf_f, v_hz, gvf_f."""
    g = facet_irradiance(
        facet_tilt,
        facet_azimuth,
        sun["zenith"],
        sun["azimuth"],
        wx["dni"],
        wx["ghi"],
        wx["dhi"],
        sun["dni_extra"],
        sun["airmass"],
        albedo=albedo,
        **visibility,
    )
    return np.nan_to_num(np.asarray(g, float), nan=0.0).clip(min=0.0)


def cell_temperature(poa, temp_air, wind, model="faiman", u0=25.0, u1=6.84, p: Params = BASE):
    """Cell temperature (C): pvlib Faiman, or the conference rule T + 25 K per kW/m2."""
    if model == "faiman":
        return np.asarray(pvlib.temperature.faiman(poa, temp_air, wind, u0=u0, u1=u1), float)
    if model == "conference":
        return np.asarray(temp_air, float) + p.cell_temp_rise * np.asarray(poa, float) / 1000.0
    raise ValueError(model)


def pv_energy(area, poa, t_cell, kappa=None, p: Params = BASE):
    kappa = p.kappa_pv if kappa is None else kappa
    return area * p.eta_pv * poa / 1000.0 * kappa * (1 + p.beta * (t_cell - 25.0))


def vehicle_pv(fs, heading_deg, wx, sun, pvcfg, drive_frac, v_drive_ms, kappa=None, p=BASE):
    """Hourly PV energy (kWh) of a set of facets at a fixed heading.

    drive_frac  fraction of each hour spent driving (8760); v_drive_ms its mean speed
    Returns (total per hour, {facet id: (poa W/m2, kWh per hour)}).
    """
    model = pvcfg.get("temperature_model", "faiman")
    fa = pvcfg.get("faiman", {})
    wind = np.asarray(wx["wind_speed"], float)
    T = np.asarray(wx["temp_air"], float)
    frac = np.asarray(drive_frac, float)
    total = np.zeros(len(T))
    per = {}
    for f in fs:
        poa = facet_poa(f.tilt_deg, float(f.compass_azimuth(heading_deg)), wx, sun, pvcfg["albedo"])
        tc_park = cell_temperature(poa, T, wind, model, fa.get("u0", 25.0), fa.get("u1", 6.84), p)
        tc_drive = cell_temperature(
            poa, T, wind + v_drive_ms, model, fa.get("u0", 25.0), fa.get("u1", 6.84), p
        )
        e = (1 - frac) * pv_energy(f.area_m2, poa, tc_park, kappa, p) + frac * pv_energy(
            f.area_m2, poa, tc_drive, kappa, p
        )
        per[f.id] = (poa, e)
        total += e
    return total, per
