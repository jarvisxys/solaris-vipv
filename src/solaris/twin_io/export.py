"""Python -> Unity exchange files (twin/exchange/README.md), P8 / E8.

trajectory_<trip>_<date>.csv  t_utc, x_e, y_n, z_u, heading_deg, speed_mps, sun_az_deg,
                              sun_el_deg, covered; ENU metres at the ENU origin, heading true
                              (bearing of the vehicle's forward axis in ENU, so the UTM grid's
                              meridian convergence is absorbed), sun from pvlib SPA at the same
                              instants E3 used (apparent elevation).
unity_geometry.json           P3 surface / tree tiles copied into Assets/Geometry for glTFast,
                              with their glTF bounding boxes (TwinSetup's axis check).
ground_control.csv            surveyed NGS marks in the corridor: ENU position, lidar surface
                              height (dsm.tif) and the same meshes' height (Embree).
"""

import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pvlib
import rasterio

from solaris.core.params import REPO_ROOT
from solaris.geometry.crs import enu_transformer
from solaris.site import site_config

EXCHANGE = REPO_ROOT / "twin" / "exchange"
UNITY_PROJECT = REPO_ROOT / "twin" / "unity" / "SOLARIS-Twin"
TRAJ = REPO_ROOT / "data" / "derived" / "trajectories"
TILES = REPO_ROOT / "data" / "derived" / "tiles"
TZ = "America/Phoenix"
TRAJ_COLUMNS = [
    "t_utc",
    "x_e",
    "y_n",
    "z_u",
    "heading_deg",
    "speed_mps",
    "sun_az_deg",
    "sun_el_deg",
    "covered",
]
LAYER = {"surface": "Buildings", "trees": "Trees"}


def origin():
    return json.loads((EXCHANGE / "enu_origin.json").read_text(encoding="utf-8"))


def enu(cfg=None):
    return enu_transformer(cfg or site_config(), origin()["h_ellipsoid_m"])


def to_enu(tf, x, y, z):
    e, n, u = tf.transform(np.asarray(x, float), np.asarray(y, float), np.asarray(z, float))
    return np.asarray(e), np.asarray(n), np.asarray(u)


def enu_heading(tf, x, y, z, grid_heading_deg, step_m=10.0):
    """True heading in ENU of a forward axis given as a UTM grid bearing."""
    x, y, z, h = np.broadcast_arrays(
        *(np.asarray(v, float) for v in (x, y, z, np.radians(np.asarray(grid_heading_deg, float))))
    )
    e0, n0, _ = to_enu(tf, x, y, z)
    e1, n1, _ = to_enu(tf, x + step_m * np.sin(h), y + step_m * np.cos(h), z)
    return np.degrees(np.arctan2(e1 - e0, n1 - n0)) % 360.0


def day_times(f, day):
    """Instants of a trace replayed on ``day`` (local clock kept), as E3 day_inputs."""
    clock = pd.to_datetime(f["time_local"]).dt.strftime("%H:%M:%S")
    return pd.DatetimeIndex(pd.to_datetime(day + " " + clock)).tz_localize(TZ)


def trajectory_frame(f, day, meta, tf):
    """One E3 trace on one day in the exchange schema."""
    times = day_times(f, day)
    sp = pvlib.solarposition.get_solarposition(
        times, meta["latitude"], meta["longitude"], altitude=meta["altitude"]
    )
    x, y, z = f["x_utm"].to_numpy(), f["y_utm"].to_numpy(), f["z_road"].to_numpy()
    e, n, u = to_enu(tf, x, y, z)
    return pd.DataFrame(
        {
            "t_utc": times.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
            "x_e": e,
            "y_n": n,
            "z_u": u,
            "heading_deg": enu_heading(tf, x, y, z, f["angle"].to_numpy()),
            "speed_mps": f["speed"].to_numpy(),
            "sun_az_deg": sp["azimuth"].to_numpy(),
            "sun_el_deg": sp["apparent_elevation"].to_numpy(),
            "covered": f["covered"].astype(bool).astype(int).to_numpy(),
        }
    )[TRAJ_COLUMNS]


def trip_names(route):
    return sorted(p.name[: -len(".csv.gz")] for p in TRAJ.glob(f"{route}_*.csv.gz"))


def load_trip(trip):
    return pd.read_csv(TRAJ / f"{trip}.csv.gz").sort_values("t").reset_index(drop=True)


def write_csv(df, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, lineterminator="\n", float_format="%.6f")
    return path


def export_trajectories(route, days, meta, out_dir=EXCHANGE / "trajectories"):
    """Every trace of ``route`` on every day; returns the manifest rows."""
    tf = enu()
    rows = []
    for trip in trip_names(route):
        f = load_trip(trip)
        for day in days:
            p = write_csv(
                trajectory_frame(f, day, meta, tf), Path(out_dir) / f"trajectory_{trip}_{day}.csv"
            )
            rows.append({"trip": trip, "day": day, "file": p.name, "records": len(f)})
    return rows


def trip_bounds(route, buffer_m):
    """UTM bounds of every trace of ``route`` plus ``buffer_m``."""
    xy = pd.concat(
        [pd.read_csv(TRAJ / f"{t}.csv.gz", usecols=["x_utm", "y_utm"]) for t in trip_names(route)]
    )
    return (
        float(xy.x_utm.min() - buffer_m),
        float(xy.y_utm.min() - buffer_m),
        float(xy.x_utm.max() + buffer_m),
        float(xy.y_utm.max() + buffer_m),
    )


def tiles_in(bounds, tiles_dir=TILES):
    man = json.loads((Path(tiles_dir) / "MANIFEST.json").read_text(encoding="utf-8"))
    x0, y0, x1, y1 = bounds
    out = []
    for t in man["tiles"]:
        a, b, c, d = t["bounds_utm"]
        if not (c <= x0 or a >= x1 or d <= y0 or b >= y1):
            out.append(t)
    return out


def export_unity_geometry(
    bounds, project=UNITY_PROJECT, tiles_dir=TILES, out=EXCHANGE / "unity_geometry.json"
):
    """Copy the tiles in ``bounds`` into Assets/Geometry/{Buildings,Trees} (only if changed)
    and write the manifest TwinSetup reads."""
    entries = []
    for t in tiles_in(bounds, tiles_dir):
        for kind, layer in LAYER.items():
            if kind not in t:
                continue
            src = Path(tiles_dir) / kind / t[kind]["file"]
            rel = Path("Assets") / "Geometry" / layer / src.name
            dst = Path(project) / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if not dst.exists() or dst.stat().st_size != src.stat().st_size:
                shutil.copyfile(src, dst)
            lo, hi = t[kind]["bbox_gltf"]
            entries.append(
                {
                    "tile": t["tile"],
                    "layer": layer,
                    "asset": rel.as_posix(),
                    "bbox_min": lo,
                    "bbox_max": hi,
                }
            )
    doc = {"bounds_utm": [round(v, 1) for v in bounds], "tiles": entries}
    Path(out).write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8", newline="\n")
    return doc


def _raster_at(path, x, y):
    with rasterio.open(path) as s:
        return np.array([v[0] for v in s.sample(list(zip(x, y, strict=True)))], float)


def select_marks(gcp, bounds, n=5, max_dev_m=0.5, margin_m=100.0):
    """Surveyed NGS marks inside ``bounds`` whose DEM agrees with the mark, best first."""
    x0, y0, x1, y1 = bounds
    g = gcp[
        (gcp["source"] == "NGS")
        & gcp["E_m"].between(x0 + margin_m, x1 - margin_m)
        & gcp["N_m"].between(y0 + margin_m, y1 - margin_m)
        & (gcp["dem_minus_mark_m"].abs() < max_dev_m)
    ].copy()
    g["absdev"] = g["dem_minus_mark_m"].abs()
    return g.sort_values(["absdev", "id"]).head(n)


def mesh_heights(e, n, bounds, tiles_dir=TILES):
    """Height (ENU u) of the P3 surface meshes straight below ENU points (Embree)."""
    import trimesh
    from trimesh.ray.ray_pyembree import RayMeshIntersector

    from solaris.shading.mesh import load_tiles

    meshes = load_tiles(tiles_dir, bounds, layers=("surface",))["surface"]
    ix = RayMeshIntersector(trimesh.util.concatenate(meshes))
    o = np.column_stack([e, n, np.full(len(e), 2000.0)])
    d = np.tile([0.0, 0.0, -1.0], (len(e), 1))
    loc, idx, _ = ix.intersects_location(o, d, multiple_hits=False)
    out = np.full(len(e), np.nan)
    out[idx] = loc[:, 2]
    return out


def export_ground_control(
    bounds,
    gcp_csv=REPO_ROOT / "results" / "p3" / "table_ground_control.csv",
    dsm=REPO_ROOT / "data" / "derived" / "dsm.tif",
    out=EXCHANGE / "ground_control.csv",
):
    tf = enu()
    g = select_marks(pd.read_csv(gcp_csv), bounds)
    h = _raster_at(dsm, g["E_m"].to_numpy(), g["N_m"].to_numpy())
    e, n, u = to_enu(tf, g["E_m"], g["N_m"], h)
    m = mesh_heights(e, n, bounds)
    df = pd.DataFrame(
        {
            "id": g["id"].to_numpy(),
            "name": g["name"].to_numpy(),
            "x_e": e,
            "y_n": n,
            "u_mark": g["u_m"].to_numpy(),
            "u_lidar": u,
            "u_mesh": m,
            "mesh_minus_lidar_m": m - u,
        }
    )
    write_csv(df, out)
    return df
