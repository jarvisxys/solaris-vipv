"""P4 / E1: verify every shading component (workflow guide Sec. 5, E1).

Analytic E1 tests run here on synthetic geometry: sun position, transposition, shadow length,
canyon SVF, plus engine unit tests. The cross-engine (1,000 downtown points) and SOLWEIG
checks need the P3 city model; they run in experiments/e1_verify (rule e1_verification), and
test_e1_report asserts its verdicts.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pvlib
import pytest
import trimesh
from rasterio.transform import from_origin

from solaris.geometry.meshes import tile_mesh
from solaris.pv.irradiance import facet_irradiance
from solaris.shading import (
    MeshEngine,
    beam_visible,
    bitmask,
    horizon,
    horizon_at,
    march_steps,
    shadow_map,
    sky_view_factor,
    sun_position,
    svf_from_mask,
)
from solaris.shading.noaa import noaa_sun

RES = 0.5
STEPS = march_steps(RES, 1000.0)
PHX = (33.4484, -112.0740)
REPORT = Path(__file__).resolve().parents[1] / "results" / "e1" / "table_e1.csv"


def angle_between(el1, az1, el2, az2):
    def v(e, a):
        e, a = np.radians(e), np.radians(a)
        return np.array([np.sin(a) * np.cos(e), np.cos(a) * np.cos(e), np.sin(e)])

    return np.degrees(np.arccos(np.clip(v(el1, az1) @ v(el2, az2), -1, 1)))


def mesh_of(z, x0, y1, error=0.01):
    v, f = tile_mesh(z, x0 + RES / 2, y1 - RES / 2, RES, error, 0.0)
    return trimesh.Trimesh(v, f, process=False)


# ---------------------------------------------------------------- E1 sun position
def test_spa_matches_nrel_reference_vector():
    """Reda & Andreas (2004) Table A5.1: 2003-10-17 12:30:30 MST-0700, Golden CO."""
    t = pd.DatetimeIndex([pd.Timestamp("2003-10-17 12:30:30", tz="Etc/GMT+7")])
    r = pvlib.solarposition.spa_python(
        t,
        39.742476,
        -105.1786,
        altitude=1830.14,
        pressure=82000,
        temperature=11,
        delta_t=67,
        atmos_refract=0.5667,
    )
    assert abs(r.apparent_zenith.iloc[0] - 50.11162) < 0.01
    assert abs(r.azimuth.iloc[0] - 194.34024) < 0.01


@pytest.mark.parametrize(
    "when",
    [
        "2023-03-20 08:00",
        "2023-06-21 12:00",
        "2023-09-22 16:00",
        "2023-12-21 10:30",
        "2023-07-15 17:15",
    ],
)
def test_sun_position_matches_noaa_in_phoenix(when):
    t = pd.Timestamp(when, tz="America/Phoenix")
    sp = sun_position([t], *PHX, altitude=331.0).iloc[0]
    el, az = noaa_sun(t.year, t.month, t.day, t.hour + t.minute / 60, -7, *PHX)
    assert angle_between(el, az, sp.elevation, sp.azimuth) < 0.01


# ---------------------------------------------------------------- E1 transposition
@pytest.fixture(scope="module")
def clear_day():
    times = pd.date_range(
        "2023-06-21 05:00", "2023-06-21 19:00", freq="10min", tz="America/Phoenix"
    )
    loc = pvlib.location.Location(*PHX, tz="America/Phoenix", altitude=331)
    sp = loc.get_solarposition(times)
    cs = loc.get_clearsky(times, model="ineichen")
    day = sp.apparent_zenith < 85
    sp, cs = sp[day], cs[day]
    ghi = cs.dni * np.cos(np.radians(sp.apparent_zenith)) + cs.dhi  # closure: GHI = DNI cosZ + DHI
    extra = pvlib.irradiance.get_extra_radiation(sp.index)
    am = pvlib.atmosphere.get_relative_airmass(sp.apparent_zenith)
    return sp, cs.dni, ghi, cs.dhi, extra, am


def test_unshaded_horizontal_facet_returns_ghi(clear_day):
    sp, dni, ghi, dhi, extra, am = clear_day
    g = facet_irradiance(0.0, 180.0, sp.apparent_zenith, sp.azimuth, dni, ghi, dhi, extra, am)
    assert np.max(np.abs(g - ghi)) < 1e-6


def test_unshaded_vertical_south_facet_matches_pvlib_perez(clear_day):
    sp, dni, ghi, dhi, extra, am = clear_day
    g = facet_irradiance(90.0, 180.0, sp.apparent_zenith, sp.azimuth, dni, ghi, dhi, extra, am)
    ref = pvlib.irradiance.get_total_irradiance(
        90.0,
        180.0,
        sp.apparent_zenith,
        sp.azimuth,
        dni,
        ghi,
        dhi,
        dni_extra=extra,
        airmass=am,
        albedo=0.20,
        model="perez",
    )
    assert np.max(np.abs(g - ref["poa_global"])) < 1e-6


def test_shading_factors_scale_their_components(clear_day):
    sp, dni, ghi, dhi, extra, am = clear_day
    args = (90.0, 180.0, sp.apparent_zenith, sp.azimuth, dni, ghi, dhi, extra, am)
    dark = facet_irradiance(*args, v_b=0.0, svf_f=0.0, v_hz=0.0, gvf_f=0.0)
    assert np.allclose(dark, 0.0)


# ---------------------------------------------------------------- E1 shadow length
@pytest.fixture(scope="module")
def box():
    """20 m tall, 20 x 20 m box at the centre of a flat 400 m square (ground 0)."""
    n = int(400 / RES)
    z = np.zeros((n, n), np.float32)
    z[n // 2 - 20 : n // 2 + 20, n // 2 - 20 : n // 2 + 20] = 20.0
    tr = from_origin(0.0, 400.0, RES, RES)
    north_face = 400.0 - (n // 2 - 20) * RES  # y of the box's north face
    return z, tr, north_face


@pytest.mark.parametrize("alpha", [15.0, 30.0, 60.0])
def test_shadow_length_raster_and_mesh(box, alpha):
    """Sun due south at elevation alpha: points north of the box at H/tan(alpha) - 1 m are
    shaded, at + 1 m sunlit."""
    z, tr, yn = box
    L = 20.0 / np.tan(np.radians(alpha))
    y = np.array([yn + L - 1.0, yn + L + 1.0])
    x = np.full(2, 200.0)
    h = horizon(z, tr, x, y, np.zeros(2), RES, STEPS, convergence=0.0)
    assert beam_visible(h, 180.0, alpha)[:, 0].tolist() == [False, True]
    sh = shadow_map(z, z, tr, RES, 180.0, alpha, STEPS)
    rows = ((400.0 - y) / RES).astype(int)
    assert sh[rows, 400].tolist() == [True, False]
    eng = MeshEngine([mesh_of(z, 0.0, 400.0)])
    pts = np.column_stack([x, y, np.full(2, 0.01)])
    assert eng.beam(pts, 180.0, alpha, trees=False)[:, 0].tolist() == [True, False]


# ---------------------------------------------------------------- E1 canyon SVF
@pytest.fixture(scope="module", params=[(0.5, 0.707), (1.0, 0.447), (2.0, 0.243)], ids=str)
def canyon(request):
    """Canyon along x, floor width 40 m, 4 km long (raster march reaches 1 km)."""
    hw, printed = request.param
    W = 40.0
    ny, nx = int(200 / RES), int(4000 / RES)
    z = np.zeros((ny, nx), np.float32)
    yc = (np.arange(ny) + 0.5) * RES - 100.0
    z[np.abs(yc) > W / 2, :] = hw * W
    return hw, printed, z, from_origin(0.0, 100.0, RES, RES)


def test_canyon_svf_raster(canyon):
    hw, printed, z, tr = canyon
    h = horizon(z, tr, [2000.0], [0.0], [0.0], RES, STEPS, convergence=0.0)
    exact = np.cos(np.arctan(2 * hw))
    assert abs(exact - printed) < 0.0005  # the guide's printed values
    assert abs(sky_view_factor(h)[0] - exact) < 0.01
    assert abs(svf_from_mask(bitmask(h))[0] - exact) < 0.01


def test_canyon_svf_mesh(canyon):
    hw, _, z, tr = canyon
    eng = MeshEngine([mesh_of(z, 0.0, 100.0)])
    m = eng.horizon_mask(np.array([[2000.0, 0.0, 0.01]]), trees=False)
    assert abs(svf_from_mask(m)[0] - np.cos(np.arctan(2 * hw))) < 0.01


# ---------------------------------------------------------------- engine unit tests
def test_meridian_convergence_rotates_the_mask():
    """A pillar due grid north appears at true azimuth = convergence (west of north here)."""
    n = int(400 / RES)
    z = np.zeros((n, n), np.float32)
    z[n // 2 - 400 : n // 2 - 398, n // 2 - 1 : n // 2 + 1] = 50.0  # 1 m pillar, 200 m grid-north
    tr = from_origin(0.0, 400.0, RES, RES)
    h = horizon(z, tr, [200.0], [200.0], [0.0], RES, STEPS, n_azimuth=3600, convergence=-0.592)
    peak = np.argmax(h[0]) / 10.0
    assert min(abs(peak - 359.408), abs(peak + 0.592)) < 0.15


def test_horizon_interpolation_wraps_at_north():
    h = np.zeros((1, 360), np.float32)
    h[0, 359], h[0, 0] = 10.0, 20.0
    assert horizon_at(h, [359.5])[0, 0] == pytest.approx(15.0)
    assert beam_visible(h, [359.5, 180.0], [14.0, 1.0]).tolist() == [[False, True]]


def test_bitmask_has_360_by_180_cells_and_open_sky_svf_is_one():
    h = np.full((2, 360), -5.0, np.float32)
    m = bitmask(h)
    assert m.shape == (2, 360, 180) and not m.any()
    assert np.allclose(svf_from_mask(m), 1.0) and np.allclose(sky_view_factor(h), 1.0)


def test_trees_block_only_the_tree_layer():
    tri = trimesh.creation.box(extents=(10, 10, 10))
    tri.apply_translation((0, 20, 5))  # 10 m cube, 15-25 m north of the point
    eng = MeshEngine([trimesh.creation.box(extents=(1, 1, 0.1))], [tri])
    hit_all = eng.beam(np.array([[0.0, 0.0, 1.0]]), 0.0, 10.0, trees=True)
    hit_bld = eng.beam(np.array([[0.0, 0.0, 1.0]]), 0.0, 10.0, trees=False)
    assert hit_all.tolist() == [[True]] and hit_bld.tolist() == [[False]]


# ---------------------------------------------------------------- E1 report (city model)
def test_e1_report():
    """Every E1 row passes (raster vs mesh on 1,000 downtown points, SOLWEIG, analytic)."""
    if not REPORT.exists():
        pytest.skip("results/e1/table_e1.csv not built (snakemake -c1 e1_verification)")
    t = pd.read_csv(REPORT)
    failed = t[~t["pass"]]
    assert failed.empty, failed.to_string()
