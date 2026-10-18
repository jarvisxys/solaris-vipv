"""E1: verify every shading component (workflow guide Sec. 5) and write the report.

One row per check in results/e1/table_e1.csv (check, case, engine, metric, value,
threshold, pass); details in results/e1/summary_e1.json. Checks:
  sun            pvlib SPA vs the NREL SPA reference vector and NOAA spot checks in Phoenix
  transposition  unshaded horizontal facet = GHI; vertical south = pvlib Perez
  shadow_length  20 m box, points at H/tan(alpha) -/+ 1 m, raster and mesh engines
  canyon_svf     floor-centre SVF of H/W = 0.5, 1, 2 canyons, raster and mesh engines
  cross_engine   1,000 random downtown points: beam agreement and |dSVF|, raster vs mesh
  solweig        shadow maps on the downtown 1 km2 vs UMEP SOLWEIG, 4 days x 3 hours

Run by Snakemake (rule e1_verification) or:
  python experiments/e1_verify/run.py [--table CSV] [--summary JSON] [--skip-city]
"""

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pvlib
import rasterio
import trimesh
import yaml
from rasterio.transform import from_origin
from rasterio.windows import from_bounds
from scipy import ndimage

from solaris.core.params import REPO_ROOT
from solaris.geometry.crs import GEOG_CRS, H_CRS
from solaris.geometry.meshes import tile_mesh
from solaris.pv.irradiance import facet_irradiance
from solaris.shading import (
    MeshEngine,
    beam_visible,
    bitmask,
    city_engine,
    convergence_deg,
    horizon,
    horizon_at,
    march_steps,
    shadow_map,
    sun_position,
    svf_from_mask,
)
from solaris.shading import solweig as sw
from solaris.shading.noaa import noaa_sun
from solaris.site import site_config

E1_YAML = REPO_ROOT / "configs" / "experiments" / "e1.yaml"
D = REPO_ROOT / "data" / "derived"
PHX = (33.4484, -112.0740)
RES = 0.5


def row(check, case, engine, metric, value, threshold, op="<="):
    ok = value <= threshold if op == "<=" else value >= threshold
    return dict(
        check=check,
        case=case,
        engine=engine,
        metric=metric,
        value=float(value),
        threshold=float(threshold),
        op=op,
        **{"pass": bool(ok)},
    )


def angle_between(el1, az1, el2, az2):
    def v(e, a):
        e, a = np.radians(e), np.radians(a)
        return np.array([np.sin(a) * np.cos(e), np.cos(a) * np.cos(e), np.sin(e)])

    return float(np.degrees(np.arccos(np.clip(v(el1, az1) @ v(el2, az2), -1, 1))))


# ---------------------------------------------------------------- analytic checks
def sun_checks(e1):
    tol = e1["sun"]["tol_deg"]
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
    rows = [
        row(
            "sun",
            "SPA reference zenith",
            "pvlib SPA",
            "abs error deg",
            abs(r.apparent_zenith.iloc[0] - 50.11162),
            tol,
        ),
        row(
            "sun",
            "SPA reference azimuth",
            "pvlib SPA",
            "abs error deg",
            abs(r.azimuth.iloc[0] - 194.34024),
            tol,
        ),
    ]
    for when in e1["sun"]["noaa_spot_checks"]:
        ts = pd.Timestamp(when, tz="America/Phoenix")
        sp = sun_position([ts], *PHX, altitude=331.0).iloc[0]
        el, az = noaa_sun(ts.year, ts.month, ts.day, ts.hour + ts.minute / 60, -7, *PHX)
        err = angle_between(el, az, sp.elevation, sp.azimuth)
        rows.append(row("sun", f"NOAA Phoenix {when}", "pvlib SPA", "angle deg", err, tol))
    return rows


def transposition_checks(e1):
    tol = e1["transposition"]["tol_wm2"]
    times = pd.date_range(
        "2023-06-21 05:00", "2023-06-21 19:00", freq="10min", tz="America/Phoenix"
    )
    loc = pvlib.location.Location(*PHX, tz="America/Phoenix", altitude=331)
    sp, cs = loc.get_solarposition(times), loc.get_clearsky(times, model="ineichen")
    day = sp.apparent_zenith < 85
    sp, cs = sp[day], cs[day]
    ghi = cs.dni * np.cos(np.radians(sp.apparent_zenith)) + cs.dhi
    extra = pvlib.irradiance.get_extra_radiation(sp.index)
    am = pvlib.atmosphere.get_relative_airmass(sp.apparent_zenith)
    args = (sp.apparent_zenith, sp.azimuth, cs.dni, ghi, cs.dhi, extra, am)
    flat = facet_irradiance(0.0, 180.0, *args)
    vert = facet_irradiance(90.0, 180.0, *args)
    ref = pvlib.irradiance.get_total_irradiance(
        90.0,
        180.0,
        sp.apparent_zenith,
        sp.azimuth,
        cs.dni,
        ghi,
        cs.dhi,
        dni_extra=extra,
        airmass=am,
        albedo=0.20,
        model="perez",
    )
    return [
        row(
            "transposition",
            "horizontal = GHI",
            "facet model",
            "max abs W/m2",
            np.max(np.abs(flat - ghi)),
            tol,
        ),
        row(
            "transposition",
            "vertical south = pvlib Perez",
            "facet model",
            "max abs W/m2",
            np.max(np.abs(vert - ref["poa_global"])),
            tol,
        ),
    ]


def _mesh(z, x0, y1, error=0.01):
    v, f = tile_mesh(z, x0 + RES / 2, y1 - RES / 2, RES, error, 0.0)
    return trimesh.Trimesh(v, f, process=False)


def shadow_length_checks(e1):
    s = e1["shadow_length"]
    H, off = s["box_height_m"], s["offset_m"]
    n = int(400 / RES)
    z = np.zeros((n, n), np.float32)
    z[n // 2 - 20 : n // 2 + 20, n // 2 - 20 : n // 2 + 20] = H
    tr = from_origin(0.0, 400.0, RES, RES)
    yn = 400.0 - (n // 2 - 20) * RES
    steps = march_steps(RES, 1000.0)
    eng = MeshEngine([_mesh(z, 0.0, 400.0)])
    rows = []
    for a in s["alphas_deg"]:
        L = H / np.tan(np.radians(a))
        y = np.array([yn + L - off, yn + L + off])
        x = np.full(2, 200.0)
        h = horizon(z, tr, x, y, np.zeros(2), RES, steps, convergence=0.0)
        rast = beam_visible(h, 180.0, a)[:, 0].tolist() == [False, True]
        sh = shadow_map(z, z, tr, RES, 180.0, a, steps)
        smap = sh[((400.0 - y) / RES).astype(int), 400].tolist() == [True, False]
        mesh = eng.beam(np.column_stack([x, y, np.full(2, 0.01)]), 180.0, a, trees=False)
        mesh_ok = mesh[:, 0].tolist() == [True, False]
        for engine, ok in (
            ("raster horizon", rast),
            ("raster shadow map", smap),
            ("mesh", mesh_ok),
        ):
            rows.append(
                row(
                    "shadow_length",
                    f"alpha {a:g} deg, L {L:.1f} m +/- {off:g} m",
                    engine,
                    "points misclassified",
                    0 if ok else 2,
                    0,
                )
            )
    return rows


def canyon_checks(e1):
    c = e1["canyon"]
    W = c["floor_width_m"]
    steps = march_steps(RES, 1000.0)
    rows = []
    for hw, printed in c["cases"]:
        ny, nx = int(200 / RES), int(4000 / RES)
        z = np.zeros((ny, nx), np.float32)
        yc = (np.arange(ny) + 0.5) * RES - 100.0
        z[np.abs(yc) > W / 2, :] = hw * W
        tr = from_origin(0.0, 100.0, RES, RES)
        exact = np.cos(np.arctan(2 * hw))
        h = horizon(z, tr, [2000.0], [0.0], [0.0], RES, steps, convergence=0.0)
        svf_r = svf_from_mask(bitmask(h))[0]
        m = MeshEngine([_mesh(z, 0.0, 100.0)]).horizon_mask(
            np.array([[2000.0, 0.0, 0.01]]), trees=False
        )
        svf_m = svf_from_mask(m)[0]
        case = f"H/W {hw:g} (exact {exact:.3f}, printed {printed})"
        rows.append(row("canyon_svf", case, "raster", "abs error", abs(svf_r - exact), c["tol"]))
        rows.append(row("canyon_svf", case, "mesh", "abs error", abs(svf_m - exact), c["tol"]))
    return rows


# ---------------------------------------------------------------- city-model checks
def read_window(path, bounds):
    with rasterio.open(path) as s:
        w = from_bounds(*bounds, transform=s.transform).round_offsets().round_lengths()
        a = s.read(1, window=w, boundless=True, masked=True, out_dtype="float32").filled(np.nan)
        return a, s.window_transform(w)


def sample_points(e1, bounds, rng):
    """Random points on open ground (class 0, no canopy, no DSM hole) in the tile, at least
    ``min_wall_distance_m`` from any building pixel. Closer than that, a point lies inside the
    mesh's wall slope (heightfield vertices sit at pixel centres), which no vehicle roof can."""
    cls, tr = read_window(D / "classes.tif", bounds)
    cdsm, _ = read_window(D / "cdsm.tif", bounds)
    holes, _ = read_window(D / "dsm_holes.tif", bounds)
    wall = ndimage.distance_transform_edt(cls != 1) * RES
    ok = (cls == 0) & (cdsm == 0) & (holes == 0)
    ok &= wall >= e1["cross_engine"]["min_wall_distance_m"]
    r, c = np.nonzero(ok)
    pick = rng.choice(len(r), e1["cross_engine"]["n_points"], replace=False)
    x, y = tr * (c[pick] + rng.random(len(pick)), r[pick] + rng.random(len(pick)))
    return np.asarray(x), np.asarray(y)


def mesh_horizon_line(mask, elevation_step=0.5):
    """Top of the highest blocked cell per azimuth (deg); -1 where nothing is blocked."""
    n = mask.shape[-1]
    idx = np.where(mask.any(-1), n - np.argmax(mask[..., ::-1], axis=-1), 0)
    return np.where(mask.any(-1), idx * elevation_step, -1.0)


def suns(e1):
    ce = e1["cross_engine"]
    ts = [
        pd.Timestamp(f"{d} {h:02d}:00", tz="America/Phoenix")
        for d in ce["days"]
        for h in ce["hours"]
    ]
    sp = sun_position(ts, *PHX, altitude=331.0)
    return sp[sp.elevation > ce["min_sun_elevation_deg"]]


def cross_engine_checks(e1, cfg, details):
    ce, sh = e1["cross_engine"], cfg["shading"]
    rng = np.random.default_rng(e1["seed"])
    tile = e1["downtown_tile_utm"]
    dmax = sh["max_distance_m"]
    big = (tile[0] - dmax, tile[1] - dmax, tile[2] + dmax, tile[3] + dmax)
    x, y = sample_points(e1, tile, rng)
    dsm, tr = read_window(D / "dsm.tif", big)
    dem, _ = read_window(D / "dem.tif", big)
    cdsm, _ = read_window(D / "cdsm.tif", big)
    col, rw = ~tr * (x, y)
    ground = dem[rw.astype(int), col.astype(int)]
    z = ground + ce["eye_height_m"]
    steps = march_steps(RES, dmax, sh["near_m"], sh["growth"])
    t0 = time.time()
    h_bld = horizon(dsm, tr, x, y, z, RES, steps, sh["n_azimuth"])
    h_all = horizon(
        np.fmax(dsm, dem + np.nan_to_num(cdsm)), tr, x, y, z, RES, steps, sh["n_azimuth"]
    )
    t_raster = time.time() - t0

    origin = json.loads((REPO_ROOT / "twin" / "exchange" / "enu_origin.json").read_text())
    t0 = time.time()
    eng, to_enu = city_engine(cfg, D / "tiles", origin, big)
    p = to_enu(x, y, z)
    m_bld = eng.horizon_mask(p, sh["n_azimuth"], sh["elevation_step_deg"], trees=False)
    m_all = eng.horizon_mask(p, sh["n_azimuth"], sh["elevation_step_deg"], trees=True)
    t_mesh = time.time() - t0

    s = suns(e1)
    az, el = s.azimuth.to_numpy(), s.elevation.to_numpy()
    rows = []
    for layer, h, m, trees in (
        ("buildings", h_bld, m_bld, False),
        ("buildings+trees", h_all, m_all, True),
    ):
        vis_r = beam_visible(h, az, el)
        vis_m = ~eng.beam(p, az, el, trees=trees)
        hz_r = horizon_at(h, az)
        hz_m = horizon_at(mesh_horizon_line(m, sh["elevation_step_deg"]), az)
        keep = (np.abs(el[None, :] - hz_r) >= ce["horizon_exclusion_deg"]) & (
            np.abs(el[None, :] - hz_m) >= ce["horizon_exclusion_deg"]
        )
        agree = float(np.mean(vis_r[keep] == vis_m[keep]))
        dsvf = np.abs(svf_from_mask(bitmask(h, sh["elevation_step_deg"])) - svf_from_mask(m))
        rows.append(
            row(
                "cross_engine",
                f"beam, {layer}",
                "raster vs mesh",
                "agreement",
                agree,
                ce["min_beam_agreement"],
                ">=",
            )
        )
        rows.append(
            row(
                "cross_engine",
                f"SVF, {layer}",
                "raster vs mesh",
                "mean |dSVF|",
                dsvf.mean(),
                ce["max_mean_abs_dsvf"],
            )
        )
        details[f"cross_engine_{layer}"] = {
            "cases": int(vis_r.size),
            "kept_after_horizon_exclusion": int(keep.sum()),
            "beam_agreement": round(agree, 4),
            "dsvf_mean": round(float(dsvf.mean()), 4),
            "dsvf_median": round(float(np.median(dsvf)), 4),
            "dsvf_p95": round(float(np.percentile(dsvf, 95)), 4),
            "dsvf_max": round(float(dsvf.max()), 4),
            "svf_raster_mean": round(float(svf_from_mask(bitmask(h)).mean()), 4),
        }
    details["cross_engine"] = {
        "points": len(x),
        "suns": len(s),
        "mesh_faces": eng.faces,
        "raster_s": round(t_raster, 1),
        "mesh_s": round(t_mesh, 1),
        "tile_utm": tile,
    }
    return rows


def solweig_checks(e1, cfg, details, work):
    so = e1["solweig"]
    tile = e1["downtown_tile_utm"]
    b = so["buffer_m"]
    big = (tile[0] - b, tile[1] - b, tile[2] + b, tile[3] + b)
    work.mkdir(parents=True, exist_ok=True)
    dsm, tr = sw.clip(D / "dsm.tif", big, work / "dsm.tif")
    cdsm, _ = sw.clip(D / "cdsm.tif", big, work / "cdsm.tif")
    dem, _ = read_window(D / "dem.tif", big)
    canopy = cdsm > 0
    top = np.where(canopy, dem + cdsm, np.nan)
    bot = np.where(canopy, dem + so["trunk_zone_pct"] / 100.0 * cdsm, np.nan)
    inner = (slice(int(b / RES), -int(b / RES)), slice(int(b / RES), -int(b / RES)))
    cx, cy = (tile[0] + tile[2]) / 2, (tile[1] + tile[3]) / 2
    conv = float(convergence_deg(np.array([cx]), np.array([cy]))[0])
    import pyproj

    lon, lat = pyproj.Transformer.from_crs(H_CRS, GEOG_CRS, always_xy=True).transform(cx, cy)
    steps = march_steps(RES, float(np.hypot(*dsm.shape) * RES))
    rows, det = [], []
    for d in so["days"]:
        for hr in so["hours"]:
            when = pd.Timestamp(f"{d} {hr:02d}:00")
            out = work / f"solweig_{when:%Y%m%d_%H%M}.tif"
            ref = (
                sw.shadow(
                    work / "dsm.tif",
                    work / "cdsm.tif",
                    when,
                    out,
                    so["transmissivity_pct"],
                    so["trunk_zone_pct"],
                )
                if not out.exists()
                else (rasterio.open(out).read(1))
            )
            sp = sun_position([when.tz_localize("America/Phoenix")], lat, lon, altitude=331.0).iloc[
                0
            ]
            bld, veg = shadow_map(
                dsm, dsm, tr, RES, sp.azimuth, sp.elevation, steps, conv, top, bot
            )
            ours = (bld | veg)[inner]
            theirs = (ref < 0.5)[inner]
            agree = float(np.mean(ours == theirs))
            rows.append(
                row(
                    "solweig",
                    f"{when:%Y-%m-%d %H:%M} MST",
                    "raster vs SOLWEIG",
                    "pixel agreement",
                    agree,
                    so["min_pixel_agreement"],
                    ">=",
                )
            )
            det.append(
                {
                    "time": f"{when:%Y-%m-%d %H:%M}",
                    "sun_el": round(float(sp.elevation), 2),
                    "agreement": round(agree, 4),
                    "shaded_ours": round(float(ours.mean()), 4),
                    "shaded_solweig": round(float(theirs.mean()), 4),
                }
            )
    details["solweig"] = det
    return rows


def main(out_table, out_summary, skip_city=False):
    e1 = yaml.safe_load(E1_YAML.read_text(encoding="utf-8"))
    cfg = site_config()
    details = {}
    rows = sun_checks(e1) + transposition_checks(e1) + shadow_length_checks(e1) + canyon_checks(e1)
    if not skip_city:
        rows += cross_engine_checks(e1, cfg, details)
        rows += solweig_checks(e1, cfg, details, D / "e1")
    t = pd.DataFrame(rows)
    Path(out_table).parent.mkdir(parents=True, exist_ok=True)
    t.to_csv(out_table, index=False, lineterminator="\n", float_format="%.6g")
    details["passed"] = int(t["pass"].sum())
    details["total"] = len(t)
    Path(out_summary).write_text(
        json.dumps(details, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return t


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--table", default="results/e1/table_e1.csv")
    ap.add_argument("--summary", default="results/e1/summary_e1.json")
    ap.add_argument("--skip-city", action="store_true")
    a = ap.parse_args()
    print(main(a.table, a.summary, a.skip_city).to_string())
