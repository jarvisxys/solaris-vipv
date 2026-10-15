#!/usr/bin/env python3
"""
SOLARIS -- Solar On-vehicle Long-horizon Assessment of Range, Insolation & Sufficiency.
A first-principles feasibility methodology & open toolkit for solar-assisted heavy EVs.

Companion code to Gaikwad, "SOLARIS: A First-Principles, Drive-Cycle- and
Climate-Resolved Methodology for Assessing Solar-Assisted Heavy Electric Vehicles."

CODE AVAILABILITY: https://github.com/anandsagar-g/solaris-vipv  (placeholder)
DEPENDENCIES: Python >=3.9, numpy>=1.24, matplotlib>=3.7  (pip install numpy matplotlib)
LICENSE: MIT.  Reproduces every table/figure deterministically (fixed seed).

Modules: (1) mass audit, (2) TEG 1-D thermal network, (3) WLTP Class-3b
reconstruction + road-load integration, (4) Aptera/Lightyear validation,
(5) 8760-h climate SoC simulation (incl. Lucknow monsoon), (6) design inversion
(required PV area / max self-sufficient range), (7) economics & grid relief,
(8) multi-objective (grid vs mass vs cost) sweep, (9) sensitivities.

NOTE: climate series are synthetic, CALIBRATED to published annual PSH (matched
to +/-0% by construction) with a physically-based seasonal+monsoon clearness
model; intra-annual distribution is NOT fitted to station monthly normals -- a
stated limitation. Replace hourly_climate() with TMY3/PVGIS for certification.
"""
import numpy as np

# ----------------------------- constants -----------------------------
g, rho = 9.81, 1.204
Cd, Af, Cr = 0.28, 2.9, 0.010
eta_dt = 0.92
ETA_REGEN_BASE = 0.60          # base case (was 0.72 optimistic)
P_SUSP = 200.0                 # W during motion
A_skin, eta_pv, beta = 11.6, 0.22, -0.004
KAPPA_PV_BASE = 0.80
E_PACK = 250.0                 # kWh usable (variant P0)

# ------------------------- 1. SYSTEMS MASS AUDIT ----------------------
MASS = {
    "Glider (body, chassis, 2 motors, interior, 7 seats, HVAC)": 1800,
    "PV skin (11.6 m^2 VIPV laminate @3.5 kg/m^2)": 41,
    "TEG subsystem (2 m^2 modules + cold plate)": 35,
    "Regenerative suspension (4 EM dampers)": 32,
    "Power electronics (multi-input MPPT, 800V DC-DC)": 12,
    "Thermal management (added pump/HX capacity)": 15,
    "HV wiring / harness (distributed PV+TEG)": 10,
    "Coolant + loops (TEG + pack)": 8,
    "Added structure (roof/panel load paths)": 20,
    "Encapsulation / protective coatings": 9,
}
HARVEST_HW = sum(v for k, v in MASS.items() if k != list(MASS)[0])
PACK = {"P0": 500, "PA": 714}      # 500 Wh/kg (CTP=1) upper bound; 350 Wh/kg realistic
CAP  = {"P0": 250.0, "PA": 250.0, "PB": 175.0}
def vehicle_mass(variant):
    pack = 500 if variant == "PB" else PACK.get(variant, 500)
    return MASS[list(MASS)[0]] + HARVEST_HW + pack
M = {v: vehicle_mass(v) for v in ("P0", "PA", "PB")}

# ------------------ 2. TEG 1-D THERMAL-NETWORK MODEL ------------------
def teg_daily_kwh(A_teg=2.0, alpha=0.90, G=700.0, h_loss=15.0,
                  k_TE=1.2, leg=0.004, fill=0.5, R_contact=1e-3,
                  S_mod=0.051, R_int=3.0, mod_per_m2=625, hours=5.0):
    """Flux-limited TEG output from series thermal network. Returns kWh/day."""
    k_TE_area = k_TE * fill / leg                       # W/m2K of TE legs
    k_stack = 1.0 / (1.0 / k_TE_area + R_contact)       # + contact resistance
    dT_skin = alpha * G / (h_loss + k_stack)
    q_through = k_stack * dT_skin                       # W/m2 through module
    dT_leg = q_through / k_TE_area                      # K across TE legs
    Voc = S_mod * dT_leg
    P_mod = Voc ** 2 / (4 * R_int)                      # matched load, W/module
    P_area = P_mod * mod_per_m2                         # W/m2
    P_teg = P_area * A_teg
    # optimized purpose-built high-R TEG upper bound (eta ~1% of q_through)
    P_opt = 0.01 * q_through * A_teg
    return dict(dT_leg=dT_leg, q_through=q_through, P_teg=P_teg, P_opt=P_opt,
                E_teg=P_teg * hours / 1000.0,        # COMMERCIAL base (adopted)
                E_teg_opt=P_opt * hours / 1000.0)    # optimized upper bound
TEG = teg_daily_kwh()
E_TEG = round(TEG["E_teg"], 3)          # COMMERCIAL module base (~0.019 kWh/day)

# ---------------- 3. WLTP CLASS-3b RECONSTRUCTION --------------------
# Phase (distance_km, duration_s, vmax_kmh, n_microtrips) -- official WLTC 3b stats.
WLTC = {"Low": (3.095, 589, 56.5, 8), "Medium": (4.756, 433, 76.6, 5),
        "High": (7.158, 455, 97.4, 4), "ExtraHigh": (8.254, 323, 131.3, 2)}
def build_phase(D_km, T_s, vmax_kmh, n, a_acc=1.0, a_dec=1.2):
    D, vpk = D_km * 1000, vmax_kmh / 3.6
    best = None
    for vc in np.linspace(0.35 * vpk, 0.95 * vpk, 60):
        ta, td = vc / a_acc, vc / a_dec
        da, dd = 0.5 * a_acc * ta ** 2, 0.5 * a_dec * td ** 2
        if da + dd > D / n:
            continue
        dc = D / n - da - dd; tc = dc / vc; ti = (T_s - n * (ta + tc + td)) / n
        if ti < 0:
            continue
        best = (vc, ta, tc, td, ti)
    vc, ta, tc, td, ti = best; v = []
    for _ in range(n):
        v += [min(vc, a_acc * t) for t in np.arange(0, ta, 1)]
        v += [vc] * int(tc)
        v += [max(0, vc - a_dec * t) for t in np.arange(0, td, 1)]
        v += [0.0] * int(ti)
    return np.array(v)
def wltp_trace(keys=tuple(WLTC)):
    return np.concatenate([build_phase(*WLTC[k]) for k in keys])
def consumption_wh_km(v_ms, m, eta_regen=ETA_REGEN_BASE):
    a = np.diff(v_ms, prepend=v_ms[0])
    F = Cr * m * g * (v_ms > 0.1) + 0.5 * rho * Cd * Af * v_ms ** 2 + m * a
    P = F * v_ms
    E_pos = np.sum(np.clip(P, 0, None)) / 3.6e6
    E_neg = np.sum(np.clip(P, None, 0)) / 3.6e6
    E_batt = E_pos / eta_dt + E_neg * eta_regen * eta_dt
    dist = np.sum(v_ms) / 1000.0
    return E_batt / dist * 1000.0, dist, np.mean(v_ms) * 3.6

def whkm(variant, city=False, eta_regen=ETA_REGEN_BASE):
    keys = ("Low", "Medium") if city else tuple(WLTC)
    v = wltp_trace(keys)
    return consumption_wh_km(v, M[variant], eta_regen)[0]

# ------------------ 4. VALIDATION: Aptera / Lightyear ----------------
def validate():
    out = {}
    # Aptera: Cd 0.13, Af ~2.2, m ~1000, Cr ~0.008; claim ~62 Wh/km, ~0.7 kWp, ~64 km/day
    g_Cd, g_Af, g_Cr = Cd, Af, Cr
    for name, cd, af, m, cr, kWp, claim_whkm, claim_solar_km, psh in [
        ("Aptera", 0.13, 2.2, 1000, 0.008, 0.70, 62, 64, 6.0),
        ("Lightyear0", 0.175, 2.36, 1575, 0.009, 1.05, 96, 70, 5.0)]:
        globals().update(Cd=cd, Af=af, Cr=cr)
        v = wltp_trace()
        wh, _, _ = consumption_wh_km(v, m, eta_regen=0.65)
        solar_kwh = kWp * psh * 0.80
        out[name] = dict(model_whkm=round(wh), claim_whkm=claim_whkm,
                         model_solar_km=round(solar_kwh / (claim_whkm/1000.0)),
                         claim_solar_km=claim_solar_km)
    globals().update(Cd=g_Cd, Af=g_Af, Cr=g_Cr)
    return out

# ---------- 5. SYNTHETIC TMY-CALIBRATED 8760-h GENERATOR -------------
LOCS = {  # (latitude, target annual PSH, T_annual_mean, T_amplitude_seasonal)
    "Phoenix":  (33.4, 6.3, 24, 12),
    "Lucknow":  (26.8, 5.2, 26, 10),
    "London":   (51.5, 2.7, 11, 7),
}
# ---------------------------------------------------------------------------
# MEASURED SOLAR RESOURCE -- primary sources (see paper Sec. "Real-data validation")
# Global Solar Atlas (Solargis / World Bank Group, CC BY 4.0 IGO), reports generated
# 18 Jul 2026 at the coordinates below. GHI = GLOBAL HORIZONTAL irradiation, which is
# the correct quantity for an (essentially horizontal) vehicle skin. Do NOT substitute
# GTI_opta or DNI: for Phoenix those are 2440.5 and 2719.8 kWh/m2/yr respectively,
# i.e. +15% and +28% above GHI, and would overstate on-vehicle yield accordingly.
GSA = {   # city: (lat, lon, GHI kWh/m2/yr, DNI, GTI_opta, TEMP degC, elevation m)
    "Phoenix": (33.543171, -112.073593, 2119.4, 2719.8, 2440.5, 23.1, 369),
    "Lucknow": (26.857530,   80.912659, 1725.6, 1145.5, 1851.5, 24.9, 127),
    "London":  (51.501993,   -0.119476, 1032.7,  883.8, 1209.5, 10.9,   9),
}
REAL_PSH = {c: round(v[2] / 365.0, 3) for c, v in GSA.items()}   # 5.807 / 4.728 / 2.829
REAL_TEMP = {c: v[5] for c, v in GSA.items()}                    # 23.1 / 24.9 / 10.9

# Hourly TMY files (user-supplied; not redistributed). Obtain via:
#   Phoenix -- NREL NSRDB viewer, lat 33.45 lon -112.06, "tmy-2023" (PSM v4.0.1)
#   London  -- PVGIS 5.2 TMY tool, lat 51.526 lon -0.129, period 2005-2023
TMY_FILES = {
    "Phoenix": "data/323705_33.45_-112.06_tmy-2023.csv",   # NSRDB format
    "London":  "data/tmy_51_526_-0_129_2005_2023.csv",     # PVGIS format
}
def hourly_climate(lat, psh_target, Tmean, Tamp, seed=0):
    rng = np.random.default_rng(seed)
    hours = np.arange(8760); d = hours // 24; hod = hours % 24
    decl = np.radians(23.45) * np.sin(2 * np.pi * (284 + d) / 365.0)
    omega = np.radians(15.0 * (hod - 12))
    la = np.radians(lat)
    cosz = (np.sin(la) * np.sin(decl) + np.cos(la) * np.cos(decl) * np.cos(omega))
    cosz = np.clip(cosz, 0, None)
    ghi_clear = 1000.0 * cosz ** 1.15
    # seasonal clearness (cloudier winters; monsoon dip Jul-Aug for Lucknow)
    Kt = 0.75 + 0.10 * np.cos(2 * np.pi * (d - 172) / 365.0)     # summer clearer
    if lat < 30:  # monsoon dip
        Kt -= 0.20 * np.exp(-((d - 200) ** 2) / (2 * 25 ** 2))
    daily_noise = rng.normal(1.0, 0.18, 366)[d]
    ghi = np.clip(ghi_clear * Kt * daily_noise, 0, None)
    # rescale to hit target annual PSH exactly
    psh_now = ghi.sum() / 1000.0 / 365.0
    ghi *= psh_target / psh_now
    # temperature: seasonal + diurnal
    Tseason = Tmean - Tamp * np.cos(2 * np.pi * (d - 200) / 365.0)
    Tdiurnal = 6.0 * (-np.cos(2 * np.pi * (hod - 15) / 24.0))
    Tamb = Tseason + Tdiurnal
    return ghi, Tamb

def park_load(Tamb, setpt=30.0, UA=25.0, COP=2.2, soak=15.0):
    return np.where(Tamb <= setpt - 2, 50.0,
                    np.maximum(50.0, UA * ((Tamb - setpt) + soak) / COP))

def simulate(loc, daily_km, city, variant="P0",
             kappa=KAPPA_PV_BASE, eta_regen=ETA_REGEN_BASE,
             floor=0.10, recharge_to=0.80, seed=0,
             pv_scale=1.0, A_over=None, cap_over=None, climate=None):
    lat, psh, Tm, Ta = LOCS[loc]
    if climate is None:
        ghi, Tamb = hourly_climate(lat, psh, Tm, Ta, seed)
    else:
        ghi, Tamb = climate            # measured TMY series (GHI W/m2, T degC)
    wh = whkm(variant, city=city, eta_regen=eta_regen)
    A = A_over if A_over is not None else A_skin
    # driving schedule: two commute trips 08:00 and 18:00, prorated by actual duration
    hod = np.arange(8760) % 24
    drive = np.isin(hod, [8, 18])
    trip_km = daily_km / 2.0
    keys = ("Low", "Medium") if city else tuple(WLTC)
    vavg = wltp_trace(keys).mean() * 3.6                     # cycle mean speed (km/h)
    drive_frac = min(1.0, (daily_km / vavg) / 2.0)          # fraction of each 1-h bucket driving
    E_prop_h = np.where(drive, wh * trip_km / 1000.0, 0.0)  # distance-based (unchanged)
    E_susp_h = np.where(drive, P_SUSP * drive_frac / 1000.0, 0.0)   # prorated by drive time
    Pcell = Tamb + 25.0 * (ghi / 1000.0)
    E_pv_h = pv_scale * A * eta_pv * (ghi / 1000.0) * kappa * (1 + beta * (Pcell - 25))
    # aux: during a drive bucket the hour is part-driving (250 W) part-parked
    P_aux = np.where(drive, 250.0 * drive_frac + park_load(Tamb) * (1 - drive_frac),
                     park_load(Tamb))
    E_aux_h = P_aux / 1000.0
    E_teg_h = E_TEG / 24.0
    harv = E_pv_h + E_susp_h + E_teg_h
    dem = E_prop_h / eta_dt + E_aux_h
    cap = cap_over if cap_over is not None else CAP[variant]
    soc = np.zeros(8761); soc[0] = 0.9 * cap
    grid = 0.0; charges = 0
    for h in range(8760):
        s = soc[h] + harv[h] - dem[h]
        if s < floor * cap:
            grid += recharge_to * cap - s
            s = recharge_to * cap; charges += 1
        soc[h + 1] = min(cap, s)
    ann_harv = harv.sum(); ann_dem = dem.sum()
    return dict(soc=soc / cap * 100, fss=ann_harv / ann_dem,
                grid_kwh=grid, charges=charges, ann_dem=ann_dem,
                solar_used=ann_dem - grid, psh=ghi.sum()/1000.0/365.0,
                whkm=wh, cap=cap)

# ---------------- granular sufficiency classification ----------------
def classify(fss):
    if fss >= 1.00: return "self-sufficient"
    if fss >= 0.90: return "quasi-self-sufficient"
    if fss >= 0.80: return "highly solar-assisted"
    if fss >= 0.50: return "moderately solar-assisted"
    return "grid-dependent"

# ---------------- TEG mass-vs-output tradeoff ------------------------
def teg_tradeoff():
    kwh_if_battery = 35 * 500 / 1000.0          # 35 kg at 500 Wh/kg -> kWh
    days_to_generate = kwh_if_battery / E_TEG   # days for TEG to make that energy
    return dict(kwh_if_battery=kwh_if_battery, days=days_to_generate,
                years=days_to_generate / 365.0)

# ---------------- regenerative-suspension sensitivity ---------------
def regen_susp_sensitivity(loc="Phoenix", km=50, city=True):
    global P_SUSP
    base = P_SUSP; out = {}
    for p in (50, 100, 150, 200):
        P_SUSP = p; out[p] = simulate(loc, km, city)['fss']
    P_SUSP = base
    return out

# ---------------- MEASURED HOURLY TMY LOADERS -----------------------
def load_tmy(path):
    """Load a measured 8760-h series -> (GHI W/m2, T_amb degC).
    Auto-detects NREL NSRDB and PVGIS TMY CSV formats."""
    import csv as _csv
    with open(path) as f:
        raw = f.read().splitlines()
    if any(l.startswith("time(UTC)") for l in raw):          # ---- PVGIS
        i = next(i for i, l in enumerate(raw) if l.startswith("time(UTC)"))
        ghi, T = [], []
        for l in raw[i + 1:]:
            p = l.split(",")
            if len(p) < 5 or not p[0][:4].isdigit():
                break
            T.append(float(p[1])); ghi.append(float(p[3]))
    else:                                                     # ---- NSRDB
        rows = list(_csv.reader(raw))
        hdr = rows[2]; gi = hdr.index("GHI"); ti = hdr.index("Temperature")
        ghi = [float(r[gi]) for r in rows[3:] if len(r) > gi]
        T = [float(r[ti]) for r in rows[3:] if len(r) > ti]
    ghi = np.asarray(ghi, float); T = np.asarray(T, float)
    if len(ghi) != 8760:                                      # resample to 8760 h
        idx = np.linspace(0, len(ghi) - 1, 8760).astype(int)
        ghi, T = ghi[idx], T[idx]
    return ghi, T

# ---------------- 6. DESIGN INVERSION -------------------------------
def engine_fT(loc):
    """Irradiance-weighted annual mean PV temperature factor, consistent with simulate()."""
    lat, psh, Tm, Taamp = LOCS[loc]
    ghi, Tamb = hourly_climate(lat, psh, Tm, Taamp)
    Pcell = Tamb + 25.0 * (ghi / 1000.0)
    w = ghi > 0
    return float(np.sum(ghi[w] * (1 + beta * (Pcell[w] - 25))) / np.sum(ghi[w]))

def engine_Eaux(loc, city, daily_km):
    """Annual-mean daily auxiliary energy (kWh), from the same park_load / drive model."""
    lat, psh, Tm, Taamp = LOCS[loc]
    ghi, Tamb = hourly_climate(lat, psh, Tm, Taamp)
    keys = ("Low", "Medium") if city else tuple(WLTC)
    vavg = wltp_trace(keys).mean() * 3.6
    drive_frac = min(1.0, (daily_km / vavg) / 2.0)
    hod = np.arange(8760) % 24
    drive = np.isin(hod, [8, 18])
    P_aux = np.where(drive, 250.0 * drive_frac + park_load(Tamb) * (1 - drive_frac),
                     park_load(Tamb))
    return float(P_aux.sum() / 1000.0 / 365.0)

def required_pv_area(daily_km, city, loc):
    """Min PV skin area (m^2) for self-sufficiency (f_ss=1); engine-consistent fT, E_aux."""
    lat, psh, Tm, Ta = LOCS[loc]
    c = whkm("P0", city=city) / 1000.0                 # kWh/km
    fT = engine_fT(loc); E_aux = engine_Eaux(loc, city, daily_km)
    return (daily_km * c / eta_dt + E_aux) / (eta_pv * psh * KAPPA_PV_BASE * fT)

def max_selfsuff_km(loc, city=True):
    """Max daily distance for self-sufficiency with the as-built 11.6 m^2 skin."""
    lat, psh, Tm, Ta = LOCS[loc]
    c = whkm("P0", city=city) / 1000.0
    fT = engine_fT(loc); E_aux = engine_Eaux(loc, city, 50)
    E_pv = A_skin * eta_pv * psh * KAPPA_PV_BASE * fT
    return eta_dt * (E_pv - E_aux) / c

# ---------------- 7. ECONOMICS & GRID RELIEF ------------------------
PRICE = {"Phoenix": 0.16, "Lucknow": 0.09, "London": 0.34}   # USD/kWh
# Bottom-up add-on cost (USD). PV ~$1.2/Wp (IEA-PVPS: VIPV heading <$1/Wp; +integration);
# ETIP-PV: solar option adds EUR 1-4k. TEG & regen dampers are the costly, low-yield items.
COST_ITEMS = {
    "PV skin (2.55 kWp @ ~$1.2/Wp incl. integration)": 3060,
    "Multi-input MPPT / power electronics": 800,
    "TEG subsystem (~1250 modules + cold plate)": 2500,
    "Regenerative suspension (4 EM dampers)": 2000,
    "HV wiring / structure / coatings": 1200,
}
SYSTEM_COST = sum(COST_ITEMS.values())                       # full as-specified
PV_ONLY_COST = COST_ITEMS["PV skin (2.55 kWp @ ~$1.2/Wp incl. integration)"] \
             + COST_ITEMS["Multi-input MPPT / power electronics"] \
             + COST_ITEMS["HV wiring / structure / coatings"] * 0.5   # drop TEG + regen susp
def economics(loc, km, city, cost=None):
    r = simulate(loc, km, city)
    saved_kwh = r['solar_used']; saved_usd = saved_kwh * PRICE[loc]
    c = SYSTEM_COST if cost is None else cost
    payback = c / saved_usd if saved_usd > 0 else float('inf')
    return dict(fss=r['fss'], grid_kwh=r['grid_kwh'], saved_kwh=saved_kwh,
                saved_usd=saved_usd, payback_yr=payback,
                payback_pvonly=PV_ONLY_COST / saved_usd if saved_usd > 0 else float('inf'),
                grid_relief_pct=100 * saved_kwh / r['ann_dem'])

# ---------------- WLTP reconstruction error vs official stats --------
def wltp_recon_error():
    official = {"Low": (3.095, 56.5), "Medium": (4.756, 76.6),
                "High": (7.158, 97.4), "ExtraHigh": (8.254, 131.3)}
    rows = {}
    for k in WLTC:
        v = build_phase(*WLTC[k]); dist = v.sum() / 1000.0
        do, vo = official[k]
        rows[k] = dict(dist=dist, dist_err=100 * (dist - do) / do,
                       vmax=v.max() * 3.6, vmax_off=vo)
    vfull = wltp_trace(); tot = vfull.sum() / 1000.0
    rows["TOTAL"] = dict(dist=tot, dist_err=100 * (tot - 23.263) / 23.263,
                         vmax=vfull.max() * 3.6, vmax_off=131.3)
    return rows

# ---------------- synthetic-climate error vs monthly normals ---------
def climate_error(loc):
    """Monthly + annual error of the synthetic series vs MEASURED hourly TMY.
    Returns None if no TMY file is available for that location."""
    import os
    path = TMY_FILES.get(loc)
    if not path or not os.path.exists(path):
        return None
    meas_ghi, _ = load_tmy(path)
    lat, psh, Tm, Ta = LOCS[loc]
    syn_ghi, _ = hourly_climate(lat, psh, Tm, Ta)
    mh = np.minimum(((np.arange(8760) // 24) / 30.44).astype(int), 11)
    meas = np.array([meas_ghi[mh == m].sum() / 1000.0 / (np.sum(mh == m) / 24.0) for m in range(12)])
    syn = np.array([syn_ghi[mh == m].sum() / 1000.0 / (np.sum(mh == m) / 24.0) for m in range(12)])
    return dict(ann_err=100 * (syn.mean() - meas.mean()) / meas.mean(),
                monthly_mape=float(np.mean(np.abs(syn - meas) / meas) * 100),
                syn=syn, meas=meas)

# ---------------- 8. MULTI-OBJECTIVE SWEEP --------------------------
def pareto(loc="Phoenix", km=50, city=True):
    """Sweep PV area and pack size; return designs (grid, mass, cost)."""
    PV_COST = 400.0     # USD per m^2 installed VIPV
    PACK_COST = 90.0    # USD per kWh (solid-state, 2030 assumption)
    rows = []
    for A in (8, 11.6, 15, 20):
        for capk in (150, 200, 250):
            grids = [simulate(loc, km, city, A_over=A, cap_over=capk, seed=sd)['grid_kwh']
                     for sd in range(4)]
            r = simulate(loc, km, city, A_over=A, cap_over=capk)
            mass = (M['P0'] - 500 - 41) + A * 3.5 + capk * 2.0
            cost = A * PV_COST + capk * PACK_COST
            rows.append(dict(A=A, cap=capk, grid=float(np.mean(grids)), charges=r['charges'],
                             mass=mass, cost=cost, fss=r['fss']))
    return rows

# ---------------- REAL-DATA VALIDATION (measured GHI) ---------------
def real_data_validation(scenarios=((50, True, "II 50km"), (100, False, "I 100km"))):
    """Tier 1: re-run with MEASURED annual GHI + air temperature (Global Solar Atlas).
    Every value below is emitted by this function, so the paper's real-data claims
    are reproducible directly from the toolkit."""
    out = []
    for km, city, tag in scenarios:
        for l in LOCS:
            lat, psh0, Tm0, Ta = LOCS[l]
            f_assumed = simulate(l, km, city)['fss']
            LOCS[l] = (lat, REAL_PSH[l], REAL_TEMP[l], Ta)     # measured GHI + temp
            r = simulate(l, km, city); f_real = r['fss']
            LOCS[l] = (lat, psh0, Tm0, Ta)
            out.append(dict(scenario=tag, city=l, assumed=psh0, real=REAL_PSH[l],
                            f_assumed=round(f_assumed, 2), f_real=round(f_real, 2),
                            cls_assumed=classify(f_assumed), cls_real=classify(f_real),
                            class_changed=classify(f_assumed) != classify(f_real),
                            charges=r['charges']))
    return out

def tmy_validation(scenarios=((50, True, "II 50km"), (100, False, "I 100km"))):
    """Tier 2 (strongest): re-run the 8760-h engine on MEASURED HOURLY TMY series
    (NSRDB for Phoenix, PVGIS for London), replacing the synthetic climate entirely.
    Returns [] for any city whose TMY file is absent."""
    import os
    out = []
    for city_name, path in TMY_FILES.items():
        if not os.path.exists(path):
            continue
        ghi, T = load_tmy(path)
        for km, city, tag in scenarios:
            f_syn = simulate(city_name, km, city)['fss']
            r = simulate(city_name, km, city, climate=(ghi, T))
            out.append(dict(scenario=tag, city=city_name,
                            psh_tmy=round(ghi.sum() / 1000 / 365, 3),
                            tmean=round(float(T.mean()), 1),
                            f_syn=round(f_syn, 2), f_tmy=round(r['fss'], 2),
                            cls_tmy=classify(r['fss']),
                            class_changed=classify(f_syn) != classify(r['fss']),
                            charges=r['charges'], grid=round(r['grid_kwh'])))
    return out

# ----------------------------- run all -------------------------------
if __name__ == "__main__":
    print("=== 1. MASS AUDIT ===")
    for k, v in MASS.items():
        print(f"  {v:5d}  {k}")
    print(f"  harvesting+integration subtotal = {HARVEST_HW} kg")
    for v in ("P0", "PA", "PB"):
        print(f"  vehicle mass {v}: {M[v]} kg (cap {CAP[v]} kWh)")

    print("\n=== 2. TEG THERMAL NETWORK ===")
    for k, val in TEG.items():
        print(f"  {k} = {val:.4f}")
    print(f"  adopted E_teg = {E_TEG} kWh/day")

    print("\n=== 3. WLTP CONSUMPTION (eta_regen=0.60 base) ===")
    v = wltp_trace(); _, dist, vavg = consumption_wh_km(v, M['P0'])
    print(f"  reconstruction: {dist:.2f} km (off 23.27), {vavg:.1f} km/h (off 46.5)")
    for var in ("P0", "PA"):
        print(f"  {var}: combined {whkm(var):.0f} Wh/km, city {whkm(var,city=True):.0f} Wh/km")
    print(f"  (eta_regen=0.72 optimistic: P0 combined {whkm('P0',eta_regen=0.72):.0f} Wh/km)")

    print("\n=== 4. VALIDATION vs Aptera / Lightyear ===")
    for name, d in validate().items():
        print(f"  {name}: model {d['model_whkm']} Wh/km (claim {d['claim_whkm']}); "
              f"solar {d['model_solar_km']} km/day (claim {d['claim_solar_km']})")

    print("\n=== 5-8. 8760-h SIMULATION (base: eta_regen=0.60, kappa=0.80, P0) ===")
    for scen, (km, city) in [("II 50km urban", (50, True)), ("I 100km mixed", (100, False))]:
        print(f"  -- Scenario {scen} --")
        for loc in LOCS:
            r = simulate(loc, km, city)
            print(f"    {loc:8s} PSH={r['psh']:.2f} f_ss={r['fss']:.2f} "
                  f"grid={r['grid_kwh']:6.0f} kWh/yr charges={r['charges']:3d}/yr -> {classify(r['fss'])}")

    print("\n=== 7. kappa_pv SENSITIVITY (Scenario II, annual f_ss) ===")
    for loc in LOCS:
        row = [f"{simulate(loc,50,True,kappa=k)['fss']:.2f}" for k in (0.60, 0.70, 0.80)]
        print(f"    {loc:8s} kappa=0.60/0.70/0.80 -> f_ss = {' / '.join(row)}")

    print("\n=== REAL-DATA VALIDATION TIER 1: measured annual GHI+temp (Global Solar Atlas) ===")
    rows = real_data_validation()
    for r in rows:
        flag = "CLASS CHANGED" if r['class_changed'] else "class unchanged"
        print(f"    {r['scenario']:8s} {r['city']:8s} assumed={r['assumed']:.2f} "
              f"measured={r['real']:.3f} -> f_ss {r['f_assumed']:.2f}->{r['f_real']:.2f} "
              f"({r['cls_real']}) [{flag}]")
    nch = sum(r['class_changed'] for r in rows)
    print(f"    SUMMARY: {len(rows)-nch}/{len(rows)} classes unchanged; "
          f"max |df_ss| = {max(abs(r['f_real']-r['f_assumed']) for r in rows):.2f}")

    print("\n=== REAL-DATA VALIDATION TIER 2: measured HOURLY TMY (NSRDB / PVGIS) ===")
    trows = tmy_validation()
    if not trows:
        print("    (no TMY files found under data/ -- see TMY_FILES)")
    for r in trows:
        flag = "CLASS CHANGED" if r['class_changed'] else "class unchanged"
        print(f"    {r['scenario']:8s} {r['city']:8s} TMY PSH={r['psh_tmy']:.3f} "
              f"Tmean={r['tmean']:.1f}C -> f_ss syn {r['f_syn']:.2f} -> TMY {r['f_tmy']:.2f} "
              f"({r['cls_tmy']}) [{flag}] {r['charges']}/yr")

    print("\n=== TEG MASS-vs-OUTPUT TRADEOFF ===")
    t = teg_tradeoff()
    print(f"    35 kg -> {t['kwh_if_battery']:.1f} kWh pack; TEG needs "
          f"{t['days']:.0f} days ({t['years']:.1f} yr) to generate that at {E_TEG} kWh/day")

    print("\n=== REGEN-SUSPENSION SENSITIVITY (Phoenix II, f_ss) ===")
    print("   ", {k: round(v, 3) for k, v in regen_susp_sensitivity().items()})

    print("\n=== NO-SOLAR BASELINE charges/yr (for honest grid-relief) ===")
    for scen, (km, city) in [("II 50km", (50, True)), ("I 100km", (100, False))]:
        for loc in LOCS:
            base = simulate(loc, km, city, pv_scale=0.0)['charges']
            solar = simulate(loc, km, city)['charges']
            print(f"    {scen} {loc:8s}: no-solar {base:3d}/yr -> solar {solar:3d}/yr "
                  f"({100*(base-solar)/base:.0f}% fewer)")

    print("\n=== 6. DESIGN INVERSION ===")
    for city, tag, km in [(True, "II 50km", 50), (False, "I 100km", 100)]:
        print(f"  Scenario {tag}:")
        for loc in LOCS:
            need = required_pv_area(km, city, loc)
            mx = max_selfsuff_km(loc, city)
            print(f"    {loc:8s} req.PV area for self-suff = {need:5.1f} m^2 "
                  f"(have 11.6); max self-suff distance = {mx:4.1f} km/day")

    print("\n=== 7. ECONOMICS & GRID RELIEF ===")
    for scen, (km, city) in [("II 50km", (50, True)), ("I 100km", (100, False))]:
        for loc in LOCS:
            e = economics(loc, km, city)
            print(f"    {scen} {loc:8s}: relief {e['grid_relief_pct']:4.0f}% "
                  f"({e['saved_kwh']:5.0f} kWh/yr), save ${e['saved_usd']:5.0f}/yr, "
                  f"payback {e['payback_yr']:4.1f} yr")

    print("\n=== 8. MULTI-OBJECTIVE (Phoenix II): design | grid | mass | cost | fss ===")
    for r in pareto():
        print(f"    A={r['A']:4.1f} cap={r['cap']:3d}: grid={r['grid']:5.0f} kWh/yr "
              f"mass={r['mass']:5.0f} kg cost=${r['cost']:5.0f} f_ss={r['fss']:.2f}")

    print("\n=== COST BREAKDOWN (USD add-on) ===")
    for k, v in COST_ITEMS.items():
        print(f"    ${v:5d}  {k}")
    print(f"    ${SYSTEM_COST:5.0f}  TOTAL as-specified;  ${PV_ONLY_COST:.0f}  PV-only (drop TEG+regen susp)")
    print("    payback (Scen. II, full / PV-only):")
    for loc in LOCS:
        e = economics(loc, 50, True)
        print(f"      {loc:8s} full {e['payback_yr']:4.1f} yr | PV-only {e['payback_pvonly']:4.1f} yr")

    print("\n=== WLTP RECONSTRUCTION ERROR vs official WLTC 3b ===")
    for k, v in wltp_recon_error().items():
        print(f"    {k:10s} dist={v['dist']:6.3f} km (err {v['dist_err']:+.2f}%)  vmax={v['vmax']:5.1f} (off {v['vmax_off']})")

    print("\n=== SYNTHETIC CLIMATE ERROR vs MEASURED hourly TMY ===")
    for loc in LOCS:
        e = climate_error(loc)
        if e is None:
            print(f"    {loc:8s} (no TMY file)")
        else:
            print(f"    {loc:8s} annual err {e['ann_err']:+.1f}%, monthly MAPE {e['monthly_mape']:.1f}%")
