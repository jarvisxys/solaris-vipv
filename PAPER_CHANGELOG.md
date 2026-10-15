# Paper changelog

Every decision that changes a number, claim or reference in the journal paper,
newest first, with date and reason.

## 2026-10-15 · P0 bootstrap

- **Conference code frozen.** The conference `solaris.py` was copied byte-identical to
  `src/solaris/legacy/solaris_v1.py`: 28,334 bytes, LF line endings, no BOM,
  SHA-256 `7b30b213d8d89addfe7edcc6a1621caf94505f28ecbdd4eb26badc39152a96d5`.
  Reason: it is the E0 regression baseline. The hash is guarded by
  `tests/test_legacy.py`, the Snakemake rule `legacy_sha256` and a pre-commit hook.
- **Code-availability URL.** The conference paper (Code Availability, ref. [1]) cites
  `github.com/anandsagar-g/solaris-vipv`, which does not exist. The journal version cites
  `github.com/jarvisxys/solaris-vipv`. The legacy module's docstring still carries the old
  URL and stays unchanged under the byte-identity rule. Reason: the placeholder never resolved.
- **Conference parameters recorded.** `configs/base.yaml` holds the constants and defaults of
  `solaris_v1.py`; `tests/test_legacy.py` asserts that each introspectable value equals the
  module. Frozen from this date. Reason: the refactored core (P1) reads parameters from config.
