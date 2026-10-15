# SOLARIS-Twin pipeline DAG: data -> geometry -> experiments -> figures.
#   dry run:     snakemake -n
#   full build:  snakemake -c8 all
# Rules are added phase by phase (workflow guide, Sec. 7). Every number that
# reaches paper/ must come from a rule in this file.

import sys
from pathlib import Path

sys.path.insert(0, str(Path(workflow.basedir) / "src"))

LEGACY = "src/solaris/legacy/solaris_v1.py"
LEGACY_SUMS = "src/solaris/legacy/SHA256SUMS"


rule all:
    input:
        "results/p0/legacy_sha256.ok",


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


# ---------------------------------------------------------------- planned rules
# P1  E0   e0_regression, e0_measured        -> results/e0/table_b0.csv
# P2       weather_tmy, weather_conus_5min   -> data/raw/nsrdb/
# P3       geom_aoi ... geom_freshness       -> data/derived/{dsm,cdsm,dem}.tif, tiles/*.glb
# P4  E1   e1_verification                   -> results/e1/
# P5  E2   e2_facets                         -> results/e2/
# P6  E3/4 routes_select, sumo_traces, e3_driving, e4_parking
# P7  E5/6 e5_annual, e6_mismatch            -> waterfall figure
# P8  E8   e8_twin_agreement, e8_mapillary_svf
# P9  E7   e7_inversion, figures, paper
