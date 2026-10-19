"""The Blender-built SOLARIS body (twin/blender/build_solaris_p0.py) carries the PV facets of
configs/vehicle/solaris_p0.yaml exactly. It is visual only, but it must never drift from the
facets the results use."""

import ast
from pathlib import Path

import pytest

from solaris.vehicle import facets, vehicle_config

SCRIPT = Path(__file__).resolve().parents[1] / "twin" / "blender" / "build_solaris_p0.py"


def blender_facets():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            getattr(t, "id", None) == "FACETS" for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError("FACETS not found in build_solaris_p0.py")


def test_blender_model_facets_equal_the_yaml():
    model = {f[0]: f[1:] for f in blender_facets()}
    yaml_facets = facets(vehicle_config())
    assert set(model) == {f.id for f in yaml_facets}
    for f in yaml_facets:
        area, tilt, az, centre, across, slope = model[f.id]
        assert area == pytest.approx(f.area_m2)
        assert tilt == pytest.approx(f.tilt_deg) and az == pytest.approx(f.azimuth_body_deg)
        assert centre == pytest.approx(f.centre_m)
        assert across == pytest.approx(f.across_m) and slope == pytest.approx(f.slope_m)
