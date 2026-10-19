# Building the Unity + Cesium twin (workflow guide Sec. 6)

The twin replays Python's trajectories against the same city meshes, casts its own rays
for the E8 cross-check, and makes the video and figures. Two rules hold throughout:

- **Only the headless batch run (step 13) feeds a reported number** (E8 agreement).
  Everything else here is visual.
- **Analysis rays only ever hit the imported P3 `.glb` meshes** (layers Buildings and Trees).
  They never hit streamed Cesium tiles, whose level of detail changes with the camera.
  Unity never computes sun angles or energy; Python sends them.

Project: `twin/unity/SOLARIS-Twin` · Unity **6000.3.6f1** · template **Universal 3D (URP)** ·
scripts in `Assets/SolarisTwin/` · menu **SOLARIS** in the editor.

## What is already done, and what you do

| Step | Status |
|---|---|
| 1–2 Project, packages, Git LFS rules | Done headless (P8). Just open it (step 3). |
| 5 Layers, analysis scene `E8.unity` | Done headless by `snakemake -c1 e8_unity`; rebuild with SOLARIS → 2. |
| 6 Ground-control check | Runs automatically before every batch run; also SOLARIS → 4. |
| 13 Headless E8 batch | Done by `snakemake -c1 e8_unity`. |
| 4, 7, 8, 9, 11, 14 Cesium backdrop, SUV, playback, render | **You**, in the editor (visual only). |

---

## 1. Install (once)

1. **Unity Hub** (unity.com/download) → sign in with your Unity ID → *Licenses* → make
   sure a Personal license is active. Headless runs use the same license.
2. Hub → *Installs* → *Install Editor* → **Unity 6000.3.6f1** (6.3 LTS). Optional modules:
   *Microsoft Visual Studio Community* (C# editing) and *Documentation*. No build platform is
   needed: the twin is never built into a player.
3. Git LFS is installed already (`git lfs version`). The repo's `.gitattributes` sends
   `*.glb *.fbx *.unity *.png *.exr` under `twin/unity/` to LFS.

## 2. The project folder (already created, for reference)

It was created with:

```
Unity.exe -batchmode -quit -nographics -createProject twin/unity/SOLARIS-Twin ^
  -cloneFromTemplate <Editor>/Data/Resources/PackageManager/ProjectTemplates/com.unity.template.3d-cross-platform-17.0.14.tgz
```

That template is *Universal 3D* (`com.unity.template.urp-blank`).

**OneDrive.** The repo sits in OneDrive. OneDrive marks synced folders read-only and would
also sync Unity's multi-GB cache. So `Library/` is a junction to
`%LOCALAPPDATA%\solaris-vipv\unity\Library`, like `.snakemake`. On a fresh clone, recreate
the junction **before** the first open:

```powershell
$lib = "$env:LOCALAPPDATA\solaris-vipv\unity\Library"
New-Item -ItemType Directory -Force $lib
New-Item -ItemType Junction -Path twin\unity\SOLARIS-Twin\Library -Target $lib
```

`Library/ Temp/ Logs/ UserSettings/ Assets/Geometry/` are gitignored
(`twin/unity/SOLARIS-Twin/.gitignore`). `Assets/Geometry` is a copy of the P3 tiles, made by
`snakemake -c1 e8_export`.

## 3. Open the project

Hub → *Projects* → *Add* → *Add project from disk* → select `twin/unity/SOLARIS-Twin` →
open it with 6000.3.6f1. The first open imports 280 tiles (~700 MB) and takes several
minutes. When it is done, the **SOLARIS** menu appears in the menu bar.

> Close the editor before running any Snakemake rule that starts Unity. A project can be
> open in only one Unity process at a time.

## 4. Packages (installed; how to check or redo)

*Window → Package Management → Package Manager*:

- **Cesium for Unity 1.26.0** (under *My Registries*).
- **Unity glTFast 6.20.0** (`com.unity.cloud.gltfast`, imports the `.glb` tiles).
- **Recorder 5.1.7**.

To redo it by hand (guide step 2):

1. *Edit → Project Settings → Package Manager → Scoped Registries → +*, with Name `Cesium`,
   URL `https://unity.pkg.cesium.com`, Scope `com.cesium.unity` → *Save*.
2. Package Manager → *My Registries* → Cesium for Unity → *Install*.
3. *Unity Registry* → *Recorder* → *Install*.
4. *+ → Install package by name* → `com.unity.cloud.gltfast` → *Install*.

The pinned versions live in `Packages/manifest.json`.

## 5. Layers, physics and analysis geometry

1. **SOLARIS → 1 Create layers and physics settings.** This creates User Layer 8
   `Buildings` and 9 `Trees` (*Project Settings → Tags and Layers*), and ticks *Project
   Settings → Physics → Queries Hit Backfaces*. Heightfield meshes are open surfaces, and a
   ray starting under a bridge deck must still hit it.
2. In a terminal, from the repo: `snakemake -c1 e8_export`. It copies the 140 surface + 140
   tree tiles around R-DENSE (trips + 1 km shading reach) into `Assets/Geometry/Buildings` and
   `Assets/Geometry/Trees`. Back in the editor they import automatically.
3. **SOLARIS → 2 Build analysis scene (E8).** This builds `Assets/Scenes/E8.unity`:
   - every tile goes under the root `AnalysisGeometry`;
   - each tile gets its layer, a *MeshCollider* and the *Static* flag;
   - a directional light `Sun` is added.

   glTF is right-handed and Unity left-handed. glTFast mirrors one axis on import. The script
   detects which axis from the tile bounding boxes and sets the root's rotation, so the scene
   is **x = east, y = up, z = north** (Python's ENU order). The Console reports
   `importer flip x` or `z`. **Do not move, rotate or scale `AnalysisGeometry`.**

## 6. Ground-control check

**SOLARIS → 4 Ground-control check.** It casts a ray straight down at five surveyed NGS marks
in the corridor (`twin/exchange/ground_control.csv`). Each must land within **0.5 m** of its
lidar surface height, or no run counts. The batch run does this itself and exits with code 2
on failure. In P8 all five passed (see `results/e8/summary_e8_unity.json`). A failure of
metres means a wrong axis or a moved root (redo step 5.3). A failure of a few decimetres at
one mark means local mesh decimation; check the mark in the Scene view.

## 7. Georeference and Cesium backdrop (visual only)

1. Open `Assets/Scenes/Playback.unity` (step 9 creates it) or any copy of `E8.unity`.
2. *Cesium → Cesium* opens the Cesium panel. Click **Connect to Cesium ion** and authorise
   in the browser (free account at ion.cesium.com). Back in Unity, accept the default token.
   The token is saved in `Assets/CesiumSettings/`, which is gitignored. Never commit it.
3. Cesium panel → *Quick Add* → **Cesium World Terrain**. This creates a
   `CesiumGeoreference` with a terrain tileset under it.
4. Select **CesiumGeoreference** → *Origin Authority* `Longitude Latitude Height`:
   - Latitude **33.4484**
   - Longitude **-112.074**
   - Height **301.742**

   This is the ENU origin of `twin/exchange/enu_origin.json`: Central Ave & Washington St,
   DEM ground + GEOID18. Unity's origin then coincides with Python's ENU origin, and Cesium
   uses the same x east, y up, z north. Keep `AnalysisGeometry` **outside** the
   georeference hierarchy.
5. *Quick Add* → **Google Photorealistic 3D Tiles** (needs the Google asset in your ion
   account; ion offers it in *Asset Depot*).
6. For **every** tileset (World Terrain, Google): select it → *Cesium 3D Tileset* →
   **untick *Create Physics Meshes***. Then no ray can ever hit streamed tiles.
7. Attribution: leave the *CesiumCreditSystemDefault* object in the scene. It draws the
   Google and Cesium credits on screen, and they must stay visible in every render.
8. Visual alignment check: in the Scene view, our meshes and the Google tiles should overlap
   within a metre or two. Google tiles are newer than the 2020–21 lidar, so new towers may
   differ.

## 8. Vehicle with facet samples

**SOLARIS → 3 Create SUV prefab with facet samples.** It builds
`Assets/SolarisTwin/Prefabs/SUV.prefab`:

- a 5.1 × 2.0 × 1.8 m box with **no collider**, so rays can never hit the car;
- 211 children under `Samples`, one per row of `twin/exchange/facet_samples.csv`
  (`FacetSampleLoader.cs`).

Body frame x forward, y left, z up maps to Unity local (−y, z, x). Each child's blue axis is
its facet normal.

**The SOLARIS P0 body** (`Assets/SolarisTwin/Models/SOLARIS_P0.glb`) replaces the box: run
**SOLARIS → 8 Use SOLARIS P0 model on the SUV prefab** (step 3 does it automatically when the
model exists). It was built in Blender by `twin/blender/build_solaris_p0.py` around the exact
PV facets of `configs/vehicle/solaris_p0.yaml` (a test keeps the two equal) and exported by
`twin/blender/export_solaris_p0.py`. Visual only: no colliders, and the results use the yaml
facets, never this mesh. To change the design: run both scripts in Blender, then SOLARIS → 8. Select the SUV to see the samples as gizmos. Right-click the
*FacetSampleLoader* component → *Load facet samples* reloads them after the skin changes
(re-run `snakemake -c1 facet_samples` first).

## 9. Playback (deterministic)

1. **SOLARIS → 5 Build playback scene (render)** creates `Assets/Scenes/Playback.unity`:
   E8 geometry, the SUV, a *TrajectoryPlayer*, the *Sun* light, a *ChaseCamera* and a
   *PvHud*.
   For a scene built before this option existed, open it and run **SOLARIS → 7** instead.
   That adds the controls below without touching your Cesium setup.
2. *TrajectoryPlayer* fields:
   - *Trajectory Path* defaults to the render trip,
     `../../exchange/trajectories/trajectory_R-DENSE_fwd_1800_medium_2023-12-21.csv`
     (R-DENSE, 08:00, 21 December). Any exported file works.
   - *Speed*: trajectory seconds per second; 1 = real time.
   - *Fixed Fps*: 0 for viewing. For Unity Recorder, set it to the recording frame rate so
     every frame advances the same amount and the video is deterministic.
   - *Wait For Tiles*: the clock stops while Cesium tiles in view load, so roads and
     buildings are drawn before the car moves on.
3. Press **Play**. The pose is interpolated between the 1 Hz records. Car yaw = heading
   (Unity +Z is north; positive rotation about +Y turns it east). The *Sun* light follows the
   pvlib sun angles and switches off when the sun is below the horizon.

   Keys:
   - Space: play/pause
   - ← / →: back / forward 10 s
   - [ / ]: half / double speed
   - R: restart
   - **Tab**: drive the car yourself (W/S throttle, A/D steer; the sun stays at the moment you
     took over; Tab again returns to the trajectory)
   - **M**: show/hide the shade dots on the skin (yellow lit, green tree, blue building, grey
     sun behind the facet, with the lit share per facet at the bottom right)
   - Right-drag: orbit the camera; scroll: zoom; C: reset the view

   All of this is display only; reported numbers come from the batch run.

## 10. Visibility probe (what the batch run does)

`VisibilityProbe.cs` is the guide's core:

1. Place the car (`x_e, z_u, y_n`, yaw = heading) and sync transforms.
2. For every sample whose facet faces the sun (sun above the horizon, normal · sun > 0),
   cast one ray on layer *Buildings* and one on layer *Trees*, from 2 cm off the skin
   toward the sun (5 km).
3. Write `t_utc, facet_id, sample_id, beam_building_hit, beam_tree_hit`.

Hit codes:

- `1` blocked, `0` clear.
- `-1` sun below the horizon or behind the facet.
- Covered records (tunnels, under bridges) are written 1/0.

Trees count once per crossing, as in the Python engine and SOLWEIG.

## 11. Headless batch run (E8)

With the editor **closed**:

```powershell
snakemake -c1 e8_unity e8_twin_agreement
```

It runs, in order:

1. `TwinSetup.BuildAnalysisSceneBatch`
2. `TwinBatch.Run`, with:
   ```
   Unity.exe -batchmode -nographics -projectPath twin/unity/SOLARIS-Twin ^
     -executeMethod SolarisTwin.Editor.TwinBatch.Run ^
     -trajectory twin/exchange/trajectories -out data/derived/e8/unity ^
     -samples twin/exchange/facet_samples.csv -gcp twin/exchange/ground_control.csv ^
     -logFile data/derived/logs/unity_e8.log
   ```

Output:

- one `visibility_<trip>_<date>.csv.gz` per trajectory;
- `ground_control_unity.csv`;
- `unity_run.txt`.

Exit codes: 0 ok, 1 error, 2 ground-control failure. Add `-resume` to skip finished files.
To use another editor install, set `UNITY_EDITOR` to its `Unity.exe`.

Then `e8_twin_agreement` writes `results/e8/summary_e8_unity.json`, `table_e8_trips.csv`,
`table_e8_clusters.csv` and `fig13a_twin_agreement.png`.

## 12. Analysis geometry display modes

**SOLARIS → 6** sets how `AnalysisGeometry` is drawn. Colliders are untouched in every mode:

- **visible**: grey meshes;
- **shadows only**: invisible, but they cast the exact shadows the analysis uses. This is
  the recommended mode under Google tiles;
- **hidden**: renderers off.

## 13. Shadows for the render (URP)

1. *Assets/Settings/PC_RPAsset* → *Shadows*:
   - *Max Distance* **400**
   - *Cascade Count* **4**
   - *Soft Shadows* on
   - Main-light shadow resolution **4096**
2. *Sun* light → *Shadow Type* **Soft Shadows**, *Strength* 1.
3. *Edit → Project Settings → Quality* → use the *PC* level.

## 14. The chase-camera video (Unity Recorder)

1. Open `Playback.unity`. Set the geometry mode to *shadows only* (step 12), with Google
   tiles on (step 7).
2. Run `snakemake -c1 e8_export` once, so `twin/exchange/render/pv_R-DENSE_fwd_1800_medium_2023-12-21.csv`
   exists. *PvHud* reads it: PV power from Python (case C, TMY day); Unity only displays it.
3. *Window → General → Recorder → Recorder Window* → *Add Recorder* → **Movie**:
   - *Source*: **Game View**, so the HUD and the Cesium credits are captured.
   - *Output resolution*: 1920 × 1080.
   - *Format*: MP4 (H.264), quality High.
   - *Recording Mode*: Manual. *Playback*: **Constant**, 30 fps, *Cap FPS* on.
   - *Path*: `Recordings/rdense_0800_1221` (inside the project; gitignored).
   - On *TrajectoryPlayer* set **Fixed Fps = 30** (the recording rate) and *Speed* as wanted
     (e.g. 4 gives a 15-min trip in about 4 min).
4. Press **Start Recording** (it enters Play mode). Stop when the trip ends.
5. The video is display only. Its numbers (HUD) come from Python.

## 15. Troubleshooting

| Symptom | Fix |
|---|---|
| "Scripts have compiler errors" in a batch log | open the project in the editor and read the Console |
| Batch exits at once, "another Unity instance" | close the editor; delete `Temp/UnityLockfile` only if no Unity runs |
| Ground control off by metres | `AnalysisGeometry` moved/rotated, or tiles re-imported with other glTFast settings; SOLARIS → 2 |
| Rays hit nothing | layers missing (SOLARIS → 1) or the scene is not `E8.unity` |
| Cesium tiles missing | not signed in to ion, or the token lacks the Google asset |
| Folder read-only / sync storms | `Library` junction missing (step 2) |
| License error in batch mode | open Unity Hub once and re-activate the Personal license |

## Files

| File | Role |
|---|---|
| `Runtime/TwinIO.cs` | CSV readers, frame conversions |
| `Runtime/VisibilityProbe.cs` | the probe (guide core) |
| `Runtime/GroundControlCheck.cs` | 0.5 m gate |
| `Runtime/FacetSampleLoader.cs` | samples under the SUV; `TwinPaths` |
| `Runtime/TrajectoryPlayer.cs` | record-by-record playback, sun light |
| `Runtime/ChaseCamera.cs`, `Runtime/PvHud.cs` | render only |
| `Editor/TwinBatch.cs` | `-executeMethod SolarisTwin.Editor.TwinBatch.Run` |
| `Editor/TwinSetup.cs` | SOLARIS menu, scene and prefab builders |
