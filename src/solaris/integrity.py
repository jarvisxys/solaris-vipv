"""Byte-identity check for the frozen conference code in src/solaris/legacy/.

Used by tests/test_legacy.py, the Snakemake rule ``legacy_sha256`` and the
pre-commit hook of the same name. Run directly: ``python src/solaris/integrity.py``.
"""

import hashlib
import sys
from pathlib import Path

LEGACY_DIR = Path(__file__).resolve().parent / "legacy"
SUMS_FILE = LEGACY_DIR / "SHA256SUMS"


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def recorded_hashes() -> dict[str, str]:
    """Return {filename: sha256} as recorded in SHA256SUMS (sha256sum format)."""
    out = {}
    for line in SUMS_FILE.read_text(encoding="ascii").splitlines():
        if line.strip():
            digest, name = line.split(maxsplit=1)
            out[name.lstrip("*")] = digest
    return out


def verify_legacy() -> list[str]:
    """Return an empty list if every legacy file matches its recorded hash."""
    errors = []
    for name, digest in recorded_hashes().items():
        actual = sha256(LEGACY_DIR / name)
        if actual != digest:
            errors.append(f"{name}: recorded {digest}, found {actual}")
    return errors


if __name__ == "__main__":
    problems = verify_legacy()
    for p in problems:
        print(f"LEGACY CODE CHANGED -- {p}", file=sys.stderr)
    sys.exit(1 if problems else 0)
