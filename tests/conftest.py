"""Shared fixtures: conference values computed once per session by each engine."""

import pytest

from solaris import core
from solaris.core.conference import conference_values, legacy_module


@pytest.fixture(scope="session")
def legacy():
    """Frozen conference toolkit v1.1.0, its data paths pointed at data/conference/."""
    return legacy_module()


@pytest.fixture(scope="session")
def values_legacy(legacy):
    return conference_values(legacy)


@pytest.fixture(scope="session")
def values_core():
    return conference_values(core)
