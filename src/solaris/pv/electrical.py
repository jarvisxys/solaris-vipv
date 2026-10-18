"""Electrical partial shading (P7 / E6): bishop88 cells, bypass-diode substrings, one MPPT
input per facet (configs/vehicle/electrical_p0.yaml).

A cell is one facet sample. Its single-diode parameters are the CEC module's (pvlib
``calcparams_cec``) divided by the module's cell count and scaled to the sample's area.
Cells in sample order form ``substrings_per_module`` series substrings; a substring's
voltage never falls below -Vf of its bypass diode. Series addition happens on a common
current grid: each cell's V(I) comes from bishop88 with reverse-bias breakdown.

The cells of a facet take only a few irradiance values at a time (lit, behind a tree,
behind a building), so one I-V curve per value serves every cell that has it.

    F_mm = P_mpp(per-cell irradiance) / P_mpp(every cell at the facet's mean irradiance)
"""

from functools import lru_cache
from pathlib import Path

import numpy as np
import pvlib
import yaml
from numba import njit

from solaris.core.params import REPO_ROOT
from solaris.vehicle import samples

ELECTRICAL_YAML = REPO_ROOT / "configs" / "vehicle" / "electrical_p0.yaml"


def electrical_config(path=ELECTRICAL_YAML) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


@lru_cache(maxsize=4)
def _source_module(name):
    return pvlib.pvsystem.retrieve_sam("CECMod")[name]


def substring_index(n_cells, n_sub=3):
    """Substring of each cell (cells in sample order, contiguous near-equal groups)."""
    out = np.empty(n_cells, int)
    for k, idx in enumerate(np.array_split(np.arange(n_cells), n_sub)):
        out[idx] = k
    return out


def cell_area(facet, vcfg):
    """Area of one cell = the facet's area over its sample count (m2)."""
    return facet.area_m2 / len(samples([facet], vcfg["sample_spacing_m"]))


def cell_params(G, T, area, ec):
    """bishop88 inputs (IL, I0, Rs, Rsh, nNsVth) of one cell of ``area`` m2 at G (W/m2), T (C)."""
    m = _source_module(ec["cell_source"])
    G = np.maximum(np.asarray(G, float), ec["min_irradiance"])
    T = np.asarray(T, float)
    IL, I0, Rs, Rsh, nNsVth = np.broadcast_arrays(
        *pvlib.pvsystem.calcparams_cec(
            G, T, m.alpha_sc, m.a_ref, m.I_L_ref, m.I_o_ref, m.R_sh_ref, m.R_s, m.Adjust
        )
    )
    k = area / (m.A_c / m.N_s)
    return IL * k, I0 * k, Rs / m.N_s / k, Rsh / m.N_s / k, nNsVth / m.N_s


def _diode_grid(ec, v_top, n_fwd=1500, n_rev=500):
    """Diode voltages: coarse in reverse bias down to just above breakdown, dense forward."""
    vbr = ec["breakdown"]["voltage"]
    rev = np.linspace(0.995 * vbr, 0.0, n_rev, endpoint=False)
    return np.concatenate([rev, np.linspace(0.0, v_top, n_fwd)])


def cell_curves(G, T, area, ec):
    """I-V curves (rows = G values): current and voltage on a shared diode-voltage grid."""
    IL, I0, Rs, Rsh, nNsVth = cell_params(G, T, area, ec)
    voc = nNsVth * np.log1p(IL / I0)
    vd = _diode_grid(ec, float(np.max(voc)) + 0.02)
    bd = ec["breakdown"]
    i, v, _ = pvlib.singlediode.bishop88(
        vd[None, :],
        IL[:, None],
        I0[:, None],
        Rs[:, None],
        Rsh[:, None],
        nNsVth[:, None],
        breakdown_factor=bd["factor"],
        breakdown_voltage=bd["voltage"],
        breakdown_exp=bd["exp"],
    )
    return np.asarray(i, float), np.asarray(v, float), IL


@njit(cache=True)
def _mpp_rows(I_top, cur, vol, counts, vf, n_points):
    """MPP of series substrings per row. cur/vol (rows, classes, grid) are I-V curves with
    current decreasing along the grid; counts (rows, substrings, classes)."""
    n, n_cls, _ = cur.shape
    n_sub = counts.shape[1]
    out = np.zeros(n)
    for r in range(n):
        Ig = np.linspace(0.0, I_top[r], n_points)
        V = np.zeros((n_cls, n_points))
        for c in range(n_cls):
            used = False
            for s in range(n_sub):
                if counts[r, s, c] > 0:
                    used = True
            if used:
                V[c] = np.interp(Ig, cur[r, c, ::-1], vol[r, c, ::-1])
        Vm = np.zeros(n_points)
        for s in range(n_sub):
            vs = np.zeros(n_points)
            for c in range(n_cls):
                if counts[r, s, c] > 0:
                    vs += counts[r, s, c] * V[c]
            Vm += np.maximum(vs, -vf)
        out[r] = np.max(Ig * Vm)
    return out


def module_mpp(G_cls, counts, T, area, ec, chunk=2000):
    """Module MPP (W) per row: G_cls (rows, classes) irradiance of each class, counts
    (rows, substrings, classes) cells of each class per substring, T (rows) cell temperature."""
    G_cls = np.asarray(G_cls, float)
    n, n_cls = G_cls.shape
    out = np.zeros(n)
    for a in range(0, n, chunk):
        b = min(n, a + chunk)
        g = G_cls[a:b].ravel()
        t = np.repeat(np.asarray(T, float)[a:b], n_cls)
        cur, vol, IL = cell_curves(g, t, area, ec)
        m = b - a
        cur, vol, IL = cur.reshape(m, n_cls, -1), vol.reshape(m, n_cls, -1), IL.reshape(m, n_cls)
        present = counts[a:b].sum(axis=1) > 0
        I_top = np.where(present, IL, 0.0).max(axis=1)
        out[a:b] = _mpp_rows(
            I_top,
            cur,
            vol,
            np.asarray(counts[a:b], np.float64),
            float(ec["bypass_diode_vf"]),
            int(ec["current_points"]),
        )
    return out


def mismatch_powers(vb, beam, diffuse, T, area, ec):
    """(P per-cell irradiance, P at the mean irradiance) per row, W.

    vb (rows, cells) beam visibility of each cell (0, tree transmissivity or 1); a cell
    receives vb * beam + diffuse, where beam = DNI cos(theta) + circumsolar and diffuse is
    everything the facet gets regardless of the cell (sky, horizon band, ground).
    """
    vb = np.asarray(vb, float)
    beam, diffuse = np.asarray(beam, float), np.asarray(diffuse, float)
    levels = np.unique(vb)
    if len(levels) > 8:
        raise ValueError(f"{len(levels)} distinct beam visibilities; expected a few classes")
    sub = substring_index(vb.shape[1], ec["substrings_per_module"])
    n_sub = sub.max() + 1
    onehot = vb[:, :, None] == levels[None, None, :]  # rows, cells, classes
    counts = np.stack([onehot[:, sub == s].sum(axis=1) for s in range(n_sub)], axis=1)
    G_cls = levels[None, :] * beam[:, None] + diffuse[:, None]
    p_mixed = module_mpp(G_cls, counts, T, area, ec)
    uni_counts = np.zeros((len(vb), n_sub, 1))
    uni_counts[:, :, 0] = np.bincount(sub)
    G_mean = (vb.mean(axis=1) * beam + diffuse)[:, None]
    p_mean = module_mpp(G_mean, uni_counts, T, area, ec)
    return p_mixed, p_mean


def mismatch(vb, beam, diffuse, T, area, ec):
    """F_mm per row (1 where the mean-irradiance power is zero)."""
    p, q = mismatch_powers(vb, beam, diffuse, T, area, ec)
    return np.where(q > 0, p / np.where(q > 0, q, 1.0), 1.0)


FMM_FORM = "F_mm = 1 - k s^alpha (1 - s)^beta"


def fmm(s, k, alpha, beta):
    """Fitted mismatch factor vs beam-shaded fraction s: 1 - k s^alpha (1 - s)^beta.

    It is 1 at s = 0 and s = 1 (uniform light) and, with alpha < 1, drops steeply at small s:
    one shaded cell already sends its substring through the bypass diode."""
    s = np.clip(np.asarray(s, float), 0.0, 1.0)
    return 1.0 - k * np.power(s, alpha) * np.power(1.0 - s, beta)


def fit_fmm(s, f, w, p0=(1.5, 0.5, 0.5)):
    """Weighted nonlinear least squares for fmm; returns ({k, alpha, beta}, weighted R2)."""
    from scipy.optimize import curve_fit

    s, f, w = (np.asarray(x, float) for x in (s, f, w))
    sigma = 1.0 / np.sqrt(np.maximum(w / w.max(), 1e-30))
    p, _ = curve_fit(
        fmm, s, f, p0=p0, sigma=sigma, bounds=([0, 0.01, 0.01], [10, 3, 3]), maxfev=20000
    )
    res = f - fmm(s, *p)
    mean = np.average(f, weights=w)
    r2 = 1 - np.sum(w * res**2) / np.sum(w * (f - mean) ** 2)
    return dict(zip(("k", "alpha", "beta"), map(float, p), strict=True)), float(r2)
