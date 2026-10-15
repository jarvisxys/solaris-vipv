"""P1/E0: every number printed in the conference paper, from the legacy module and the core.

The printed values, their tolerances and climate basis live in configs/experiments/e0.yaml.
"""

import hashlib
from decimal import Decimal

import pytest
import yaml

from solaris.core.conference import E0_YAML, input_path

E0 = yaml.safe_load(E0_YAML.read_text(encoding="utf-8"))
EXPECTED = E0["expected"]
EPS = 1e-12


def tolerance(entry):
    """Explicit tol, else half a unit of the last printed digit."""
    if "tol" in entry:
        return float(entry["tol"])
    exponent = Decimal(str(entry["printed"])).as_tuple().exponent
    return 0.5 * 10.0 ** min(exponent, 0)


def skip_if_missing(entry):
    key = entry.get("requires")
    if key and not input_path(key).exists():
        pytest.skip(f"input '{key}' not supplied ({E0['inputs'][key]['path']})")


def test_expected_ids_are_unique():
    ids = [e["id"] for e in EXPECTED]
    assert len(ids) == len(set(ids))


def test_tolerance_rule():
    assert tolerance({"printed": 0.88}) == pytest.approx(0.005)
    assert tolerance({"printed": 237}) == pytest.approx(0.5)
    assert tolerance({"printed": 9.0}) == pytest.approx(0.05)
    assert tolerance({"printed": 920, "tol": 5}) == 5


@pytest.mark.parametrize("key", sorted(E0["inputs"]))
def test_input_files_match_pinned_hash(key):
    spec = E0["inputs"][key]
    path = input_path(key)
    if not path.exists():
        pytest.skip(f"{spec['path']} not supplied")
    assert spec["sha256"], f"{key} is present but has no sha256 pinned in e0.yaml"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == spec["sha256"]


@pytest.mark.parametrize("engine", ["legacy", "core"])
@pytest.mark.parametrize("entry", EXPECTED, ids=[e["id"] for e in EXPECTED])
def test_printed_value(entry, engine, request):
    skip_if_missing(entry)
    values = request.getfixturevalue(f"values_{engine}")
    assert entry["id"] in values, f"{entry['id']} is not computed by conference_values()"
    got, printed = float(values[entry["id"]]), float(entry["printed"])
    if entry.get("op", "eq") == "lt":
        assert got < printed, f"{entry['where']}: {got} is not < {printed}"
    else:
        tol = tolerance(entry)
        assert abs(got - printed) <= tol + EPS, (
            f"{entry['where']}: computed {got:.6g}, printed {printed} (tol {tol})"
        )
