"""P7 / E5: daily archetypes A1-A4 (configs/schedules/archetypes.yaml)."""

import numpy as np
import pandas as pd
import pytest

from solaris.core.conference import SCENARIOS
from solaris.core.soc_loop import drive_fraction
from solaris.trajectory import schedules as sch

CFG = sch.schedules_config()


def test_four_archetypes_with_the_guide_routes_and_sites():
    assert list(CFG["archetypes"]) == ["A1", "A2", "A3", "A4"]
    routes = {a: {r for t in v["trips"] for r in t["routes"]} for a, v in CFG["archetypes"].items()}
    assert routes["A1"] == {"R-MIXED", "R-OPEN"}
    assert routes["A2"] == routes["A3"] == {"R-DENSE", "R-OPEN"}
    assert routes["A4"] == {"R-OPEN", "R-MIXED", "R-DENSE"}
    day = {a: sch.site_at(a, 12, weekend=False) for a in CFG["archetypes"]}
    assert day == {"A1": "P1", "A2": "P2", "A3": "P5", "A4": "P2"}
    assert sch.site_at("A4", 10, weekend=False) == "P1"


def test_demand_matches_the_b0_scenario():
    for a in ("A1", "A2", "A3"):
        assert sch.scenario(a) == SCENARIOS["II"] == (50, True)
    assert sch.scenario("A4") == SCENARIOS["I"] == (100, False)


@pytest.mark.parametrize("arch", ["A1", "A2", "A3", "A4"])
def test_drive_seconds_follow_the_conference_time_split(arch):
    km, city = sch.scenario(arch)
    p = sch.archetype_params(arch)
    assert p.drive_hours == tuple(t["hour"] for t in CFG["archetypes"][arch]["trips"])
    n = sch.drive_seconds(arch)
    assert n == round(drive_fraction(km, city, p) * 3600)
    segs = sch.segments(arch)
    for t in CFG["archetypes"][arch]["trips"]:
        mine = [s for s in segs if s.start_s // 3600 == t["hour"]]
        assert sum(s.duration_s for s in mine) == n
        assert [s.route for s in mine] == t["routes"]
        # sequential, starting on the hour
        starts = [s.start_s for s in mine]
        assert starts[0] == t["hour"] * 3600
        assert all(b == a + s.duration_s for a, b, s in zip(starts, starts[1:], mine, strict=False))


def test_evening_trip_replays_the_1600_traces_one_hour_later():
    eve = [s for s in sch.segments("A1") if s.start_s // 3600 == 17]
    assert {s.departure for s in eve} == {"16:00"} and eve[0].start_s == 17 * 3600
    assert eve[0].first == "rev"
    morning = [s for s in sch.segments("A1") if s.start_s // 3600 == 8]
    assert {s.departure for s in morning} == {"08:00"}


def test_trace_ids_match_the_p6_naming():
    assert sch.trace_id("R-DENSE", "fwd", "08:00", "medium") == "R-DENSE_fwd_1800_medium"
    assert sch.trace_id("R-OPEN", "rev", "16:00", "medium") == "R-OPEN_rev_30600_medium"


def test_shared_segments_between_commuters():
    a1, a2 = set(sch.segments("A1")), set(sch.segments("A2"))
    assert sch.segments("A2") == sch.segments("A3")
    shared = a1 & a2
    assert {s.route for s in shared} == {"R-OPEN"} and len(shared) == 2


def test_replay_loops_the_two_directions():
    fwd = pd.DataFrame({"x_utm": [0.0, 1, 2], "speed": 1.0})
    rev = pd.DataFrame({"x_utm": [2.0, 1], "speed": 2.0})
    seg = sch.Segment("R", "fwd", "08:00", 8 * 3600, 7)
    out = sch.replay(seg, lambda d: fwd if d == "fwd" else rev)
    assert out["x_utm"].tolist() == [0, 1, 2, 2, 1, 0, 1]
    assert out["clock_s"].tolist() == list(range(8 * 3600, 8 * 3600 + 7))


@pytest.mark.parametrize("arch", ["A1", "A4"])
@pytest.mark.parametrize("weekend", [False, True])
def test_steps_split_every_5_min_between_driving_and_parking(arch, weekend):
    steps = sch.day_steps(arch, weekend, step_min=5)
    assert len(steps) == 288
    drive = sch.drive_mask_seconds(arch)
    per_step = drive.reshape(288, 300).sum(axis=1)
    assert np.allclose(steps["parked_frac"] + per_step / 300, 1.0)
    assert drive.sum() == sch.drive_seconds(arch) * len(CFG["archetypes"][arch]["trips"])
    if weekend:
        assert set(steps["site"]) == {CFG["archetypes"][arch]["parking"]["weekend"]["default"]}
