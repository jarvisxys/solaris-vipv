# SOLARIS-Twin rules for Claude Code
- Never modify src/solaris/legacy/ or configs/base.yaml. They define the conference baseline.
- Every number that reaches paper/ comes from a Snakemake rule. No hand-typed results.
- Units SI. Time zone America/Phoenix (no DST). CRS EPSG:26912 + ENU origin in configs/site/phoenix.yaml.
- Sun position comes only from pvlib (SPA). Unity receives sun vectors from Python; it never computes them.
- Unity never computes energy. It exports visibility only.
- Fixed seeds. Results must be bit-reproducible on rerun.
- Before finishing any task: run `pytest -q` and `snakemake -n`; both must pass.
- Log every paper-affecting decision in PAPER_CHANGELOG.md with date and reason.
- Tests use small fixtures in tests/fixtures/, never network downloads.
- SOLWEIG/UMEP are GPL-3: call them as external tools; never copy their code here.

## Working conventions
- Platform: Windows 11 native (conda env `solaris` from environment.yml; no WSL).
  Snakemake rules use `run:` or `script:`, not `shell:`; build paths with pathlib.
- One phase (P0-P9) per session; start in plan mode; write tests before implementation.
- Commit after every passing task with the phase and experiment ID in the subject,
  e.g. `P1/E0: regression tests for Tables II-IV`. Remote: github.com/jarvisxys/solaris-vipv.
- Gates: no E2 work until Table B0 is frozen; no annual runs until E1 passes;
  no results writing until E8 is done.
- Legacy integrity: `python src/solaris/integrity.py` (also a Snakemake rule and a pre-commit hook).
  Conference solaris.py SHA-256: 7b30b213d8d89addfe7edcc6a1621caf94505f28ecbdd4eb26badc39152a96d5.
- Every baseline number comes from the measured NSRDB TMY run; synthetic-climate values
  appear only as a labelled historical row.
