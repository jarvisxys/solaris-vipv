"""P7 / E5: weather and facet irradiance at arbitrary instants (solaris.pv.series)."""

import numpy as np
import pytest

from solaris.pv import series

META = {"latitude": 33.45, "longitude": -112.06, "altitude": 340.0}


def _wx(n, step):
    v = {k: np.arange(n, dtype=float) for k in series.FIELDS}
    return series.Weather("x", v, "hold" if step == 3600 else "linear", step)


def test_hold_takes_the_hour_value_and_linear_interpolates():
    h = _wx(8760, 3600)
    assert h.at([0, 3599, 3600, 7199])["ghi"].tolist() == [0, 0, 1, 1]
    m = _wx(105120, 300)
    assert m.at([0, 150, 300])["ghi"].tolist() == [0, 0.5, 1]


def test_hourly_climate_averages_5_min_values():
    m = _wx(105120, 300)
    ghi, T = m.hourly_climate()
    assert len(ghi) == 8760 and ghi[0] == pytest.approx(5.5) and T[1] == pytest.approx(17.5)


def test_horizontal_open_facet_gets_dni_cos_z_plus_dhi():
    t = np.array([12 * 3600 + 1800, 170 * 86400 + 9 * 3600, 2 * 3600])  # noon, morning, night
    sun = series.sun_at(t, META)
    w = {"ghi": np.full(3, 900.0), "dni": np.full(3, 800.0), "dhi": np.full(3, 100.0)}
    beam, iso, hz, ground, sunny = series.facet_terms(0.0, 180.0, sun, w, 0.2)
    g = beam + iso + hz + ground
    ref = 800 * np.cos(np.radians(sun["zen"][:2])) + 100
    assert g[:2] == pytest.approx(ref, rel=1e-9)
    assert g[2] == 0 and not sunny[2] and sunny[0]
