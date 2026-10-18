"""Parking sites P1-P5 (workflow guide Sec. 3 table), chosen from SVF near each seed.

P1  open surface lot     SVF >= 0.95, no canopy within 20 m          nearest the seed
P2  downtown curb        SVF <= 0.5 on the Central Ave curb, Adams-Monroe   lowest SVF
P3  residential driveway open ground with canopy within 5 m and a building within 15 m
P4  garage top deck      roof of an Overture 'parking' structure >= 8 m tall, highest SVF
P5  shade-canopy lot     the P1 stall under a 4 m roof (modelled in E4, not in the DSM)
"""

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from scipy import ndimage

from solaris.geometry.crs import H_CRS, to_utm
from solaris.shading import sky_view_factor
from solaris.shading.city import RES, D, ground, horizons, read_window
from solaris.trajectory.routes import street_name

GROUND, BUILDING = 0, 1


def grid_around(x0, y0, radius, step):
    g = np.arange(-radius, radius + 1e-9, step)
    xx, yy = np.meshgrid(x0 + g, y0 + g)
    keep = np.hypot(xx - x0, yy - y0) <= radius
    return xx[keep], yy[keep]


def _layers(x0, y0, radius):
    b = (x0 - radius - 30, y0 - radius - 30, x0 + radius + 30, y0 + radius + 30)
    cls, tr = read_window(D / "classes.tif", b)
    cdsm, _ = read_window(D / "cdsm.tif", b)
    return cls, np.nan_to_num(cdsm), tr


def _at(arr, tr, x, y):
    c, r = ~tr * (np.asarray(x), np.asarray(y))
    return arr[np.asarray(r, int), np.asarray(c, int)]


def svf_at(x, y, z, shading_cfg):
    _, h_all = horizons(x, y, z, shading_cfg)
    return sky_view_factor(h_all)


def p1_open_lot(seed, pc, sc, eye):
    x0, y0 = seed
    x, y = grid_around(x0, y0, pc["search_radius_m"], pc["grid_m"])
    cls, cdsm, tr = _layers(x0, y0, pc["search_radius_m"])
    far_canopy = ndimage.distance_transform_edt(cdsm <= 0) * RES
    ok = (_at(cls, tr, x, y) == GROUND) & (_at(far_canopy, tr, x, y) >= pc["P1"]["canopy_free_m"])
    x, y = x[ok], y[ok]
    svf = svf_at(x, y, ground(x, y) + eye, sc)
    k = np.nonzero(svf >= pc["P1"]["svf_min"])[0]
    i = k[np.argmin(np.hypot(x[k] - x0, y[k] - y0))]
    return {
        "x": x[i],
        "y": y[i],
        "svf": svf[i],
        "heading_deg": 0.0,
        "criterion": f"SVF {svf[i]:.3f} >= {pc['P1']['svf_min']}, no canopy within "
        f"{pc['P1']['canopy_free_m']} m, nearest the seed",
    }


def p2_curb(arterials, pc, sc, eye):
    p = pc["P2"]
    e = arterials[arterials["name"].map(street_name) == p["street"]]
    lat0, lat1 = p["lat_range"]
    (_, y0), (_, y1) = to_utm(lat0, -112.074), to_utm(lat1, -112.074)
    rows = []
    for gm in e.geometry:
        d = np.arange(1.0, gm.length - 1.0, pc["grid_m"])
        if len(d) == 0:
            continue
        pts = shapely.line_interpolate_point(gm, d)
        nxt = shapely.line_interpolate_point(gm, d + 1.0)
        px, py = shapely.get_x(pts), shapely.get_y(pts)
        tx, ty = shapely.get_x(nxt) - px, shapely.get_y(nxt) - py
        nx, ny = ty, -tx
        flip = np.where(nx < 0, -1.0, 1.0)  # make the normal point east
        nrm = np.hypot(nx, ny) + 1e-9
        ex, ey = flip * nx / nrm, flip * ny / nrm
        for off in p["curb_offsets_m"]:
            # right-hand traffic: cars on the east curb face north, on the west curb south
            rows.append(
                pd.DataFrame(
                    {"x": px + off * ex, "y": py + off * ey, "side": "east", "heading_deg": 0.0}
                )
            )
            rows.append(
                pd.DataFrame(
                    {"x": px - off * ex, "y": py - off * ey, "side": "west", "heading_deg": 180.0}
                )
            )
    c = pd.concat(rows, ignore_index=True)
    c = c[(c["y"] >= y0) & (c["y"] <= y1)].drop_duplicates(subset=["x", "y"])
    # OSM merges ways that turn onto couplets; keep the curbs of the avenue itself
    x_axis, _ = to_utm(sum(p["lat_range"]) / 2, p["axis_lon"])
    c = c[np.abs(c["x"] - x_axis) <= p["axis_tolerance_m"]]
    # the curb must be open ground: no building, arcade, canopy or DSM hole over it
    cx, cy = c["x"].to_numpy(), c["y"].to_numpy()
    b = (cx.min() - 5, cy.min() - 5, cx.max() + 5, cy.max() + 5)
    cls, tr = read_window(D / "classes.tif", b)
    cdsm, _ = read_window(D / "cdsm.tif", b)
    holes, _ = read_window(D / "dsm_holes.tif", b)
    to_bld = ndimage.distance_transform_edt(cls != BUILDING) * RES
    ok = (_at(cls, tr, cx, cy) == GROUND) & (_at(np.nan_to_num(cdsm), tr, cx, cy) <= 0)
    ok &= (_at(holes, tr, cx, cy) == 0) & (_at(to_bld, tr, cx, cy) >= p["min_wall_distance_m"])
    c = c[ok]
    svf = svf_at(c["x"].to_numpy(), c["y"].to_numpy(), ground(c["x"], c["y"]) + eye, sc)
    i = int(np.argmin(svf))
    r = c.iloc[i]
    return {
        "x": r["x"],
        "y": r["y"],
        "svf": svf[i],
        "heading_deg": r["heading_deg"],
        "criterion": f"lowest curb SVF on {p['street']} between the lat range: {svf[i]:.3f} "
        f"(<= {p['svf_max']} required), {r['side']} curb",
    }


def p3_driveway(seed, pc, sc, eye):
    x0, y0 = seed
    x, y = grid_around(x0, y0, pc["search_radius_m"], pc["grid_m"])
    cls, cdsm, tr = _layers(x0, y0, pc["search_radius_m"])
    to_canopy = ndimage.distance_transform_edt(cdsm <= 0) * RES
    to_bld = ndimage.distance_transform_edt(cls != BUILDING) * RES
    ok = (
        (_at(cls, tr, x, y) == GROUND)
        & (_at(cdsm, tr, x, y) <= 0)
        & (_at(to_canopy, tr, x, y) <= pc["P3"]["canopy_within_m"])
        & (_at(to_bld, tr, x, y) <= pc["P3"]["building_within_m"])
    )
    x, y = x[ok], y[ok]
    i = int(np.argmin(np.hypot(x - x0, y - y0)))
    svf = svf_at(x[i : i + 1], y[i : i + 1], ground(x[i : i + 1], y[i : i + 1]) + eye, sc)[0]
    d_c = _at(to_canopy, tr, x[i : i + 1], y[i : i + 1])[0]
    return {
        "x": x[i],
        "y": y[i],
        "svf": svf,
        "heading_deg": 0.0,
        "criterion": f"open ground, canopy {d_c:.1f} m away (<= {pc['P3']['canopy_within_m']}), "
        f"building within {pc['P3']['building_within_m']} m, nearest the seed",
    }


def p4_garage_deck(seed, footprints, pc, sc, eye):
    p = pc["P4"]
    fp = footprints[
        (footprints["class"] == p["footprint_class"])
        & (footprints["height_m"] >= p["min_height_m"])
    ]
    fp = fp.assign(d=fp.distance(shapely.Point(seed))).sort_values("d").head(5)
    best = None
    for row in fp.itertuples():
        poly = row.geometry.buffer(-3.0)  # stay off the parapet
        if poly.is_empty:
            continue
        x0, y0, x1, y1 = poly.bounds
        xx, yy = np.meshgrid(np.arange(x0, x1, pc["grid_m"]), np.arange(y0, y1, pc["grid_m"]))
        inside = shapely.contains_xy(poly, xx.ravel(), yy.ravel())
        x, y = xx.ravel()[inside], yy.ravel()[inside]
        if len(x) == 0:
            continue
        z = ground(x, y, layer="dsm.tif") + eye
        svf = svf_at(x, y, z, sc)
        i = int(np.argmax(svf))
        if best is None or svf[i] > best["svf"]:
            best = {
                "x": x[i],
                "y": y[i],
                "svf": svf[i],
                "heading_deg": 0.0,
                "deck": True,
                "criterion": f"top deck of Overture '{p['footprint_class']}' structure "
                f"{row.overture_id} ({row.height_m:.0f} m), highest-SVF point",
            }
    return best


def site_table(sites):
    g = gpd.GeoDataFrame(
        [{k: v for k, v in s.items() if k not in ("x", "y")} | {"id": k} for k, s in sites.items()],
        geometry=[shapely.Point(s["x"], s["y"]) for s in sites.values()],
        crs=H_CRS,
    )
    return g
