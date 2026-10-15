# Python-Unity exchange schema

File exchange, not a live socket, so files are deterministic, diffable and archivable.
Positions are in the local ENU frame of `configs/site/phoenix.yaml`; Unity axes are
X = East, Y = Up, Z = North. Times are UTC.

| File | Direction | Columns |
|---|---|---|
| `trajectory_<route>_<date>.csv` | Python -> Unity | `t_utc, x_e, y_n, z_u, heading_deg, speed_mps, sun_az_deg, sun_el_deg, covered` |
| `facet_samples.csv` | Python -> Unity | `facet_id, sample_id, x_body, y_body, z_body, nx, ny, nz` |
| `visibility_<route>_<date>.csv` | Unity -> Python | `t_utc, facet_id, sample_id, beam_building_hit, beam_tree_hit` |

`beam_*_hit`: 1 = blocked, 0 = clear, -1 = sun below the horizon or behind the facet.
Covered records (bridges, tunnels) are written as building hit = 1, tree hit = 0.
Sun angles come from pvlib (SPA) only; Unity never computes them.
