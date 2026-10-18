# Python-Unity exchange schema

File exchange, not a live socket, so files are deterministic, diffable and archivable.
Positions are in the local ENU frame of `configs/site/phoenix.yaml` (`enu_origin.json`);
Unity axes are X = East, Y = Up, Z = North. Times are UTC.

| File | Direction | Columns / content |
|---|---|---|
| `trajectories/trajectory_<trip>_<date>.csv` | Python -> Unity | `t_utc, x_e, y_n, z_u, heading_deg, speed_mps, sun_az_deg, sun_el_deg, covered` |
| `facet_samples.csv` | Python -> Unity | `facet_id, sample_id, x_body, y_body, z_body, nx, ny, nz` |
| `visibility_<trip>_<date>.csv.gz` (in `data/derived/e8/unity/`) | Unity -> Python | `t_utc, facet_id, sample_id, beam_building_hit, beam_tree_hit` |
| `ground_control.csv` | Python -> Unity | `id, name, x_e, y_n, u_mark, u_lidar, u_mesh, mesh_minus_lidar_m` |
| `unity_geometry.json` | Python -> Unity | tiles copied into `Assets/Geometry/{Buildings,Trees}` with glTF bboxes |
| `render/pv_<trip>_<date>.csv` | Python -> Unity | `t_utc, pv_W` (HUD of the render; display only) |
| `export_manifest.json` | Python | what rule `e8_export` wrote |

- `<trip>` is the SUMO trace id (`R-DENSE_fwd_1800_medium` = forward, 08:00 departure,
  medium demand); `<date>` is the replay day.
- `heading_deg` is true (ENU) heading, so the UTM grid's meridian convergence is already
  removed.
- `z_u` is the road surface; facet sample heights are measured from it.
- `beam_*_hit`: 1 = blocked, 0 = clear, -1 = sun below the horizon or behind the facet.
  Covered records (bridges, tunnels) are written as building hit = 1, tree hit = 0.
- Sun angles come from pvlib (SPA) only; Unity never computes them.
- `trajectories/` and `render/` are rebuilt by `snakemake -c1 e8_export` and not committed.
