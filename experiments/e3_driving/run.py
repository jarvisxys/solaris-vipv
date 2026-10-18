"""E3: driving shading on the frozen routes (workflow guide Sec. 5).

360 trips: 3 routes x 2 directions x 5 departures x 4 days x 3 SUMO demand seeds, 1 Hz.
Paired cases on the identical trajectory: A = facets, no obstruction; B = buildings;
C = buildings + trees (transmissivity 0.03, swept to 0.3). Covered seconds (tunnels, under
bridges) block beam and sky in B and C. Clear sky (Ineichen) and the matching TMY day.

Per second and facet: v_b per facet sample (ray toward the sun over the P3 rasters), SVF_f
and v_hz from the horizon at the vehicle's roof centre, Perez components for the facet's
compass orientation, Faiman temperature with wind = TMY wind + vehicle speed.

Outputs: results/e3/table_e3_trips.csv (trip x day x sky x case), table_e3_summary.csv,
table_e3_tod.csv (time-of-day map), summary_e3.json (incl. the R-TUNNEL covered check).
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pvlib
import yaml

from solaris.core.params import BASE, REPO_ROOT
from solaris.pv.irradiance import perez_components
from solaris.pv.model import cell_temperature, pv_energy
from solaris.shading import beam_points, convergence_deg, facet_sky_weights, facet_view, march_steps
from solaris.shading.city import RES, horizons, surfaces
from solaris.site import site_config
from solaris.vehicle import body_axes, facets, normal_enu, samples, vehicle_config
from solaris.weather import tmy_hourly

E3_YAML = REPO_ROOT / "configs" / "experiments" / "e3.yaml"
TRAJ = REPO_ROOT / "data" / "derived" / "trajectories"
EL_STEP = 0.5


def load_trip(trip):
    f = pd.read_csv(TRAJ / f"{trip}.csv.gz")
    return f.sort_values("t").reset_index(drop=True)


def trip_ids(e3, routes=None, demand=None, departures=None):
    out = []
    for r in routes or e3["routes"]:
        for d in e3["directions"]:
            for dep in departures or e3["departures"]:
                h, m = map(int, dep.split(":"))
                secs = int((h * 60 + m - 450) * 60)  # seconds after the 07:30 sim start
                for s in demand or e3["demand"]:
                    out.append((f"{r}_{d}_{secs}_{s}", r, d, dep, s))
    return out


def position_horizons(trips, cfg, round_m):
    """Horizons at the roof centre of every rounded position over all trips."""
    keys = []
    for f in trips.values():
        keys.append(
            np.column_stack(
                [
                    np.round(f["x_utm"] / round_m),
                    np.round(f["y_utm"] / round_m),
                    np.round(f["z_road"], 1),
                ]
            )
        )
    uniq, inv = np.unique(np.concatenate(keys), axis=0, return_inverse=True)
    eye = cfg["routes"]["eye_height_m"]
    h_b, h_a = horizons(
        uniq[:, 0] * round_m, uniq[:, 1] * round_m, uniq[:, 2] + eye, cfg["shading"]
    )
    out, k = {}, 0
    for trip, f in trips.items():
        idx = inv.ravel()[k : k + len(f)]
        out[trip] = (h_b[idx], h_a[idx])
        k += len(f)
    return out


def facet_views(h_b, h_a, heading, fs, band_deg):
    """Per facet: (sky view, band view) for buildings-only and buildings+trees horizons."""
    hd = np.rint(heading).astype(int) % 360
    out = {f.id: {k: np.ones(len(hd)) for k in ("svf_b", "svf_a", "hz_b", "hz_a")} for f in fs}
    for h in np.unique(hd):
        sel = hd == h
        for f in fs:
            W = facet_sky_weights(normal_enu(f, float(h)), h_b.shape[1], EL_STEP)
            o = out[f.id]
            o["svf_b"][sel] = facet_view(h_b[sel], W, EL_STEP)
            o["svf_a"][sel] = facet_view(h_a[sel], W, EL_STEP)
            o["hz_b"][sel] = facet_view(h_b[sel], W, EL_STEP, band_deg)
            o["hz_a"][sel] = facet_view(h_a[sel], W, EL_STEP, band_deg)
    return out


class TripGeometry:
    """Everything about one trajectory that does not depend on the day or the sky."""

    def __init__(self, f, hz, e3, cfg, vcfg):
        self.fs = facets(vcfg)
        s = samples(self.fs, vcfg["sample_spacing_m"])
        body = s[["x_body", "y_body", "z_body"]].to_numpy()
        self.sid, self.area_s = s["facet_id"].to_numpy(), s["area_m2"].to_numpy()
        self.heading = f["angle"].to_numpy()
        self.cov = f["covered"].to_numpy().astype(bool)
        fwd, left = body_axes(self.heading)
        px, py, pz = f["x_utm"].to_numpy(), f["y_utm"].to_numpy(), f["z_road"].to_numpy()
        self.wx = (
            px[:, None] + body[None, :, 0] * fwd[:, None, 0] + body[None, :, 1] * left[:, None, 0]
        )
        self.wy = (
            py[:, None] + body[None, :, 0] * fwd[:, None, 1] + body[None, :, 1] * left[:, None, 1]
        )
        self.wz = pz[:, None] + body[None, :, 2]
        sh = cfg["shading"]
        d = sh["max_distance_m"]
        b = (self.wx.min() - d, self.wy.min() - d, self.wx.max() + d, self.wy.max() + d)
        self.dsm, self.allv, _, self.tr = surfaces(b)
        self.conv = float(convergence_deg(np.array([px.mean()]), np.array([py.mean()]))[0])
        self.steps = march_steps(RES, d, sh["near_m"], sh["growth"])
        self.views = facet_views(*hz, self.heading, self.fs, e3["horizon_band_deg"])

    def beam(self, sun_az, sun_el):
        """Beam blocked by buildings / trees for every sample of every second (n_s, n_samples)."""
        n, m = self.wx.shape
        az = np.repeat(np.asarray(sun_az)[:, None], m, axis=1).ravel()
        el = np.repeat(np.asarray(sun_el)[:, None], m, axis=1).ravel()
        bld, tree = beam_points(
            self.dsm,
            self.allv,
            self.tr,
            self.wx.ravel(),
            self.wy.ravel(),
            self.wz.ravel(),
            az,
            el,
            RES,
            self.steps,
            np.full(n * m, self.conv),
        )
        return bld.reshape(n, m), tree.reshape(n, m)


def irradiance(times, sky, wx, lat, lon, alt):
    if sky == "clear":
        cs = pvlib.location.Location(lat, lon, "America/Phoenix", alt).get_clearsky(
            times, model="ineichen"
        )
        return cs["ghi"].to_numpy(), cs["dni"].to_numpy(), cs["dhi"].to_numpy()
    hour = (times.dayofyear - 1) * 24 + times.hour
    r = wx.iloc[hour]
    return r["ghi"].to_numpy(), r["dni"].to_numpy(), r["dhi"].to_numpy()


def day_inputs(f, day, meta):
    clock = pd.to_datetime(f["time_local"]).dt.strftime("%H:%M:%S")
    times = pd.DatetimeIndex(pd.to_datetime(day + " " + clock)).tz_localize("America/Phoenix")
    sp = pvlib.solarposition.get_solarposition(
        times, meta["latitude"], meta["longitude"], altitude=meta["altitude"]
    )
    return times, sp


def run_trip(trip, f, geo, e3, vcfg, wx, meta, day, sky, times, sp, beam):
    fs, sid, area_s = geo.fs, geo.sid, geo.area_s
    zen, az, el = (
        sp["apparent_zenith"].to_numpy(),
        sp["azimuth"].to_numpy(),
        sp["apparent_elevation"].to_numpy(),
    )
    ghi, dni, dhi = irradiance(
        times, sky, wx, meta["latitude"], meta["longitude"], meta["altitude"]
    )
    extra = pvlib.irradiance.get_extra_radiation(times).to_numpy()
    am = pvlib.atmosphere.get_relative_airmass(zen)
    hour = (times.dayofyear - 1) * 24 + times.hour
    T = wx["temp_air"].to_numpy()[hour]
    wind = wx["wind_speed"].to_numpy()[hour] + f["speed"].to_numpy()
    heading, cov, views = geo.heading, geo.cov, geo.views
    bld, tree = beam
    # tau: what a tree passes. B ignores trees entirely (tau 1 in beam and sky); C has trees.
    cases = {"A": None, "B": 1.0, **{f"C{t:g}": t for t in e3["tau_sweep"]}}
    res = {c: {"pv_Wh": 0.0, "shaded_num": 0.0, "shaded_den": 0.0} for c in cases}
    for fct in fs:
        k = sid == fct.id
        caz = (heading + fct.azimuth_body_deg) % 360
        iso, cs, hzc = (
            np.nan_to_num(np.asarray(c, float))
            for c in perez_components(fct.tilt_deg, caz, zen, az, dni, dhi, extra, am)
        )
        cos_i = np.clip(pvlib.irradiance.aoi_projection(fct.tilt_deg, caz, zen, az), 0, None)
        beam = dni * cos_i
        gvf = (1 - np.cos(np.radians(fct.tilt_deg))) / 2
        sunny = (cos_i > 0) & (el > 0)
        a_k = area_s[k]
        v = views[fct.id]
        for c, tau in cases.items():
            if tau is None:
                vb, svf, vhz, g_r = np.ones(len(f)), 1.0, 1.0, gvf
            else:
                blk = np.where(bld[:, k], 0.0, np.where(tree[:, k], tau, 1.0))
                vb = (blk * a_k).sum(1) / a_k.sum()
                if c == "B":
                    svf, vhz = v["svf_b"], v["hz_b"]
                else:
                    svf = v["svf_a"] + tau * (v["svf_b"] - v["svf_a"])
                    vhz = v["hz_a"] + tau * (v["hz_b"] - v["hz_a"])
                vb, svf, vhz = np.where(cov, 0, vb), np.where(cov, 0, svf), np.where(cov, 0, vhz)
                g_r = np.where(cov, 0, gvf)
            g = vb * (beam + cs) + svf * iso + vhz * hzc + vcfg["pv"]["albedo"] * ghi * g_r
            fa = vcfg["pv"]["faiman"]
            tc = cell_temperature(g, T, wind, "faiman", fa["u0"], fa["u1"])
            res[c]["pv_Wh"] += float(
                (pv_energy(fct.area_m2, g, tc, p=BASE) * 1000.0 / 3600.0).sum()
            )
            res[c][f"inc_{fct.id}_Wh_m2"] = float(g.sum() / 3600.0)
            res[c]["shaded_num"] += float(((1 - vb) * sunny).sum() * a_k.sum())
            res[c]["shaded_den"] += float(sunny.sum() * a_k.sum())
    dist_km = float(np.hypot(np.diff(f["x_utm"]), np.diff(f["y_utm"])).sum() / 1000)
    rows = []
    for c, r in res.items():
        rows.append(
            {
                "trip": trip,
                "day": day,
                "sky": sky,
                "case": c,
                "duration_s": len(f),
                "distance_km": dist_km,
                "pv_Wh": r["pv_Wh"],
                "Wh_per_km": r["pv_Wh"] / dist_km,
                "beam_shaded_frac": r["shaded_num"] / r["shaded_den"]
                if r["shaded_den"]
                else np.nan,
                "covered_s": int(cov.sum()),
                **{k: v for k, v in r.items() if k.startswith("inc_")},
            }
        )
    return rows


def main(out_trips, out_summary_table, out_tod, out_summary):
    e3 = yaml.safe_load(E3_YAML.read_text(encoding="utf-8"))
    cfg, vcfg = site_config(), vehicle_config()
    wx, meta = tmy_hourly()
    tc = e3["tunnel_check"]
    trips = trip_ids(e3) + trip_ids(e3, [tc["route"]], [tc["demand"]], [tc["departure"]])
    data = {t[0]: load_trip(t[0]) for t in trips}
    hz = position_horizons(data, cfg, e3["position_round_m"])
    rows = []
    for trip, route, direction, dep, demand in trips:
        f = data[trip]
        geo = TripGeometry(f, hz[trip], e3, cfg, vcfg)
        for day in [tc["day"]] if route == tc["route"] else e3["days"]:
            times, sp = day_inputs(f, day, meta)
            beam = geo.beam(sp["azimuth"].to_numpy(), sp["apparent_elevation"].to_numpy())
            for sky in e3["skies"]:
                for r in run_trip(trip, f, geo, e3, vcfg, wx, meta, day, sky, times, sp, beam):
                    rows.append(
                        {
                            "route": route,
                            "direction": direction,
                            "departure": dep,
                            "demand": demand,
                            **r,
                        }
                    )
        del geo
    t = pd.DataFrame(rows)
    key = ["trip", "day", "sky"]
    a = t[t["case"] == "A"].set_index(key)["pv_Wh"]
    t["ratio_to_A"] = t.set_index(key).index.map(a.to_dict()).to_numpy()
    t["ratio_to_A"] = t["pv_Wh"] / t["ratio_to_A"]
    matrix = t[t["route"] != tc["route"]]
    summ = (
        matrix.groupby(["route", "direction", "sky", "case"])
        .agg(
            trips=("trip", "nunique"),
            pv_Wh=("pv_Wh", "mean"),
            Wh_per_km=("Wh_per_km", "mean"),
            ratio_to_A=("ratio_to_A", "mean"),
            beam_shaded_frac=("beam_shaded_frac", "mean"),
        )
        .reset_index()
    )
    tod = (
        matrix[matrix["case"].isin(["B", f"C{e3['tree_transmissivity']:g}"])]
        .groupby(["route", "direction", "departure", "day", "sky", "case"])["ratio_to_A"]
        .mean()
        .reset_index()
    )
    # tables first: a failure in the summary must not lose the computed trips
    for p in (out_trips, out_summary_table, out_tod, out_summary):
        Path(p).parent.mkdir(parents=True, exist_ok=True)
    t.to_csv(out_trips, index=False, lineterminator="\n", float_format="%.6g")
    summ.to_csv(out_summary_table, index=False, lineterminator="\n", float_format="%.6g")
    tod.to_csv(out_tod, index=False, lineterminator="\n", float_format="%.6g")

    def by_route_sky(case):
        s = matrix[matrix["case"] == case].groupby(["route", "sky"])["ratio_to_A"].mean()
        return {f"{r}|{k}": round(float(v), 4) for (r, k), v in s.items()}

    tun = t[(t["route"] == tc["route"]) & (t["case"] == "B")]
    summary = {
        "trips_in_matrix": int(matrix[["trip", "day"]].drop_duplicates().shape[0]),
        "mean_ratio_B_to_A": by_route_sky("B"),
        "mean_ratio_C_to_A": by_route_sky(f"C{e3['tree_transmissivity']:g}"),
        "tunnel_check": tun[["trip", "sky", "covered_s", "duration_s", "ratio_to_A"]].to_dict(
            "records"
        ),
    }
    summary = json.loads(json.dumps(summary, default=str))
    Path(out_summary).write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--trips", default="results/e3/table_e3_trips.csv")
    ap.add_argument("--table", default="results/e3/table_e3_summary.csv")
    ap.add_argument("--tod", default="results/e3/table_e3_tod.csv")
    ap.add_argument("--summary", default="results/e3/summary_e3.json")
    a = ap.parse_args()
    print(json.dumps(main(a.trips, a.table, a.tod, a.summary), indent=2))
