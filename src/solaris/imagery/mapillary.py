"""Mapillary panoramas and fisheye-equivalent sky view factor (workflow guide E8).

Mapillary imagery is openly licensed (CC BY-SA); Google Street View is excluded by its terms.
Access needs a free client token in MAPILLARY_TOKEN (user environment, like NREL_API_KEY).

Sky pixels come from Mapillary's own semantic segmentation (Graph API v4 /detections,
class ``nature--sky``), delivered as polygons in a base64 Mapbox Vector Tile (extent 4096)
in normalised image coordinates. For an equirectangular panorama with a level camera, row
r is elevation el = 90 - 180 (r + 0.5) / H degrees and the column is azimuth, so the
horizontal-surface sky view factor needs no heading:

    SVF = 2 * integral_0^90 f(el) sin(el) cos(el) d(el),   f = sky share of the row,

the same cosine-weighted definition as the engine's 1 - mean(sin^2 h) for a horizon h.
"""

import base64
import json
import time
from pathlib import Path

import numpy as np

from solaris.core.params import REPO_ROOT
from solaris.weather.nsrdb import _user_env

API = "https://graph.mapillary.com"
RAW = REPO_ROOT / "data" / "raw" / "mapillary"
SKY = "nature--sky"
IMAGE_FIELDS = (
    "id,captured_at,is_pano,camera_type,width,height,compass_angle,computed_compass_angle,"
    "geometry,computed_geometry,sequence"
)


def token():
    t = _user_env("MAPILLARY_TOKEN")
    if not t:
        raise RuntimeError(
            "MAPILLARY_TOKEN is not set. Create a free client token at "
            "https://www.mapillary.com/dashboard/developers (Register application) and store "
            'it with [Environment]::SetEnvironmentVariable("MAPILLARY_TOKEN", "MLY|...", "User")'
        )
    return t


def _get(url, params, cache, retries=4):
    """GET JSON with an on-disk cache (the token is never written to disk)."""
    import requests

    cache = Path(cache)
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    for k in range(retries):
        r = requests.get(url, params={**params, "access_token": token()}, timeout=60)
        if r.status_code == 200:
            data = r.json()
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(data), encoding="utf-8")
            return data
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(5 * 2**k)
            continue
        raise RuntimeError(f"Mapillary {r.status_code}: {r.text[:300]}")
    raise RuntimeError(f"Mapillary: gave up on {url}")


def images_in_bbox(lon0, lat0, lon1, lat1, root=RAW):
    """Panoramas in a small lon/lat box (keep boxes well under 0.01 deg^2)."""
    key = f"images_{lon0:.5f}_{lat0:.5f}_{lon1:.5f}_{lat1:.5f}.json"
    d = _get(
        f"{API}/images",
        {
            "fields": IMAGE_FIELDS,
            "bbox": f"{lon0},{lat0},{lon1},{lat1}",
            "is_pano": "true",
            "limit": 2000,
        },
        Path(root) / "search" / key,
    )
    return d.get("data", [])


def detections(image_id, root=RAW):
    d = _get(
        f"{API}/{image_id}/detections",
        {"fields": "value,geometry"},
        Path(root) / "detections" / f"{image_id}.json",
    )
    return d.get("data", [])


# ---------------------------------------------------------------- vector tile decoding
def _varint(buf, i):
    shift = result = 0
    while True:
        b = buf[i]
        i += 1
        result |= (b & 0x7F) << shift
        if not b & 0x80:
            return result, i
        shift += 7


def _fields(buf):
    """Protobuf wire fields: (field number, wire type, value) with value bytes for type 2."""
    i = 0
    while i < len(buf):
        key, i = _varint(buf, i)
        num, wt = key >> 3, key & 7
        if wt == 0:
            v, i = _varint(buf, i)
        elif wt == 2:
            n, i = _varint(buf, i)
            v, i = buf[i : i + n], i + n
        elif wt == 5:
            v, i = buf[i : i + 4], i + 4
        elif wt == 1:
            v, i = buf[i : i + 8], i + 8
        else:
            raise ValueError(f"unsupported protobuf wire type {wt}")
        yield num, wt, v


def _packed(buf):
    out, i = [], 0
    while i < len(buf):
        v, i = _varint(buf, i)
        out.append(v)
    return out


def _zigzag(n):
    return (n >> 1) ^ -(n & 1)


def _rings(cmds):
    """MVT geometry commands -> list of rings (lists of (x, y) in tile units)."""
    rings, ring, x, y, i = [], [], 0, 0, 0
    while i < len(cmds):
        cid, count = cmds[i] & 7, cmds[i] >> 3
        i += 1
        if cid == 7:  # ClosePath
            if ring:
                rings.append(ring)
            ring = []
            continue
        for _ in range(count):
            x += _zigzag(cmds[i])
            y += _zigzag(cmds[i + 1])
            i += 2
            if cid == 1 and ring:  # MoveTo starts a new ring
                rings.append(ring)
                ring = []
            ring.append((x, y))
    if ring:
        rings.append(ring)
    return rings


def decode_polygons(b64):
    """Base64 Mapbox Vector Tile -> (extent, [rings]) over all features of all layers."""
    raw = base64.b64decode(b64)
    rings, extent = [], 4096
    for num, _, layer in _fields(raw):
        if num != 3:
            continue
        for lnum, _, v in _fields(layer):
            if lnum == 5:
                extent = v
            elif lnum == 2:
                for fnum, _, fv in _fields(v):
                    if fnum == 4:
                        rings += _rings(_packed(fv))
    return extent, rings


def ring_area(ring):
    """Signed area (MVT convention: exterior rings positive in y-down tile coordinates)."""
    a = np.asarray(ring, float)
    x, y = a[:, 0], a[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))


def sky_mask(detection_list, width=1024, height=512):
    """Boolean (height, width) sky mask from Mapillary detections of one panorama."""
    from PIL import Image, ImageDraw

    img = Image.new("1", (width, height), 0)
    draw = ImageDraw.Draw(img)
    for d in detection_list:
        if d.get("value") != SKY or not d.get("geometry"):
            continue
        extent, rings = decode_polygons(d["geometry"])
        for ring in rings:
            if len(ring) < 3:
                continue
            # tile units -> pixel-centre coordinates (pixel i spans [i - 0.5, i + 0.5))
            pts = [(x / extent * width - 0.5, y / extent * height - 0.5) for x, y in ring]
            draw.polygon(pts, fill=1 if ring_area(ring) > 0 else 0)
    return np.array(img, bool)


def svf_equirect(mask):
    """Horizontal-surface sky view factor of an equirectangular sky mask (level camera)."""
    h = mask.shape[0]
    el = np.radians(90.0 - 180.0 * (np.arange(h) + 0.5) / h)
    up = el > 0
    f = mask[up].mean(axis=1)
    d_el = np.radians(180.0 / h)
    return float(np.sum(2.0 * f * np.sin(el[up]) * np.cos(el[up]) * d_el))


# ---------------------------------------------------------------- point selection
def pick_spread(cands, n, min_sep_m):
    """Newest-first greedy pick of ``n`` candidates at least ``min_sep_m`` apart.
    ``cands``: DataFrame with x, y, captured_at."""
    order = cands.sort_values(["captured_at", "id"], ascending=[False, True])
    chosen = []
    for r in order.itertuples():
        if all(np.hypot(r.x - c.x, r.y - c.y) >= min_sep_m for c in chosen):
            chosen.append(r)
        if len(chosen) == n:
            break
    return order.loc[[c.Index for c in chosen]]
