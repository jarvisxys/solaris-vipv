"""E4: parking shading at P1-P5 x 4 headings (workflow guide Sec. 5).

Horizon masks once per facet sample (360 azimuth x 0.5 deg, buildings and buildings+trees;
the P5 shade roof is added to the mask), then every daylight 5-min step of the TMY year:

    G = v_b (DNI cos(theta) + D_cs) + SVF_f D_iso + v_hz D_hz + rho GHI GVF_f

per sample (v_b: 0 under buildings or the roof, tau under trees only, 1 open), averaged
over each facet, Faiman cell temperature (parked: ambient wind), conference electrical
model. F_park = E_site / E_open per site, heading, month. SOLWEIG cross-check at P1-P3.

Outputs: results/e4/table_e4.csv, results/e4/table_e4_sites.csv, results/e4/summary_e4.json;
masks in data/derived/e4/.
"""

import argparse
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pvlib
import yaml

from solaris.core.params import BASE, REPO_ROOT
from solaris.geometry.crs import H_CRS
from solaris.pv.irradiance import perez_components
from solaris.pv.model import cell_temperature, pv_energy
from solaris.shading import bitmask, facet_sky_weights, solweig
from solaris.shading.city import D, ground, horizons
from solaris.site import site_config
from solaris.vehicle import facets, normal_enu, samples, to_world, vehicle_config
from solaris.weather import tmy_hourly

E4_YAML = REPO_ROOT / "configs" / "experiments" / "e4.yaml"
SITES = REPO_ROOT / "routes" / site_config()["routes"]["version"] / "parking_sites.geojson"
EL_STEP = 0.5


def canopy_mask(world, x0, y0, z_ground, heading, pc5, n_az=360):
    """Cells (samples, az, el) blocked by a flat roof pc5 x pc5 at canopy_height above
    ground, centred over the car and aligned with it."""
    az = np.radians(np.arange(n_az) * 360.0 / n_az)
    el = np.radians((np.arange(int(90 / EL_STEP)) + 0.5) * EL_STEP)
    A, E = np.meshgrid(az, el, indexing="ij")
    h = np.radians(heading)
    fwd, left = np.array([np.sin(h), np.cos(h)]), np.array([-np.cos(h), np.sin(h)])
    out = np.zeros((len(world), n_az, len(el)), bool)
    for i, (sx, sy, sz) in enumerate(world):
        r = (z_ground + pc5["canopy_height_m"] - sz) / np.tan(E)
        hx, hy = sx + r * np.sin(A) - x0, sy + r * np.cos(A) - y0
        along, across = hx * fwd[0] + hy * fwd[1], hx * left[0] + hy * left[1]
        out[i] = (np.abs(along) <= pc5["canopy_along_m"] / 2) & (
            np.abs(across) <= pc5["canopy_across_m"] / 2
        )
    return out


def time_steps(step_min, lat, lon, alt):
    """Daylight 5-min steps of the TMY reference year with sun position at the step centre."""
    t = pd.date_range(
        "2023-01-01", "2024-01-01", freq=f"{step_min}min", tz="America/Phoenix", inclusive="left"
    )
    mid = t + pd.Timedelta(minutes=step_min / 2)
    sp = pvlib.solarposition.get_solarposition(mid, lat, lon, altitude=alt)
    day = (sp["apparent_elevation"] > 0).to_numpy()
    return t[day], sp[day]


def site_energy(site, heading, e4, vcfg, wx_steps, sp, steps_dt_h, cfg, tau, cache):
    """(E_site, E_open) per step (kWh) for one site, heading and tree transmissivity."""
    pvcfg = vcfg["pv"]
    key = (site["id"], heading)
    if key not in cache:
        cache[key] = site_masks(site, heading, vcfg, cfg)
    mb, ma, world = cache[key]
    az_i = np.rint(sp["azimuth"].to_numpy()).astype(int) % mb.shape[1]
    el_i = np.clip((sp["apparent_elevation"].to_numpy() / EL_STEP).astype(int), 0, mb.shape[2] - 1)
    zen, az = sp["apparent_zenith"].to_numpy(), sp["azimuth"].to_numpy()
    dni, dhi, ghi = (wx_steps[k].to_numpy() for k in ("dni", "dhi", "ghi"))
    extra = pvlib.irradiance.get_extra_radiation(sp.index).to_numpy()
    am = pvlib.atmosphere.get_relative_airmass(zen)
    s = samples(facets(vcfg), vcfg["sample_spacing_m"])
    e_site = np.zeros(len(sp))
    e_open = np.zeros(len(sp))
    band = int(round(e4["horizon_band_deg"] / EL_STEP))
    for f in facets(vcfg):
        idx = np.nonzero(s["facet_id"].to_numpy() == f.id)[0]
        n = normal_enu(f, heading)
        caz = (heading + f.azimuth_body_deg) % 360
        iso, cs, hz = (
            np.nan_to_num(np.asarray(c, float))
            for c in perez_components(f.tilt_deg, caz, zen, az, dni, dhi, extra, am)
        )
        cos_i = np.clip(pvlib.irradiance.aoi_projection(f.tilt_deg, caz, zen, az), 0, None)
        beam = dni * cos_i
        gvf = (1 - np.cos(np.radians(f.tilt_deg))) / 2
        W = facet_sky_weights(n, mb.shape[1], EL_STEP)
        wt, wb = W.sum(), W[:, :band].sum()
        # per-sample view of sky and horizon band; trees pass tau
        open_cells = ~ma[idx]
        tree_cells = ma[idx] & ~mb[idx]
        svf = ((open_cells * W).sum((1, 2)) + tau * (tree_cells * W).sum((1, 2))) / wt
        vhz = (
            (
                (open_cells[:, :, :band] * W[:, :band]).sum((1, 2))
                + tau * (tree_cells[:, :, :band] * W[:, :band]).sum((1, 2))
            )
            / wb
            if wb > 0
            else np.ones(len(idx))
        )
        blocked_b = mb[idx][:, az_i, el_i]
        blocked_a = ma[idx][:, az_i, el_i]
        vb = np.where(blocked_b, 0.0, np.where(blocked_a, tau, 1.0)).mean(axis=0)
        g_site = vb * (beam + cs) + svf.mean() * iso + vhz.mean() * hz + pvcfg["albedo"] * ghi * gvf
        g_open = beam + cs + iso + hz + pvcfg["albedo"] * ghi * gvf
        fa = pvcfg["faiman"]
        T, ws = wx_steps["temp_air"].to_numpy(), wx_steps["wind_speed"].to_numpy()
        for g, acc in ((g_site, e_site), (g_open, e_open)):
            tc = cell_temperature(g, T, ws, "faiman", fa["u0"], fa["u1"])
            acc += pv_energy(f.area_m2, g, tc, p=BASE) * steps_dt_h
    return e_site, e_open


def site_masks(site, heading, vcfg, cfg):
    s = samples(facets(vcfg), vcfg["sample_spacing_m"])
    x0, y0 = site["x"], site["y"]
    zg = float(ground([x0], [y0], layer="dsm.tif" if site.get("deck") else "dem.tif")[0])
    world = to_world(s[["x_body", "y_body", "z_body"]].to_numpy(), x0, y0, zg, heading)
    h_b, h_a = horizons(world[:, 0], world[:, 1], world[:, 2], cfg["shading"])
    mb, ma = bitmask(h_b, EL_STEP), bitmask(h_a, EL_STEP)
    if site.get("canopy"):
        c = canopy_mask(world, x0, y0, zg, heading, cfg["parking"]["P5"])
        mb, ma = mb | c, ma | c
    out = D / "e4"
    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out / f"masks_{site['id']}_{int(heading):03d}.npz",
        buildings=np.packbits(mb, axis=-1),
        all=np.packbits(ma, axis=-1),
        world=world,
        azimuth_bins=360,
        elevation_step_deg=EL_STEP,
    )
    return mb, ma, world


def load_sites():
    g = gpd.read_file(SITES).to_crs(H_CRS)
    out = {}
    for r in g.itertuples():
        d = {k: getattr(r, k) for k in g.columns if k != "geometry"}
        d.update(x=r.geometry.x, y=r.geometry.y)
        d["deck"] = bool(d.get("deck")) if d.get("deck") == d.get("deck") else False
        d["canopy"] = bool(d.get("canopy")) if d.get("canopy") == d.get("canopy") else False
        out[d["id"]] = d
    return out


def main(out_table, out_sites, out_summary):
    e4 = yaml.safe_load(E4_YAML.read_text(encoding="utf-8"))
    cfg, vcfg = site_config(), vehicle_config()
    sites = load_sites()
    wx, meta = tmy_hourly()
    t, sp = time_steps(e4["step_min"], meta["latitude"], meta["longitude"], meta["altitude"])
    hour = (t.dayofyear - 1) * 24 + t.hour
    wx_steps = wx.iloc[hour].set_index(t)
    dt_h = e4["step_min"] / 60.0
    rows, cache = [], {}
    for sid in e4["sites"]:
        for hname, hdeg in e4["headings_deg"].items():
            for tau in e4["tau_sweep"]:
                es, eo = site_energy(
                    sites[sid], hdeg, e4, vcfg, wx_steps, sp, dt_h, cfg, tau, cache
                )
                m = pd.Series(es).groupby(t.month).sum(), pd.Series(eo).groupby(t.month).sum()
                for month in range(1, 13):
                    rows.append(
                        {
                            "site": sid,
                            "heading": hname,
                            "tau": tau,
                            "month": month,
                            "E_site_kWh": m[0][month],
                            "E_open_kWh": m[1][month],
                            "F_park": m[0][month] / m[1][month],
                        }
                    )
                rows.append(
                    {
                        "site": sid,
                        "heading": hname,
                        "tau": tau,
                        "month": "year",
                        "E_site_kWh": es.sum(),
                        "E_open_kWh": eo.sum(),
                        "F_park": es.sum() / eo.sum(),
                    }
                )
    table = pd.DataFrame(rows)

    so = e4["solweig"]
    checks = []
    for sid in so["sites"]:
        x, y, hs = sites[sid]["x"], sites[sid]["y"], so["half_size_m"]
        tile = (round(x - hs), round(y - hs), round(x + hs), round(y + hs))
        for d in solweig.compare_tile(
            tile,
            so["days"],
            so["hours"],
            so["buffer_m"],
            so["transmissivity_pct"],
            so["trunk_zone_pct"],
            D / "e4" / f"solweig_{sid}",
            D,
        ):
            checks.append({"site": sid, **d, "pass": d["agreement"] >= so["min_pixel_agreement"]})
    year = table[(table["month"] == "year") & (table["tau"] == e4["tree_transmissivity"])]
    summary = {
        "F_park_year_base_tau": {
            f"{r.site}-{r.heading}": round(r.F_park, 4) for r in year.itertuples()
        },
        "F_park_year_mean_heading": year.groupby("site")["F_park"].mean().round(4).to_dict(),
        "solweig": checks,
        "solweig_min_agreement": round(min(c["agreement"] for c in checks), 4),
        "pass": all(c["pass"] for c in checks),
    }
    for p in (out_table, out_sites, out_summary):
        Path(p).parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(out_table, index=False, lineterminator="\n", float_format="%.6g")
    pd.DataFrame([{k: v for k, v in s.items()} for s in sites.values()]).to_csv(
        out_sites, index=False, lineterminator="\n", float_format="%.6g"
    )
    Path(out_summary).write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--table", default="results/e4/table_e4.csv")
    ap.add_argument("--sites", default="results/e4/table_e4_sites.csv")
    ap.add_argument("--summary", default="results/e4/summary_e4.json")
    a = ap.parse_args()
    print(json.dumps(main(a.table, a.sites, a.summary), indent=2))
