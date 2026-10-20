"""Prove that visual-only work changed no computed result (P8-visual freeze, rule 4).

Checks, in order; exits 1 on the first failure:
  1. frozen paths are clean in git (no edits to sources, configs, results, exchange, models)
  2. pytest -q passes
  3. snakemake -n schedules nothing but the pending Mapillary jobs
  4. TwinBatch re-run on the reference trip gives a byte-identical visibility file

Run from the repo with the solaris env (Library\\bin on PATH) and the Unity editor closed:
    python twin/visual/verify_frozen.py
"""

import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
UNITY = os.environ.get(
    "UNITY_EDITOR", r"C:\Program Files\Unity\Hub\Editor\6000.3.6f1\Editor\Unity.exe"
)
TRIP = "R-DENSE_fwd_1800_medium_2023-12-21"
REF = REPO / "data" / "derived" / "e8" / "unity" / f"visibility_{TRIP}.csv.gz"
CHECK = REPO / "data" / "derived" / "e8" / "check"
EX = REPO / "twin" / "exchange"
# Snakefile: clean in git, or exactly the author-approved edit of 2026-10-20 (e8_unity depends
# only on the five result-producing C# files).
SNAKEFILE_APPROVED = "1cfcdec75333d4488e850ba10de66f1306a94e58b29423732ba1a0417a5e52d0"
FROZEN = [
    "src",
    "configs",
    "results",
    "routes",
    "twin/blender",
    "PAPER_CHANGELOG.md",
    "twin/exchange/facet_samples.csv",
    "twin/exchange/ground_control.csv",
    "twin/exchange/enu_origin.json",
    "twin/unity/SOLARIS-Twin/Assets/SolarisTwin/Editor/TwinBatch.cs",
    "twin/unity/SOLARIS-Twin/Assets/SolarisTwin/Runtime/VisibilityProbe.cs",
    "twin/unity/SOLARIS-Twin/Assets/SolarisTwin/Runtime/GroundControlCheck.cs",
    "twin/unity/SOLARIS-Twin/Assets/SolarisTwin/Runtime/TwinIO.cs",
]
ALLOWED_JOBS = {"e8_mapillary_fetch", "e8_mapillary_svf", "all"}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(cmd, **kw):
    return subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, **kw)


def step(n, name, ok, detail=""):
    print(f"[{n}] {name}: {'PASS' if ok else 'FAIL'} {detail}".rstrip(), flush=True)
    if not ok:
        sys.exit(1)


def main():
    r = run(["git", "status", "--porcelain", "--", *FROZEN])
    step(1, "frozen paths clean in git", r.stdout.strip() == "", r.stdout.strip())
    snake_clean = run(["git", "status", "--porcelain", "--", "Snakefile"]).stdout.strip() == ""
    step(
        1,
        "Snakefile clean or the approved edit",
        snake_clean or sha(REPO / "Snakefile") == SNAKEFILE_APPROVED,
    )

    r = run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"])
    tail = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-300:]
    step(2, "pytest -q", r.returncode == 0, tail)

    snake = Path(sys.executable).parent / "Scripts" / "snakemake.exe"
    r = run([str(snake) if snake.exists() else "snakemake", "-n"])
    jobs = set(re.findall(r"^(\w+)\s+\d+\s*$", r.stdout, re.M)) - {"total", "job"}
    step(3, "snakemake -n", r.returncode == 0 and jobs <= ALLOWED_JOBS, f"jobs: {sorted(jobs)}")

    busy = run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-CimInstance Win32_Process -Filter \"Name='Unity.exe'\" | "
            "ForEach-Object { $_.CommandLine }",
        ]
    ).stdout
    free = "SOLARIS-Twin" not in busy
    step(
        4,
        "no other Unity has the project open",
        free,
        "" if free else "close the Unity editor (or wait for the running batch) and re-run",
    )
    CHECK.mkdir(parents=True, exist_ok=True)
    out = CHECK / f"visibility_{TRIP}.csv.gz"
    if out.exists():
        out.unlink()
    log = REPO / "data" / "derived" / "logs" / "verify_frozen_unity.log"
    r = subprocess.run(
        [
            UNITY,
            "-batchmode",
            "-nographics",
            "-projectPath",
            str(REPO / "twin" / "unity" / "SOLARIS-Twin"),
            "-executeMethod",
            "SolarisTwin.Editor.TwinBatch.Run",
            "-trajectory",
            str(EX / "trajectories" / f"trajectory_{TRIP}.csv"),
            "-out",
            str(out),
            "-samples",
            str(EX / "facet_samples.csv"),
            "-gcp",
            str(EX / "ground_control.csv"),
            "-logFile",
            str(log),
        ]
    )
    same = r.returncode == 0 and out.exists() and sha(out) == sha(REF)
    step(
        4,
        "TwinBatch byte-identical",
        same,
        f"{sha(out)[:16] if out.exists() else 'missing'} vs {sha(REF)[:16]} (exit {r.returncode})",
    )
    print("ALL FROZEN RESULTS UNCHANGED")


if __name__ == "__main__":
    main()
