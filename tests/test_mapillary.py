"""P8 / E8: Mapillary sky masks and sky view factor (hand-built tiles, no network)."""

import base64
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from solaris.imagery import mapillary as mp

RESULTS = Path(__file__).resolve().parents[1] / "results" / "e8"


def _varint(v):
    out = bytearray()
    while True:
        b = v & 0x7F
        v >>= 7
        if v:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def _field(num, payload):
    return _varint((num << 3) | 2) + _varint(len(payload)) + payload


def _zz(n):
    return (n << 1) ^ (n >> 31)


def _tile(rings, extent=4096):
    """Mapbox Vector Tile with one layer and one polygon feature made of ``rings``."""
    move_to, line_to, close = 1 | (1 << 3), 2, 7 | (1 << 3)
    cmds, px, py = [], 0, 0  # the cursor carries over between rings (MVT deltas)
    for ring in rings:
        cmds += [move_to, _zz(ring[0][0] - px), _zz(ring[0][1] - py)]
        px, py = ring[0]
        cmds.append(line_to | ((len(ring) - 1) << 3))
        for x, y in ring[1:]:
            cmds += [_zz(x - px), _zz(y - py)]
            px, py = x, y
        cmds.append(close)
    geom = b"".join(_varint(c) for c in cmds)
    feature = _field(4, geom) + _varint((3 << 3) | 0) + _varint(3)
    layer = _field(1, b"mpy-or") + _field(2, feature) + _varint((5 << 3) | 0) + _varint(extent)
    return base64.b64encode(_field(3, layer)).decode()


def test_decoder_reads_a_polygon_with_a_hole():
    outer = [(0, 0), (4096, 0), (4096, 2048), (0, 2048)]
    hole = [(1000, 500), (1000, 1000), (2000, 1000), (2000, 500)]
    extent, rings = mp.decode_polygons(_tile([outer, hole]))
    assert extent == 4096 and rings == [outer, hole]
    assert mp.ring_area(outer) > 0 > mp.ring_area(hole)


def test_open_sky_gives_svf_one_and_hole_reduces_it():
    outer = [(0, 0), (4096, 0), (4096, 2048), (0, 2048)]
    m = mp.sky_mask([{"value": mp.SKY, "geometry": _tile([outer])}], 720, 360)
    assert m[:180].all() and not m[180:].any()
    assert mp.svf_equirect(m) == pytest.approx(1.0, abs=2e-3)
    hole = [(1000, 500), (1000, 1000), (2000, 1000), (2000, 500)]
    m2 = mp.sky_mask([{"value": mp.SKY, "geometry": _tile([outer, hole])}], 720, 360)
    assert mp.svf_equirect(m2) < mp.svf_equirect(m)
    other = mp.sky_mask([{"value": "nature--vegetation", "geometry": _tile([outer])}], 720, 360)
    assert not other.any()


@pytest.mark.parametrize("h", [10.0, 30.0, 60.0])
def test_uniform_horizon_matches_the_engine_definition(h):
    H = 1800
    el = 90 - 180 * (np.arange(H) + 0.5) / H
    mask = np.repeat((el > h)[:, None], 8, axis=1)
    assert mp.svf_equirect(mask) == pytest.approx(1 - np.sin(np.radians(h)) ** 2, abs=2e-3)


def test_pick_spread_is_newest_first_and_spaced():
    c = pd.DataFrame(
        {
            "id": ["a", "b", "c", "d"],
            "x": [0.0, 50, 300, 600],
            "y": 0.0,
            "captured_at": [4, 5, 1, 2],
        }
    )
    p = mp.pick_spread(c, 3, 250)
    assert p["id"].tolist() == ["b", "d", "c"]


def test_token_message(monkeypatch):
    monkeypatch.setattr(mp, "_user_env", lambda name: None)
    with pytest.raises(RuntimeError, match="MAPILLARY_TOKEN"):
        mp.token()


def test_e8_svf_reported():
    p = RESULTS / "summary_e8_svf.json"
    if not p.exists():
        pytest.skip("results/e8/summary_e8_svf.json not built (needs MAPILLARY_TOKEN)")
    s = json.loads(p.read_text())
    assert s["points"] > 0 and {"mae", "rmse", "r2"} <= set(s["buildings_trees"])
