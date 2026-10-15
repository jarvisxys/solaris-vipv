"""Shared fixtures: conference values computed once per session by each engine."""

import pytest

from solaris import core
from solaris.core.conference import conference_values
from solaris.legacy import solaris_v1


@pytest.fixture(scope="session")
def values_legacy():
    return conference_values(solaris_v1)


@pytest.fixture(scope="session")
def values_core():
    return conference_values(core)
