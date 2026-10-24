"""Visual-only data for the Unity Playback scene (P8-visual). Never feeds a reported number.

Writes twin/exchange/visual/hud_<trip>_<date>.csv (gitignored) for every exported trajectory:
    t_utc, pv_W, trip_Wh, pv_<facet>_W ..., street
Per-second PV is E3 case C (buildings + trees, tau base) on the matching TMY day, the same
arithmetic as the E8 render overlay (experiments/e8_validation/run.py: render_overlay). Street
names come from the trace's OSM way ids and the raw OSM tiles of the SUMO network. This
script only reads the frozen code and data.

    python twin/visual/export_visual.py            # all 120 R-DENSE trip-dates
    python twin/visual/export_visual.py --trip R-DENSE_fwd_1800_medium
    python twin/visual/export_visual.py --streets  # street names only, into existing files
    python twin/visual/export_visual.py --traffic  # background cars + signals, from the
        visual SUMO re-run (twin/visual/sumo_visual_job.py -> data/derived/visual/sumo)
"""

import argparse
import importlib.util
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from solaris.pv import series  # noqa: E402
from solaris.pv.model import cell_temperature, pv_energy  # noqa: E402
from solaris.site import site_config  # noqa: E402
from solaris.twin_io import export as ex  # noqa: E402
from solaris.vehicle import vehicle_config  # noqa: E402
from solaris.weather import tmy_hourly  # noqa: E402

OUT = REPO / "twin" / "exchange" / "visual"


def e3_module():
    p = REPO / "experiments" / "e3_driving" / "run.py"
    spec = importlib.util.spec_from_file_location("e3_driving_run", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def trip_day_pv(e3m, geo, f, day, e3, vcfg, wx, meta):
    """Per-second PV power (W), total and per facet, case C on the TMY day."""
    times, sp = e3m.day_inputs(f, day, meta)
    bld, tree = geo.beam(sp["azimuth"].to_numpy(), sp["apparent_elevation"].to_numpy())
    ghi, dni, dhi = e3m.irradiance(
        times, "tmy", wx, meta["latitude"], meta["longitude"], meta["altitude"]
    )
    sun = series.sun_at((times - series.YEAR_START).total_seconds().to_numpy(), meta)
    hour = (times.dayofyear - 1) * 24 + times.hour
    T = wx["temp_air"].to_numpy()[hour]
    wind = wx["wind_speed"].to_numpy()[hour] + f["speed"].to_numpy()
    tau, fa = e3["tree_transmissivity"], vcfg["pv"]["faiman"]
    w = {"ghi": ghi, "dni": dni, "dhi": dhi}
    cols = {}
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
        tc = cell_temperature(g, T, wind, "faiman", fa["u0"], fa["u1"])
        cols[f"pv_{fct.id}_W"] = pv_energy(fct.area_m2, g, tc) * 1000.0
    pv = sum(cols.values())
    df = pd.DataFrame(
        {
            "t_utc": times.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
            "pv_W": pv,
            "trip_Wh": np.cumsum(pv) / 3600.0,
            **cols,
        }
    )
    return df


def main(route="R-DENSE", only=None):
    e3 = yaml.safe_load((REPO / "configs" / "experiments" / "e3.yaml").read_text(encoding="utf-8"))
    cfg, vcfg = site_config(), vehicle_config()
    wx, meta = tmy_hourly()
    e3m = e3_module()
    trips = [t for t in ex.trip_names(route) if only is None or t == only]
    data = {t: e3m.load_trip(t) for t in trips}
    hz = e3m.position_horizons(data, cfg, e3["position_round_m"])
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    for i, trip in enumerate(trips):
        f = data[trip]
        geo = e3m.TripGeometry(f, hz[trip], e3, cfg, vcfg)
        streets = trip_streets(f, osm_street_names())
        for day in e3["days"]:
            df = trip_day_pv(e3m, geo, f, day, e3, vcfg, wx, meta)
            df["street"] = streets
            df.to_csv(
                OUT / f"hud_{trip}_{day}.csv", index=False, lineterminator="\n", float_format="%.3f"
            )
        del geo
        print(f"[visual] {i + 1}/{len(trips)} {trip} ({time.time() - t0:.0f} s)", flush=True)


# ---------------------------------------------------------------- street names (feature 2)
_NAMES = None


def osm_street_names():
    """OSM way id -> street name, from the raw OSM tiles behind the frozen SUMO network."""
    global _NAMES
    if _NAMES is None:
        import xml.etree.ElementTree as ET

        _NAMES = {}
        for fn in sorted((REPO / "data" / "raw" / "osm").glob("sumo_roads_v2.osm_*.xml")):
            for _, el in ET.iterparse(fn):
                if el.tag == "way":
                    tags = {t.get("k"): t.get("v") for t in el.findall("tag")}
                    name = tags.get("name") or tags.get("ref") or ""
                    _NAMES[el.get("id")] = name.replace(",", " ").strip()
                    el.clear()
    return _NAMES


def trip_streets(f, names):
    """Street name per trace second; junction seconds (no OSM way) keep the last street."""
    way = f["way"].astype(str).str.replace(r"\.0$", "", regex=True)
    s = way.map(lambda w: names.get(w, "")).replace("", np.nan)
    return s.ffill().bfill().fillna("").to_numpy()


def add_streets(route="R-DENSE"):
    """Add or refresh the street column of existing HUD files without recomputing PV."""
    e3 = yaml.safe_load((REPO / "configs" / "experiments" / "e3.yaml").read_text(encoding="utf-8"))
    names = osm_street_names()
    n = 0
    for trip in ex.trip_names(route):
        streets = trip_streets(ex.load_trip(trip), names)
        for day in e3["days"]:
            p = OUT / f"hud_{trip}_{day}.csv"
            df = pd.read_csv(p, dtype={"t_utc": str})
            if len(df) != len(streets):
                raise ValueError(f"{p}: {len(df)} rows, trace has {len(streets)}")
            df["street"] = streets
            df.to_csv(p, index=False, lineterminator="\n", float_format="%.3f")
            n += 1
    print(f"[visual] street names added to {n} HUD files")


# ---------------------------------------------------------------- map (feature 3)
SITE_LABEL = {
    "P1": "P1 open lot",
    "P2": "P2 curb",
    "P3": "P3 driveway",
    "P4": "P4 garage deck",
    "P5": "P5 shade canopy",
}


def export_map(out=OUT / "map.json"):
    """Routes (polylines) and parking sites in Unity's ENU frame for the mini-map."""
    import json

    import geopandas as gpd

    from solaris.geometry.crs import H_CRS

    version = site_config()["routes"]["version"]
    rdir = REPO / "routes" / version
    tf = ex.enu()
    h0 = ex.origin()["H_navd88_m"]  # map is 2-D: one height for the horizontal transform
    routes = []
    for p in sorted(rdir.glob("R-*.geojson")):
        g = gpd.read_file(p).to_crs(H_CRS)
        line = g.geometry.iloc[0]
        x, y = np.asarray(line.coords)[:, 0], np.asarray(line.coords)[:, 1]
        e, n, _ = ex.to_enu(tf, x, y, np.full(len(x), h0))
        xy = np.column_stack([e, n])[:: max(1, len(x) // 400)].round(1).ravel().tolist()
        routes.append({"id": p.stem, "label": f"{p.stem} {g['street'].iloc[0]}", "xy": xy})
    s = gpd.read_file(rdir / "parking_sites.geojson").to_crs(H_CRS)
    e, n, _ = ex.to_enu(tf, s.geometry.x.to_numpy(), s.geometry.y.to_numpy(), np.full(len(s), h0))
    points = []
    for i, a, b in zip(s["id"], e, n, strict=True):
        same = [p for p in points if abs(p["x"] - a) < 1 and abs(p["y"] - b) < 1]
        if same:  # P5 is the P1 stall under a canopy: one dot, both names
            same[0]["label"] += " · " + SITE_LABEL.get(i, i)
            continue
        points.append(
            {
                "id": i,
                "label": SITE_LABEL.get(i, i),
                "x": round(float(a), 1),
                "y": round(float(b), 1),
            }
        )
    points.append({"id": "O", "label": "Central Ave & Washington St", "x": 0.0, "y": 0.0})

    lines = [
        gpd.read_file(p).to_crs(H_CRS).geometry.iloc[0] for p in sorted(rdir.glob("R-*.geojson"))
    ]
    buildings = map_buildings(lines, tf, h0)
    landmarks = map_landmarks(lines, tf, h0)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = {"routes": routes, "points": points, "buildings": buildings, "landmarks": landmarks}
    out.write_text(json.dumps(doc), encoding="utf-8")
    print(
        f"[visual] map: {len(routes)} routes, {len(points)} points, {len(buildings)} buildings "
        f"({sum(b['h'] >= TALL_M for b in buildings)} tall), {len(landmarks)} landmarks -> {out}"
    )


def export_map_image(px=4096, margin_m=800.0, out=OUT / "map_naip.jpg"):
    """Aerial background for the maps: USDA NAIP true colour (public domain, the lidar-era year
    of P3), resampled onto a north-up ENU square covering the routes + margin."""
    import json

    import rasterio
    from PIL import Image
    from pyproj.enums import TransformDirection
    from rasterio.transform import Affine
    from rasterio.warp import Resampling, reproject

    doc = json.loads((OUT / "map.json").read_text(encoding="utf-8"))
    xs = [v for r in doc["routes"] for v in r["xy"][0::2]]
    ys = [v for r in doc["routes"] for v in r["xy"][1::2]]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    half = max(max(xs) - min(xs), max(ys) - min(ys)) / 2 + margin_m
    x0, x1, y0, y1 = cx - half, cx + half, cy - half, cy + half
    # pixel (col, row) -> UTM, from three ENU corners (ENU and UTM differ by ~0.6 deg rotation)
    tf = ex.enu()
    e = np.array([x0, x1, x0])
    n = np.array([y1, y1, y0])
    ux, uy, _ = tf.transform(e, n, np.zeros(3), direction=TransformDirection.INVERSE)
    ax, ay = (ux[1] - ux[0]) / px, (uy[1] - uy[0]) / px  # per column
    bx, by = (ux[2] - ux[0]) / px, (uy[2] - uy[0]) / px  # per row
    dst_tf = Affine(ax, bx, ux[0], ay, by, uy[0])
    rgb = np.zeros((3, px, px), np.uint8)
    with rasterio.open(REPO / "data" / "derived" / "naip.vrt") as s:
        for b in range(3):
            reproject(
                rasterio.band(s, b + 1),
                rgb[b],
                dst_transform=dst_tf,
                dst_crs=s.crs,
                resampling=Resampling.average,
            )
    img = rgb.transpose(1, 2, 0).astype(float)
    valid = img.sum(axis=2) > 0
    for b in range(3):  # 2-98 % stretch, gentle
        lo, hi = np.percentile(img[..., b][valid], [2, 98])
        img[..., b] = np.clip((img[..., b] - lo) / max(hi - lo, 1) * 235 + 10, 0, 255)
    Image.fromarray(img.astype(np.uint8)).save(out, quality=88)
    meta = {"x0": x0, "y0": y0, "x1": x1, "y1": y1, "px": px, "source": "USDA NAIP"}
    (OUT / "map_naip.json").write_text(json.dumps(meta), encoding="utf-8")
    print(f"[visual] aerial map {px} px, {2 * half / px:.2f} m/px -> {out}")


TALL_M = 20.0  # full map shows buildings at least this tall
NEAR_M = 300.0  # mini-map shows every building this close to a route


def _ring_xy(poly, tf, h0):
    x, y = np.asarray(poly.exterior.coords)[:, 0], np.asarray(poly.exterior.coords)[:, 1]
    e, n, _ = ex.to_enu(tf, x, y, np.full(len(x), h0))
    return np.column_stack([e, n]).round(1).ravel().tolist()


def map_buildings(lines, tf, h0):
    """Footprints (ENU, 1 m simplified) of buildings near the routes or at least TALL_M tall,
    from the frozen Overture file (read-only)."""
    import geopandas as gpd
    import shapely

    g = gpd.read_file(REPO / "data" / "raw" / "overture" / "buildings.gpkg")
    near = g.intersects(shapely.union_all([ln.buffer(NEAR_M) for ln in lines]))
    tall = g["height_m"].fillna(0) >= TALL_M
    out = []
    for geom, h in zip(g.geometry[near | tall], g["height_m"].fillna(0)[near | tall], strict=True):
        geom = geom.simplify(1.0)
        for poly in getattr(geom, "geoms", [geom]):
            if poly.geom_type == "Polygon" and poly.area >= 20:
                out.append({"h": round(float(h), 1), "xy": _ring_xy(poly, tf, h0)})
    return out


LANDMARK_QUERY = """
[out:json][timeout:90];
(
  nwr["leisure"="stadium"]["name"]({b});
  nwr["building"~"^(stadium|government|civic|university|hospital)$"]["name"]({b});
  nwr["amenity"~"^(townhall|university|college|hospital|conference_centre|exhibition_centre|courthouse|library)$"]["name"]({b});
  nwr["tourism"~"^(museum|attraction)$"]["name"]({b});
  nwr["aeroway"="aerodrome"]["name"]({b});
);
out tags center bb;
"""


def map_landmarks(lines, tf, h0, n_max=16):
    """Named landmarks from OpenStreetMap (one Overpass query, cached in twin/exchange/visual),
    largest first: stadiums, arenas, civic buildings, universities, hospitals, museums, airport."""
    import json

    import requests
    import shapely
    from pyproj import Transformer

    from solaris.geometry.crs import H_CRS

    cache = OUT / "landmarks_osm.json"
    area = shapely.union_all([ln.buffer(800.0) for ln in lines])
    to_ll = Transformer.from_crs(H_CRS, "EPSG:4326", always_xy=True)
    x0, y0, x1, y1 = area.bounds
    (lon0, lat0), (lon1, lat1) = to_ll.transform(x0, y0), to_ll.transform(x1, y1)
    if not cache.exists():
        q = LANDMARK_QUERY.replace("{b}", f"{lat0:.5f},{lon0:.5f},{lat1:.5f},{lon1:.5f}")
        r = requests.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": q},
            headers={"User-Agent": "SOLARIS-Twin visual export (research; contact via GitHub)"},
            timeout=120,
        )
        r.raise_for_status()
        cache.write_text(r.text, encoding="utf-8")
    to_utm = Transformer.from_crs("EPSG:4326", H_CRS, always_xy=True)
    best = {}
    for el in json.loads(cache.read_text(encoding="utf-8")).get("elements", []):
        name = (el.get("tags") or {}).get("name", "").replace(",", " ").strip()
        bb = el.get("bounds")
        c = el.get("center") or ({"lat": el["lat"], "lon": el["lon"]} if "lat" in el else None)
        if c is None and bb:  # ways and relations come with a bounding box only
            c = {"lat": (bb["minlat"] + bb["maxlat"]) / 2, "lon": (bb["minlon"] + bb["maxlon"]) / 2}
        if not name or c is None:
            continue
        x, y = to_utm.transform(c["lon"], c["lat"])
        if not area.contains(shapely.Point(x, y)):
            continue
        size = 0.0
        if bb:
            bx0, by0 = to_utm.transform(bb["minlon"], bb["minlat"])
            bx1, by1 = to_utm.transform(bb["maxlon"], bb["maxlat"])
            size = abs(bx1 - bx0) * abs(by1 - by0)
        if name not in best or size > best[name][0]:  # nodes have no extent: size 0
            best[name] = (size, x, y)
    top = sorted(best.items(), key=lambda kv: -kv[1][0])[:n_max]
    out = []
    for name, (_, x, y) in top:
        e, n, _ = ex.to_enu(tf, np.array([x]), np.array([y]), np.array([h0]))
        out.append(
            {"id": "L", "label": name, "x": round(float(e[0]), 1), "y": round(float(n[0]), 1)}
        )
    return out


# visual-only SUMO re-run (twin/visual/sumo_visual_job.py)
VSUMO = REPO / "data" / "derived" / "visual" / "sumo"
MODELS = 10  # visual car models (all SUMO background vehicles are 5 m passenger cars)


def _ways(edges):
    """OSM way per FCD row; None on a junction-internal lane (':...'), filled per vehicle by
    the caller from the edge driven before it, so cars on a bridge junction stay on the deck."""
    from solaris.trajectory.sumo import osm_way

    return pd.Series([None if str(e).startswith(":") else osm_way(e) for e in edges], dtype=object)


def export_traffic(route="R-DENSE"):
    """Background cars around each R-DENSE ego, per trip, in the ego trace's own seconds.

    Rows come from the visual SUMO re-run, which reproduces the frozen ego FCD exactly (checked
    here again for every trip). Coordinates go through the frozen trace pipeline: lon/lat ->
    to_utm -> ENU, heading from the SUMO angle via enu_heading, z = DEM (DSM on bridge ways);
    vehicles on tunnel ways are dropped. Position = SUMO's front-bumper point, the convention
    the ego car uses in Unity, so gaps and queues match SUMO.

    twin/exchange/visual/traffic/traffic_<trip>.csv: k (s since the trace start), v (vehicle
    number), x_e, y_n, z_u, heading_deg, model (0..3)."""
    import zlib

    from solaris.geometry.crs import to_utm
    from solaris.shading.city import ground
    from solaris.trajectory.sumo import bridge_way_ids, covered_layer

    polys = covered_layer()
    bridges = bridge_way_ids(polys)
    tunnels = set(polys.loc[polys["kind"] == "tunnel", "osm_id"].astype(str))
    tf = ex.enu()
    out_dir = OUT / "traffic"
    out_dir.mkdir(parents=True, exist_ok=True)
    egos = {}
    cols = ["k", "v", "x_e", "y_n", "z_u", "heading_deg", "model"]
    for trip in ex.trip_names(route):
        veh, seed = trip.rsplit("_", 1)
        f = ex.load_trip(trip)
        t0, t1 = float(f["t"].iloc[0]), float(f["t"].iloc[-1])
        if seed not in egos:
            egos[seed] = pd.read_csv(VSUMO / f"ego_{seed}.csv")
        ego = egos[seed][egos[seed]["veh"] == veh].set_index("t")
        if not np.array_equal(ego.loc[f["t"], ["x", "y"]].to_numpy(), f[["x", "y"]].to_numpy()):
            raise RuntimeError(f"{trip}: the visual SUMO re-run does not reproduce the frozen ego")
        src = VSUMO / f"traffic_{veh}_{seed}.csv"
        g = pd.read_csv(src) if src.exists() else pd.DataFrame(columns=["veh", "t", "edge"])
        g = g[(g["t"] >= t0) & (g["t"] <= t1)].sort_values(["veh", "t"]).reset_index(drop=True)
        if len(g):
            way = (
                _ways(g["edge"]).groupby(g["veh"].to_numpy()).transform(lambda s: s.ffill().bfill())
            )
            g = g.assign(way=way.to_numpy())
            g = g[~g["way"].isin(tunnels)].reset_index(drop=True)
        if len(g):
            x, y = to_utm(g["lat"].to_numpy(), g["lon"].to_numpy())
            on_bridge = g["way"].isin(bridges).to_numpy()
            z = np.where(on_bridge, ground(x, y, layer="dsm.tif"), ground(x, y))
            e, n, u = ex.to_enu(tf, x, y, z)
            num = {v: i for i, v in enumerate(pd.unique(g["veh"]))}
            t = pd.DataFrame(
                {
                    "k": (g["t"] - t0).round().astype(int),
                    "v": g["veh"].map(num),
                    "x_e": e.round(2),
                    "y_n": n.round(2),
                    "z_u": u.round(2),
                    "heading_deg": ex.enu_heading(tf, x, y, z, g["angle"].to_numpy()).round(1),
                    "model": [zlib.crc32(v.encode()) % MODELS for v in g["veh"]],
                }
            ).sort_values(["k", "v"])
        else:
            t = pd.DataFrame(columns=cols)
        t[cols].to_csv(out_dir / f"traffic_{trip}.csv", index=False, lineterminator="\n")
        at_once = int(t.groupby("k").size().max()) if len(t) else 0
        print(f"[visual] {trip}: {t['v'].nunique()} cars, up to {at_once} at once")


def export_signals(route="R-DENSE"):
    """Traffic-signal heads of every signalised approach and their SUMO states per trip.

    traffic/signals.json: heads at the stop-line point of each approach's rightmost lane (ENU,
    z = DEM) with the lane heading, lane width, the SUMO link the head shows and `over`, the
    head's position across the approach in lanes from the rightmost lane centre. Every approach
    gets a head for its straight movement (or its only movement) and, where the left turn has
    its own phase (its state differs from straight at some instant), a left-turn head over the
    leftmost lane. `mast` marks the head that carries the pole and arm (the farthest left).
    traffic/signals_<trip>.csv: k, head, state (G/Y/R) at every change, from the visual SUMO
    run's SaveTLSSwitchStates."""
    import json
    import xml.etree.ElementTree as ET

    from solaris.geometry.crs import to_utm
    from solaris.shading.city import ground

    colour = {"G": "G", "g": "G", "y": "Y", "Y": "Y"}  # red, red-yellow, off: red
    switches = {}
    for seed in ("low", "medium", "high"):
        rows = [
            (float(el.get("time")), el.get("id"), el.get("state"))
            for el in ET.parse(VSUMO / f"tls_{seed}.xml").getroot()
            if el.tag == "tlsState"
        ]
        switches[seed] = pd.DataFrame(rows, columns=["t", "tls", "state"])
    states = pd.concat(switches.values())

    def seq(tls, link):
        s = states.loc[states["tls"] == tls, "state"].str[link]
        return "".join(colour.get(ch, "R") for ch in s)

    tf = ex.enu()
    meta = json.loads((VSUMO / "tls_meta.json").read_text(encoding="utf-8"))
    heads = []
    for tls in meta:
        by_edge = {}
        for ln in tls["links"]:
            by_edge.setdefault(ln["edge"], []).append(ln)
        for edge, links in sorted(by_edge.items()):
            right = min(links, key=lambda ln: ln["lane"])
            lanes = right["lanes"]
            main = min(links, key=lambda ln: (ln["dir"] != "s", ln["lane"]))
            lefts = [ln for ln in links if ln["dir"] == "l"]
            left = max(lefts, key=lambda ln: ln["lane"]) if lefts else None
            if left is not None and seq(tls["id"], left["link"]) == seq(tls["id"], main["link"]):
                left = None  # turns with the straight phase: one head says it all
            x, y = to_utm(np.array([right["lat"]]), np.array([right["lon"]]))
            z = ground(x, y)
            e, n, u = ex.to_enu(tf, x, y, z)
            heading = float(ex.enu_heading(tf, x, y, z, right["bearing"])[0])
            # far side of the junction: where the shown movement's outgoing lane starts,
            # measured along the approach (US mast arms stand on the far-side corner)
            fx, fy = to_utm(np.array([main["far"][1]]), np.array([main["far"][0]]))
            fe, fn, _ = ex.to_enu(tf, fx, fy, z)
            hr = np.radians(heading)
            far = float((fe[0] - e[0]) * np.sin(hr) + (fn[0] - n[0]) * np.cos(hr))
            base = {
                "tls": tls["id"],
                "edge": edge,
                "x": round(float(e[0]), 2),
                "y": round(float(n[0]), 2),
                "z": round(float(u[0]), 2),
                "heading": round(heading, 1),
                "width": right["width"],
                "far": round(min(max(far, 0.0), 60.0), 2),
            }
            if left is None:
                heads.append(
                    {
                        **base,
                        "link": main["link"],
                        "turn": "s",
                        "over": (lanes - 1) / 2,
                        "mast": True,
                    }
                )
            else:
                heads.append(
                    {
                        **base,
                        "link": main["link"],
                        "turn": "s",
                        "over": max(0, lanes - 2) / 2,
                        "mast": False,
                    }
                )
                heads.append(
                    {**base, "link": left["link"], "turn": "l", "over": lanes - 1, "mast": True}
                )
    out_dir = OUT / "traffic"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "signals.json").write_text(json.dumps({"heads": heads}), encoding="utf-8")
    for trip in ex.trip_names(route):
        seed = trip.rsplit("_", 1)[1]
        f = ex.load_trip(trip)
        t0, t1 = float(f["t"].iloc[0]), float(f["t"].iloc[-1])
        sw = switches[seed]
        rows = []
        for i, h in enumerate(heads):
            s = sw[sw["tls"] == h["tls"]]
            c = s["state"].str[h["link"]].map(lambda ch: colour.get(ch, "R")).to_numpy()
            t = s["t"].to_numpy()
            before = np.nonzero(t <= t0)[0]
            last = None
            for j in range(before[-1] if len(before) else 0, len(t)):
                if t[j] > t1:
                    break
                if c[j] != last:
                    rows.append((max(0, int(round(t[j] - t0))), i, c[j]))
                    last = c[j]
        pd.DataFrame(rows, columns=["k", "head", "state"]).sort_values(["k", "head"]).to_csv(
            out_dir / f"signals_{trip}.csv", index=False, lineterminator="\n"
        )
    n_left = sum(h["turn"] == "l" for h in heads)
    print(f"[visual] signals: {len(heads)} heads ({n_left} left-turn) on {len(meta)} signals")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--route", default="R-DENSE")
    ap.add_argument("--trip", default=None)
    ap.add_argument(
        "--streets", action="store_true", help="only add street names to existing files"
    )
    ap.add_argument("--map", action="store_true", help="only write map.json (routes, sites)")
    ap.add_argument(
        "--traffic", action="store_true", help="only background cars and signals (SUMO re-run)"
    )
    a = ap.parse_args()
    if a.traffic:
        export_traffic(a.route)
        export_signals(a.route)
    elif a.map:
        export_map()
        export_map_image()
    elif a.streets:
        add_streets(a.route)
    else:
        main(a.route, a.trip)
