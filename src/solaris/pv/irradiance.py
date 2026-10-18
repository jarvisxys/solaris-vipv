"""Facet irradiance with Perez components scaled by what the facet sees (workflow guide, E2):

    G_f = v_b (DNI cos(theta_i) + D_cs) + SVF_f D_iso + v_hz D_hz + rho GHI GVF_f

v_b beam visibility, SVF_f the facet's sky view relative to open ground (1 = unobstructed;
the (1 + cos beta) / 2 tilt factor is already in pvlib's isotropic term), v_hz horizon-band
visibility, GVF_f the ground view ((1 - cos beta) / 2 when unobstructed), rho the albedo.
With every factor at its unobstructed value G_f equals pvlib's Perez plane-of-array total.
"""

import numpy as np
import pvlib


def perez_components(tilt, azimuth, solar_zenith, solar_azimuth, dni, dhi, dni_extra, airmass):
    """pvlib Perez diffuse split: isotropic, circumsolar, horizon (W/m2)."""
    comp = pvlib.irradiance.perez(
        tilt,
        azimuth,
        dhi,
        dni,
        dni_extra,
        solar_zenith,
        solar_azimuth,
        airmass,
        return_components=True,
    )
    return comp["poa_isotropic"], comp["poa_circumsolar"], comp["poa_horizon"]


def facet_irradiance(
    tilt,
    azimuth,
    solar_zenith,
    solar_azimuth,
    dni,
    ghi,
    dhi,
    dni_extra,
    airmass,
    albedo=0.20,
    v_b=1.0,
    svf_f=1.0,
    v_hz=1.0,
    gvf_f=None,
):
    """Plane-of-facet irradiance (W/m2). ``airmass`` is relative (pvlib Perez input)."""
    iso, cs, hz = perez_components(
        tilt, azimuth, solar_zenith, solar_azimuth, dni, dhi, dni_extra, airmass
    )
    cos_i = np.maximum(
        pvlib.irradiance.aoi_projection(tilt, azimuth, solar_zenith, solar_azimuth), 0.0
    )
    if gvf_f is None:
        gvf_f = (1.0 - np.cos(np.radians(tilt))) / 2.0
    return v_b * (dni * cos_i + cs) + svf_f * iso + v_hz * hz + albedo * ghi * gvf_f
