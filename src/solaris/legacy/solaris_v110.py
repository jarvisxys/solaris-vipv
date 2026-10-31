#!/usr/bin/env python3
"""
SOLARIS -- Solar On-vehicle Long-horizon Assessment of Range, Insolation & Sufficiency.
A first-principles feasibility methodology & open toolkit for solar-assisted heavy EVs.

Companion code to A. Gaikwad, A. Kumar, and A. Deo, "SOLARIS: A First-Principles,
Drive-Cycle- and Climate-Resolved Methodology and Open Toolkit for Assessing
Solar-Assisted Heavy Electric Vehicles," IEEE ITEC Asia-Pacific (ITEC-AP) 2026.

CODE:         https://github.com/Anandsagar18/Solaris
VERSION:      1.1.0
DEPENDENCIES: Python >=3.9, numpy>=1.24 (core); matplotlib>=3.7 (figures only)
LICENSE:      MIT.  Deterministic (fixed seeds): `python solaris.py` prints every
              number in the paper; `python make_figures.py` redraws every figure.

Modules: (1) mass audit, (2) TEG 1-D thermal network, (3) WLTP Class-3b
reconstruction + road-load integration, (4) Aptera/Lightyear validation,
(5) 8760-h climate SoC simulation (incl. Lucknow monsoon), (6) design inversion
(required PV area / max self-sufficient range), (7) economics & grid relief,
(8) multi-objective (grid vs mass vs cost) sweep, (9) sensitivities,
(10) satellite-derived-data validation (Global Solar Atlas annual; NSRDB/PVGIS hourly TMY).

NOTE: the base-case climate series are synthetic, SCALED to assumed annual PSH
(matched to +/-0% by construction; an idealized climate) with a physically-based seasonal+monsoon
clearness model. Satellite-derived hourly TMY series for all three cities ship in data/
(grouped by city) and are used via load_tmy() / tmy_validation(); those results
are the authoritative ones reported in the paper.
"""
import os
import numpy as np

__version__ = "1.1.0"
HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")

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
        "High": (7.162, 455, 97.4, 4), "ExtraHigh": (8.254, 323, 131.3, 2)}
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
    # Reference claims are BATTERY-referenced (usable pack / rated range), matching the
    # battery-side energy that consumption_wh_km() returns:
    #   Aptera (Launch Edition, as reported Nov 2024): Cd 0.13, ~700 W solar, ~40 mi/day
    #     (64 km/day) solar, 42 kWh / 400 mi -> 65 Wh/km; m ~1000 kg; Af ~2.2 m^2 (est.)
    #   Lightyear 0 (2022): Cd 0.175, 1575 kg, 1.05 kW solar, up to 70 km/day solar,
    #     60 kWh usable / 625 km WLTP -> 96 Wh/km (certified grid-side figure is 105 Wh/km)
    g_Cd, g_Af, g_Cr = Cd, Af, Cr
    for name, cd, af, m, cr, kWp, claim_whkm, claim_solar_km, psh in [
        ("Aptera", 0.13, 2.2, 1000, 0.008, 0.70, 65, 64, 6.0),
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

# ---------- 5. IDEALIZED SYNTHETIC 8760-h GENERATOR (scaled to assumed PSH) -------------
LOCS = {  # (latitude, target annual PSH, T_annual_mean, T_amplitude_seasonal)
    "Phoenix":  (33.4, 6.3, 24, 12),
    "Lucknow":  (26.8, 5.2, 26, 10),
    "London":   (51.5, 2.7, 11, 7),
}
# ---------------------------------------------------------------------------
# SATELLITE-DERIVED SOLAR RESOURCE -- primary sources (see paper Sec. V-B)
# Global Solar Atlas (Solargis / World Bank Group, CC BY 4.0), reports generated
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

# Satellite-derived hourly TMY files, grouped by city under data/<city>/ (see data/README.md):
#   Phoenix -- NREL NSRDB (PSM v4.0.1), location 323705 (33.45, -112.06), TMY-2023
#              [TMY-2022/2024/2025 releases also shipped for the robustness check]
#   Lucknow -- NREL NSRDB international (SUNY) TMY, location 46088 (26.85, 80.95)
#   London  -- EC-JRC PVGIS 5.3 TMY (PVGIS-SARAH3), (51.526, -0.129), period 2005-2023
# NSRDB/PVGIS timestamps are UTC; load_tmy() rolls them to LOCAL STANDARD TIME so the
# 08:00/18:00 commute schedule and the parked-cabin load line up with local daylight.
# (UTC offsets: Phoenix -7 (MST, no DST), Lucknow +5.5 (IST), London 0 (GMT).)
UTC_OFFSET = {"Phoenix": -7.0, "Lucknow": 5.5, "London": 0.0}
TMY_FILES = {
    "Phoenix": os.path.join(DATA_DIR, "phoenix", "nsrdb_tmy", "323705_33.45_-112.06_tmy-2023.csv"),
    "Lucknow": os.path.join(DATA_DIR, "lucknow", "nsrdb_tmy", "46088_26.85_80.95_tmy.csv"),
    "London":  os.path.join(DATA_DIR, "london", "pvgis_tmy", "tmy_51.526_-0.129_2005_2023.csv"),
}
TMY_RELEASES = {  # Phoenix NSRDB TMY releases, for the inter-release robustness check
    y: os.path.join(DATA_DIR, "phoenix", "nsrdb_tmy", f"323705_33.45_-112.06_tmy-{y}.csv")
    for y in (2022, 2023, 2024, 2025)
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
             pv_scale=1.0, A_over=None, cap_over=None, climate=None,
             m_over=None, warmup=True):
    """8760-h energy balance. Returns f_ss, grid energy, plug-ins, curtailment, SoC trace.

    * Consumption from whkm()/consumption_wh_km() is already BATTERY-side (traction /eta_dt,
      regen *eta_regen*eta_dt), so it is NOT divided by eta_dt again here.
      (v1.0.0-1.0.1 divided by eta_dt a second time; fixed in v1.1.0.)
    * warmup=True runs the year twice and reports the second pass, which starts from the
      first pass's end-of-year SoC (periodic steady state). This removes the free energy of
      an arbitrary initial charge from the grid/relief/plug-in accounting.
    * relief = harvest actually used (harvest - curtailment) / demand, so relief <= f_ss.
    * m_over overrides the vehicle mass used for consumption (mass feedback in pareto()).
    """
    lat, psh, Tm, Ta = LOCS[loc]
    if climate is None:
        ghi, Tamb = hourly_climate(lat, psh, Tm, Ta, seed)
    else:
        ghi, Tamb = climate            # satellite-derived TMY series (GHI W/m2, T degC)
    keys = ("Low", "Medium") if city else tuple(WLTC)
    trace = wltp_trace(keys)
    if m_over is None:
        wh = whkm(variant, city=city, eta_regen=eta_regen)
    else:
        wh = consumption_wh_km(trace, m_over, eta_regen)[0]
    A = A_over if A_over is not None else A_skin
    # driving schedule: two commute trips 08:00 and 18:00, prorated by actual duration
    hod = np.arange(8760) % 24
    drive = np.isin(hod, [8, 18])
    trip_km = daily_km / 2.0
    vavg = trace.mean() * 3.6                                # cycle mean speed (km/h)
    drive_frac = min(1.0, (daily_km / vavg) / 2.0)          # fraction of each 1-h bucket driving
    E_prop_h = np.where(drive, wh * trip_km / 1000.0, 0.0)  # battery-side, distance-based
    E_susp_h = np.where(drive, P_SUSP * drive_frac / 1000.0, 0.0)   # prorated by drive time
    Pcell = Tamb + 25.0 * (ghi / 1000.0)
    E_pv_h = pv_scale * A * eta_pv * (ghi / 1000.0) * kappa * (1 + beta * (Pcell - 25))
    # aux: during a drive bucket the hour is part-driving (250 W) part-parked
    P_aux = np.where(drive, 250.0 * drive_frac + park_load(Tamb) * (1 - drive_frac),
                     park_load(Tamb))
    E_aux_h = P_aux / 1000.0
    E_teg_h = E_TEG / 24.0
    harv = E_pv_h + E_susp_h + E_teg_h
    dem = E_prop_h + E_aux_h
    cap = cap_over if cap_over is not None else CAP[variant]

    def _run(s0):
        soc = np.zeros(8761); soc[0] = s0
        grid = 0.0; charges = 0; curt = 0.0
        for h in range(8760):
            s = soc[h] + harv[h] - dem[h]
            if s < floor * cap:
                grid += recharge_to * cap - s
                s = recharge_to * cap; charges += 1
            if s > cap:
                curt += s - cap; s = cap
            soc[h + 1] = s
        return soc, grid, charges, curt

    s0 = 0.9 * cap
    if warmup:
        s0 = _run(s0)[0][-1]
    soc, grid, charges, curt = _run(s0)
    ann_harv = harv.sum(); ann_dem = dem.sum()
    used = ann_harv - curt
    return dict(soc=soc / cap * 100, fss=float(ann_harv / ann_dem),
                grid_kwh=float(grid), charges=int(charges), ann_dem=float(ann_dem),
                ann_harv=float(ann_harv), curtailed=float(curt), solar_used=float(used),
                relief=float(used / ann_dem), soc_change=float(soc[-1] - soc[0]),
                psh=float(ghi.sum() / 1000.0 / 365.0), whkm=float(wh), cap=float(cap))

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
def regen_susp_sensitivity(loc="Phoenix", km=50, city=True, climate=None):
    global P_SUSP
    base = P_SUSP; out = {}
    for p in (50, 100, 150, 200):
        P_SUSP = p; out[p] = simulate(loc, km, city, climate=climate)['fss']
    P_SUSP = base
    return out

# ---------------- SATELLITE-DERIVED HOURLY TMY LOADERS -----------------------
def load_tmy(path, utc_offset=None):
    """Load a satellite-derived 8760-h series -> (GHI W/m2, T_amb degC) in LOCAL STANDARD TIME.

    Auto-detects NREL NSRDB and PVGIS TMY CSV formats. Both store UTC timestamps.
    For NSRDB the offset is read from the header ('Time Zone' = stored zone,
    'Local Time Zone' = site zone); for PVGIS pass `utc_offset` (hours, default 0).
    The series is rolled cyclically by round(offset) hours (Lucknow +5.5 h -> +6 h,
    i.e. NSRDB's half-hour-centred 06:30 UTC record becomes the 12:00 IST hour)."""
    import csv as _csv
    with open(path) as f:
        raw = f.read().splitlines()
    shift = 0.0
    if any(l.startswith("time(UTC)") for l in raw):          # ---- PVGIS
        i = next(i for i, l in enumerate(raw) if l.startswith("time(UTC)"))
        ghi, T = [], []
        for l in raw[i + 1:]:
            p = l.split(",")
            if len(p) < 5 or not p[0][:4].isdigit():
                break
            T.append(float(p[1])); ghi.append(float(p[3]))
        shift = 0.0 if utc_offset is None else float(utc_offset)
    else:                                                     # ---- NSRDB
        rows = list(_csv.reader(raw))
        meta = dict(zip(rows[0], rows[1]))
        stored, local = float(meta.get("Time Zone", 0)), float(meta.get("Local Time Zone", 0))
        shift = (local - stored) if utc_offset is None else float(utc_offset) - stored
        hdr = rows[2]; gi = hdr.index("GHI"); ti = hdr.index("Temperature")
        ghi = [float(r[gi]) for r in rows[3:] if len(r) > gi]
        T = [float(r[ti]) for r in rows[3:] if len(r) > ti]
    ghi = np.asarray(ghi, float); T = np.asarray(T, float)
    if len(ghi) != 8760:                                      # resample to 8760 h
        idx = np.linspace(0, len(ghi) - 1, 8760).astype(int)
        ghi, T = ghi[idx], T[idx]
    k = int(np.floor(shift + 0.5))                            # round half up
    if k:
        ghi, T = np.roll(ghi, k), np.roll(T, k)
    return ghi, T

def load_city_tmy(city):
    """Satellite-derived hourly TMY for a study city (local standard time), or None if absent."""
    path = TMY_FILES.get(city)
    if not path or not os.path.exists(path):
        return None
    return load_tmy(path, utc_offset=UTC_OFFSET.get(city))

# ---------------- 6. DESIGN INVERSION -------------------------------
def _climate(loc, climate=None):
    if climate is not None:
        return climate
    lat, psh, Tm, Taamp = LOCS[loc]
    return hourly_climate(lat, psh, Tm, Taamp)

def engine_fT(loc, climate=None):
    """Irradiance-weighted annual mean PV temperature factor, consistent with simulate()."""
    ghi, Tamb = _climate(loc, climate)
    Pcell = Tamb + 25.0 * (ghi / 1000.0)
    w = ghi > 0
    return float(np.sum(ghi[w] * (1 + beta * (Pcell[w] - 25))) / np.sum(ghi[w]))

def engine_Eaux(loc, city, daily_km, climate=None):
    """Annual-mean daily auxiliary energy (kWh), from the same park_load / drive model."""
    ghi, Tamb = _climate(loc, climate)
    keys = ("Low", "Medium") if city else tuple(WLTC)
    vavg = wltp_trace(keys).mean() * 3.6
    drive_frac = min(1.0, (daily_km / vavg) / 2.0)
    hod = np.arange(8760) % 24
    drive = np.isin(hod, [8, 18])
    P_aux = np.where(drive, 250.0 * drive_frac + park_load(Tamb) * (1 - drive_frac),
                     park_load(Tamb))
    return float(P_aux.sum() / 1000.0 / 365.0)

def required_pv_area(daily_km, city, loc, climate=None):
    """Min PV skin area (m^2) for f_ss = 1 (TEG and suspension neglected).
    c is battery-side consumption (already includes eta_dt). climate=None uses the
    idealized synthetic climate; pass load_city_tmy(loc) for the satellite TMY."""
    ghi, T = _climate(loc, climate)
    psh = ghi.sum() / 1000.0 / 365.0
    c = whkm("P0", city=city) / 1000.0                 # kWh/km, battery-side
    fT = engine_fT(loc, (ghi, T)); E_aux = engine_Eaux(loc, city, daily_km, (ghi, T))
    return float((daily_km * c + E_aux) / (eta_pv * psh * KAPPA_PV_BASE * fT))

def max_selfsuff_km(loc, city=True, climate=None, A=None):
    """Max daily distance for f_ss = 1 with PV area A (default: as-built 11.6 m^2)."""
    A = A_skin if A is None else A
    ghi, T = _climate(loc, climate)
    psh = ghi.sum() / 1000.0 / 365.0
    c = whkm("P0", city=city) / 1000.0
    fT = engine_fT(loc, (ghi, T)); E_aux = engine_Eaux(loc, city, 50, (ghi, T))
    E_pv = A * eta_pv * psh * KAPPA_PV_BASE * fT
    return float((E_pv - E_aux) / c)

# ---------------- 7. ECONOMICS & GRID RELIEF ------------------------
# Residential electricity tariffs, converted at fixed exchange rates (see paper Table V):
#   Phoenix: Arizona average residential price 15.76 US c/kWh, May 2025 (U.S. EIA, quoted by
#            the Arizona Corporation Commission, 6 Aug 2025). Average price, incl. fixed charges.
#   Lucknow: UPPCL LMV-1 urban metered domestic, energy charge Rs 6.50/kWh for >300 kWh/month
#            (FY 2024-25 rate schedule; tariffs retained unchanged for FY 2025-26). Marginal rate.
#   London:  Ofgem price cap, electricity unit rate 26.32 p/kWh, 1 Oct-31 Dec 2026 (direct
#            debit, GB average; excludes VAT, which is waived to 31 Mar 2027). Marginal rate.
FX_INR_PER_USD = 94.5975     # RBI reference rate, 30 Jun 2026
FX_USD_PER_GBP = 1.3373      # GBP/USD close, 21 Oct 2026
PRICE = {"Phoenix": 0.1576,
         "Lucknow": 6.50 / FX_INR_PER_USD,
         "London": 0.2632 * FX_USD_PER_GBP}   # USD/kWh
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
# PV-only build: drop TEG (2500) and regenerative suspension (2000) AND the half of the
# wiring/structure/coatings item (600 of 1200) that serves them -> 9560 - 5100 = 4460.
PV_ONLY_COST = COST_ITEMS["PV skin (2.55 kWp @ ~$1.2/Wp incl. integration)"] \
             + COST_ITEMS["Multi-input MPPT / power electronics"] \
             + COST_ITEMS["HV wiring / structure / coatings"] * 0.5
def economics(loc, km, city, cost=None, climate=None):
    r = simulate(loc, km, city, climate=climate)
    saved_kwh = r['solar_used']; saved_usd = saved_kwh * PRICE[loc]
    c = SYSTEM_COST if cost is None else cost
    payback = c / saved_usd if saved_usd > 0 else float('inf')
    return dict(fss=r['fss'], grid_kwh=r['grid_kwh'], saved_kwh=saved_kwh,
                saved_usd=saved_usd, payback_yr=payback,
                payback_pvonly=PV_ONLY_COST / saved_usd if saved_usd > 0 else float('inf'),
                grid_relief_pct=100 * r['relief'])

# ---------------- WLTP reconstruction error vs official stats --------
def wltp_recon_error():
    official = {"Low": (3.095, 56.5), "Medium": (4.756, 76.6),
                "High": (7.162, 97.4), "ExtraHigh": (8.254, 131.3)}
    rows = {}
    for k in WLTC:
        v = build_phase(*WLTC[k]); dist = v.sum() / 1000.0
        do, vo = official[k]
        rows[k] = dict(dist=dist, dist_err=100 * (dist - do) / do,
                       vmax=v.max() * 3.6, vmax_off=vo)
    vfull = wltp_trace(); tot = vfull.sum() / 1000.0
    rows["TOTAL"] = dict(dist=tot, dist_err=100 * (tot - 23.266) / 23.266,
                         vmax=vfull.max() * 3.6, vmax_off=131.3)
    return rows

# ---------------- synthetic-climate error vs monthly normals ---------
def climate_error(loc):
    """Monthly + annual error of the synthetic series vs SATELLITE-DERIVED hourly TMY.
    Returns None if no TMY file is available for that location."""
    tmy = load_city_tmy(loc)
    if tmy is None:
        return None
    meas_ghi, _ = tmy
    lat, psh, Tm, Ta = LOCS[loc]
    syn_ghi, _ = hourly_climate(lat, psh, Tm, Ta)
    mh = np.minimum(((np.arange(8760) // 24) / 30.44).astype(int), 11)
    meas = np.array([meas_ghi[mh == m].sum() / 1000.0 / (np.sum(mh == m) / 24.0) for m in range(12)])
    syn = np.array([syn_ghi[mh == m].sum() / 1000.0 / (np.sum(mh == m) / 24.0) for m in range(12)])
    return dict(ann_err=100 * (syn.mean() - meas.mean()) / meas.mean(),
                monthly_mape=float(np.mean(np.abs(syn - meas) / meas) * 100),
                syn=syn, meas=meas)

# ---------------- 8. MULTI-OBJECTIVE SWEEP --------------------------
def pareto(loc="Phoenix", km=50, city=True, climate=None, areas=(8, 11.6, 15, 20),
           caps=(150, 200, 250, 300)):
    """Sweep PV area and pack size; return designs (grid, mass, cost, f_ss).
    climate=None: synthetic climate, grid energy averaged over 4 weather seeds.
    climate=(ghi, T): one satellite TMY year (no seed averaging)."""
    PV_COST = COST_ITEMS["PV skin (2.55 kWp @ ~$1.2/Wp incl. integration)"] / A_skin  # ~264 USD/m^2, same basis as economics()
    PACK_COST = 90.0    # USD per kWh (solid-state, 2030 assumption)
    rows = []
    for A in areas:
        for capk in caps:
            # mass feeds back into consumption: PV at 3.5 kg/m^2, pack at 2 kg/kWh (500 Wh/kg)
            mass = (M['P0'] - 500 - 41) + A * 3.5 + capk * 2.0
            if climate is None:
                grids = [simulate(loc, km, city, A_over=A, cap_over=capk, seed=sd,
                                  m_over=mass)['grid_kwh'] for sd in range(4)]
            r = simulate(loc, km, city, A_over=A, cap_over=capk, m_over=mass, climate=climate)
            if climate is not None:
                grids = [r['grid_kwh']]
            cost = A * PV_COST + capk * PACK_COST
            rows.append(dict(A=A, cap=capk, grid=float(np.mean(grids)), charges=r['charges'],
                             mass=mass, cost=cost, fss=r['fss'], relief=r['relief']))
    return rows

# ---------------- REAL-DATA VALIDATION (satellite-derived GHI) ---------------
def real_data_validation(scenarios=((50, True, "II 50km"), (100, False, "I 100km"))):
    """Tier 1: re-run with SATELLITE-DERIVED annual GHI + air temperature (Global Solar Atlas).
    Every value below is emitted by this function, so the paper's real-data claims
    are reproducible directly from the toolkit."""
    out = []
    for km, city, tag in scenarios:
        for l in LOCS:
            lat, psh0, Tm0, Ta = LOCS[l]
            f_assumed = simulate(l, km, city)['fss']
            LOCS[l] = (lat, REAL_PSH[l], REAL_TEMP[l], Ta)     # satellite-derived GHI + temp
            r = simulate(l, km, city); f_real = r['fss']
            LOCS[l] = (lat, psh0, Tm0, Ta)
            out.append(dict(scenario=tag, city=l, assumed=psh0, real=REAL_PSH[l],
                            f_assumed=round(f_assumed, 2), f_real=round(f_real, 2),
                            cls_assumed=classify(f_assumed), cls_real=classify(f_real),
                            class_changed=classify(f_assumed) != classify(f_real),
                            charges=r['charges']))
    return out

def tmy_validation(scenarios=((50, True, "II 50km"), (100, False, "I 100km"))):
    """Tier 2 (strongest): re-run the 8760-h engine on SATELLITE-DERIVED HOURLY TMY series
    (NSRDB for Phoenix and Lucknow, PVGIS for London), replacing the synthetic
    climate entirely. Cities whose TMY file is absent are skipped."""
    out = []
    for city_name in LOCS:
        tmy = load_city_tmy(city_name)
        if tmy is None:
            continue
        ghi, T = tmy
        for km, city, tag in scenarios:
            f_syn = simulate(city_name, km, city)['fss']
            r = simulate(city_name, km, city, climate=(ghi, T))
            r0 = simulate(city_name, km, city, climate=(ghi, T), pv_scale=0.0)
            out.append(dict(scenario=tag, city=city_name,
                            psh_tmy=round(ghi.sum() / 1000 / 365, 3),
                            ghi_tmy=round(ghi.sum() / 1000, 1),
                            tmean=round(float(T.mean()), 1),
                            f_syn=round(f_syn, 2), f_tmy=round(r['fss'], 2),
                            cls_tmy=classify(r['fss']),
                            class_changed=classify(f_syn) != classify(r['fss']),
                            charges=r['charges'], charges_nosolar=r0['charges'],
                            grid=round(r['grid_kwh']),
                            relief_pct=round(100 * r['relief'])))
    return out

def tmy_robustness(scenarios=((50, True, "II 50km"), (100, False, "I 100km"))):
    """Phoenix f_ss across the NSRDB TMY-2022/2023/2024/2025 releases (inter-release spread)."""
    out = []
    for yr, path in TMY_RELEASES.items():
        if not os.path.exists(path):
            continue
        ghi, T = load_tmy(path)
        for km, city, tag in scenarios:
            r = simulate("Phoenix", km, city, climate=(ghi, T))
            out.append(dict(release=yr, scenario=tag, psh=round(ghi.sum() / 1000 / 365, 3),
                            fss=round(r['fss'], 3), charges=r['charges'],
                            grid=round(r['grid_kwh'])))
    return out

def gap_decomposition(km=50, city=True):
    """Split the synthetic -> TMY f_ss gap into
       MAGNITUDE    = f(synthetic) - f(synthetic rescaled to the TMY's own annual GHI and
                      annual-mean temperature), and
       DISTRIBUTION = f(rescaled synthetic) - f(TMY)  (hour-to-hour / day-to-day pattern).
    Using the TMY's own annual totals (not Global Solar Atlas) keeps the two parts
    independent when the databases disagree (Lucknow: NSRDB GHI +6.8%, mean T +1.9 C vs GSA)."""
    out = {}
    for l in LOCS:
        tmy = load_city_tmy(l)
        if tmy is None:
            continue
        ghi, T = tmy
        lat, psh0, Tm0, Ta = LOCS[l]
        f_syn = simulate(l, km, city)['fss']
        LOCS[l] = (lat, ghi.sum() / 1000.0 / 365.0, float(T.mean()), Ta)
        f_mag = simulate(l, km, city)['fss']
        LOCS[l] = (lat, psh0, Tm0, Ta)
        f_t2 = simulate(l, km, city, climate=tmy)['fss']
        out[l] = dict(f_syn=f_syn, f_mag=f_mag, f_t2=f_t2,
                      magnitude=f_syn - f_mag, distribution=f_mag - f_t2,
                      total=f_syn - f_t2)
    return out

def design_levers_tmy(loc="Phoenix", km=50, city=True):
    """Sec. V-D numbers on the satellite TMY: kappa sweep, kappa needed for the quasi tier,
    eta_regen 0.72, suspension sweep, area for f_ss = 1 (with mass feedback), pack sweep."""
    t = load_city_tmy(loc)
    out = {}
    out["kappa"] = {l: [simulate(l, km, city, kappa=k, climate=load_city_tmy(l))["fss"]
                        for k in (0.60, 0.70, 0.80)] for l in LOCS}
    ks = np.linspace(0.5, 1.2, 29)
    fk = [simulate(loc, km, city, kappa=k, climate=t)["fss"] for k in ks]
    out["kappa_for_quasi"] = float(np.interp(0.90, fk, ks))
    out["regen_072"] = (whkm("P0", city=city), whkm("P0", city=city, eta_regen=0.72),
                        simulate(loc, km, city, climate=t)["fss"],
                        simulate(loc, km, city, eta_regen=0.72, climate=t)["fss"])
    out["susp"] = regen_susp_sensitivity(loc, km, city, climate=t)
    A = np.linspace(12, 17, 51)
    fA = [simulate(loc, km, city, A_over=a, climate=t,
                   m_over=(M["P0"] - 541) + a * 3.5 + 500)["fss"] for a in A]
    out["area_for_fss1"] = float(np.interp(1.0, fA, A))
    out["pack"] = pareto(loc, km, city, climate=t, areas=(11.6, 15), caps=(150, 200, 250))
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

    print("\n=== 7. kappa_pv SENSITIVITY (Scenario II, annual f_ss, idealized climate; TMY values below) ===")
    for loc in LOCS:
        row = [f"{simulate(loc,50,True,kappa=k)['fss']:.2f}" for k in (0.60, 0.70, 0.80)]
        print(f"    {loc:8s} kappa=0.60/0.70/0.80 -> f_ss = {' / '.join(row)}")

    print("\n=== REAL-DATA VALIDATION TIER 1: satellite-derived annual GHI+temp (Global Solar Atlas) ===")
    rows = real_data_validation()
    for r in rows:
        flag = "CLASS CHANGED" if r['class_changed'] else "class unchanged"
        print(f"    {r['scenario']:8s} {r['city']:8s} assumed={r['assumed']:.2f} "
              f"satellite-derived={r['real']:.3f} -> f_ss {r['f_assumed']:.2f}->{r['f_real']:.2f} "
              f"({r['cls_real']}) [{flag}]")
    nch = sum(r['class_changed'] for r in rows)
    print(f"    SUMMARY: {len(rows)-nch}/{len(rows)} classes unchanged; "
          f"max |df_ss| = {max(abs(r['f_real']-r['f_assumed']) for r in rows):.2f}")

    print("\n=== REAL-DATA VALIDATION TIER 2: satellite-derived HOURLY TMY (NSRDB / PVGIS) ===")
    trows = tmy_validation()
    if not trows:
        print("    (no TMY files found under data/ -- see TMY_FILES)")
    for r in trows:
        flag = "CLASS CHANGED" if r['class_changed'] else "class unchanged"
        print(f"    {r['scenario']:8s} {r['city']:8s} TMY GHI={r['ghi_tmy']:.1f} kWh/m2/yr "
              f"(PSH={r['psh_tmy']:.3f}) Tmean={r['tmean']:.1f}C -> f_ss syn {r['f_syn']:.2f} "
              f"-> TMY {r['f_tmy']:.2f} ({r['cls_tmy']}) [{flag}] charges {r['charges_nosolar']}"
              f"->{r['charges']}/yr, grid {r['grid']} kWh/yr, relief {r['relief_pct']}%")
    print("    database agreement (TMY annual GHI vs Global Solar Atlas GHI):")
    for l in LOCS:
        tmy = load_city_tmy(l)
        if tmy is not None:
            ghi_ann = tmy[0].sum() / 1000.0     # (do not reuse the name `g`: gravity)
            print(f"      {l:8s} {ghi_ann:7.1f} vs {GSA[l][2]:7.1f} kWh/m2/yr "
                  f"({100*(ghi_ann-GSA[l][2])/GSA[l][2]:+.1f}%)")

    print("\n=== GAP DECOMPOSITION (Scen. II): synthetic -> synthetic at TMY totals (magnitude) -> TMY (distribution) ===")
    for l, d in gap_decomposition().items():
        print(f"    {l:8s} f_ss {d['f_syn']:.3f} -> {d['f_mag']:.3f} -> {d['f_t2']:.3f}: "
              f"magnitude {d['magnitude']:+.3f}, distribution {d['distribution']:+.3f}, "
              f"total {d['total']:+.3f}")

    print("\n=== TMY INTER-RELEASE ROBUSTNESS (Phoenix NSRDB TMY-2022..2025) ===")
    for r in tmy_robustness():
        print(f"    TMY-{r['release']} {r['scenario']:8s} PSH={r['psh']:.3f} f_ss={r['fss']:.3f} "
              f"charges={r['charges']}/yr grid={r['grid']} kWh/yr")

    print("\n=== DESIGN LEVERS ON THE SATELLITE TMY (paper Sec. V-D, Phoenix II) ===")
    dl = design_levers_tmy()
    for l, v in dl["kappa"].items():
        print(f"    {l:8s} kappa=0.60/0.70/0.80 -> f_ss = " + " / ".join(f"{x:.2f}" for x in v))
    print(f"    Phoenix kappa needed for f_ss = 0.90: {dl['kappa_for_quasi']:.2f}")
    w0, w1, f0, f1 = dl["regen_072"]
    print(f"    eta_regen 0.60 -> 0.72: city {w0:.0f} -> {w1:.0f} Wh/km, f_ss {f0:.3f} -> {f1:.3f}")
    print("    suspension 50/100/150/200 W -> f_ss " + " / ".join(f"{v:.3f}" for v in dl["susp"].values()))
    print(f"    PV area for f_ss = 1 (full simulation, mass fed back): {dl['area_for_fss1']:.2f} m^2")
    for r in dl["pack"]:
        print(f"    A={r['A']:4.1f} cap={r['cap']:3d}: f_ss={r['fss']:.3f} relief={100*r['relief']:.1f}% "
              f"grid={r['grid']:5.0f} kWh/yr (lumpy: plug-ins x refill size) "
              f"mass={r['mass']:6.1f} kg plug-ins={r['charges']}")

    print("\n=== TEG MASS-vs-OUTPUT TRADEOFF ===")
    t = teg_tradeoff()
    print(f"    35 kg -> {t['kwh_if_battery']:.1f} kWh pack; TEG needs "
          f"{t['days']:.0f} days ({t['years']:.1f} yr) to generate that at {E_TEG} kWh/day")

    print("\n=== REGEN-SUSPENSION SENSITIVITY (Phoenix II, f_ss, idealized climate; TMY values above) ===")
    print("   ", {k: round(v, 3) for k, v in regen_susp_sensitivity().items()})

    print("\n=== NO-SOLAR BASELINE charges/yr (for honest grid-relief) ===")
    for scen, (km, city) in [("II 50km", (50, True)), ("I 100km", (100, False))]:
        for loc in LOCS:
            base = simulate(loc, km, city, pv_scale=0.0)['charges']
            solar = simulate(loc, km, city)['charges']
            print(f"    {scen} {loc:8s}: no-solar {base:3d}/yr -> solar {solar:3d}/yr "
                  f"({100*(base-solar)/base:.0f}% fewer)")

    print("\n=== 6. DESIGN INVERSION (closed form, battery-side c) ===")
    for city, tag, km in [(True, "II 50km", 50), (False, "I 100km", 100)]:
        print(f"  Scenario {tag}:")
        for loc in LOCS:
            tmy = load_city_tmy(loc)
            need = required_pv_area(km, city, loc); mx = max_selfsuff_km(loc, city)
            line = (f"    {loc:8s} synthetic: A_req = {need:5.1f} m^2, D_max = {mx:4.1f} km/day")
            if tmy is not None:
                need_t = required_pv_area(km, city, loc, climate=tmy)
                mx_t = max_selfsuff_km(loc, city, climate=tmy)
                line += f" | TMY: A_req = {need_t:5.1f} m^2, D_max = {mx_t:4.1f} km/day"
            print(line)

    print("\n=== 7. ECONOMICS & GRID RELIEF (tariffs USD/kWh: " +
          ", ".join(f"{k} {v:.4f}" for k, v in PRICE.items()) + ") ===")
    for clim in ("synthetic", "TMY"):
        for scen, (km, city) in [("II 50km", (50, True)), ("I 100km", (100, False))]:
            for loc in LOCS:
                c = load_city_tmy(loc) if clim == "TMY" else None
                e = economics(loc, km, city, climate=c)
                print(f"    {clim:9s} {scen} {loc:8s}: relief {e['grid_relief_pct']:4.1f}% "
                      f"({e['saved_kwh']:5.0f} kWh/yr), save ${e['saved_usd']:5.0f}/yr, "
                      f"payback {e['payback_yr']:4.1f} yr, PV-only {e['payback_pvonly']:4.1f} yr")

    print("\n=== 8. MULTI-OBJECTIVE (Phoenix II, satellite TMY, mass fed back into consumption) ===")
    for r in pareto(climate=load_city_tmy("Phoenix")):
        print(f"    A={r['A']:4.1f} cap={r['cap']:3d}: grid={r['grid']:5.0f} kWh/yr "
              f"mass={r['mass']:5.0f} kg cost=${r['cost']:5.0f} f_ss={r['fss']:.3f}")

    print("\n=== COST BREAKDOWN (USD add-on) ===")
    for k, v in COST_ITEMS.items():
        print(f"    ${v:5d}  {k}")
    print(f"    ${SYSTEM_COST:5.0f}  TOTAL as-specified;  ${PV_ONLY_COST:.0f}  PV-only "
          f"(drop TEG 2500 + regen susp 2000 + half of wiring/structure 600)")

    print("\n=== WLTP RECONSTRUCTION ERROR vs official WLTC 3b ===")
    for k, v in wltp_recon_error().items():
        print(f"    {k:10s} dist={v['dist']:6.3f} km (err {v['dist_err']:+.2f}%)  vmax={v['vmax']:5.1f} (off {v['vmax_off']})")

    print("\n=== SYNTHETIC CLIMATE ERROR vs SATELLITE-DERIVED hourly TMY ===")
    for loc in LOCS:
        e = climate_error(loc)
        if e is None:
            print(f"    {loc:8s} (no TMY file)")
        else:
            print(f"    {loc:8s} annual err {e['ann_err']:+.1f}%, monthly MAPE {e['monthly_mape']:.1f}%")
