"""ENU origin and ground control (P3).

The ENU origin's ellipsoidal height is the DEM ground at the origin plus GEOID18, written to
twin/exchange/enu_origin.json for Unity. Ground control points are NGS survey marks inside the
AOI with adjusted horizontal positions and adjusted NAVD88 heights; each row gives the mark
in every frame (lat/lon, UTM, NAVD88, ellipsoidal, ENU, glTF) and the DEM minus the
published height, an independent check of the lidar's vertical datum.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
import requests

from .crs import ellipsoidal_height, enu_transformer, to_gltf, to_utm
from .sources import lonlat_bounds

NGS_URL = "https://geodesy.noaa.gov/api/nde/bounds"
POOR_POSITION = {"SCALED", "", "NO CHECK", "HANDHELD"}


def dem_height(dem_path, x, y) -> np.ndarray:
    """Bilinear DEM height at UTM points; neighbours that are nodata or off the raster
    drop out and the remaining weights are renormalised."""
    with rasterio.open(dem_path) as src:
        col, row = ~src.transform * (np.asarray(x, float), np.asarray(y, float))
        c0, r0 = np.floor(col - 0.5).astype(int), np.floor(row - 0.5).astype(int)
        fc, fr = col - 0.5 - c0, row - 0.5 - r0
        out = []
        for i in range(len(c0)):
            w = rasterio.windows.Window(c0[i], r0[i], 2, 2)
            z = src.read(1, window=w, boundless=True, masked=True).filled(np.nan)
            wt = np.outer([1 - fr[i], fr[i]], [1 - fc[i], fc[i]])
            ok = np.isfinite(z) & (wt > 0)
            out.append(float((z[ok] * wt[ok]).sum() / wt[ok].sum()) if ok.any() else np.nan)
    return np.array(out)


def enu_origin(cfg, dem_path) -> dict:
    o = cfg["enu_origin"]
    x, y = to_utm(o["lat_deg"], o["lon_deg"])
    H = float(dem_height(dem_path, [x], [y])[0])
    h = ellipsoidal_height(o["lat_deg"], o["lon_deg"], H)
    return {
        "lat_deg": o["lat_deg"],
        "lon_deg": o["lon_deg"],
        "datum": "NAD83 / GRS80",
        "E_m": round(x, 3),
        "N_m": round(y, 3),
        "H_navd88_m": round(H, 3),
        "h_ellipsoid_m": round(h, 3),
        "geoid": "GEOID18",
        "note": "Cesium for Unity: set CesiumGeoreference to lat/lon/h_ellipsoid_m",
    }


def fetch_ngs(polygon_utm, out) -> Path:
    w, s, e, n = lonlat_bounds(polygon_utm, pad_deg=0)
    r = requests.get(
        NGS_URL, params={"minlat": s, "maxlat": n, "minlon": w, "maxlon": e}, timeout=120
    )
    r.raise_for_status()
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(r.json(), indent=1) + "\n", encoding="utf-8", newline="\n")
    return out


def good_marks(marks) -> pd.DataFrame:
    df = pd.DataFrame(marks)
    for c in ("lat", "lon", "orthoHt"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    pos = df["posSource"].str.strip().str.upper()
    ok = ~pos.isin(POOR_POSITION) & (df["vertSource"].str.strip().str.upper() == "ADJUSTED")
    return df[ok & df[["lat", "lon", "orthoHt"]].notna().all(axis=1)].reset_index(drop=True)


def ground_control(cfg, marks, dem_path, origin) -> pd.DataFrame:
    df = good_marks(marks)
    enu = enu_transformer(cfg, origin["h_ellipsoid_m"])
    rows = [
        {
            "id": "ENU_ORIGIN",
            "name": "Central Ave & Washington St",
            "source": "config",
            "lat_deg": origin["lat_deg"],
            "lon_deg": origin["lon_deg"],
            "H_navd88_m": origin["H_navd88_m"],
            "pos_source": "",
            "vert_source": "DEM",
            "monument": "",
            "setting": "",
        }
    ]
    for m in df.to_dict("records"):
        rows.append(
            {
                "id": m["pid"],
                "name": m["name"].strip(),
                "source": "NGS",
                "lat_deg": m["lat"],
                "lon_deg": m["lon"],
                "H_navd88_m": m["orthoHt"],
                "pos_source": m["posSource"].strip(),
                "vert_source": m["vertSource"].strip(),
                "monument": str(m.get("monumentType", "")).strip(),
                "setting": str(m.get("setting", "")).strip(),
            }
        )
    out = pd.DataFrame(rows)
    E, N = to_utm(out["lat_deg"].to_numpy(), out["lon_deg"].to_numpy())
    out["E_m"], out["N_m"] = np.round(E, 3), np.round(N, 3)
    out["h_ellipsoid_m"] = [
        round(ellipsoidal_height(a, b, h), 3)
        for a, b, h in zip(out.lat_deg, out.lon_deg, out.H_navd88_m, strict=True)
    ]
    e, n, u = enu.transform(E, N, out["H_navd88_m"].to_numpy())
    out["e_m"], out["n_m"], out["u_m"] = np.round(e, 3), np.round(n, 3), np.round(u, 3)
    g = to_gltf(np.column_stack([e, n, u]))
    out["gltf_x"], out["gltf_y"], out["gltf_z"] = (
        g[:, 0].round(3),
        g[:, 1].round(3),
        g[:, 2].round(3),
    )
    out["dem_H_m"] = np.round(dem_height(dem_path, E, N), 3)
    out["dem_minus_mark_m"] = (out["dem_H_m"] - out["H_navd88_m"]).round(3)
    # Marks on structures sit above the ground the DEM models; hand-held positions (a few m)
    # can land a mark on a freeway cut or curb. Flagged, not dropped.
    out["outlier_gt_1m"] = (out["dem_minus_mark_m"].abs() > 1.0) & (out["source"] == "NGS")
    return out


def control_summary(gcp) -> dict:
    d = gcp.loc[gcp.source == "NGS", "dem_minus_mark_m"].dropna()
    if d.empty:
        return {"n_marks": 0}
    return {
        "n_marks": int(len(d)),
        "median_m": round(float(d.median()), 3),
        "mad_m": round(float((d - d.median()).abs().median()), 3),
        "within_0p5m_pct": round(float(100 * (d.abs() <= 0.5).mean()), 1),
        "p90_abs_m": round(float(d.abs().quantile(0.9)), 3),
        "outliers_gt_1m": int((d.abs() > 1.0).sum()),
    }
