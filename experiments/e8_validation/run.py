"""E8: validate the twin (workflow guide Sec. 5 and 6).

Unity vs Python. Every R-DENSE trace on the four E3 days (120 trip-dates, 1 Hz) is exported
in ENU (twin_io.export), replayed in Unity against the P3 meshes imported as assets
(TwinBatch, PhysX rays per facet sample) and compared with the Python raster engine (E3
TripGeometry.beam at the same sun angles). Gates: per-sample beam state agreement >= 97 %;
every trip's lit fraction within 2 percentage points. A third engine, the same probe on
the same .glb meshes with Embree (twin_io.agreement.MeshProbe), separates raster-vs-mesh
differences from Unity-specific ones. Disagreements are binned on a 5 m grid.

Street-level imagery. Mapillary panoramas on R-DENSE and R-MIXED (15 each, >= 250 m apart,
within 10 m of the route); sky from Mapillary's segmentation; SVF vs the engine's horizon
SVF at camera height (2.0 m, swept 1.5-2.5). MAE, RMSE, R2 and bias.

Steps (Snakefile): export -> run_unity -> twin_agreement; mapillary_fetch -> mapillary_svf.
"""

import argparse
import importlib.util
import json
import subprocess
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import yaml

from solaris.core.params import REPO_ROOT
from solaris.geometry.crs import H_CRS
from solaris.pv import series
from solaris.pv.model import cell_temperature, pv_energy
from solaris.shading.city import D, ground, horizons
from solaris.shading.horizon import sky_view_factor
from solaris.shading.mesh import load_tiles
from solaris.site import site_config
from solaris.twin_io import agreement as ag
from solaris.twin_io import export as ex
from solaris.vehicle import vehicle_config
from solaris.weather import tmy_hourly
from solaris.weather.nsrdb import _user_env

E8_YAML = REPO_ROOT / "configs" / "experiments" / "e8.yaml"
E3_YAML = REPO_ROOT / "configs" / "experiments" / "e3.yaml"
UNITY_OUT = D / "e8" / "unity"
LOGS = D / "logs"


def cfgs():
    load = lambda p: yaml.safe_load(p.read_text(encoding="utf-8"))  # noqa: E731
    return load(E8_YAML), load(E3_YAML), site_config(), vehicle_config()


def e3_module():
    p = REPO_ROOT / "experiments" / "e3_driving" / "run.py"
    spec = importlib.util.spec_from_file_location("e3_driving_run", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def write_json(path, doc):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(doc, indent=2, default=float) + "\n", encoding="utf-8", newline="\n"
    )


# ---------------------------------------------------------------- export (Python -> Unity)
def export(out_manifest):
    e8, e3, cfg, vcfg = cfgs()
    _, meta = tmy_hourly()
    route = e8["unity"]["route"]
    files = ex.export_trajectories(route, e3["days"], meta)
    bounds = ex.trip_bounds(route, cfg["shading"]["max_distance_m"])
    geo = ex.export_unity_geometry(bounds)
    gcp = ex.export_ground_control(bounds)
    rd = e8["render"]
    pv = render_overlay(rd["trip"], rd["day"], rd["sky"], e3, cfg, vcfg)
    doc = {
        "route": route,
        "days": e3["days"],
        "trajectories": files,
        "geometry_tiles": len(geo["tiles"]),
        "geometry_bounds_utm": geo["bounds_utm"],
        "ground_control": gcp[["id", "u_lidar", "u_mesh", "mesh_minus_lidar_m"]]
        .round(3)
        .to_dict("records"),
        "render_overlay": pv,
    }
    write_json(out_manifest, doc)
    return doc


def render_overlay(trip, day, sky, e3, cfg, vcfg):
    """Per-second PV power (W) of one trip, case C (buildings + trees, tau base): the HUD."""
    e3m = e3_module()
    wx, meta = tmy_hourly()
    f = e3m.load_trip(trip)
    hz = e3m.position_horizons({trip: f}, cfg, e3["position_round_m"])[trip]
    geo = e3m.TripGeometry(f, hz, e3, cfg, vcfg)
    times, sp = e3m.day_inputs(f, day, meta)
    bld, tree = geo.beam(sp["azimuth"].to_numpy(), sp["apparent_elevation"].to_numpy())
    ghi, dni, dhi = e3m.irradiance(
        times, sky, wx, meta["latitude"], meta["longitude"], meta["altitude"]
    )
    sun = series.sun_at((times - series.YEAR_START).total_seconds().to_numpy(), meta)
    hour = (times.dayofyear - 1) * 24 + times.hour
    T = wx["temp_air"].to_numpy()[hour]
    wind = wx["wind_speed"].to_numpy()[hour] + f["speed"].to_numpy()
    tau, fa = e3["tree_transmissivity"], vcfg["pv"]["faiman"]
    w = {"ghi": ghi, "dni": dni, "dhi": dhi}
    p = np.zeros(len(f))
    for fct in geo.fs:
        k = geo.sid == fct.id
        caz = (geo.heading + fct.azimuth_body_deg) % 360
        beam, iso, hzc, ground_r, _ = series.facet_terms(
            fct.tilt_deg, caz, sun, w, vcfg["pv"]["albedo"]
        )
        v = geo.views[fct.id]
        vb = np.where(bld[:, k], 0.0, np.where(tree[:, k], tau, 1.0)).mean(axis=1)
        svf = v["svf_a"] + tau * (v["svf_b"] - v["svf_a"])
        vhz = v["hz_a"] + tau * (v["hz_b"] - v["hz_a"])
        g = np.where(geo.cov, 0.0, vb * beam + svf * iso + vhz * hzc + ground_r)
        p += (
            pv_energy(fct.area_m2, g, cell_temperature(g, T, wind, "faiman", fa["u0"], fa["u1"]))
            * 1000.0
        )
    out = ex.EXCHANGE / "render" / f"pv_{trip}_{day}.csv"
    ex.write_csv(
        pd.DataFrame({"t_utc": times.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"), "pv_W": p}),
        out,
    )
    return {
        "file": out.relative_to(REPO_ROOT).as_posix(),
        "mean_W": round(float(p.mean()), 1),
        "max_W": round(float(p.max()), 1),
    }


# ---------------------------------------------------------------- Unity batch
def unity_exe(e8):
    exe = _user_env("UNITY_EDITOR") or e8["unity"]["editor"]
    if not Path(exe).exists():
        raise FileNotFoundError(f"Unity editor not found at {exe}; set UNITY_EDITOR")
    return exe


def unity(method, args, log):
    e8 = cfgs()[0]
    cmd = [
        unity_exe(e8),
        "-batchmode",
        "-nographics",
        "-projectPath",
        str(ex.UNITY_PROJECT),
        "-executeMethod",
        method,
        *map(str, args),
        "-logFile",
        str(log),
    ]
    Path(log).parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(cmd, check=False)
    if r.returncode != 0:
        tail = Path(log).read_text(encoding="utf-8", errors="replace").splitlines()[-40:]
        raise RuntimeError(f"Unity {method} exited {r.returncode}; log {log}:\n" + "\n".join(tail))


def run_unity(out_marker, out_dir=UNITY_OUT):
    """Import the tiles, build E8.unity, then probe every exported trajectory."""
    unity("SolarisTwin.Editor.TwinSetup.BuildAnalysisSceneBatch", [], LOGS / "unity_setup.log")
    unity(
        "SolarisTwin.Editor.TwinBatch.Run",
        [
            "-trajectory",
            ex.EXCHANGE / "trajectories",
            "-out",
            out_dir,
            "-samples",
            ex.EXCHANGE / "facet_samples.csv",
            "-gcp",
            ex.EXCHANGE / "ground_control.csv",
        ],
        LOGS / "unity_e8.log",
    )
    if Path(out_marker) != Path(out_dir) / "unity_run.txt":
        Path(out_marker).write_text((Path(out_dir) / "unity_run.txt").read_text(), encoding="utf-8")


# ---------------------------------------------------------------- agreement
def twin_agreement(
    out_trips, out_clusters, out_summary, out_fig, unity_dir=UNITY_OUT, use_unity=True
):
    e8, e3, cfg, vcfg = cfgs()
    route = e8["unity"]["route"]
    e3m = e3_module()
    _, meta = tmy_hourly()
    smp = pd.read_csv(ex.EXCHANGE / "facet_samples.csv")
    pos_b = smp[["x_body", "y_body", "z_body"]].to_numpy()
    nrm_b = smp[["nx", "ny", "nz"]].to_numpy()
    bounds = ex.trip_bounds(route, cfg["shading"]["max_distance_m"])
    tiles = load_tiles(ex.TILES, bounds)
    probe = ag.MeshProbe(tiles["surface"], tiles["trees"])
    trips = ex.trip_names(route)
    data = {t: ex.load_trip(t) for t in trips}
    hz = e3m.position_horizons(data, cfg, e3["position_round_m"])
    rows = []
    results = {k: [] for k in ("raster_unity", "embree_unity", "raster_embree")}
    results["raster_unity_beyond_1deg"] = []
    dis = {"x": [], "y": [], "kind": [], "el": []}
    band = {"dis": 0, "dis_edge": 0, "valid": 0, "valid_edge": 0}
    for trip in trips:
        f = data[trip]
        geo = e3m.TripGeometry(f, hz[trip], e3, cfg, vcfg)
        for day in e3["days"]:
            traj = pd.read_csv(ex.EXCHANGE / "trajectories" / f"trajectory_{trip}_{day}.csv")
            el = traj["sun_el_deg"].to_numpy()
            bld, tree = geo.beam(traj["sun_az_deg"].to_numpy(), el)
            cov = traj["covered"].to_numpy().astype(bool)
            bld[cov], tree[cov] = True, False
            valid = ag.valid_mask(traj, nrm_b)
            py = ag.engine_state(bld, tree, valid)
            # Horizon-line band (E1 convention): the raster state changes when the sun moves
            # 1 deg in elevation or azimuth, so the ray grazes an edge of the surface.
            az = traj["sun_az_deg"].to_numpy()
            edge = np.zeros(py.shape, bool)
            for da, de in ((0.0, 1.0), (0.0, -1.0), (1.0, 0.0), (-1.0, 0.0)):
                b2, t2 = geo.beam(az + da, el + de)
                b2[cov], t2[cov] = True, False
                edge |= ag.engine_state(b2, t2, valid) != py
            em = probe.states(traj, pos_b, nrm_b)
            r_pe = ag.compare(py, em)
            results["raster_embree"].append(r_pe)
            row = {
                "trip": trip,
                "day": day,
                "records": len(traj),
                "raster_embree_agreement": r_pe["agreement"],
                "lit_raster": r_pe["lit_a"],
                "lit_embree": r_pe["lit_b"],
            }
            if use_unity:
                vis = unity_dir / f"visibility_{trip}_{day}.csv.gz"
                t, ub, ut, sid, _ = ag.read_visibility(vis, len(smp))
                if not (
                    np.array_equal(t, traj["t_utc"].to_numpy())
                    and np.array_equal(sid, smp["sample_id"])
                ):
                    raise ValueError(f"{vis}: records or samples out of order")
                un = ag.unity_state(ub, ut)
                r_pu, r_eu = ag.compare(py, un), ag.compare(em, un)
                r_far = ag.compare(np.where(edge, ag.INVALID, py), np.where(edge, ag.INVALID, un))
                results["raster_unity"].append(r_pu)
                results["embree_unity"].append(r_eu)
                results["raster_unity_beyond_1deg"].append(r_far)
                row.update(
                    raster_unity_agreement=r_pu["agreement"],
                    embree_unity_agreement=r_eu["agreement"],
                    lit_unity=r_pu["lit_b"],
                    lit_diff_pp=r_pu["lit_diff_pp"],
                    valid_only_one=r_pu["valid_only_one"],
                    within_1deg_share=float(edge[valid].mean()) if valid.any() else np.nan,
                    agreement_beyond_1deg=r_far["agreement"],
                    lit_diff_pp_beyond_1deg=r_far["lit_diff_pp"],
                )
                other = un
            else:
                other = em
            m = (py != ag.INVALID) & (other != ag.INVALID) & (py != other)
            band["dis"] += int(m.sum())
            band["dis_edge"] += int((m & edge).sum())
            band["valid"] += int((valid).sum())
            band["valid_edge"] += int((valid & edge).sum())
            if m.any():
                dis["x"].append(geo.wx[m])
                dis["y"].append(geo.wy[m])
                dis["kind"].append(ag.disagreement_kind(py[m], other[m]))
                dis["el"].append(np.broadcast_to(el[:, None], m.shape)[m])
            rows.append(row)
        del geo
        print(f"[e8] {trip}: done ({len(rows)} trip-dates)", flush=True)
    table = pd.DataFrame(rows)
    cl = ag.clusters(
        *(np.concatenate(dis[k]) if dis[k] else np.array([]) for k in ("x", "y", "kind", "el")),
        cell_m=e8["unity"]["cluster_cell_m"],
    )
    kinds = pd.Series(np.concatenate(dis["kind"]) if dis["kind"] else []).value_counts()
    summary = {
        "route": route,
        "trip_dates": len(table),
        "python_raster_vs_embree_mesh": ag.summarize(results["raster_embree"], "raster", "embree"),
        "disagreement_kinds_raster_vs_" + ("unity" if use_unity else "embree"): {
            k: int(v) for k, v in kinds.items()
        },
        "horizon_band_1deg": {
            "definition": "raster state changes when the sun moves 1 deg in elevation or azimuth",
            "share_of_valid_sample_records": round(band["valid_edge"] / max(band["valid"], 1), 4),
            "share_of_disagreements": round(band["dis_edge"] / max(band["dis"], 1), 4),
        },
    }
    if use_unity:
        gc = pd.read_csv(unity_dir / "ground_control_unity.csv")
        summary["ground_control"] = {
            "marks": gc[["id", "delta_m"]].round(3).to_dict("records"),
            "max_abs_delta_m": round(float(gc["delta_m"].abs().max()), 3),
            "pass": bool(gc["pass"].all()),
        }
        summary["python_raster_vs_unity"] = ag.summarize(results["raster_unity"], "raster", "unity")
        summary["embree_vs_unity"] = ag.summarize(results["embree_unity"], "embree", "unity")
        summary["python_raster_vs_unity_beyond_1deg"] = ag.summarize(
            results["raster_unity_beyond_1deg"], "raster", "unity"
        )
        g = summary["python_raster_vs_unity"]
        summary["pass"] = bool(
            summary["ground_control"]["pass"] and g["pass_agreement"] and g["pass_lit_fraction"]
        )
        f = summary["python_raster_vs_unity_beyond_1deg"]
        summary["pass_beyond_1deg"] = bool(f["pass_agreement"] and f["pass_lit_fraction"])
    for p in (out_trips, out_clusters, out_summary, out_fig):
        Path(p).parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(out_trips, index=False, lineterminator="\n", float_format="%.6g")
    cl.to_csv(out_clusters, index=False, lineterminator="\n", float_format="%.6g")
    write_json(out_summary, summary)
    fig_agreement(table, kinds, use_unity, str(Path(out_fig).with_suffix("")))
    return summary


def fig_agreement(table, kinds, use_unity, stem):
    from solaris import figures

    plt = figures.style()
    fig, (a, b) = plt.subplots(1, 2, figsize=(8.4, 3.4))
    other = "lit_unity" if use_unity else "lit_embree"
    lab = "Unity (PhysX, meshes)" if use_unity else "Embree (meshes)"
    x, y = 100 * table["lit_raster"], 100 * table[other]
    lo, hi = float(min(x.min(), y.min())) - 2, float(max(x.max(), y.max())) + 2
    a.fill_between([lo, hi], [lo - 2, hi - 2], [lo + 2, hi + 2], color=figures.GRID, lw=0)
    a.plot([lo, hi], [lo, hi], color=figures.MUTED, lw=1)
    a.plot(x, y, "o", ms=4, color=figures.SERIES[0], mec=figures.SURFACE, mew=0.6)
    a.set_xlim(lo, hi)
    a.set_ylim(lo, hi)
    a.set_xlabel("Lit fraction, Python raster engine (%)")
    a.set_ylabel(f"Lit fraction, {lab} (%)")
    a.set_title("Trip-integrated beam, 120 trip-dates (band ±2 pp)", loc="left", fontsize=9)
    k = kinds.head(6)
    b.barh(
        range(len(k))[::-1],
        k.to_numpy() / max(kinds.sum(), 1) * 100,
        color=figures.SERIES[1],
        height=0.6,
    )
    b.set_yticks(range(len(k))[::-1], k.index)
    b.set_xlabel("Share of disagreeing sample-seconds (%)")
    b.set_title(
        "Disagreements: raster state → " + ("Unity" if use_unity else "Embree"),
        loc="left",
        fontsize=9,
    )
    b.grid(axis="y", visible=False)
    fig.tight_layout()
    figures.save(fig, stem)
    plt.close(fig)


# ---------------------------------------------------------------- Mapillary
def route_line(route, cfg):
    g = gpd.read_file(REPO_ROOT / "routes" / cfg["routes"]["version"] / f"{route}.geojson").to_crs(
        H_CRS
    )
    return g.geometry.union_all()


def mapillary_fetch(out_manifest):
    from shapely.geometry import Point

    from solaris.imagery import mapillary as mp

    e8, _, cfg, _ = cfgs()
    mc = e8["mapillary"]
    chosen = []
    for route in mc["routes"]:
        line = route_line(route, cfg)
        pts = [line.interpolate(d) for d in np.arange(0, line.length, mc["search_step_m"])]
        ll = gpd.GeoSeries(pts, crs=H_CRS).to_crs(4326)
        found = {}
        for p in ll:
            h = mc["search_half_deg"]
            for im in mp.images_in_bbox(p.x - h, p.y - h, p.x + h, p.y + h):
                found[im["id"]] = im
        rows = []
        for im in found.values():
            g = im.get("computed_geometry") or im.get("geometry")
            if not g or not im.get("is_pano"):
                continue
            lon, lat = g["coordinates"]
            xy = gpd.GeoSeries([Point(lon, lat)], crs=4326).to_crs(H_CRS).iloc[0]
            off = line.distance(xy)
            if off <= mc["max_offset_m"]:
                rows.append(
                    {
                        "id": im["id"],
                        "route": route,
                        "x": xy.x,
                        "y": xy.y,
                        "lon": lon,
                        "lat": lat,
                        "offset_m": off,
                        "captured_at": im.get("captured_at", 0),
                        "camera_type": im.get("camera_type"),
                        "width": im.get("width"),
                        "height": im.get("height"),
                    }
                )
        cand = pd.DataFrame(rows)
        picked = []
        if len(cand):
            for r in mp.pick_spread(cand, len(cand), mc["min_separation_m"]).itertuples():
                if any(
                    np.hypot(r.x - q["x"], r.y - q["y"]) < mc["min_separation_m"] for q in picked
                ):
                    continue
                if any(d.get("value") == mp.SKY for d in mp.detections(r.id)):
                    picked.append(r._asdict())
                if len(picked) == mc["per_route"]:
                    break
        chosen += picked
        print(f"[e8] {route}: {len(found)} panoramas nearby, {len(cand)} on the route, ", end="")
        print(f"{len(picked)} chosen")
    for c in chosen:
        c.pop("Index", None)
    write_json(out_manifest, {"images": chosen})
    return chosen


def mapillary_svf(manifest, out_table, out_summary, out_fig):
    from solaris.imagery import mapillary as mp

    e8, _, cfg, _ = cfgs()
    mc = e8["mapillary"]
    im = pd.DataFrame(json.loads(Path(manifest).read_text(encoding="utf-8"))["images"])
    if im.empty:
        raise RuntimeError("no Mapillary panoramas were selected")
    w, h = mc["mask_size"]
    im["svf_image"] = [mp.svf_equirect(mp.sky_mask(mp.detections(i), w, h)) for i in im["id"]]
    z0 = ground(im["x"], im["y"])
    for hc in [mc["camera_height_m"], *mc["height_sweep_m"]]:
        h_b, h_a = horizons(im["x"].to_numpy(), im["y"].to_numpy(), z0 + hc, cfg["shading"])
        im[f"svf_engine_b_{hc:g}"] = sky_view_factor(h_b)
        im[f"svf_engine_a_{hc:g}"] = sky_view_factor(h_a)

    def stats(eng, img):
        d = eng - img
        ss = float(np.sum((img - img.mean()) ** 2))
        return {
            "mae": round(float(np.mean(np.abs(d))), 4),
            "rmse": round(float(np.sqrt(np.mean(d**2))), 4),
            "bias_engine_minus_image": round(float(np.mean(d)), 4),
            "r2": round(1 - float(np.sum(d**2)) / ss, 4) if ss > 0 else None,
            "pearson_r": round(float(np.corrcoef(eng, img)[0, 1]), 4) if len(img) > 2 else None,
        }

    hc = mc["camera_height_m"]
    img = im["svf_image"].to_numpy()
    summary = {
        "points": int(len(im)),
        "per_route": im["route"].value_counts().to_dict(),
        "camera_height_m": hc,
        "buildings_trees": stats(im[f"svf_engine_a_{hc:g}"].to_numpy(), img),
        "buildings_only": stats(im[f"svf_engine_b_{hc:g}"].to_numpy(), img),
        "height_sweep_buildings_trees": {
            f"{x:g}": stats(im[f"svf_engine_a_{x:g}"].to_numpy(), img) for x in mc["height_sweep_m"]
        },
        "by_route": {
            r: stats(g[f"svf_engine_a_{hc:g}"].to_numpy(), g["svf_image"].to_numpy())
            for r, g in im.groupby("route")
        },
        "captured": [
            str(pd.to_datetime(im["captured_at"].min(), unit="ms").date()),
            str(pd.to_datetime(im["captured_at"].max(), unit="ms").date()),
        ],
        "attribution": "Imagery and segmentation: Mapillary contributors, CC BY-SA 4.0",
    }
    for p in (out_table, out_summary, out_fig):
        Path(p).parent.mkdir(parents=True, exist_ok=True)
    im.to_csv(out_table, index=False, lineterminator="\n", float_format="%.6g")
    write_json(out_summary, summary)
    fig_svf(im, hc, str(Path(out_fig).with_suffix("")))
    return summary


def fig_svf(im, hc, stem):
    from solaris import figures

    plt = figures.style()
    fig, ax = plt.subplots(figsize=(4.2, 3.8))
    ax.plot([0, 1], [0, 1], color=figures.MUTED, lw=1)
    for i, (route, g) in enumerate(im.groupby("route")):
        ax.plot(
            g["svf_image"],
            g[f"svf_engine_a_{hc:g}"],
            "o",
            ms=5,
            color=figures.SERIES[i],
            mec=figures.SURFACE,
            mew=0.6,
            label=route,
        )
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal")
    ax.set_xlabel("SVF from Mapillary panorama sky")
    ax.set_ylabel(f"SVF engine, buildings + trees ({hc:g} m)")
    ax.legend(loc="upper left", fontsize=8)
    ax.set_title("Imagery vs engine sky view factor", loc="left", fontsize=9)
    figures.save(fig, stem)
    plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("step", choices=["export", "agreement-embree"])
    a = ap.parse_args()
    if a.step == "export":
        print(
            json.dumps(export(ex.EXCHANGE / "export_manifest.json"), indent=2, default=str)[:3000]
        )
    else:
        out = D / "e8" / "dev"
        print(
            json.dumps(
                twin_agreement(
                    out / "t.csv", out / "c.csv", out / "s.json", out / "f.png", use_unity=False
                ),
                indent=2,
                default=str,
            )
        )
