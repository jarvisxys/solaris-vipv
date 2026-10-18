"""Route selection by a measured obstruction metric (workflow guide Sec. 3, P6).

1. Every OSM trunk / primary / secondary way in the AOI (named arterials, not freeways).
2. Points every 10 m along each centreline at 1.8 m above the DEM (vehicle roof).
3. Per point: sky view factor (buildings + trees, E1 raster engine) and the annual sunlit
   fraction of the sky path (TMY daylight hours with the sun above the horizon mask).
4. Candidate routes: 8 km windows every 1 km along each arterial (whole arterials of
   6-10 km too); score = mean SVF and SVF variance.
5. Open = highest mean SVF; Dense = lowest; Mixed = highest variance among candidates whose
   mean SVF lies in the middle quantile band. At least one N-S and one E-W route.
6. Frozen as routes/v1/*.geojson with SHA-256 in routes/v1/MANIFEST.json.
"""

import re

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import LineString

from solaris.geometry.crs import H_CRS


def download_arterials(lonlat_bbox, road_types):
    """Undirected OSM ways of the given highway types in a lon/lat bbox, in UTM."""
    import osmnx as ox

    filt = '["highway"~"^(' + "|".join(road_types) + ')$"]'
    G = ox.graph_from_bbox(
        lonlat_bbox, custom_filter=filt, simplify=True, retain_all=True, truncate_by_edge=True
    )
    e = ox.graph_to_gdfs(ox.convert.to_undirected(G), nodes=False).to_crs(H_CRS).reset_index()
    first = lambda v: v[0] if isinstance(v, list) else v  # noqa: E731
    out = gpd.GeoDataFrame(
        {
            "osmid": e["osmid"].map(
                lambda v: ";".join(map(str, v)) if isinstance(v, list) else str(v)
            ),
            "name": e["name"].map(first),
            "highway": e["highway"].map(first),
            "oneway": e["oneway"].astype(str),
        },
        geometry=e.geometry.values,
        crs=H_CRS,
    )
    return out


def street_name(name):
    """'North Central Avenue' -> 'Central Avenue' (direction prefixes dropped)."""
    if not isinstance(name, str):
        return None
    return re.sub(r"^(North|South|East|West)\s+", "", name).strip()


def arterial_points(edges, step_m, suffix_regex):
    """Points every ``step_m`` along every named arterial edge: street, x, y, s (axis)."""
    e = edges.assign(street=edges["name"].map(street_name)).dropna(subset=["street"])
    e = e[e["street"].str.match(f".*{suffix_regex}")]
    rows = []
    for street, g in e.groupby("street"):
        geoms = list(g.geometry)
        xs = np.concatenate([np.asarray(gm.coords)[:, 0] for gm in geoms])
        ys = np.concatenate([np.asarray(gm.coords)[:, 1] for gm in geoms])
        ns = (ys.max() - ys.min()) >= (xs.max() - xs.min())
        for gm in geoms:
            d = np.arange(step_m / 2, gm.length, step_m)
            if len(d) == 0:
                continue
            pts = shapely.line_interpolate_point(gm, d)
            px, py = shapely.get_x(pts), shapely.get_y(pts)
            rows.append(
                pd.DataFrame(
                    {
                        "street": street,
                        "x": px,
                        "y": py,
                        "s": py if ns else px,
                        "orientation": "N-S" if ns else "E-W",
                    }
                )
            )
    return pd.concat(rows, ignore_index=True)


def sunlit_fraction(h_all, sun_az, sun_el, chunk=2000):
    """Share of the given sun positions (e.g. TMY daylight hours) above each point's horizon."""
    from solaris.shading import beam_visible

    out = np.empty(len(h_all))
    for i in range(0, len(h_all), chunk):
        out[i : i + chunk] = beam_visible(h_all[i : i + chunk], sun_az, sun_el).mean(axis=1)
    return out


def candidates(points, r):
    """8 km windows (stride 1 km) per arterial plus whole 6-10 km arterials, with scores."""
    rows = []
    step = r["sample_step_m"]
    for street, g in points.groupby("street"):
        s0, s1 = g["s"].min(), g["s"].max()
        span = s1 - s0
        starts = []
        if r["min_m"] <= span <= r["max_m"]:
            starts.append((s0, s1))
        if span >= r["window_m"]:
            starts += [
                (a, a + r["window_m"])
                for a in np.arange(s0, s1 - r["window_m"] + 1e-6, r["stride_m"])
            ]
        for a, b in starts:
            w = g[(g["s"] >= a) & (g["s"] <= b)]
            # coverage: occupied 10 m bins along the axis (both carriageways count once)
            bins = np.unique(np.floor((w["s"] - a) / step))
            cov = len(bins) * step / (b - a)
            if cov < r["min_coverage"]:
                continue
            rows.append(
                {
                    "street": street,
                    "orientation": g["orientation"].iloc[0],
                    "s_from": a,
                    "s_to": b,
                    "length_m": b - a,
                    "coverage": cov,
                    "n_points": len(w),
                    "svf_mean": w["svf"].mean(),
                    "svf_var": w["svf"].var(),
                    "svf_bld_mean": w["svf_bld"].mean(),
                    "sunlit_mean": w["sunlit"].mean(),
                }
            )
    return pd.DataFrame(rows)


def choose(c, mixed_band):
    """Open, Dense, Mixed on distinct streets, with at least one N-S and one E-W route."""
    order = {
        "R-OPEN": c.sort_values("svf_mean", ascending=False),
        "R-DENSE": c.sort_values("svf_mean", ascending=True),
    }
    lo, hi = c["svf_mean"].quantile(mixed_band)
    band = c[(c["svf_mean"] >= lo) & (c["svf_mean"] <= hi)]
    order["R-MIXED"] = band.sort_values("svf_var", ascending=False)

    def pick(taken, need=None):
        out = {}
        for k in ("R-DENSE", "R-OPEN", "R-MIXED"):
            for _, row in order[k].iterrows():
                if row["street"] in taken or (
                    need and k == need[0] and row["orientation"] != need[1]
                ):
                    continue
                out[k] = row
                taken = taken | {row["street"]}
                break
        return out

    sel = pick(frozenset())
    if len({s["orientation"] for s in sel.values()}) < 2:
        # force the Mixed route (the least constrained rule) onto the other orientation
        other = "E-W" if sel["R-DENSE"]["orientation"] == "N-S" else "N-S"
        sel = pick(frozenset(), need=("R-MIXED", other))
    return sel


def route_line(edges, street, s_from, s_to, orientation, off_street_penalty=3.0):
    """Driving line for a window: the shortest path over the arterial network between the
    street's points nearest the window ends, with edges of other streets weighted x3 so the
    path stays on the street and only bridges its gaps. Runs north (N-S) or east (E-W)."""
    import networkx as nx

    def node(xy):
        return (round(xy[0], 1), round(xy[1], 1))

    G = nx.Graph()
    for nm, gm in zip(edges["name"].map(street_name), edges.geometry, strict=True):
        c = list(gm.coords)
        w = gm.length * (1.0 if nm == street else off_street_penalty)
        a, b = node(c[0]), node(c[-1])
        if not G.has_edge(a, b) or G[a][b]["weight"] > w:
            G.add_edge(a, b, weight=w, coords=c)
    on = edges[edges["name"].map(street_name) == street]
    ends = np.array([xy for gm in on.geometry for xy in (gm.coords[0], gm.coords[-1])])
    axis = ends[:, 1] if orientation == "N-S" else ends[:, 0]
    start = node(ends[np.argmin(np.abs(axis - s_from))])
    stop = node(ends[np.argmin(np.abs(axis - s_to))])
    path = nx.shortest_path(G, start, stop, weight="weight")
    coords = []
    for a, b in zip(path[:-1], path[1:], strict=True):
        c = G[a][b]["coords"]
        if node(c[0]) != a:
            c = c[::-1]
        coords += c if not coords else c[1:]
    return LineString(coords)


def seed_overlap(line, seeds, buffer_m=100.0):
    """Share of the route within ``buffer_m`` of each seed route."""
    return {
        k: round(line.intersection(g.buffer(buffer_m)).length / line.length, 3)
        for k, g in seeds.items()
        if k.startswith("R-")
    }
