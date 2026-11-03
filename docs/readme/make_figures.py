"""Figures and 3D files for the README (docs/readme/). Not part of the Snakemake DAG.

Reads the pipeline's inputs and outputs (data/, routes/v2/, configs/, paper/figures/) and never
writes outside docs/readme/. Blender renders and Unity captures are composed only when their
folders are given (they are not in the repository; docs/readme/blender_renders.py makes the
Blender ones).

    python docs/readme/make_figures.py                       # data figures only
    python docs/readme/make_figures.py --renders DIR --unity DIR
"""

import argparse
import json
import shutil
import struct
import subprocess
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import rasterio  # noqa: E402
import rasterio.features  # noqa: E402
import rasterio.windows  # noqa: E402
import yaml  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "readme"
E0, N0, H0 = 400179.648, 3701514.105, 331.663  # twin/exchange/enu_origin.json
ROUTE_COL = {"R-OPEN": "#2a9d8f", "R-MIXED": "#e9a23b", "R-DENSE": "#d1495b", "R-TUNNEL": "#6a4c93"}
INK, MUTED, PAPER = "#1f2933", "#7b8794", "#f7f5f0"


def font(size, bold=False):
    for name in ("arialbd.ttf", "DejaVuSans-Bold.ttf") if bold else ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


# ---------------------------------------------------------------- interactive files (GitHub)


def routes_geojson():
    """Routes and parking sites as one small GeoJSON for the README map (5 decimals, ~1 m)."""
    feats = []
    for rid in ROUTE_COL:
        g = json.loads((ROOT / "routes/v2" / f"{rid}.geojson").read_text())
        for f in g["features"]:
            coords = f["geometry"]["coordinates"]
            if f["geometry"]["type"] == "LineString":
                coords = coords[:: max(1, len(coords) // 60)] + [coords[-1]]
            p = f["properties"]
            props = {
                "route": rid,
                "street": p.get("street"),
                "length_km": round(p["length_m"] / 1000, 2),
            }
            if "svf_mean" in p:
                props["mean_sky_view_factor"] = round(p["svf_mean"], 2)
            if "tunnel_m" in p:
                props["covered_m"] = p["tunnel_m"]
            feats.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": f["geometry"]["type"],
                        "coordinates": np.round(coords, 5).tolist(),
                    },
                    "properties": {**props, "stroke": ROUTE_COL[rid], "stroke-width": 6},
                }
            )
            # GitHub's map opens a popup only for markers, so each route also gets one
            mid = coords[len(coords) // 2]
            feats.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": np.round(mid, 5).tolist()},
                    "properties": {
                        **props,
                        "marker-color": ROUTE_COL[rid],
                        "marker-symbol": "road",
                    },
                }
            )
    names = {
        "P1": "open lot",
        "P2": "street-canyon curb",
        "P3": "residential driveway beside a tree",
        "P4": "garage top deck",
        "P5": "P1 under a shade roof",
    }
    g = json.loads((ROOT / "routes/v2/parking_sites.geojson").read_text())
    for f in g["features"]:
        p = f["properties"]
        if p["id"] == "P5":
            continue  # same stall as P1
        feats.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": np.round(f["geometry"]["coordinates"], 5).tolist(),
                },
                "properties": {
                    "site": p["id"],
                    "kind": names[p["id"]]
                    + (" (P5: same stall under a shade roof)" if p["id"] == "P1" else ""),
                    "sky_view_factor": round(p["svf"], 2),
                    "marker-color": "#264653",
                    "marker-symbol": "parking",
                },
            }
        )
    (OUT / "routes.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": feats}, separators=(",", ":")) + "\n",
        newline="\n",
    )


def _compact_stl(name, tris, nd=1):
    """ASCII STL with short numbers, small enough to inline in the README."""

    def g(x):
        s = f"{x:.{nd}f}".rstrip("0").rstrip(".")
        return "0" if s in ("", "-0") else s

    lines = [f"solid {name}"]
    for a, b, c in tris:
        n = np.cross(b - a, c - a)
        n = n / (np.linalg.norm(n) or 1)
        lines += ["facet normal " + " ".join(f"{q:.2f}".rstrip("0").rstrip(".") or "0" for q in n)]
        lines += ["outer loop", *("vertex " + " ".join(g(q) for q in p) for p in (a, b, c))]
        lines += ["endloop", "endfacet"]
    return "\n".join(lines + [f"endsolid {name}"]) + "\n"


def vehicle_skin_stl(lift=0.05, thick=0.05):
    """The Blender vehicle wearing the exact PV skin of configs/vehicle/solaris_p0.yaml.

    Each facet is a thin plate raised `lift` m along its normal so it stands out in GitHub's
    single-colour viewer. The vehicle comes from blender_renders.py (body frame, x forward,
    y left, z up, ground under the body centre), the same frame as the facets.
    """
    cfg = yaml.safe_load((ROOT / "configs/vehicle/solaris_p0.yaml").read_text())
    v = [
        list(map(float, ln.split()[1:]))
        for ln in (OUT / "solaris_p0_vehicle_lowpoly.stl").read_text().splitlines()
        if ln.startswith("vertex")
    ]
    tris = [tuple(np.array(v[i : i + 3])) for i in range(0, len(v), 3)]
    for f in cfg["facets"]:
        t, a = np.radians(f["tilt_deg"]), np.radians(f["azimuth_body_deg"])
        nrm = np.array([np.cos(a) * np.sin(t), -np.sin(a) * np.sin(t), np.cos(t)])
        across = np.array([-np.sin(a), -np.cos(a), 0.0]) * f["across_m"] / 2
        up = np.cross(nrm, across / np.linalg.norm(across)) * f["slope_m"] / 2
        c0 = np.array(f["centre_m"]) + lift * nrm
        lo = [c0 + su * across + sv * up for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        hi = [p + thick * nrm for p in lo]
        tris += [
            (lo[0], lo[2], lo[1]),
            (lo[0], lo[3], lo[2]),
            (hi[0], hi[1], hi[2]),
            (hi[0], hi[2], hi[3]),
        ]
        for i in range(4):
            j = (i + 1) % 4
            tris += [(lo[i], lo[j], hi[j]), (lo[i], hi[j], hi[i])]
    stl = _compact_stl("solaris_p0_skin", tris, nd=2)
    (OUT / "solaris_p0_skin.stl").write_text(stl, newline="\n")


def canyon_stl(half=150.0, step=2.0):
    """Buildings and trees within `half` m of the P2 curb as a binary STL height field."""
    m = json.loads((ROOT / "routes/v2/MANIFEST.json").read_text())["parking"]["P2"]
    x0, y0 = m["x"], m["y"]

    def grab(p):  # block maximum of the 0.5 m raster on the coarser step
        with rasterio.open(p) as s:
            w = rasterio.windows.from_bounds(
                x0 - half, y0 - half, x0 + half, y0 + half, s.transform
            )
            a = s.read(1, window=w.round_offsets().round_lengths()).astype(np.float32)
            k = int(round(step / s.res[0]))
            n = a.shape[0] // k
            return a[: n * k, : n * k].reshape(n, k, n, k).max(axis=(1, 3))

    z = np.maximum(
        grab(ROOT / "data/derived/dsm.tif"),
        grab(ROOT / "data/derived/dem.tif") + grab(ROOT / "data/derived/cdsm.tif"),
    )
    z = np.where(z < -1000, np.nan, z) - H0
    z = np.nan_to_num(z, nan=float(np.nanmin(z)))
    n = z.shape[0]
    xs = (np.arange(n) + 0.5) * step - half
    X, Y = np.meshgrid(xs, -xs)
    P = np.dstack([X, Y, z])
    a, b, c, d = P[:-1, :-1], P[:-1, 1:], P[1:, 1:], P[1:, :-1]
    tris = np.concatenate(
        [np.stack([a, c, b], 2).reshape(-1, 3, 3), np.stack([a, d, c], 2).reshape(-1, 3, 3)]
    )
    nrm = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
    rec = np.zeros(len(tris), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("attr", "<u2")])
    rec["n"], rec["v"] = nrm, tris
    with open(OUT / "canyon_p2.stl", "wb") as f:
        f.write(
            b"SOLARIS-Twin: 300 m around the P2 curb (Central Ave), lidar buildings + trees".ljust(
                80, b" "
            )
        )
        f.write(struct.pack("<I", len(rec)))
        f.write(rec.tobytes())


# ---------------------------------------------------------------- static figures


def weather():
    """Typical-year (TMY) global horizontal irradiance and air temperature, hour by day."""
    df = pd.read_csv(ROOT / "data/raw/nsrdb/33.45_-112.06_tmy-2023_60min.csv", skiprows=2)
    ghi = df["GHI"].to_numpy().reshape(365, 24).T
    tmp = df["Temperature"].to_numpy().reshape(365, 24).T
    fig, axs = plt.subplots(2, 1, figsize=(9, 4.6), sharex=True, facecolor=PAPER)
    for ax, z, cmap, lab in (
        (axs[0], ghi, "inferno", "Sunlight on a flat surface, GHI (W/m²)"),
        (axs[1], tmp, "coolwarm", "Air temperature (°C)"),
    ):
        im = ax.imshow(z, aspect="auto", origin="lower", cmap=cmap, extent=(0.5, 365.5, -0.5, 23.5))
        ax.set_yticks([0, 6, 12, 18, 23]), ax.set_ylabel("hour", color=INK)
        ax.set_facecolor(PAPER)
        cb = fig.colorbar(im, ax=ax, pad=0.01)
        cb.set_label(lab, fontsize=8, color=INK)
        cb.ax.tick_params(labelsize=7)
    months = pd.date_range("2023-01-01", periods=12, freq="MS").dayofyear
    axs[1].set_xticks(months, ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"])
    fig.suptitle(
        "Phoenix typical meteorological year (NSRDB TMY-2023), every hour of the year",
        fontsize=10,
        color=INK,
    )
    fig.tight_layout()
    fig.savefig(OUT / "weather_tmy.png", dpi=150, facecolor=PAPER)
    plt.close(fig)


def network_map():
    """OSM arterials, the four frozen routes and the parking sites."""
    art = gpd.read_file(ROOT / "data/raw/osm/arterials.gpkg").to_crs(26912)
    fig, ax = plt.subplots(figsize=(7.2, 7.2), facecolor=PAPER)
    ax.set_facecolor(PAPER)
    art.plot(ax=ax, color="#c3c8cf", lw=0.7)
    for rid, col in ROUTE_COL.items():
        r = gpd.read_file(ROOT / "routes/v2" / f"{rid}.geojson").to_crs(26912)
        r.plot(ax=ax, color=col, lw=3.2, zorder=3)
        c = r.geometry.iloc[0].interpolate(0.85 if rid == "R-DENSE" else 0.5, normalized=True)
        ax.annotate(
            rid,
            (c.x, c.y),
            xytext=(6, 6),
            textcoords="offset points",
            fontsize=9,
            weight="bold",
            color=col,
            bbox=dict(boxstyle="round,pad=0.2", fc=PAPER, ec="none", alpha=0.85),
            zorder=5,
        )
    p = gpd.read_file(ROOT / "routes/v2/parking_sites.geojson").to_crs(26912)
    p = p[p["id"] != "P5"]
    ax.scatter(
        p.geometry.x, p.geometry.y, s=60, c="#264653", marker="s", zorder=6, edgecolor="white", lw=1
    )
    offs = {"P1": (6, -12), "P2": (-22, -4), "P3": (-8, -14), "P4": (7, 2)}
    for _, r in p.iterrows():
        lab = "P1/P5" if r["id"] == "P1" else r["id"]
        ax.annotate(
            lab,
            (r.geometry.x, r.geometry.y),
            xytext=offs[r["id"]],
            textcoords="offset points",
            fontsize=8,
            color="#264653",
            weight="bold",
        )
    ax.add_patch(
        plt.Rectangle((399500, 3701000), 1000, 1000, fill=False, ec=INK, lw=1, ls="--", zorder=4)
    )
    ax.annotate(
        "1 km block\nin the renders",
        (399500, 3701000),
        xytext=(-4, -4),
        textcoords="offset points",
        fontsize=7.5,
        color=INK,
        ha="right",
        va="top",
    )
    ax.set_xlabel(""), ax.set_ylabel("")
    xs = pd.concat(
        [gpd.read_file(ROOT / "routes/v2" / f"{k}.geojson").to_crs(26912) for k in ROUTE_COL]
    ).total_bounds
    pad = 900
    ax.set_xlim(xs[0] - pad, xs[2] + pad), ax.set_ylim(xs[1] - pad, xs[3] + pad)
    ax.set_xticks([]), ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.plot([xs[2] - 2000 + pad / 2, xs[2] + pad / 2], [xs[1] - pad / 2] * 2, color=INK, lw=2)
    ax.annotate(
        "2 km",
        (xs[2] - 1000 + pad / 2, xs[1] - pad / 2),
        xytext=(0, 4),
        textcoords="offset points",
        ha="center",
        fontsize=8,
    )
    ax.set_title(
        "Central Phoenix: OSM arterials, the four test routes and the parking sites",
        fontsize=10,
        color=INK,
    )
    fig.tight_layout()
    fig.savefig(OUT / "network_routes.png", dpi=150, facecolor=PAPER)
    plt.close(fig)


def traffic():
    """The frozen SUMO trips: one trip at three traffic levels, and every trip's duration."""
    T = ROOT / "data/derived/trajectories"
    lev_col = {"low": "#2a9d8f", "medium": "#e9a23b", "high": "#d1495b"}
    fig, (a, b) = plt.subplots(
        1, 2, figsize=(10, 3.8), facecolor=PAPER, gridspec_kw={"width_ratios": [1.25, 1]}
    )
    for lev, col in lev_col.items():
        d = pd.read_csv(T / f"R-DENSE_fwd_16200_{lev}.csv.gz")
        s = np.concatenate([[0], np.cumsum(np.hypot(np.diff(d.x_utm), np.diff(d.y_utm)))]) / 1000
        a.plot(
            d.t - d.t.iloc[0],
            s,
            color=col,
            lw=1.8,
            label=f"{lev} traffic ({(d.t.iloc[-1] - d.t.iloc[0]) / 60:.1f} min)",
        )
    a.set_xlabel("time since departure (s)"), a.set_ylabel("distance along Central Ave (km)")
    a.set_title(
        "R-DENSE northbound, 12:00: flat steps are red lights and queues", fontsize=9, color=INK
    )
    a.legend(fontsize=8, frameon=False)
    rows = []
    for f in sorted(T.glob("*.csv.gz")):
        route, way, dep, lev = f.name.removesuffix(".csv.gz").split("_")
        t = pd.read_csv(f, usecols=["t"]).t
        rows.append((route, lev, (t.iloc[-1] - t.iloc[0]) / 60))
    df = pd.DataFrame(rows, columns=["route", "level", "min"])
    order = [r for r in ROUTE_COL if r in set(df.route)]
    for i, r in enumerate(order):
        for j, (lev, col) in enumerate(lev_col.items()):
            v = df[(df.route == r) & (df.level == lev)]["min"]
            b.scatter(
                np.full(len(v), i + (j - 1) * 0.22)
                + np.random.default_rng(i * 3 + j).uniform(-0.06, 0.06, len(v)),
                v,
                s=16,
                color=col,
                alpha=0.85,
                label=lev if i == 0 else None,
            )
    b.set_xticks(range(len(order)), order, fontsize=8)
    (
        b.set_ylabel("trip duration (min)"),
        b.set_title(
            f"All {len(df)} simulated trips (route, direction, departure, traffic)",
            fontsize=9,
            color=INK,
        ),
    )
    b.legend(fontsize=8, frameon=False, title="traffic", title_fontsize=8)
    for ax in (a, b):
        ax.set_facecolor(PAPER)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.tick_params(labelsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "traffic_trips.png", dpi=150, facecolor=PAPER)
    plt.close(fig)


def paper_figures():
    """The paper's vector figures as PNG for the README (pdftoppm from Poppler or MiKTeX)."""
    exe = shutil.which("pdftoppm")
    if not exe:
        print("pdftoppm not found: paper figures skipped")
        return
    for pdf in sorted((ROOT / "paper/figures").glob("fig_*.pdf")):
        subprocess.run(
            [exe, "-png", "-r", "220", "-singlefile", str(pdf), str(OUT / pdf.stem)], check=True
        )


# ---------------------------------------------------------------- renders and captures


def _trim(im, pad=12):
    bb = im.getchannel("A").getbbox() if im.mode == "RGBA" else None
    if bb:
        im = im.crop(
            (
                max(bb[0] - pad, 0),
                max(bb[1] - pad, 0),
                min(bb[2] + pad, im.width),
                min(bb[3] + pad, im.height),
            )
        )
    return im


def compose(renders: Path, unity: Path | None):
    for name, w in (
        ("L1_points_height", 960),
        ("L2_points_class", 960),
        ("L3_mesh_buildings", 960),
        ("L4_mesh_trees", 960),
        ("suv_beauty", 900),
        ("suv_facets_front", 640),
        ("suv_facets_rear", 640),
    ):
        p = renders / f"{name}.png"
        if p.exists():
            im = _trim(Image.open(p).convert("RGBA"))
            im.thumbnail((w, w))
            im.save(OUT / f"{name}.webp", quality=84, method=6)
    frames = sorted((renders / "sunday").glob("f*.png"))
    if frames:
        sun = json.loads((renders / "sunday" / "sun.json").read_text())
        out = []
        for p, (hh, el, az) in zip(frames, sun, strict=True):
            bg = Image.new("RGB", Image.open(p).size, (17, 22, 28))
            im = Image.open(p).convert("RGBA")
            bg.paste(im, mask=im.getchannel("A"))
            d = ImageDraw.Draw(bg)
            d.rounded_rectangle((14, 14, 250, 84), 10, fill=(17, 22, 28))
            d.text((26, 20), f"{hh} MST", font=font(28, True), fill=(245, 166, 35))
            d.text(
                (26, 56),
                f"21 June  sun {el:4.1f}° up, az {az:5.1f}°",
                font=font(14),
                fill=(217, 226, 236),
            )
            out.append(bg)
        out[0].save(
            OUT / "sun_day.webp",
            save_all=True,
            append_images=out[1:],
            duration=[700] * (len(out) - 1) + [1600],
            loop=0,
            quality=72,
            method=6,
        )
    if unity:
        for src, dst in (
            (
                "R-DENSE_rev_16200_high_2023-06-21_20230621T190229Z_043433.png",
                "unity_google_tiles.jpg",
            ),
            ("R-DENSE_rev_16200_high_2023-06-21_20230621T190550Z_015313.png", "unity_topdown.jpg"),
        ):
            hits = list(unity.rglob(src))
            if hits:
                im = Image.open(hits[0]).convert("RGB")
                im.thumbnail((1280, 1280))
                im.save(OUT / dst, quality=82, optimize=True, progressive=True)


def social_preview():
    """1280x640 card for the repository's social preview (Settings > General)."""
    W, H = 1280, 640
    card = Image.new("RGB", (W, H), (17, 22, 28))
    for name, box in (
        ("L1_points_height.webp", (0, 0, 640, 360)),
        ("L4_mesh_trees.webp", (640, 0, 1280, 360)),
    ):
        p = OUT / name
        if p.exists():
            im = Image.open(p).convert("RGBA")
            im = im.resize((box[2] - box[0], int(im.height * (box[2] - box[0]) / im.width)))
            card.paste(im, (box[0], box[1] + (360 - im.height) // 2), im)
    d = ImageDraw.Draw(card)
    d.text((60, 400), "SOLARIS-Twin", font=font(64, True), fill=(245, 166, 35))
    d.text(
        (60, 482),
        "Shading-aware assessment of vehicle-integrated photovoltaics",
        font=font(30),
        fill=(217, 226, 236),
    )
    d.text(
        (60, 530),
        "lidar city twin of Phoenix  ·  facet-level PV  ·  traffic, parking, a full year",
        font=font(22),
        fill=(150, 160, 172),
    )
    card.save(OUT / "social_preview.png", optimize=True)


def readme():
    """README.md from README.template.md with the GeoJSON map and the vehicle STL inlined."""
    t = (OUT / "README.template.md").read_text(encoding="utf-8")
    t = t.replace("{{GEOJSON}}", (OUT / "routes.geojson").read_text(encoding="utf-8").strip())
    t = t.replace("{{VEHICLE}}", (OUT / "solaris_p0_skin.stl").read_text(encoding="utf-8").strip())
    (ROOT / "README.md").write_bytes(t.encode("utf-8"))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--renders", type=Path, help="folder with the Blender renders")
    ap.add_argument("--unity", type=Path, help="folder with Unity photo-mode captures")
    ap.add_argument("--only", nargs="*", help="run only these steps")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    steps = {
        "routes": routes_geojson,
        "canyon": canyon_stl,
        "skin": vehicle_skin_stl,
        "weather": weather,
        "network": network_map,
        "traffic": traffic,
        "paper": paper_figures,
    }
    if a.renders:
        steps["compose"] = lambda: compose(a.renders, a.unity)
    steps["social"] = social_preview
    steps["readme"] = readme
    for k, fn in steps.items():
        if not a.only or k in a.only:
            print("-", k)
            fn()


if __name__ == "__main__":
    main()
