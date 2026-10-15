# SOLARIS-Twin pipeline DAG: data -> geometry -> experiments -> figures.
#   dry run:     snakemake -n
#   full build:  snakemake -c8 all
# Rules are added phase by phase (workflow guide, Sec. 7). Every number that
# reaches paper/ must come from a rule in this file.

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(workflow.basedir) / "src"))

LEGACY = "src/solaris/legacy/solaris_v1.py"
LEGACY_SUMS = "src/solaris/legacy/SHA256SUMS"
CORE_SRC = sorted(str(f) for f in Path("src/solaris/core").glob("*.py"))
E0_CFG = "configs/experiments/e0.yaml"
E0 = yaml.safe_load(Path(E0_CFG).read_text(encoding="utf-8"))


def experiment(name):
    """Load experiments/<name>/run.py in-process. Rules use run: rather than script:
    because Snakemake's script: launches python through cmd without quoting its path,
    which breaks under a user profile containing a space."""
    import importlib.util

    path = Path(workflow.basedir) / "experiments" / name / "run.py"
    spec = importlib.util.spec_from_file_location(f"experiments.{name}.run", path)
    run_py = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run_py)
    return run_py


rule all:
    input:
        "results/p0/legacy_sha256.ok",
        E0["b0"]["out_table"],
        E0["b0"]["out_pareto"],


# ---------------------------------------------------------------- P0 bootstrap
rule legacy_sha256:
    """Stop the whole DAG if the conference code is no longer byte-identical."""
    input:
        LEGACY,
        LEGACY_SUMS,
    output:
        "results/p0/legacy_sha256.ok",
    run:
        from solaris.integrity import recorded_hashes, verify_legacy

        problems = verify_legacy()
        if problems:
            raise ValueError("legacy code changed:\n" + "\n".join(problems))
        Path(output[0]).write_text(
            "".join(f"{h}  {n}\n" for n, h in recorded_hashes().items()), encoding="ascii"
        )


# ---------------------------------------------------------------- P1 / E0
rule e0_measured:
    """Table B0: conference metrics on the measured NSRDB TMY (Phoenix), next to the
    reproduced synthetic values and the numbers printed in the conference paper."""
    input:
        tmy=E0["inputs"]["tmy_phoenix"]["path"],
        base="configs/base.yaml",
        e0=E0_CFG,
        legacy_ok="results/p0/legacy_sha256.ok",
        code=CORE_SRC,
    output:
        table=E0["b0"]["out_table"],
        pareto=E0["b0"]["out_pareto"],
    run:
        experiment("e0_reproduce").main(input.tmy, output.table, output.pareto)


# ---------------------------------------------------------------- planned rules
# P2      weather_tmy, weather_conus_5min   -> data/raw/nsrdb/
# P3       geom_aoi ... geom_freshness       -> data/derived/{dsm,cdsm,dem}.tif, tiles/*.glb
# P4  E1   e1_verification                   -> results/e1/
# P5  E2   e2_facets                         -> results/e2/
# P6  E3/4 routes_select, sumo_traces, e3_driving, e4_parking
# P7  E5/6 e5_annual, e6_mismatch            -> waterfall figure
# P8  E8   e8_twin_agreement, e8_mapillary_svf
# P9  E7   e7_inversion, figures, paper
