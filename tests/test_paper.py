"""P9: paper macros come from results/ only, and main.tex uses no undefined result macro."""

import re
from pathlib import Path

import pytest

from solaris import paper

PAPER = Path(__file__).resolve().parents[1] / "paper"
PREFIXES = (
    "Bz", "Gap", "Wx", "Geo", "Fresh", "Route", "Site", "Facet", "Psix",
    "Eone", "Etwo", "Ethree", "Efour", "Efive", "Esix", "Eseven", "Eeight",
)  # fmt: skip


def test_names_are_letters_only():
    assert paper.name("Efive", "A1", "B0") == "EfiveAOneBZero"
    assert paper.name("Eseven", "A2", "Full Skin", "F_geo") == "EsevenATwoFullSkinFgeo"
    with pytest.raises(ValueError):
        paper.name("-", "_")


def test_number_formats():
    assert paper.f(0.8319964, 3) == "0.832"
    assert paper.f(-0.0302, 3) == "\\textminus{}0.030"
    assert paper.pct(0.99141, 1) == "99.1"
    assert paper.thousands(5541.4) == "5{,}541"
    assert paper.sci(1.09e-14) == "\\ensuremath{1\\times10^{-14}}"


def test_macros_reject_duplicates_and_bad_names():
    m = paper.Macros()
    m["Abc"] = 1
    with pytest.raises(KeyError):
        m["Abc"] = 2
    with pytest.raises(ValueError):
        m["A1"] = 3
    assert m.tex().endswith("\\newcommand{\\Abc}{1}\n")


def test_main_tex_uses_only_generated_result_macros():
    macros = PAPER / "generated" / "macros.tex"
    if not macros.exists():
        pytest.skip("paper/generated/macros.tex not built (snakemake -c1 paper_macros)")
    defined = set(re.findall(r"\\newcommand\{\\([A-Za-z]+)\}", macros.read_text(encoding="utf-8")))
    used = set(re.findall(r"\\([A-Za-z]+)", (PAPER / "main.tex").read_text(encoding="utf-8")))
    used = {u for u in used if u.startswith(PREFIXES)}
    assert used, "main.tex uses no result macros"
    assert used <= defined, sorted(used - defined)


def test_main_tex_has_no_unresolved_placeholders_in_results():
    text = (PAPER / "main.tex").read_text(encoding="utf-8")
    assert "??" not in text
