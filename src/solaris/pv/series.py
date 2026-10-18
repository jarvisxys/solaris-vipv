"""Irradiance at arbitrary instants of the reference year (P7 / E5, E6).

Times are seconds of the year from 2023-01-01 00:00 America/Phoenix (see solaris.annual).
Sun position is pvlib SPA at each instant. Weather comes from one of three series:

  tmy          NSRDB TMY, hourly: each instant takes its hour's value (the hourly-TMY
               convention every earlier experiment uses)
  y2023_hourly NSRDB CONUS 2023 5-min averaged to clock hours, used like the TMY
  y2023_5min   NSRDB CONUS 2023 5-min, linear between the 5-min instants

Facet terms follow the G_f equation of the workflow guide (pv.irradiance):
  G = v_b * beam + SVF_f * iso + v_hz * hz + ground,  beam = DNI cos(theta) + D_cs.
Everything is zero while the sun is below the horizon.
"""

import numpy as np
import pandas as pd
import pvlib

from solaris.weather import conus_5min, tmy_hourly

from .irradiance import perez_components

TZ = "America/Phoenix"
YEAR_START = pd.Timestamp("2023-01-01", tz=TZ)
YEAR_S = 8760 * 3600
FIELDS = ("ghi", "dni", "dhi", "temp_air", "wind_speed")


def times_of(t_s):
    return YEAR_START + pd.to_timedelta(np.asarray(t_s, np.int64), unit="s")


def sun_at(t_s, meta, offset_s=0.0):
    """Apparent zenith, azimuth, elevation, extraterrestrial DNI and relative air mass."""
    t = YEAR_START + pd.to_timedelta(np.asarray(t_s, float) + offset_s, unit="s")
    sp = pvlib.solarposition.get_solarposition(
        t, meta["latitude"], meta["longitude"], altitude=meta["altitude"]
    )
    zen = sp["apparent_zenith"].to_numpy()
    return {
        "zen": zen,
        "az": sp["azimuth"].to_numpy(),
        "el": sp["apparent_elevation"].to_numpy(),
        "extra": pvlib.irradiance.get_extra_radiation(t).to_numpy(),
        "am": np.asarray(pvlib.atmosphere.get_relative_airmass(zen), float),
    }


class Weather:
    """Weather at seconds of the year: ``hold`` = value of the hour, ``linear`` = between
    instants spaced ``step_s`` from 00:00."""

    def __init__(self, name, values: dict, mode, step_s):
        self.name, self.v, self.mode, self.step_s = name, values, mode, step_s

    def at(self, t_s):
        t = np.asarray(t_s, float)
        if self.mode == "hold":
            i = np.clip((t // self.step_s).astype(np.int64), 0, len(self.v["ghi"]) - 1)
            return {k: a[i] for k, a in self.v.items()}
        x = np.arange(len(self.v["ghi"])) * float(self.step_s)
        return {k: np.interp(t, x, a) for k, a in self.v.items()}

    def hourly_climate(self):
        """(GHI W/m2, T C) per hour for the SoC loop's demand side."""
        if self.mode == "hold" and self.step_s == 3600:
            return self.v["ghi"].copy(), self.v["temp_air"].copy()
        k = 3600 // self.step_s
        return (
            self.v["ghi"].reshape(-1, k).mean(axis=1),
            self.v["temp_air"].reshape(-1, k).mean(axis=1),
        )


def _cols(df):
    return {k: df[k].to_numpy(float) for k in FIELDS}


def load_weather(name):
    """(Weather, NSRDB metadata) for 'tmy', 'y2023_hourly' or 'y2023_5min'."""
    if name == "tmy":
        df, meta = tmy_hourly()
        return Weather(name, _cols(df), "hold", 3600), meta
    df, meta = conus_5min()
    v = _cols(df)
    if name == "y2023_5min":
        return Weather(name, v, "linear", 300), meta
    if name == "y2023_hourly":
        return Weather(
            name, {k: a.reshape(-1, 12).mean(axis=1) for k, a in v.items()}, "hold", 3600
        ), meta
    raise ValueError(name)


def facet_terms(tilt, compass_az, sun, w, albedo):
    """(beam, iso, hz, ground, sunny) for a facet; arrays over instants. ``sunny`` = sun up
    and in front of the facet."""
    iso, cs, hz = (
        np.nan_to_num(np.asarray(c, float))
        for c in perez_components(
            tilt, compass_az, sun["zen"], sun["az"], w["dni"], w["dhi"], sun["extra"], sun["am"]
        )
    )
    cos_i = np.clip(
        np.nan_to_num(pvlib.irradiance.aoi_projection(tilt, compass_az, sun["zen"], sun["az"])),
        0,
        None,
    )
    day = sun["el"] > 0
    gvf = (1 - np.cos(np.radians(tilt))) / 2
    beam = np.where(day, w["dni"] * cos_i + cs, 0.0)
    return (
        beam,
        np.where(day, iso, 0.0),
        np.where(day, hz, 0.0),
        np.where(day, albedo * w["ghi"] * gvf, 0.0),
        day & (cos_i > 0),
    )
