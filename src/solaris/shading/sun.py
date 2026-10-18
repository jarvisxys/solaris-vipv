"""Sun position, only from pvlib SPA (CLAUDE.md), and sun vectors in the ENU frame."""

import numpy as np
import pandas as pd
import pvlib

TZ = "America/Phoenix"


def sun_position(times, lat, lon, altitude=334.0):
    """Apparent elevation and true-north azimuth (deg) from NREL SPA (pvlib 'nrel_numpy')."""
    times = pd.DatetimeIndex(times)
    if times.tz is None:
        times = times.tz_localize(TZ)
    sp = pvlib.solarposition.get_solarposition(times, lat, lon, altitude=altitude)
    return pd.DataFrame(
        {"elevation": sp["apparent_elevation"], "azimuth": sp["azimuth"]}, index=times
    )


def sun_vector(azimuth_deg, elevation_deg):
    """Unit vectors toward the sun in ENU (x east, y north, z up); azimuth from true north."""
    az = np.radians(np.asarray(azimuth_deg, float))
    el = np.radians(np.asarray(elevation_deg, float))
    return np.stack([np.sin(az) * np.cos(el), np.cos(az) * np.cos(el), np.sin(el)], axis=-1)
