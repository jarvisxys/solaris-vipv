"""Site definition (configs/site/phoenix.yaml) shared by the weather and geometry packages."""

from pathlib import Path

import yaml

from solaris.core.params import REPO_ROOT

SITE_YAML = REPO_ROOT / "configs" / "site" / "phoenix.yaml"


def site_config(path=SITE_YAML) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))
