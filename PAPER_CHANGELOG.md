# Paper changelog

Every decision that changes a number, claim or reference in the journal paper,
newest first, with date and reason.

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
