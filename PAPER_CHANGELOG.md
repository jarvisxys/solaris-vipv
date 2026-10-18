# Paper changelog

Every decision that changes a number, claim or reference in the journal paper,
newest first, with date and reason.

## 2026-10-19 · P8 / E8 Unity twin and validation

Sources: `twin/unity/SOLARIS-Twin/Assets/SolarisTwin/`, `twin/unity/README.md` (Section 6
walkthrough), `src/solaris/twin_io/`, `src/solaris/imagery/mapillary.py`,
`configs/experiments/e8.yaml`, `results/e8/` (rules `e8_export`, `e8_unity`,
`e8_twin_agreement`, `e8_mapillary_fetch`, `e8_mapillary_svf`).

- **Unity twin built headless (author decision).** Unity 6000.3.6f1 from the Universal 3D
  (URP) template, with Cesium for Unity 1.26.0, glTFast 6.20.0 and Recorder 5.1.7.
  - The P3 tiles are imported as assets with glTFast (author decision, guide step 5): 140
    surface + 140 tree tiles around R-DENSE plus the 1 km shading reach.
  - glTFast mirrors the x axis on import; the scene root undoes it with a 180° turn. The
    flip is detected from the tile bounding boxes, not assumed.
  - `Library/` is a junction outside OneDrive.
  - PhysX warns about Delatin triangles longer than 500 m on 8 flat tiles. The Embree
    comparison below shows it does not affect the rays.
- **Ground control passes.** At five NGS pavement marks in the corridor, Unity's surface
  lies within 0.14 m of the lidar DSM (limit 0.5 m). It equals the Embree height of the
  same meshes to the millimetre.
- **E8 Unity vs Python (120 R-DENSE trip-dates, 15.5 M sample-seconds valid in both).**

  | Pair | Per-sample agreement | Trips within 2 pp | Max lit-fraction difference |
  |---|---|---|---|
  | Python raster vs Unity | **99.14 %** (gate ≥ 97 %) | 119 / 120 | 2.37 pp |
  | Embree on the same meshes vs Unity | 99.994 % | 120 / 120 | 0.02 pp |
  | Python raster vs Unity, beyond ±1° of the horizon line | 99.69 % | 120 / 120 | 0.65 pp |

  - **The one trip outside 2 pp is explained.** R-DENSE southbound at 14:00 on 21 March
    differs by 2.37 pp; three more southbound 14:00 trips sit at 1.5–2.0 pp.
  - The cause is surface representation, not Unity: Embree on the same meshes reproduces
    Unity to 0.02 pp.
  - Mechanism: the raster engine treats each 0.5 m pixel as a flat-topped column, while the
    mesh interpolates between pixel centres and so rounds roof edges by up to half a pixel.
  - Rays that graze a roof edge change state between the two. Mostly the raster says
    building and the mesh says lit (58 % of disagreements, against 25 % the other way), so
    Unity's lit fraction is on average 0.38 pp higher.
  - The ±1° horizon-line band (E1's convention) is 3.2 % of sample-seconds but holds 65 %
    of the disagreements. On the afternoon southbound trips the car drives along building
    shadow edges for long stretches, which doubles its share of the band.
  - Outside the band every trip is within 0.65 pp.
  - The paper should report both rows and this mechanism. **Proposed:** "Unity and Python
    agree on 99.1 % of sample-seconds; trip lit fractions agree within 2.4 pp, and within
    0.65 pp outside ±1° of the horizon line."
- **Mapillary SVF comparison: built, not yet run.** The module, rules and tests exist.
  - Panoramas come from Graph API v4, 15 per route on R-DENSE and R-MIXED.
  - The sky mask comes from Mapillary's own `nature--sky` segmentation (vector tiles, decoded
    in-repo).
  - SVF is computed with the same cosine-weighted definition as the engine.
  - The live fetch needs `MAPILLARY_TOKEN` (open). E8's "SVF error reported" item is
    pending until then.
- **Open author items (not computable here).** The literature bracket (Hoth et al., Berlin;
  San José et al.; refs [12], [14]); and asking ASU's heat-research groups for a mobile
  radiation transect in the AOI. Until measured data exist the paper says "cross-verified,
  simulation-based digital twin", not "physically validated".
- **Render inputs exported.** The HUD PV for R-DENSE 08:00 on 21 December (TMY, case C) has
  a mean of 46 W and a peak of 78 W. Display only.

## 2026-10-18 · P7 / E5, E6 annual waterfall and electrical mismatch

Sources: `configs/schedules/archetypes.yaml`, `configs/experiments/e5.yaml`, `e6.yaml`,
`configs/vehicle/electrical_p0.yaml`, `src/solaris/trajectory/schedules.py`, `src/solaris/annual.py`,
`src/solaris/pv/{electrical,series}.py`, `src/solaris/shading/parked.py`, `results/e5/`,
`results/e6/` (rules `e6_mismatch`, `e5_annual`).

- **Archetypes (author decisions).** Each archetype keeps the demand of its B0 scenario, driven
  every day, so the waterfall changes only the harvest:
  - A1–A3 use Scenario II (50 km/day, WLTP city) with trips at 08:00 and 17:00, and start from
    B0 II (f_ss 0.779).
  - A4 uses Scenario I (100 km/day, WLTP combined) with trips at 08, 10, 12, 14 and 16 h, and
    starts from B0 I (0.389).
  - On weekends, daytime parking moves to the evening site.
  - The 17:00 trip replays the frozen 16:00 SUMO traces one hour later (P6 stays frozen).
  - Each trip hour drives the conference time split, drive_fraction × 3600 s, so driving and
    parked seconds close to 3600 in every hour. The routes share that time in order; each
    replays its medium-demand trace, out then back.
  - Parked headings are averaged: P2 (curb) N/S, the other sites N/E/S/W.
- **E6 string model (placeholder layout).**
  - Each facet is one module on its own MPPT input. A cell is one 0.25 m facet sample, and the
    cells form three bypass-diode substrings.
  - Cell parameters: CEC SunPower SPR-X22-360 (22.1 %), per cell and area-scaled; pvlib
    bishop88 with reverse-bias breakdown.
  - **Gate passes:** under uniform light the string MPP equals n_cells × the cell MPP within
    7 × 10⁻⁵ (limit 10⁻³).
- **E6 result: mismatch is the steepest loss per shaded cell.**
  - One shaded cell already sends its substring through the bypass diode: F_mm is about 0.73
    at s ≈ 0.03 and falls to about 0.3 at s = 0.3–0.6.
  - Fit (energy-weighted, driving and parking weighted equally; R² 0.84):
    F_mm = 1 − 1.490 s^0.462 (1 − s)^0.578.
  - A two-parameter polynomial, 1 − s(1 − s)(a + bs), was tried first and rejected. It missed
    the shoulder at small s and understated the loss by 0.6 points (driving) and 1.2 points
    (parking).
  - Energy-weighted F_mm: R-DENSE trips 0.958; P2 curb 0.96; P3 tree-dappled driveway 0.56–0.73.
  - **The size depends on the placeholder layout** (three bypass diodes per facet module,
    0.25 m cells). The paper must state this. More diodes or per-substring MPPT would reduce it.
- **E5 energy balance closes.** Three checks run for every archetype × weather × step:
  1 s / 5 min energy vs hourly bins; driving + parked seconds = 3600 in every hour; and the SoC
  loop's pack balance. The worst residual is 1 × 10⁻¹⁴ (limit 10⁻³). Step B0 reproduces Table B0
  exactly.
- **E5 headline waterfall (Phoenix, measured TMY), f_ss:**

  | Step | A1 commuter | A2 downtown street | A3 downtown shade canopy | A4 fleet 100 km |
  |---|---|---|---|---|
  | Table B0 | 0.779 | 0.779 | 0.779 | 0.389 |
  | + trip hours | 0.780 | 0.780 | 0.780 | 0.390 |
  | + Perez chain, Faiman | 0.782 | 0.782 | 0.782 | 0.394 |
  | + facets (schedule headings) | 0.634 | 0.634 | 0.632 | 0.320 |
  | + parking shade | 0.517 | 0.288 | 0.393 | 0.252 |
  | + driving buildings | 0.509 | 0.272 | 0.377 | 0.243 |
  | + driving trees | 0.507 | 0.271 | 0.376 | 0.242 |
  | + electrical mismatch | **0.479** | **0.239** | **0.313** | **0.239** |
  | Charges/yr, B0 → final | 6 → 15 | 6 → 22 | 6 → 20 | 35 → 44 |
  | Balanced relief, final | 47.9 % | 23.9 % | 31.3 % | 23.9 % |
  | Grid energy, final (kWh/yr) | 2666 | 3908 | 3540 | 7779 |

  - Facets (−0.15) and parking (−0.12 to −0.35) carry the loss, as the guide expected (risk
    table: "facets and parking carry C1–C3").
  - Driving shade costs 0.01–0.02 and trees under 0.002.
  - Grid energy is not monotonic in harvest (A4: mismatch 7779 < trees 7797 kWh) because of
    the recharge-to-80 % policy (see the B0 note).
- **Sub-hourly sensitivity (A1, A2; final f_ss).**

  | Run | A1 | A2 |
  |---|---|---|
  | TMY, hourly | 0.479 | 0.239 |
  | NSRDB 2023 averaged to hours | 0.476 | 0.238 |
  | NSRDB 2023 at 5 min | 0.477 | 0.239 |

  - Year effect: +0.003 / +0.002.
  - TMY interpolation limit: hourly data understates f_ss by 0.001 (final step) and by at most
    0.004 at the open-sky chain step (0.5 %), because each hour's DNI is held while the sun
    moves.
  - Hourly TMY is adequate for the annual waterfall.

## 2026-10-18 · P6 / E3, E4 routes, traffic, driving and parking shading

Sources: `routes/select_routes.py`, `routes/v2/` (MANIFEST), `src/solaris/trajectory/`,
`results/p6/`, `results/e3/`, `results/e4/`, `results/p3/freshness_applied.json`
(rules `routes_select`, `sumo_traces`, `e3_driving`, `e4_parking`).

- **Finding, power lines in the DSM (P3 corrected).** E3 showed 15–27 % beam shading on the
  most open route at noon. The cause was overhead power lines, poles and signal arms along
  the arterials. The lidar sees them as 1-pixel lines about 10 m up; joined into long blobs,
  they passed the 4 m² filter and acted as walls. Height-rule structures narrower than
  1.5 m are no longer buildings (morphological opening; footprint buildings and strips
  joined to them are kept). Every P3 product, E1 and the routes were rebuilt. "Demolished"
  freshness candidates fell from 102 to 57.
  The author's 26 confirmations carry over:
  - Most matched a candidate within 1–20 m.
  - One rejection lost its candidate, so there is nothing to apply.
  - Two demolitions use the lidar blob at the confirmed spot, because their candidates fell
    below the thresholds once the wires were removed.

  The re-mapping is logged in `results/p3/freshness_applied.json`. Reason: a classification
  artefact that biased every shading result on arterials.
- **Routes v2 (v1 superseded).** routes/v1 had been selected on the DSM with power-line
  walls. routes/v2 applies the same rule to the corrected DSM: every named trunk / primary
  / secondary arterial in the AOI, 45,601 points at 10 m, 128 candidate 8 km windows.
  - **Open:** Southern Ave (E–W, mean SVF 0.961).
  - **Dense:** Central Ave (N–S, 0.740; overlaps 57 % of the guide's seed loop).
  - **Mixed:** 19th Ave (N–S, mean 0.902, highest variance in the median band).
  - **R-TUNNEL:** the I-10 Deck Park Tunnel (5.6 km, 822 m covered), a covered-segment check
    outside the E3 matrix.

  v1 picked the same three streets, so the selection is robust to the fix. The guide's seeds
  (Baseline Rd, Camelback Rd) were not the metric's extremes, and the paper uses the
  measured choice.
- **Parking sites** (chosen from SVF by the guide's criteria):

  | Site | Description | SVF |
  |---|---|---|
  | P1 | open lot near Chase Field | 0.95 |
  | P2 | Central Ave west curb between Adams and Monroe, a car-width off the building face | 0.336 |
  | P3 | Encanto–Palmcroft driveway, canopy 2.5 m away | 0.48 |
  | P4 | top deck of a 19 m downtown garage | 0.91 |
  | P5 | the P1 stall under a modelled 4 m × 3 m × 6 m shade roof | — |

  P2 needed three corrections: open ground only, a minimum 4 m off the building face, and
  the avenue's own axis (OSM merges ways that jog onto couplets). Without them, the
  minimum-SVF rule had picked points inside arcades and on sidewalks hugging walls.
- **SUMO traces.** SUMO 1.28 runs in its own conda env. The network comes from OSM
  (motorway to tertiary, guessed signals), with three demand seeds (randomTrips periods 6,
  3 and 1.5 s) and 5 departures from 08:00 to 16:00, giving 120 ego traces at 1 Hz with 0
  teleports. Ego routes chain shortest paths between via points every 400 m along the
  frozen route. sumolib's map matching gave undrivable edge sequences through downtown
  couplets: 70–90 min trips with 300 s teleports. Trip times vary only modestly across demand seeds
  (a few percent to ~9 %), so the arterials stay below saturation even at high demand; the paper
  states this.
- **E3 driving (360 trips: 3 routes × 2 directions × 5 departures × 4 days × 3 demand seeds;
  1 Hz).** PV energy relative to open sky, matching TMY day (clear sky in brackets):

  | Route | Buildings (B / A) | Buildings + trees, τ = 0.03 (C / A) | Beam-shaded time (C) |
  |---|---|---|---|
  | R-OPEN | 0.93 (0.91) | 0.91 (0.89) | 10 % |
  | R-MIXED | 0.90 (0.88) | 0.90 (0.87) | 12 % |
  | R-DENSE | 0.72 (0.68) | 0.71 (0.67) | 32 % |

  - Trees cost a further 0.5–2 %; raising τ to 0.3 recovers less than half of that.
  - Shading peaks at the 08:00 and 16:00 departures and on 21 December. On R-OPEN at noon it
    is 2–5 % (intersections, overpasses).
  - R-TUNNEL's covered seconds (62–71 s) block beam and sky as designed.
  - Correction during the run: case B had treated trees as opaque for the beam. It now
    ignores trees (τ = 1), and a test asserts A ≥ B ≥ C on every trip.
- **E4 parking passes.** SOLWEIG agreement at P1–P3 is ≥ 96.7 % (required ≥ 95 %). Annual
  F_park, averaged over headings (τ = 0.03):

  | Site | F_park |
  |---|---|
  | P1 open lot | 0.94 |
  | P2 canyon curb | 0.32 |
  | P3 tree-shaded driveway | 0.45 |
  | P4 garage deck | 0.88 |
  | P5 shade canopy | 0.64 |

  Heading moves F_park by up to 0.05 at P2 and 0.10 at P3.

## 2026-10-18 · P5 / E2 facet orientation, open sky

Sources: `configs/vehicle/solaris_p0.yaml`, `src/solaris/vehicle/`, `src/solaris/pv/`,
`tests/test_vehicle.py`, `results/e2/table_e2.csv`, `results/e2/table_e2_facets.csv`,
`results/e2/summary_e2.json`, `twin/exchange/facet_samples.csv` (rules `e2_facets`, `facet_samples`).

- **Skin layout: the guide's placeholder (author decision).** Roof 4.4 m² at 2°, hood 1.6 m²
  at 10°, tailgate glass 0.6 m² at 60°, two side panels of 2.5 m² at 85°, sampled on a
  0.25 m grid. The intended layout is unconfirmed, so the paper must label this layout a
  placeholder and report case 2d (roof only) as the bound.
- **E2 gate passes.** Case 2b, the 11.6 m² skin laid horizontal through the new irradiance
  chain, equals 2a within −0.031 % PV energy and −0.030 % f_ss in both scenarios (limit
  ±0.5 %). The chain is pvlib Perez G_f at the TMY's own stamps, with solar position from SPA.
- **Definition of 2b (author decision).** 2b keeps the conference cell-temperature rule
  (T + 25 K per kW/m²). Faiman cell temperature enters as its own step, 2b+F: +0.55 %
  (Scenario II) and +0.60 % (Scenario I) PV energy, because pvlib's open-rack coefficients
  (u0 25, u1 6.84) plus vehicle speed cool the cells more than the conference rule. With
  Faiman inside 2b the gate would be missed by 0.02–0.06 points. Reason: the gate tests the
  irradiance chain, and the E5 waterfall must show the thermal change separately.
- **The headline correction: facet orientation.** On the measured TMY, with the
  heading-averaged placeholder skin (case 2c):

  | Scenario | f_ss, conference flat GHI (2a) | f_ss, facet skin (2c) | f_ss, roof only (2d) | Charges/yr (2a → 2c → 2d) |
  |---|---|---|---|---|
  | II, 50 km/day | 0.779 | **0.635** | 0.314 | 6 → 10 → 20 |
  | I, 100 km/day | 0.389 | **0.317** | 0.157 | 35 → 39 → 48 |

  F_geo = E_facets / E_flat = 0.805. Balanced grid relief (Scenario II) falls from 77.9 % to
  63.5 %. Each facet's incident irradiation relative to GHI, averaged over headings:
  roof 1.00, hood 0.99, tailgate 0.74, side panels 0.56. Parked or driven facing N or S, f_ss
  is 0.652; facing E or W, 0.616. Reason: workflow guide Sec. 0, item 2 (a vertical panel is
  not GHI).
- **Thermal sensitivity.** Body-bonded coefficients lower 2c's f_ss (Scenario II) to 0.627
  (close-mount, u0 20, u1 6) or 0.591 (semi-integrated, u0 20, u1 0). The journal default
  stays pvlib's Faiman default, as the guide specifies.
- **Headings in 2c.** 2c averages 36 headings because schedules A1–A4 arrive in P7, which
  will replace this with schedule headings (author decision).
- **Core extension.** `core.simulate` gained `pv_kwh=`, an 8760-h PV series that replaces
  the flat-GHI model. Without it the core is unchanged: Table B0 regenerates byte-identical,
  and a test checks the hook bit-identical against the conference formula.

## 2026-10-18 · P4 / E1 shading engines verified

Sources: `src/solaris/shading/`, `src/solaris/pv/irradiance.py`, `configs/experiments/e1.yaml`,
`tests/test_shading.py`, `results/e1/table_e1.csv`, `results/e1/summary_e1.json`
(rule `e1_verification`).

- **E1 passes: 40 of 40 checks.** The guide's E1 thresholds are all met (Sec. 5):
  - **Sun position.** pvlib SPA is within 2 × 10⁻⁶° of the NREL SPA reference vector. Against
    NOAA's solar-calculator algorithm at five Phoenix times it is within 0.008° (angle
    between the sun vectors).
  - **Transposition.** An unshaded horizontal facet returns GHI to 1 × 10⁻¹³ W/m², and a
    vertical south facet matches pvlib's Perez total to 3 × 10⁻¹³ W/m².
  - **Shadow length.** At α = 15°, 30° and 60°, points at H/tan α ± 1 m from a 20 m box are
    classified correctly by the raster horizon engine, the raster shadow map and the mesh engine.
  - **Canyon SVF.** At H/W = 0.5, 1 and 2 the raster engine is within 0.002 of
    cos(arctan(2H/W)) and the mesh engine within 0.004 (tolerance 0.01).
  - **Raster vs mesh**, on 1,000 random downtown points (1 km², Central Ave towers) under 43 sun
    positions across the solstices and equinoxes: beam agreement is 99.6 %, against ≥ 98 %
    required, after excluding 3 % of cases within 1° of a horizon line. Mean |ΔSVF| is 0.008
    (median 0.005, p95 0.023), against < 0.02 required.
  - **SOLWEIG** (UMEP 3.0 Shadow Generator) on the same 1 km² at 08:00, 12:00 and 16:00 on the
    four days: pixel agreement is 98.0–99.3 %, against ≥ 95 % required. Our engine shades
    −0.03 to +1.0 percentage points more pixels than SOLWEIG.

  Reason: the E1 gate; annual runs may now start (CLAUDE.md).
- **Method: raster engine.** The engine marches horizons over dsm.tif (buildings, terrain,
  bridges) and over max(dsm, dem + cdsm) (trees opaque). It uses 360 azimuth bins with a
  0.5° elevation mask, out to 1,000 m, in half-pixel steps to 50 m and then steps of 0.5 % of
  the distance. Azimuths are rotated per point by the meridian convergence (−0.59° downtown).
  The mesh engine casts Embree rays against the P3 .glb tiles in the true-north ENU frame. It
  needs no convergence correction, so the cross-engine agreement checks the correction independently.
- **Interpretation of "|ΔSVF| < 0.02".** It is applied to the mean over the 1,000 points.
  Individual points differ by up to 0.16. Reason: the guide does not say whether the
  threshold is per point or on average.
- **Cross-engine sample: points 1 m or more from any building.** A point within 0.5 m of a
  facade sits inside the mesh's wall slope: heightfield vertices lie at pixel centres, so
  every upward ray hits the wall and the mesh reports SVF 0 where the raster gives up to
  0.39. No vehicle roof can be that close to a wall. The same exclusion must apply in E8
  (Unity uses these meshes). Reason: a mesh-representation artefact, not a shading difference.
- **SOLWEIG setup.** `solweig` is not on PyPI, so the reference is UMEP for Processing 3.0 in
  QGIS 3.44, run through `qgis_process`. UMEP's daily-shading routine fails under QGIS's
  numpy 2.4.6; two lines were patched locally, as recorded in `shading/solweig.py`. SOLWEIG
  uses 3 % canopy transmissivity and a 25 % trunk zone, and our shadow map uses the same
  trunk zone for this comparison.

## 2026-10-18 · P3 freshness confirmed

Sources: `configs/site/freshness_v1.yaml`, `results/p3/summary_geometry.json` (rule `geom_dsm`).

- **City model updated to the present.** The author checked the 45 tallest and largest of the
  204 freshness candidates against current imagery (Esri World Imagery, QGIS):
  - **14 buildings added.** They are burnt into `dsm.tif` as footprint × floors × 3.5 m.
    Among them are a 23-floor tower at 33.4572, −112.0758 and an 18-floor block at
    33.4549, −112.0732, both on R-DENSE.
  - **12 structures demolished**, lowered to the DEM. One of them is a 2020–21 tower crane
    whose 110 m jib the lidar recorded beside a building under construction (33.4473, −112.0702).
  - **19 rejected:** standing bridges and their railings, parking decks, dense trees, a
    glass roof and a tall palm.
  - **159 candidates were not reviewed** and stay as in the lidar.

  The meshes were rebuilt from the updated `dsm.tif`. Reason: guide Sec. 2 step 8; the
  paper reports this list.
- **Method change.** A confirmed addition only raises the DSM, as max(lidar DSM, ground +
  floors × 3.5 m). It never lowers taller lidar structures inside its footprint: candidate
  A-E400317-N3706332 holds a 38.9 m parking structure inside a 4-floor footprint. Reason:
  the step 8 burn must not delete standing structures.
- **Finding, freshness detector.** Of the 16 rejected "demolished" candidates, 8 are bridges
  or bridge railings. The OSM bridge polygons, buffered to tag widths, are narrower than the
  lidar decks, so deck edges survive the bridge mask. Shading is unaffected, since bridges
  stay in the DSM; only the candidate list is noisier.

## 2026-10-16 · P3 geometry

Sources: `src/solaris/geometry/`, `geom/README.md`, `tests/test_geometry.py`,
`results/p3/summary_geometry.json`, `results/p3/table_ground_control.csv`,
`results/p3/table_freshness.csv`, `twin/exchange/enu_origin.json` (rules `geom_*`).

- **City model built.** The AOI is the bounding box of the seed routes and parking sites
  plus 1 km: 238 km², 952 tiles of 500 m (author decision: full box rather than corridors).
  USGS 3DEP AZ_MaricopaPinal_2020 gives 5.28 billion points after noise and withheld
  points are removed, 22.2 points/m². `dsm.tif`, `cdsm.tif` and `dem.tif` are 0.5 m,
  EPSG:26912 + NAVD88. Classes: 25.4 % building, 4.4 % tree, 70.2 % ground. DSM holes
  (no return) cover 0.75 % and take the DEM, flagged in `dsm_holes.tif`. Sources: NAIP
  2021 (flown 14 Oct–12 Nov 2021, matching the lidar), Overture release 2026-09-23.1
  (135,145 buildings), OSM covered ways (911 bridges, 481 covered, 364 tunnels).
- **Vertical datum checked.** The EPT carries NAVD88 heights, not ellipsoidal ones (ground
  downtown 331.7 m). Against 87 NGS marks with adjusted heights, DEM − mark has median
  −0.11 m and MAD 0.14 m; 69 % agree within 0.5 m. The 22 marks off by more than 1 m sit on
  structures or have hand-held positions; they are flagged in the table, not dropped.
- **Unity frame.** The ENU origin is Central Ave & Washington St: ground 331.66 m NAVD88,
  301.74 m ellipsoidal (GEOID18). The meshes have 193 M surface faces and 55 M tree faces
  (0.25 m Delatin error), 5.3 GB of `.glb`. Raycasts under bridges need
  `Physics.queriesHitBackfaces`.
- **Deviation from the guide, tree height cap.** Pixels taller than 35 m are never trees.
  NAIP's relief displacement paints tower walls green, which produced "trees" of up to
  77 m downtown; the tallest real trees here are palms of ~33 m. Reason: step 4 as written
  misclassifies tower edges.
- **Deviation from the guide, DSM gridding.** The DSM and HAG keep each return in its own
  0.5 m cell (PDAL binmode). PDAL's default search radius spreads roof maxima into
  neighbouring cells, which widens every building by 0.5 m. Reason: footprint accuracy for shading.
- **Deviation from the guide, covered points.** A point driving on a bridge is not covered
  by that bridge, and the DSM − DTM rule measures from the road surface: the bridge deck
  for a point on a bridge. Taken literally, step 6 would tag every bridge crossing as a
  tunnel. Reason: step 6 is ambiguous for vehicles on overpasses.
- **Freshness list (step 8), pending author confirmation.** 204 candidates in 250 m route
  corridors, all at least 8 m tall: 102 *added* (current footprint, little lidar height
  under it; the largest is a 76 m tower on R-DENSE at 33.4572, −112.0758) and 102
  *demolished* (lidar structure ≥ 400 m² outside every footprint, grown by 3 m, and every
  bridge; many will be unmapped parking garages that still stand). Thresholds were set
  on a ten-tile trial, where the raw comparison flagged 464 blobs downtown, mostly shade
  canopies, rooftop structures and tower edges. `dsm.tif` equals the lidar-epoch DSM until
  confirmations are entered in `configs/site/freshness_v1.yaml`. The confirmed list is
  reported in the paper.

## 2026-10-16 · P2 weather

Sources: `src/solaris/weather/`, `tests/test_weather.py`, `results/p2/summary_weather.json`
(rules `weather_tmy`, `weather_conus_5min`, `weather_check`).

- **Weather inputs downloaded and pinned.** NSRDB GOES TMY v4 tmy-2023 (cell 323705,
  hourly, SHA-256 `a44db2d2…ca9a`) and GOES CONUS v4 2023 5-min (SHA-256 `256f0e8a…feca`),
  both PSM v4.0.1 in local standard time, cached in `data/raw/nsrdb/`. The downloaded TMY's
  GHI, DNI, DHI and temperature are identical to the file behind Table B0, so B0 stands.
  Reason: P2; the E5 sub-hourly sensitivity needs the 5-min year.
- **The 5-min year comes from a neighbouring cell.** The CONUS v4 grid cell nearest the site
  is 518064 at 33.46/−112.07, about 1.4 km from the TMY cell 323705. Its 2023 GHI is
  2132.9 kWh/m², against 2110.0 for the TMY. The E5 sensitivity must state both the cell
  and the year. Reason: NSRDB serves the two products on different grids.
- **Time convention fixed.** All series use America/Phoenix (UTC−7 all year). Stamps keep
  NSRDB's Minute column: :30 for the TMY and :00…:55 for the 5-min year. pvlib SPA at those
  stamps reproduces NSRDB's own solar zenith within 0.06° (5-min) and 0.24° (TMY), while a
  5-min slip gives ≥1.5° and a 30-min slip ≥6.8°. TMY rows are relabelled onto 2023; the
  TMY months come from 2014–2023. Reason: workflow guide, weather timestamp convention.
- **Finding, TMY month seams.** NSRDB stitches TMY months in UTC. In the local-time file the
  last local hours of some months come from another source day: 32 of 8760 rows, sun
  position off by up to 0.24°. The irradiance values are unchanged. No effect on hourly
  energy totals; noted for the E5 interpolation-limit statement.

## 2026-10-16 · P1 / E0 author decisions

- **Grid relief: energy-balanced definition adopted.** The journal reports relief as
  (harvest − curtailed)/demand, which closes the pack energy balance, instead of the
  conference (demand − grid)/demand. Table B0, measured: 77.9 % (Scen. II, 4055 kWh/yr) and
  38.9 % (Scen. I). Paybacks on the balanced savings are now in B0:
  full 14.7 yr / PV-only 6.9 yr for both scenarios (conference definition: 14.4 / 6.7 and
  14.3 / 6.7). Reason: author decision; the conference definition counts the pack's
  year-end deficit (94 kWh) as solar.
- **London measured-hourly values dropped.** The PVGIS London TMY will not be supplied. The
  5 London measured-hourly values (Table IV T2 0.48/0.23, PVGIS GHI 1050.7,
  −6.2 %/12.1 % MAPE) stay unverified and are not carried into the journal. Reason: author
  decision; the journal baseline is Phoenix only.

## 2026-10-16 · P1 / E0 reproduce and reconcile

Sources: `configs/experiments/e0.yaml` (printed values), `tests/test_regression_v1.py`,
`results/e0/table_b0.csv`, `results/e0/table_b0_pareto.csv` (rule `e0_measured`).

- **Conference paper reproduced.** 98 numbers printed in the paper (Tables I–VI, TEG,
  WLTP, Table IV, Sec. IX-A, design inversion, Pareto, sensitivities, Sec. XVIII) are
  asserted against the legacy module and the refactored `solaris.core`. 93 pass to
  the printed precision. 5 London measured-hourly values (Table IV T2 0.48/0.23,
  PVGIS GHI 1050.7, synthetic error −6.2 %/12.1 % MAPE) are skipped until the
  PVGIS 5.2 London TMY (51.526/−0.129, 2005–2023) is supplied. Reason: E0 pass condition.
- **Refactor is bit-identical.** `solaris.core` reproduces every legacy output, including
  all 8760-h SoC traces, with maximum difference 0.0 (test tolerance 1e-9).
- **Measured input pinned.** NSRDB TMY-2023 local-time file, SHA-256
  `a7e851c33c58b88cd18459321a4630bfc4486297e518e18fbeccd21d6a3e687a` (2110.0 kWh/m²,
  5.781 PSH, 23.2 °C). A UTC-stamped copy of the same data, shifted by 7 h, is rejected
  by `core.load_tmy`. Reason: the SoC loop indexes local hours, and the legacy loader
  would silently accept UTC stamps.
- **Sec. IX-A decomposition explained.** The printed split (0.055 magnitude + 0.045
  distribution) was not emitted by `solaris.py`. It reproduces (0.0549 + 0.0447) when the
  magnitude step rescales the synthetic climate to the TMY's own annual PSH and mean T
  (5.781, 23.2 °C). With the Global Solar Atlas values (5.807, 23.1 °C) the split is
  0.050 + 0.049. It is now emitted by `conference_values()`. The journal must state which
  definition it uses.
- **Correction, Sec. XIII η_regen.** "0.60 → 0.72 shifts f_ss by < 0.03" holds only for
  Scenario I (combined cycle; 0.011–0.021). For Scenario II (city cycle) the shift is
  0.033–0.054 (Phoenix 0.054), larger than the suspension sweep (0.019). The lever ordering
  "κ_pv ≫ η_regen ≈ suspension" is wrong for light use; it should be
  κ_pv ≫ η_regen > suspension.
- **Table B0 frozen (Phoenix, measured hourly TMY).** These replace the synthetic-climate
  values the conference paper used as headline numbers:

  | Metric | Conference (synthetic) | B0, Scen. II 50 km/day | B0, Scen. I 100 km/day |
  |---|---|---|---|
  | f_ss | 0.88 / 0.44 | 0.779, moderately solar-assisted | 0.389, grid-dependent |
  | charges/yr (no solar) | 6 (28) / 32 (57) | 6 (28), −79 % | 35 (57), −39 % |
  | grid energy, kWh/yr | — | 1058 | 6298 |
  | relief, conference definition | 80 %, 4198 kWh | 79.7 %, 4150 kWh | 39.8 % |
  | relief, energy-balanced | — | 77.9 % | 38.9 % |
  | payback full / PV-only, yr | 14.2 / 6.6 | 14.4 / 6.7 | 14.3 / 6.7 |
  | A_req (Eq. 2), m² | 13.6 / 27.3 | 15.4 | 31.0 |
  | D_max, km/day | 40.6 | 34.5 | 30.9 |
  | f_ss at κ_pv = 0.60 | 0.67 | 0.59 | 0.30 |
  | f_ss at 15 m² (Sec. XII) | 1.13 | 1.00 (0.999, quasi-self-sufficient) | — |

  Synthetic-climate values to replace or relabel in the journal: Sec. XVIII example
  (0.88, 6), Table VI, Sec. X (13.6 m², 40.6 km), Sec. XII (1.13, ~850, 853 → 705 kWh),
  Sec. XIII κ_pv range (0.67–0.88). On measured data the 15 m² grid energy is
  319/427/180 kWh for 150/200/250 kWh packs. That is not monotonic in capacity, because
  of the recharge-to-80 % policy, so the "+100 kWh of pack saves ~17 %" claim does not carry over.
- **Finding, grid-relief accounting.** The conference relief, (demand − grid)/demand,
  ignores the pack's net change in stored energy over the year. The pack ends 94 kWh
  (measured) or 161 kWh (synthetic) below its initial 90 % SoC, and that energy is counted
  as solar. This is why measured relief (79.7 %) exceeds measured f_ss (0.779), which
  contradicts Sec. XI. B0 now also reports an energy-balanced relief, (harvest − curtailed)/demand,
  and `core.simulate` reports curtailment; a test checks that the pack balance closes.
  **Proposed** for the journal, pending author decision: report the balanced relief.
- **Finding, climate vs grid energy.** In Scenario II the measured climate never fills the
  pack (0 kWh curtailed), whereas the synthetic climate curtails 581 kWh. The 0.10 drop in
  f_ss therefore costs only about 2 kWh/yr of extra grid energy and no extra charges.
  Relief and charge reduction are nearly unchanged by the measured climate; f_ss and the
  design inversion are not.

## 2026-10-15 · P0 bootstrap

- **Conference code frozen.** The conference `solaris.py` was copied byte-identical to
  `src/solaris/legacy/solaris_v1.py`: 28,334 bytes, LF line endings, no BOM,
  SHA-256 `7b30b213d8d89addfe7edcc6a1621caf94505f28ecbdd4eb26badc39152a96d5`.
  Reason: it is the E0 regression baseline. The hash is guarded by
  `tests/test_legacy.py`, the Snakemake rule `legacy_sha256` and a pre-commit hook.
- **Code-availability URL.** The conference paper (Code Availability, ref. [1]) cites
  `github.com/anandsagar-g/solaris-vipv`, which does not exist. The journal version cites
  `github.com/jarvisxys/solaris-vipv`. The legacy module's docstring still carries the old
  URL and stays unchanged under the byte-identity rule. Reason: the placeholder never resolved.
- **Conference parameters recorded.** `configs/base.yaml` holds the constants and defaults of
  `solaris_v1.py`; `tests/test_legacy.py` asserts that each introspectable value equals the
  module. Frozen from this date. Reason: the refactored core (P1) reads parameters from config.
