"""Hourly aggregation of sub-hourly PV energy into the 8760-h SoC loop, with the E5
energy-balance checks (workflow guide E5: "energy balance closes to 0.1 %").

Times are seconds of the reference year from 2023-01-01 00:00 local standard time
(America/Phoenix, no DST), so hour h of the loop holds seconds [3600 h, 3600 (h + 1)).

Three closures are asserted for every run:
  energy  sum of the fine-resolution energies = sum of the hourly bins;
  time    driving + parked seconds = 3600 in every hour;
  pack    soc_end - soc_start = (harvest - curtailed) + grid - demand in core.simulate.
"""

import numpy as np

TOL = 1e-3
HOURS = 8760


def bin_hourly(t_s, kwh, n=HOURS):
    """Sum energies (kWh) at seconds of the year into n hourly bins; nothing may fall outside."""
    t_s, kwh = np.asarray(t_s), np.asarray(kwh, float)
    h = t_s // 3600
    if h.size and (h.min() < 0 or h.max() >= n):
        raise ValueError(f"times outside the {n}-h year: hours {h.min()}..{h.max()}")
    return np.bincount(h.astype(np.int64), weights=kwh, minlength=n)


def rel(a, b):
    a, b = float(a), float(b)
    return abs(a - b) / max(abs(a), abs(b), 1e-12)


def assert_closure(fine_total, binned_total, what, tol=TOL):
    r = rel(fine_total, np.sum(binned_total))
    assert r <= tol, f"{what}: hourly bins {np.sum(binned_total):.6g} vs fine {fine_total:.6g}"
    return r


def assert_time_closure(drive_s, park_s):
    t = np.asarray(drive_s, float) + np.asarray(park_s, float)
    bad = np.flatnonzero(np.abs(t - 3600) > 1e-6)
    assert bad.size == 0, f"hours {bad[:5]} hold {t[bad[:5]]} s, not 3600"


def pack_balance(r):
    """Pack-balance residual of a core.simulate result, relative to annual demand."""
    lhs = r["soc_end_kwh"] - r["soc_start_kwh"]
    rhs = r["harvest_used_kwh"] + r["grid_kwh"] - r["ann_dem"]
    return (lhs - rhs) / r["ann_dem"]


def assert_pack_balance(r, what, tol=TOL):
    b = pack_balance(r)
    assert abs(b) <= tol, f"{what}: pack balance residual {b:.2e} of demand"
    return abs(b)
