"""Daily archetypes A1-A4 for E5 (configs/schedules/archetypes.yaml).

A day is the same every day of the year: trips in the listed hours, parking elsewhere. Each
trip hour drives N = drive_fraction(km, city) x 3600 s from the start of the hour, the time
split the conference SoC loop uses for demand, so driving and parked seconds close to 3600
in every hour. The N seconds go to the trip's routes in order, N/k each; a route replays
its frozen SUMO trace from the start, first direction then the other, looping.
"""

from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from solaris.core.conference import SCENARIOS
from solaris.core.params import BASE, REPO_ROOT, Params
from solaris.core.soc_loop import drive_fraction

SCHED_YAML = REPO_ROOT / "configs" / "schedules" / "archetypes.yaml"
SIM_START_MIN = 7 * 60 + 30  # SUMO traces: seconds after 07:30 (configs/site/phoenix.yaml)
OTHER = {"fwd": "rev", "rev": "fwd"}


@lru_cache(maxsize=2)
def _load(path):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def schedules_config(path=SCHED_YAML) -> dict:
    return _load(str(path))


def _arch(name):
    return schedules_config()["archetypes"][name]


@dataclass(frozen=True)
class Segment:
    """One stretch of driving: ``route`` replayed from its ``departure`` traces, starting in
    direction ``first``, on the clock from ``start_s`` (seconds of the day) for ``duration_s``."""

    route: str
    first: str
    departure: str
    start_s: int
    duration_s: int


def trace_id(route, direction, departure, demand):
    h, m = map(int, departure.split(":"))
    return f"{route}_{direction}_{(h * 60 + m - SIM_START_MIN) * 60}_{demand}"


def scenario(arch):
    """(daily km, city cycle) of the archetype's B0 scenario."""
    return SCENARIOS[_arch(arch)["scenario"]]


def archetype_params(arch, p: Params = BASE) -> Params:
    """Conference parameters with the archetype's trip hours (demand and aux load)."""
    return replace(p, drive_hours=tuple(t["hour"] for t in _arch(arch)["trips"]))


def drive_seconds(arch) -> int:
    """Driving seconds in each trip hour."""
    km, city = scenario(arch)
    return int(round(drive_fraction(km, city, archetype_params(arch)) * 3600))


def departure_for(hour):
    cfg = schedules_config()
    dep = cfg["trace_for_hour"].get(hour, f"{hour:02d}:00")
    if dep not in cfg["trace_departures"]:
        raise ValueError(f"no SUMO departure for trip hour {hour}")
    return dep


def segments(arch) -> list[Segment]:
    n = drive_seconds(arch)
    out = []
    for t in _arch(arch)["trips"]:
        start = t["hour"] * 3600
        for route, idx in zip(
            t["routes"], np.array_split(np.arange(n), len(t["routes"])), strict=True
        ):
            out.append(Segment(route, t["first"], departure_for(t["hour"]), start, len(idx)))
            start += len(idx)
    return out


def replay(seg: Segment, load) -> pd.DataFrame:
    """Per-second rows of a segment. ``load(direction)`` returns that direction's trace
    (1 Hz, sorted); traces alternate from ``seg.first`` until ``duration_s`` rows exist."""
    parts, have, d = [], 0, seg.first
    while have < seg.duration_s:
        f = load(d)
        if len(f) == 0:
            raise ValueError(f"empty trace {seg.route} {d}")
        parts.append(f)
        have += len(f)
        d = OTHER[d]
    out = pd.concat(parts, ignore_index=True).iloc[: seg.duration_s].copy()
    out["clock_s"] = seg.start_s + np.arange(seg.duration_s)
    return out


def site_at(arch, hour, weekend):
    rule = _arch(arch)["parking"]["weekend" if weekend else "weekday"]
    for r in rule.get("ranges", []):
        if r["hours"][0] <= hour <= r["hours"][1]:
            return r["site"]
    return rule["default"]


def drive_mask_seconds(arch) -> np.ndarray:
    """True for every driving second of the day (86400)."""
    m = np.zeros(86400, bool)
    for s in segments(arch):
        m[s.start_s : s.start_s + s.duration_s] = True
    return m


def day_steps(arch, weekend, step_min=5) -> pd.DataFrame:
    """Parking steps of one day: start (s of day), site, parked fraction of the step."""
    step = step_min * 60
    drive = drive_mask_seconds(arch).reshape(-1, step).sum(axis=1)
    start = np.arange(0, 86400, step)
    return pd.DataFrame(
        {
            "start_s": start,
            "site": [site_at(arch, int(s // 3600), weekend) for s in start],
            "parked_frac": 1.0 - drive / step,
        }
    )


def sites_used(arch):
    return sorted({site_at(arch, h, w) for h in range(24) for w in (False, True)})
