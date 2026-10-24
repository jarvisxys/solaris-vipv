# Third-party assets and data in the Unity visual twin

Visual only (Playback scene). None of these feeds a reported number.

## Models

| File(s) | Asset | Author | Source | Licence | Changes |
|---|---|---|---|---|---|
| `SOLARIS-Twin/Assets/SolarisTwin/Visual/Models/Cars/Car_*.glb` (10 cars) | "Generic passenger car pack" | comrade1280 | https://sketchfab.com/3d-models/20f9af9b8a404d5cb022ac6fe87f21f5 | CC BY 4.0 | Split into single cars, wheels joined to their body, rescaled to real lengths of 4.0–5.0 m (SUMO passenger cars are 5 m), origin moved to the ground under the body centre, front along +z (Unity), textures reduced to 1024 px JPEG |
| `SOLARIS-Twin/Assets/SolarisTwin/Visual/Models/Signals/*.glb` | Signal head, pole, mast arm, R10-10L "LEFT TURN SIGNAL" sign | built for this project in Blender 4.5 | — | same as this repository | — |

## Map data (on-screen credit in the full map)

- Street names and landmarks: © OpenStreetMap contributors, ODbL.
- Building footprints: Overture Maps Foundation.
- Aerial imagery: USDA NAIP (public domain).
- Photorealistic 3D tiles: Google, via Cesium ion (attribution shown by Cesium in the scene).
