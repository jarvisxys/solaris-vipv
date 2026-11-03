<div align="center">

# SOLARIS-Twin

**A digital twin for shading-aware assessment of vehicle-integrated photovoltaics on a heavy electric vehicle**

[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.23896001-1682D4)](https://doi.org/10.5281/zenodo.23896001)
[![License: MIT](https://img.shields.io/badge/license-MIT-2a9d8f)](LICENSE)
![Python 3.11](https://img.shields.io/badge/python-3.11-3776AB)
![Snakemake](https://img.shields.io/badge/pipeline-Snakemake-039475)
![Tests](https://img.shields.io/badge/tests-568%20passed-2a9d8f)
![Unity 6](https://img.shields.io/badge/twin-Unity%206%20%2B%20Cesium-222222)
[![Paper](https://img.shields.io/badge/paper-PDF-d1495b)](paper/main.pdf)

<img src="docs/readme/twin_drive.webp" width="100%" alt="The SOLARIS vehicle driving north on 1st Avenue in the Unity twin of downtown Phoenix at noon on 21 June, with live readouts of speed, PV power per facet and trip energy; mid-clip it passes under a bridge and the PV power drops to 0 W">

<sub>The Unity twin replaying a simulated trip through downtown Phoenix, 21 June, 12:05 MST. The panel on the right shows which facets are in direct sun; under the bridge every facet goes dark. Full clip: <a href="docs/readme/twin_drive.mp4">twin_drive.mp4</a>.</sub>

</div>

Solar panels on a car are usually judged as if the whole skin were a flat roof under an open sky. In a real city the panels face different directions, buildings and trees shade them, and the car spends most of the day parked wherever its owner leaves it. SOLARIS-Twin measures how much of the solar energy survives all of that.

It extends the SOLARIS conference toolkit (an hour-by-hour energy model of a 2.5 t, seven-seat electric vehicle) with a lidar-built 3D model of central Phoenix, Arizona. The vehicle drives traffic-simulated trips on real arterials, parks at five sites, and the shadow on each of its five PV facets is computed every second while driving and every five minutes while parked, for a whole typical year.

> [!NOTE]
> This repository is the code and data pipeline behind the journal manuscript *"A Digital Twin for Shading-Aware Assessment of Vehicle-Integrated Photovoltaics on a Heavy Electric Vehicle"* (A. Kumar, A. Gaikwad, A. Deo), submitted to the IEEE Transactions on Transportation Electrification. It extends our ITEC-AP 2026 conference paper. Every number in [`paper/main.pdf`](paper/main.pdf) is written by a Snakemake rule from the files in [`results/`](results/).

## Results at a glance

| | Phoenix, 50 km/day |
|---|---|
| Solar self-sufficiency of the conference model (whole skin flat, never shaded) | **0.832** |
| ... with the five facets facing where they really face | **0.677** |
| ... for a suburban commuter after parking shade, driving shade and electrical mismatch | **0.512** |
| ... for a car parked at a downtown street-canyon curb | **0.256** |
| Share of the shading loss that happens while parked (commuter / downtown) | **92 % / 95 %** |
| Shading-aware design equation vs. the full simulation | **within 2.6 %** |
| Unity ray-casting twin vs. the Python shading engine | **99.1 % agreement over 15.5 million sample-seconds** |

*Self-sufficiency* is the share of the vehicle's yearly energy demand that it covers on board (PV plus small thermoelectric and suspension-recovery terms). Parking, not driving, decides most of the outcome: the street canyon costs at most 0.017 while driving.

## How the twin is built

The same 1 km block of downtown Phoenix at each stage of the pipeline (Blender renders of the pipeline's own files; the sun is placed for 21 December, 15:00 MST).

<table>
<tr>
<td width="50%"><img src="docs/readme/L1_points_height.webp" alt="USGS lidar point cloud of downtown Phoenix coloured by height above ground"></td>
<td width="50%"><img src="docs/readme/L2_points_class.webp" alt="The same points coloured by the pipeline's classes: ground grey, buildings orange, trees green"></td>
</tr>
<tr>
<td><b>1. Lidar.</b> USGS 3DEP airborne lidar, 5.28 billion points over 952 tiles of 500 m (14 × 17 km), cleaned and reprojected with PDAL. Colour: height above ground.</td>
<td><b>2. Classification.</b> Each 0.5 m cell becomes ground, building or tree from the lidar height and NAIP near-infrared imagery (NDVI). Downtown has few trees: about 1 % of this block.</td>
</tr>
<tr>
<td><img src="docs/readme/L3_mesh_buildings.webp" alt="Clay render of the building and ground mesh built from the 0.5 m surface model"></td>
<td><img src="docs/readme/L4_mesh_trees.webp" alt="The same mesh with the separate tree canopy mesh in green"></td>
</tr>
<tr>
<td><b>3. Surface mesh.</b> A 0.5 m surface model checked against 87 NGS survey marks (median absolute deviation 0.14 m), with building changes since the lidar epoch reviewed against Overture footprints, then meshed per tile.</td>
<td><b>4. Trees kept separate.</b> Canopy is a second mesh because leaves let some light through (transmittance τ), while buildings block it completely.</td>
</tr>
<tr>
<td><img src="docs/readme/unity_google_tiles.jpg" alt="Unity twin view along Central Avenue with Google Photorealistic 3D Tiles, the SOLARIS vehicle and live PV readouts"></td>
<td><img src="docs/readme/unity_topdown.jpg" alt="Top-down Unity view of downtown Phoenix at noon with the vehicle's facet panel"></td>
</tr>
<tr>
<td><b>5. Visual twin.</b> Unity 6 with Cesium streams Google Photorealistic 3D Tiles over the same coordinates (ENU origin 33.4484° N, 112.0740° W), so the scene looks like the city while the shading still comes from the lidar mesh.</td>
<td><b>6. Replay.</b> The twin replays the exact trips and sun positions of the simulation. Its own ray casts are an independent check of the Python engine (E8).</td>
</tr>
</table>

### Sun and shade over a day

<table>
<tr>
<td width="62%"><img src="docs/readme/sun_day.webp" alt="Animated clay render of downtown Phoenix from 05:45 to 19:15 on 21 June with the sun at its computed position; building shadows sweep across the streets"></td>
<td>The sun position for every second of the year comes from the NREL solar position algorithm (pvlib). Each facet sample gets a horizon mask from the surface model; the beam is blocked when the sun is behind it, and diffuse light is scaled by the sky view factor. On 21 June the sun stands 79° high at noon, so even narrow canyons get light at midday; morning and evening are where buildings take it away.</td>
</tr>
</table>

<img src="docs/readme/weather_tmy.png" width="100%" alt="Heat maps of hourly global horizontal irradiance and air temperature for the Phoenix typical meteorological year">

Weather is the NSRDB typical meteorological year for the cell over downtown Phoenix (TMY-2023, hourly). Temperature matters as well as sunlight: cell temperature follows the Faiman model with the vehicle's speed added to the wind.

## Routes, traffic and parking

Pan and zoom the map; click a coloured route marker or a parking pin for its details.

```geojson
{"type":"FeatureCollection","features":[{"type":"Feature","geometry":{"type":"LineString","coordinates":[[-112.06469,33.39224],[-112.06354,33.39224],[-112.0622,33.39224],[-112.05928,33.39226],[-112.05774,33.39226],[-112.05514,33.39226],[-112.0541,33.39234],[-112.05249,33.39253],[-112.0511,33.39263],[-112.04951,33.39268],[-112.04787,33.39273],[-112.04695,33.39275],[-112.04565,33.39278],[-112.04339,33.39284],[-112.04235,33.39286],[-112.04126,33.39284],[-112.04013,33.39282],[-112.03916,33.39287],[-112.03817,33.39291],[-112.03552,33.39301],[-112.03381,33.39307],[-112.03089,33.39318],[-112.03008,33.3932],[-112.0293,33.39322],[-112.02718,33.3933],[-112.02578,33.39335],[-112.02437,33.3934],[-112.02255,33.39346],[-112.02111,33.39352],[-112.02023,33.39358],[-112.01919,33.39367],[-112.01841,33.39374],[-112.01743,33.39382],[-112.01684,33.39384],[-112.01636,33.39378],[-112.01576,33.39361],[-112.01515,33.39336],[-112.01417,33.39296],[-112.01327,33.39264],[-112.01254,33.39254],[-112.01155,33.39254],[-112.00997,33.39255],[-112.00867,33.39256],[-112.00597,33.39258],[-112.00493,33.39259],[-112.00323,33.39259],[-112.00107,33.39261],[-111.99989,33.39262],[-111.99672,33.39263],[-111.99624,33.39263],[-111.99539,33.39264],[-111.99416,33.39264],[-111.99118,33.39267],[-111.98923,33.39268],[-111.98692,33.3927],[-111.98536,33.39271],[-111.98184,33.39274],[-111.97907,33.39276],[-111.97836,33.39276],[-111.97739,33.39276],[-111.97601,33.39276]]},"properties":{"route":"R-OPEN","street":"Southern Avenue","length_km":8.28,"mean_sky_view_factor":0.96,"stroke":"#2a9d8f","stroke-width":6}},{"type":"Feature","geometry":{"type":"Point","coordinates":[-112.01919,33.39367]},"properties":{"route":"R-OPEN","street":"Southern Avenue","length_km":8.28,"mean_sky_view_factor":0.96,"marker-color":"#2a9d8f","marker-symbol":"road"}},{"type":"Feature","geometry":{"type":"LineString","coordinates":[[-112.09915,33.39227],[-112.09916,33.39311],[-112.09921,33.39545],[-112.09922,33.39593],[-112.09925,33.39777],[-112.09927,33.39893],[-112.09929,33.39966],[-112.09932,33.40133],[-112.09934,33.40244],[-112.09936,33.4039],[-112.0994,33.40529],[-112.09941,33.40611],[-112.09944,33.40668],[-112.09945,33.40735],[-112.09947,33.40849],[-112.09956,33.41222],[-112.0996,33.41416],[-112.09968,33.41835],[-112.09974,33.42095],[-112.09976,33.42224],[-112.09977,33.42284],[-112.0998,33.42382],[-112.09983,33.42503],[-112.09986,33.42653],[-112.09988,33.42783],[-112.09996,33.42847],[-112.09997,33.42935],[-112.0999,33.4303],[-112.09991,33.43102],[-112.09993,33.43178],[-112.09994,33.43294],[-112.1,33.4353],[-112.10001,33.43589],[-112.10001,33.43654],[-112.10002,33.43724],[-112.10003,33.43787],[-112.10003,33.43856],[-112.10004,33.43948],[-112.10004,33.44024],[-112.10004,33.44052],[-112.10004,33.44123],[-112.10005,33.44182],[-112.10007,33.44304],[-112.10008,33.44391],[-112.1001,33.44553],[-112.10011,33.44667],[-112.10011,33.44724],[-112.10013,33.4481],[-112.10012,33.44912],[-112.10011,33.44965],[-112.10011,33.45019],[-112.1001,33.45069],[-112.10009,33.45114],[-112.1001,33.45183],[-112.10006,33.45341],[-112.10009,33.45451],[-112.10011,33.45555],[-112.10009,33.45727],[-112.10008,33.45858],[-112.10007,33.45947],[-112.10003,33.46039],[-112.10009,33.46204],[-112.10002,33.46214]]},"properties":{"route":"R-MIXED","street":"19th Avenue","length_km":7.75,"mean_sky_view_factor":0.9,"stroke":"#e9a23b","stroke-width":6}},{"type":"Feature","geometry":{"type":"Point","coordinates":[-112.1,33.4353]},"properties":{"route":"R-MIXED","street":"19th Avenue","length_km":7.75,"mean_sky_view_factor":0.9,"marker-color":"#e9a23b","marker-symbol":"road"}},{"type":"Feature","geometry":{"type":"LineString","coordinates":[[-112.07331,33.41937],[-112.07322,33.4196],[-112.07327,33.42334],[-112.07331,33.42474],[-112.07351,33.42576],[-112.07364,33.42652],[-112.07366,33.42763],[-112.07367,33.42834],[-112.07365,33.42925],[-112.07368,33.43126],[-112.07369,33.43253],[-112.07371,33.43455],[-112.07372,33.43671],[-112.07373,33.43752],[-112.07373,33.43928],[-112.07372,33.44016],[-112.07372,33.44106],[-112.07372,33.44205],[-112.07374,33.44279],[-112.07378,33.445],[-112.07375,33.44608],[-112.07376,33.44684],[-112.0738,33.44716],[-112.07458,33.44716],[-112.07511,33.44727],[-112.0751,33.4478],[-112.0751,33.44823],[-112.0751,33.44923],[-112.07512,33.44975],[-112.07519,33.45037],[-112.07519,33.45128],[-112.07465,33.4514],[-112.07399,33.45139],[-112.07383,33.45213],[-112.0738,33.45343],[-112.07379,33.45453],[-112.07379,33.45543],[-112.07379,33.45665],[-112.07379,33.45785],[-112.0738,33.45879],[-112.07377,33.45978],[-112.07374,33.46094],[-112.0737,33.46174],[-112.07373,33.46319],[-112.0737,33.46451],[-112.07369,33.46516],[-112.07383,33.46572],[-112.07396,33.46666],[-112.07393,33.46737],[-112.07393,33.46868],[-112.07393,33.46956],[-112.0739,33.4711],[-112.07391,33.47255],[-112.07394,33.4738],[-112.07391,33.47487],[-112.07392,33.47616],[-112.07394,33.47673],[-112.0739,33.47881],[-112.0739,33.48003],[-112.07391,33.48094],[-112.07391,33.48185],[-112.07391,33.48237],[-112.07393,33.48338],[-112.07393,33.48471],[-112.07392,33.48635],[-112.07393,33.48754],[-112.07393,33.48754]]},"properties":{"route":"R-DENSE","street":"Central Avenue","length_km":7.84,"mean_sky_view_factor":0.74,"stroke":"#d1495b","stroke-width":6}},{"type":"Feature","geometry":{"type":"Point","coordinates":[-112.07383,33.45213]},"properties":{"route":"R-DENSE","street":"Central Avenue","length_km":7.84,"mean_sky_view_factor":0.74,"marker-color":"#d1495b","marker-symbol":"road"}},{"type":"Feature","geometry":{"type":"LineString","coordinates":[[-112.10002,33.46214],[-112.10009,33.46204],[-112.10009,33.46123],[-112.10002,33.46111],[-112.09999,33.46108],[-112.09995,33.46105],[-112.09984,33.46105],[-112.09979,33.46105],[-112.09964,33.46106],[-112.0981,33.46122],[-112.09733,33.46131],[-112.09657,33.46138],[-112.09646,33.46139],[-112.09632,33.4614],[-112.09522,33.46145],[-112.09418,33.46156],[-112.09336,33.46157],[-112.09293,33.46157],[-112.09247,33.46157],[-112.09204,33.46156],[-112.09165,33.46154],[-112.09132,33.46152],[-112.09095,33.46149],[-112.09061,33.46146],[-112.09024,33.46143],[-112.0897,33.46136],[-112.08852,33.46124],[-112.08699,33.46107],[-112.08553,33.46092],[-112.08511,33.46087],[-112.0847,33.46083],[-112.08435,33.46081],[-112.08397,33.46079],[-112.08356,33.46078],[-112.08316,33.46078],[-112.08264,33.4608],[-112.0821,33.46084],[-112.0811,33.46097],[-112.07928,33.46132],[-112.07871,33.4614],[-112.07798,33.46146],[-112.07709,33.46145],[-112.07382,33.46145],[-112.07265,33.46155],[-112.07136,33.46178],[-112.06998,33.46207],[-112.06923,33.46219],[-112.0688,33.46222],[-112.06842,33.46223],[-112.06792,33.46222],[-112.06768,33.46222],[-112.06699,33.46217],[-112.06655,33.46213],[-112.06625,33.46211],[-112.06487,33.462],[-112.06404,33.46193],[-112.06321,33.46187],[-112.06237,33.46181],[-112.06178,33.46177],[-112.06096,33.46174],[-112.0609,33.46174],[-112.06008,33.4617],[-112.05926,33.46171],[-112.05852,33.4617],[-112.05588,33.4617],[-112.05512,33.46171],[-112.0544,33.46173],[-112.05293,33.46184],[-112.05226,33.46176],[-112.05192,33.46175],[-112.0516,33.46174],[-112.05116,33.46172],[-112.05065,33.46168],[-112.05054,33.46167],[-112.04981,33.46161],[-112.0496,33.46159],[-112.0494,33.46158],[-112.04919,33.46158],[-112.0483,33.46158],[-112.04789,33.46158],[-112.04777,33.46157],[-112.04777,33.46149],[-112.04777,33.46138],[-112.04776,33.46115],[-112.04775,33.46086],[-112.04775,33.46077],[-112.04774,33.46067],[-112.04769,33.46057],[-112.04766,33.46052],[-112.0475,33.46052],[-112.04747,33.46052],[-112.04704,33.46052],[-112.04644,33.46051],[-112.04614,33.46051],[-112.04547,33.46051],[-112.04541,33.46051],[-112.04454,33.4605],[-112.04439,33.4605],[-112.04433,33.4605],[-112.04387,33.4605],[-112.04341,33.46049],[-112.04334,33.46049],[-112.04334,33.46044],[-112.04333,33.45959],[-112.04333,33.45959]]},"properties":{"route":"R-TUNNEL","street":"I-10 Deck Park Tunnel (seed)","length_km":5.62,"covered_m":822.0,"stroke":"#6a4c93","stroke-width":6}},{"type":"Feature","geometry":{"type":"Point","coordinates":[-112.06655,33.46213]},"properties":{"route":"R-TUNNEL","street":"I-10 Deck Park Tunnel (seed)","length_km":5.62,"covered_m":822.0,"marker-color":"#6a4c93","marker-symbol":"road"}},{"type":"Feature","geometry":{"type":"Point","coordinates":[-112.06589,33.44369]},"properties":{"site":"P1","kind":"open lot (P5: same stall under a shade roof)","sky_view_factor":0.95,"marker-color":"#264653","marker-symbol":"parking"}},{"type":"Feature","geometry":{"type":"Point","coordinates":[-112.07388,33.44853]},"properties":{"site":"P2","kind":"street-canyon curb","sky_view_factor":0.34,"marker-color":"#264653","marker-symbol":"parking"}},{"type":"Feature","geometry":{"type":"Point","coordinates":[-112.09002,33.46898]},"properties":{"site":"P3","kind":"residential driveway beside a tree","sky_view_factor":0.48,"marker-color":"#264653","marker-symbol":"parking"}},{"type":"Feature","geometry":{"type":"Point","coordinates":[-112.07146,33.44897]},"properties":{"site":"P4","kind":"garage top deck","sky_view_factor":0.91,"marker-color":"#264653","marker-symbol":"parking"}}]}
```

| Route | Street | Length | Why it was picked |
|---|---|---|---|
| R-OPEN | Southern Avenue, E-W | 8.3 km | highest mean sky view factor (0.96) of 128 candidate arterial windows |
| R-MIXED | 19th Avenue, N-S | 7.8 km | most variable sky view in the middle band |
| R-DENSE | Central Avenue, N-S | 7.8 km | lowest mean sky view factor (0.74), through the high-rise core |
| R-TUNNEL | I-10 Deck Park Tunnel, E-W | 5.6 km | covered-road check (822 m under deck) |

<img src="docs/readme/network_routes.png" width="49%" alt="Map of the OSM arterial network of central Phoenix with the four routes and the parking sites"> <img src="docs/readme/traffic_trips.png" width="49%" alt="Distance against time for one R-DENSE trip at three traffic levels, and the durations of all 120 simulated trips">

Traffic comes from SUMO on the OSM network: background demand at three levels, five departure times (08:00 to 16:00) and both directions, giving 120 frozen trips with a position and speed every second. The vehicle parks at five sites: an open lot (P1), the darkest curb on Central Avenue (P2, sky view factor 0.34), a residential driveway beside a tree (P3), a garage top deck (P4) and the P1 stall under a shade roof (P5).

### The street canyon at the P2 curb, in 3D

Drag to rotate, scroll to zoom. This is the block around the darkest curb on Central Avenue, where the downtown archetype parks all day: Overture building footprints raised to their lidar roof height (trees left out), with the curb at the centre. The tallest tower is 114 m; the canyon floor keeps a sky view factor of 0.34.

```stl
solid p2_canyon
facet normal -1 0 0
outer loop
vertex -98.4 37.1 0
vertex -98.5 -14.5 0
vertex -98.5 -14.5 113.8
endloop
endfacet
facet normal -1 0 0
outer loop
vertex -98.4 37.1 0
vertex -98.5 -14.5 113.8
vertex -98.4 37.1 113.8
endloop
endfacet
facet normal -0.01 -1 0
outer loop
vertex -98.5 -14.5 0
vertex -39.2 -14.8 0
vertex -39.2 -14.8 113.8
endloop
endfacet
facet normal -0.01 -1 0
outer loop
vertex -98.5 -14.5 0
vertex -39.2 -14.8 113.8
vertex -98.5 -14.5 113.8
endloop
endfacet
facet normal 1 -0.01 0
outer loop
vertex -39.2 -14.8 0
vertex -39.2 -13.9 0
vertex -39.2 -13.9 113.8
endloop
endfacet
facet normal 1 -0.01 0
outer loop
vertex -39.2 -14.8 0
vertex -39.2 -13.9 113.8
vertex -39.2 -14.8 113.8
endloop
endfacet
facet normal -0.01 -1 0
outer loop
vertex -39.2 -13.9 0
vertex -33.5 -13.9 0
vertex -33.5 -13.9 113.8
endloop
endfacet
facet normal -0.01 -1 0
outer loop
vertex -39.2 -13.9 0
vertex -33.5 -13.9 113.8
vertex -39.2 -13.9 113.8
endloop
endfacet
facet normal -0.62 -0.78 0
outer loop
vertex -33.5 -13.9 0
vertex -32 -15.1 0
vertex -32 -15.1 113.8
endloop
endfacet
facet normal -0.62 -0.78 0
outer loop
vertex -33.5 -13.9 0
vertex -32 -15.1 113.8
vertex -33.5 -13.9 113.8
endloop
endfacet
facet normal 0 -1 0
outer loop
vertex -32 -15.1 0
vertex -15.9 -15.1 0
vertex -15.9 -15.1 113.8
endloop
endfacet
facet normal 0 -1 0
outer loop
vertex -32 -15.1 0
vertex -15.9 -15.1 113.8
vertex -32 -15.1 113.8
endloop
endfacet
facet normal 1 -0.04 0
outer loop
vertex -15.9 -15.1 0
vertex -15.9 -13.6 0
vertex -15.9 -13.6 113.8
endloop
endfacet
facet normal 1 -0.04 0
outer loop
vertex -15.9 -15.1 0
vertex -15.9 -13.6 113.8
vertex -15.9 -15.1 113.8
endloop
endfacet
facet normal 0.65 -0.76 0
outer loop
vertex -15.9 -13.6 0
vertex -13.2 -11.4 0
vertex -13.2 -11.4 113.8
endloop
endfacet
facet normal 0.65 -0.76 0
outer loop
vertex -15.9 -13.6 0
vertex -13.2 -11.4 113.8
vertex -15.9 -13.6 113.8
endloop
endfacet
facet normal -0.7 -0.71 0
outer loop
vertex -13.2 -11.4 0
vertex -9.4 -15.2 0
vertex -9.4 -15.2 113.8
endloop
endfacet
facet normal -0.7 -0.71 0
outer loop
vertex -13.2 -11.4 0
vertex -9.4 -15.2 113.8
vertex -13.2 -11.4 113.8
endloop
endfacet
facet normal -0.02 -1 0
outer loop
vertex -9.4 -15.2 0
vertex -7.9 -15.2 0
vertex -7.9 -15.2 113.8
endloop
endfacet
facet normal -0.02 -1 0
outer loop
vertex -9.4 -15.2 0
vertex -7.9 -15.2 113.8
vertex -9.4 -15.2 113.8
endloop
endfacet
facet normal 1 -0 0
outer loop
vertex -7.9 -15.2 0
vertex -7.9 1.1 0
vertex -7.9 1.1 113.8
endloop
endfacet
facet normal 1 -0 0
outer loop
vertex -7.9 -15.2 0
vertex -7.9 1.1 113.8
vertex -7.9 -15.2 113.8
endloop
endfacet
facet normal 0.7 0.71 0
outer loop
vertex -7.9 1.1 0
vertex -9.1 2.2 0
vertex -9.1 2.2 113.8
endloop
endfacet
facet normal 0.7 0.71 -0
outer loop
vertex -7.9 1.1 0
vertex -9.1 2.2 113.8
vertex -7.9 1.1 113.8
endloop
endfacet
facet normal 1 -0.02 0
outer loop
vertex -9.1 2.2 0
vertex -9 7.7 0
vertex -9 7.7 113.8
endloop
endfacet
facet normal 1 -0.02 0
outer loop
vertex -9.1 2.2 0
vertex -9 7.7 113.8
vertex -9.1 2.2 113.8
endloop
endfacet
facet normal 0.01 -1 0
outer loop
vertex -9 7.7 0
vertex -7.9 7.7 0
vertex -7.9 7.7 113.8
endloop
endfacet
facet normal 0.01 -1 0
outer loop
vertex -9 7.7 0
vertex -7.9 7.7 113.8
vertex -9 7.7 113.8
endloop
endfacet
facet normal 1 -0.02 0
outer loop
vertex -7.9 7.7 0
vertex -7.7 24.6 0
vertex -7.7 24.6 113.8
endloop
endfacet
facet normal 1 -0.02 0
outer loop
vertex -7.9 7.7 0
vertex -7.7 24.6 113.8
vertex -7.9 7.7 113.8
endloop
endfacet
facet normal 0.01 1 0
outer loop
vertex -7.7 24.6 0
vertex -23.4 24.7 0
vertex -23.4 24.7 113.8
endloop
endfacet
facet normal 0.01 1 -0
outer loop
vertex -7.7 24.6 0
vertex -23.4 24.7 113.8
vertex -7.7 24.6 113.8
endloop
endfacet
facet normal -0.5 0.86 0
outer loop
vertex -23.4 24.7 0
vertex -24.6 24 0
vertex -24.6 24 113.8
endloop
endfacet
facet normal -0.5 0.86 0
outer loop
vertex -23.4 24.7 0
vertex -24.6 24 113.8
vertex -23.4 24.7 113.8
endloop
endfacet
facet normal -0.94 -0.35 0
outer loop
vertex -24.6 24 0
vertex -24.1 22.7 0
vertex -24.1 22.7 113.8
endloop
endfacet
facet normal -0.94 -0.35 0
outer loop
vertex -24.6 24 0
vertex -24.1 22.7 113.8
vertex -24.6 24 113.8
endloop
endfacet
facet normal 0.01 1 0
outer loop
vertex -24.1 22.7 0
vertex -29.4 22.7 0
vertex -29.4 22.7 113.8
endloop
endfacet
facet normal 0.01 1 -0
outer loop
vertex -24.1 22.7 0
vertex -29.4 22.7 113.8
vertex -24.1 22.7 113.8
endloop
endfacet
facet normal 0.72 0.69 0
outer loop
vertex -29.4 22.7 0
vertex -31.1 24.6 0
vertex -31.1 24.6 113.8
endloop
endfacet
facet normal 0.72 0.69 -0
outer loop
vertex -29.4 22.7 0
vertex -31.1 24.6 113.8
vertex -29.4 22.7 113.8
endloop
endfacet
facet normal 0.01 1 0
outer loop
vertex -31.1 24.6 0
vertex -39 24.7 0
vertex -39 24.7 113.8
endloop
endfacet
facet normal 0.01 1 -0
outer loop
vertex -31.1 24.6 0
vertex -39 24.7 113.8
vertex -31.1 24.6 113.8
endloop
endfacet
facet normal 0.69 0.72 0
outer loop
vertex -39 24.7 0
vertex -52.1 37.2 0
vertex -52.1 37.2 113.8
endloop
endfacet
facet normal 0.69 0.72 -0
outer loop
vertex -39 24.7 0
vertex -52.1 37.2 113.8
vertex -39 24.7 113.8
endloop
endfacet
facet normal 1 0.04 0
outer loop
vertex -52.1 37.2 0
vertex -52.9 59.7 0
vertex -52.9 59.7 113.8
endloop
endfacet
facet normal 1 0.04 -0
outer loop
vertex -52.1 37.2 0
vertex -52.9 59.7 113.8
vertex -52.1 37.2 113.8
endloop
endfacet
facet normal 0.02 -1 0
outer loop
vertex -52.9 59.7 0
vertex -51.9 59.7 0
vertex -51.9 59.7 113.8
endloop
endfacet
facet normal 0.02 -1 0
outer loop
vertex -52.9 59.7 0
vertex -51.9 59.7 113.8
vertex -52.9 59.7 113.8
endloop
endfacet
facet normal 1 -0.01 0
outer loop
vertex -51.9 59.7 0
vertex -51.8 76.5 0
vertex -51.8 76.5 113.8
endloop
endfacet
facet normal 1 -0.01 0
outer loop
vertex -51.9 59.7 0
vertex -51.8 76.5 113.8
vertex -51.9 59.7 113.8
endloop
endfacet
facet normal 0 1 0
outer loop
vertex -51.8 76.5 0
vertex -68.1 76.5 0
vertex -68.1 76.5 113.8
endloop
endfacet
facet normal 0 1 -0
outer loop
vertex -51.8 76.5 0
vertex -68.1 76.5 113.8
vertex -51.8 76.5 113.8
endloop
endfacet
facet normal -0.88 0.47 0
outer loop
vertex -68.1 76.5 0
vertex -68.6 75.7 0
vertex -68.6 75.7 113.8
endloop
endfacet
facet normal -0.88 0.47 0
outer loop
vertex -68.1 76.5 0
vertex -68.6 75.7 113.8
vertex -68.1 76.5 113.8
endloop
endfacet
facet normal 0.05 1 0
outer loop
vertex -68.6 75.7 0
vertex -90.9 76.7 0
vertex -90.9 76.7 113.8
endloop
endfacet
facet normal 0.05 1 -0
outer loop
vertex -68.6 75.7 0
vertex -90.9 76.7 113.8
vertex -68.6 75.7 113.8
endloop
endfacet
facet normal -0.79 0.61 0
outer loop
vertex -90.9 76.7 0
vertex -93.9 72.7 0
vertex -93.9 72.7 113.8
endloop
endfacet
facet normal -0.79 0.61 0
outer loop
vertex -90.9 76.7 0
vertex -93.9 72.7 113.8
vertex -90.9 76.7 113.8
endloop
endfacet
facet normal 0.6 0.8 0
outer loop
vertex -93.9 72.7 0
vertex -98.9 76.5 0
vertex -98.9 76.5 113.8
endloop
endfacet
facet normal 0.6 0.8 -0
outer loop
vertex -93.9 72.7 0
vertex -98.9 76.5 113.8
vertex -93.9 72.7 113.8
endloop
endfacet
facet normal -1 -0.05 0
outer loop
vertex -98.9 76.5 0
vertex -97.9 53.9 0
vertex -97.9 53.9 113.8
endloop
endfacet
facet normal -1 -0.05 0
outer loop
vertex -98.9 76.5 0
vertex -97.9 53.9 113.8
vertex -98.9 76.5 113.8
endloop
endfacet
facet normal 0.01 1 0
outer loop
vertex -97.9 53.9 0
vertex -99.3 53.9 0
vertex -99.3 53.9 113.8
endloop
endfacet
facet normal 0.01 1 -0
outer loop
vertex -97.9 53.9 0
vertex -99.3 53.9 113.8
vertex -97.9 53.9 113.8
endloop
endfacet
facet normal -1 -0 0
outer loop
vertex -99.3 53.9 0
vertex -99.3 37.1 0
vertex -99.3 37.1 113.8
endloop
endfacet
facet normal -1 -0 0
outer loop
vertex -99.3 53.9 0
vertex -99.3 37.1 113.8
vertex -99.3 53.9 113.8
endloop
endfacet
facet normal -0.01 -1 0
outer loop
vertex -99.3 37.1 0
vertex -98.4 37.1 0
vertex -98.4 37.1 113.8
endloop
endfacet
facet normal -0.01 -1 0
outer loop
vertex -99.3 37.1 0
vertex -98.4 37.1 113.8
vertex -99.3 37.1 113.8
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -99.3 53.9 113.8
vertex -99.3 37.1 113.8
vertex -98.4 37.1 113.8
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -93.9 72.7 113.8
vertex -98.9 76.5 113.8
vertex -97.9 53.9 113.8
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -68.6 75.7 113.8
vertex -90.9 76.7 113.8
vertex -93.9 72.7 113.8
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -51.8 76.5 113.8
vertex -68.1 76.5 113.8
vertex -68.6 75.7 113.8
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -52.9 59.7 113.8
vertex -51.9 59.7 113.8
vertex -51.8 76.5 113.8
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -29.4 22.7 113.8
vertex -31.1 24.6 113.8
vertex -39 24.7 113.8
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -23.4 24.7 113.8
vertex -24.6 24 113.8
vertex -24.1 22.7 113.8
endloop
endfacet
facet normal 0 -0 1
outer loop
vertex -7.9 7.7 113.8
vertex -7.7 24.6 113.8
vertex -9 7.7 113.8
endloop
endfacet
facet normal 0 -0 1
outer loop
vertex -7.9 -15.2 113.8
vertex -7.9 1.1 113.8
vertex -13.2 -11.4 113.8
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -13.2 -11.4 113.8
vertex -9.4 -15.2 113.8
vertex -7.9 -15.2 113.8
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -32 -15.1 113.8
vertex -15.9 -15.1 113.8
vertex -15.9 -13.6 113.8
endloop
endfacet
facet normal -0 0 1
outer loop
vertex -98.5 -14.5 113.8
vertex -39.2 -14.8 113.8
vertex -39.2 -13.9 113.8
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -97.9 53.9 113.8
vertex -99.3 53.9 113.8
vertex -98.4 37.1 113.8
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -68.6 75.7 113.8
vertex -93.9 72.7 113.8
vertex -97.9 53.9 113.8
endloop
endfacet
facet normal 0 -0 1
outer loop
vertex -52.9 59.7 113.8
vertex -51.8 76.5 113.8
vertex -68.6 75.7 113.8
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -23.4 24.7 113.8
vertex -24.1 22.7 113.8
vertex -7.7 24.6 113.8
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -9.1 2.2 113.8
vertex -13.2 -11.4 113.8
vertex -7.9 1.1 113.8
endloop
endfacet
facet normal 0 -0 1
outer loop
vertex -32 -15.1 113.8
vertex -15.9 -13.6 113.8
vertex -33.5 -13.9 113.8
endloop
endfacet
facet normal -0 0 1
outer loop
vertex -98.4 37.1 113.8
vertex -98.5 -14.5 113.8
vertex -52.1 37.2 113.8
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -68.6 75.7 113.8
vertex -97.9 53.9 113.8
vertex -52.9 59.7 113.8
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -52.1 37.2 113.8
vertex -52.9 59.7 113.8
vertex -97.9 53.9 113.8
endloop
endfacet
facet normal -0 0 1
outer loop
vertex -24.1 22.7 113.8
vertex -9 7.7 113.8
vertex -7.7 24.6 113.8
endloop
endfacet
facet normal 0 -0 1
outer loop
vertex -13.2 -11.4 113.8
vertex -9.1 2.2 113.8
vertex -33.5 -13.9 113.8
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -13.2 -11.4 113.8
vertex -33.5 -13.9 113.8
vertex -15.9 -13.6 113.8
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -52.1 37.2 113.8
vertex -98.5 -14.5 113.8
vertex -39 24.7 113.8
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -98.4 37.1 113.8
vertex -52.1 37.2 113.8
vertex -97.9 53.9 113.8
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -9 7.7 113.8
vertex -24.1 22.7 113.8
vertex -9.1 2.2 113.8
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -33.5 -13.9 113.8
vertex -9.1 2.2 113.8
vertex -29.4 22.7 113.8
endloop
endfacet
facet normal 0 -0 1
outer loop
vertex -39.2 -13.9 113.8
vertex -39 24.7 113.8
vertex -98.5 -14.5 113.8
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -29.4 22.7 113.8
vertex -9.1 2.2 113.8
vertex -24.1 22.7 113.8
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -39 24.7 113.8
vertex -39.2 -13.9 113.8
vertex -29.4 22.7 113.8
endloop
endfacet
facet normal 0 -0 1
outer loop
vertex -33.5 -13.9 113.8
vertex -29.4 22.7 113.8
vertex -39.2 -13.9 113.8
endloop
endfacet
facet normal -1 -0 0
outer loop
vertex -53.4 117.7 0
vertex -53.4 100.8 0
vertex -53.4 100.8 6.6
endloop
endfacet
facet normal -1 -0 0
outer loop
vertex -53.4 117.7 0
vertex -53.4 100.8 6.6
vertex -53.4 117.7 6.6
endloop
endfacet
facet normal -0 -1 0
outer loop
vertex -53.4 100.8 0
vertex -45.5 100.8 0
vertex -45.5 100.8 6.6
endloop
endfacet
facet normal -0 -1 0
outer loop
vertex -53.4 100.8 0
vertex -45.5 100.8 6.6
vertex -53.4 100.8 6.6
endloop
endfacet
facet normal 1 0 0
outer loop
vertex -45.5 100.8 0
vertex -45.5 117.8 0
vertex -45.5 117.8 6.6
endloop
endfacet
facet normal 1 0 -0
outer loop
vertex -45.5 100.8 0
vertex -45.5 117.8 6.6
vertex -45.5 100.8 6.6
endloop
endfacet
facet normal -0 1 0
outer loop
vertex -45.5 117.8 0
vertex -53.4 117.7 0
vertex -53.4 117.7 6.6
endloop
endfacet
facet normal -0 1 0
outer loop
vertex -45.5 117.8 0
vertex -53.4 117.7 6.6
vertex -45.5 117.8 6.6
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -45.5 100.8 6.6
vertex -45.5 117.8 6.6
vertex -53.4 100.8 6.6
endloop
endfacet
facet normal -0 0 1
outer loop
vertex -53.4 117.7 6.6
vertex -53.4 100.8 6.6
vertex -45.5 117.8 6.6
endloop
endfacet
facet normal -0 1 0
outer loop
vertex -30.9 113.1 0
vertex -45.5 113.1 0
vertex -45.5 113.1 7.1
endloop
endfacet
facet normal -0 1 0
outer loop
vertex -30.9 113.1 0
vertex -45.5 113.1 7.1
vertex -30.9 113.1 7.1
endloop
endfacet
facet normal -1 -0 0
outer loop
vertex -45.5 113.1 0
vertex -45.5 100.8 0
vertex -45.5 100.8 7.1
endloop
endfacet
facet normal -1 -0 0
outer loop
vertex -45.5 113.1 0
vertex -45.5 100.8 7.1
vertex -45.5 113.1 7.1
endloop
endfacet
facet normal -0 -1 0
outer loop
vertex -45.5 100.8 0
vertex -30.9 100.8 0
vertex -30.9 100.8 7.1
endloop
endfacet
facet normal -0 -1 0
outer loop
vertex -45.5 100.8 0
vertex -30.9 100.8 7.1
vertex -45.5 100.8 7.1
endloop
endfacet
facet normal 1 0 0
outer loop
vertex -30.9 100.8 0
vertex -30.9 113.1 0
vertex -30.9 113.1 7.1
endloop
endfacet
facet normal 1 0 -0
outer loop
vertex -30.9 100.8 0
vertex -30.9 113.1 7.1
vertex -30.9 100.8 7.1
endloop
endfacet
facet normal -0 0 1
outer loop
vertex -45.5 100.8 7.1
vertex -30.9 100.8 7.1
vertex -30.9 113.1 7.1
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -30.9 113.1 7.1
vertex -45.5 113.1 7.1
vertex -45.5 100.8 7.1
endloop
endfacet
facet normal -0.26 -0.97 0
outer loop
vertex -37.8 -61.8 0
vertex -18.7 -66.9 0
vertex -18.7 -66.9 12.9
endloop
endfacet
facet normal -0.26 -0.97 0
outer loop
vertex -37.8 -61.8 0
vertex -18.7 -66.9 12.9
vertex -37.8 -61.8 12.9
endloop
endfacet
facet normal 0.95 -0.31 0
outer loop
vertex -18.7 -66.9 0
vertex -10.7 -42.4 0
vertex -10.7 -42.4 12.9
endloop
endfacet
facet normal 0.95 -0.31 0
outer loop
vertex -18.7 -66.9 0
vertex -10.7 -42.4 12.9
vertex -18.7 -66.9 12.9
endloop
endfacet
facet normal 0.01 1 0
outer loop
vertex -10.7 -42.4 0
vertex -71.1 -42.1 0
vertex -71.1 -42.1 12.9
endloop
endfacet
facet normal 0.01 1 -0
outer loop
vertex -10.7 -42.4 0
vertex -71.1 -42.1 12.9
vertex -10.7 -42.4 12.9
endloop
endfacet
facet normal -1 0 0
outer loop
vertex -71.1 -42.1 0
vertex -71.2 -52.5 0
vertex -71.2 -52.5 12.9
endloop
endfacet
facet normal -1 0 0
outer loop
vertex -71.1 -42.1 0
vertex -71.2 -52.5 12.9
vertex -71.1 -42.1 12.9
endloop
endfacet
facet normal -0.28 -0.96 0
outer loop
vertex -71.2 -52.5 0
vertex -52.9 -57.8 0
vertex -52.9 -57.8 12.9
endloop
endfacet
facet normal -0.28 -0.96 0
outer loop
vertex -71.2 -52.5 0
vertex -52.9 -57.8 12.9
vertex -71.2 -52.5 12.9
endloop
endfacet
facet normal -0.98 0.2 0
outer loop
vertex -52.9 -57.8 0
vertex -53.3 -59.8 0
vertex -53.3 -59.8 12.9
endloop
endfacet
facet normal -0.98 0.2 0
outer loop
vertex -52.9 -57.8 0
vertex -53.3 -59.8 12.9
vertex -52.9 -57.8 12.9
endloop
endfacet
facet normal -0.26 -0.97 0
outer loop
vertex -53.3 -59.8 0
vertex -38.4 -63.8 0
vertex -38.4 -63.8 12.9
endloop
endfacet
facet normal -0.26 -0.97 0
outer loop
vertex -53.3 -59.8 0
vertex -38.4 -63.8 12.9
vertex -53.3 -59.8 12.9
endloop
endfacet
facet normal 0.96 -0.28 0
outer loop
vertex -38.4 -63.8 0
vertex -37.8 -61.8 0
vertex -37.8 -61.8 12.9
endloop
endfacet
facet normal 0.96 -0.28 0
outer loop
vertex -38.4 -63.8 0
vertex -37.8 -61.8 12.9
vertex -38.4 -63.8 12.9
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -53.3 -59.8 12.9
vertex -38.4 -63.8 12.9
vertex -37.8 -61.8 12.9
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -71.1 -42.1 12.9
vertex -71.2 -52.5 12.9
vertex -52.9 -57.8 12.9
endloop
endfacet
facet normal 0 -0 1
outer loop
vertex -18.7 -66.9 12.9
vertex -10.7 -42.4 12.9
vertex -37.8 -61.8 12.9
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -52.9 -57.8 12.9
vertex -53.3 -59.8 12.9
vertex -37.8 -61.8 12.9
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -71.1 -42.1 12.9
vertex -52.9 -57.8 12.9
vertex -10.7 -42.4 12.9
endloop
endfacet
facet normal -0 0 1
outer loop
vertex -52.9 -57.8 12.9
vertex -37.8 -61.8 12.9
vertex -10.7 -42.4 12.9
endloop
endfacet
facet normal -0.34 -0.94 0
outer loop
vertex 16.4 -74.4 0
vertex 43.2 -84 0
vertex 43.2 -84 17.1
endloop
endfacet
facet normal -0.34 -0.94 0
outer loop
vertex 16.4 -74.4 0
vertex 43.2 -84 17.1
vertex 16.4 -74.4 17.1
endloop
endfacet
facet normal 1 0 0
outer loop
vertex 43.2 -84 0
vertex 43.2 -77.8 0
vertex 43.2 -77.8 17.1
endloop
endfacet
facet normal 1 0 -0
outer loop
vertex 43.2 -84 0
vertex 43.2 -77.8 17.1
vertex 43.2 -84 17.1
endloop
endfacet
facet normal -0 1 0
outer loop
vertex 43.2 -77.8 0
vertex 37.6 -77.8 0
vertex 37.6 -77.8 17.1
endloop
endfacet
facet normal -0 1 0
outer loop
vertex 43.2 -77.8 0
vertex 37.6 -77.8 17.1
vertex 43.2 -77.8 17.1
endloop
endfacet
facet normal 1 0 0
outer loop
vertex 37.6 -77.8 0
vertex 37.6 -73.2 0
vertex 37.6 -73.2 17.1
endloop
endfacet
facet normal 1 0 -0
outer loop
vertex 37.6 -77.8 0
vertex 37.6 -73.2 17.1
vertex 37.6 -77.8 17.1
endloop
endfacet
facet normal -0 1 0
outer loop
vertex 37.6 -73.2 0
vertex 34.3 -73.2 0
vertex 34.3 -73.2 17.1
endloop
endfacet
facet normal -0 1 0
outer loop
vertex 37.6 -73.2 0
vertex 34.3 -73.2 17.1
vertex 37.6 -73.2 17.1
endloop
endfacet
facet normal 1 0 0
outer loop
vertex 34.3 -73.2 0
vertex 34.2 -54.7 0
vertex 34.2 -54.7 17.1
endloop
endfacet
facet normal 1 0 -0
outer loop
vertex 34.3 -73.2 0
vertex 34.2 -54.7 17.1
vertex 34.3 -73.2 17.1
endloop
endfacet
facet normal 0 -1 0
outer loop
vertex 34.2 -54.7 0
vertex 38.1 -54.7 0
vertex 38.1 -54.7 17.1
endloop
endfacet
facet normal 0 -1 0
outer loop
vertex 34.2 -54.7 0
vertex 38.1 -54.7 17.1
vertex 34.2 -54.7 17.1
endloop
endfacet
facet normal 1 0 0
outer loop
vertex 38.1 -54.7 0
vertex 38.1 -50.4 0
vertex 38.1 -50.4 17.1
endloop
endfacet
facet normal 1 0 -0
outer loop
vertex 38.1 -54.7 0
vertex 38.1 -50.4 17.1
vertex 38.1 -54.7 17.1
endloop
endfacet
facet normal 0 -1 0
outer loop
vertex 38.1 -50.4 0
vertex 45.5 -50.3 0
vertex 45.5 -50.3 17.1
endloop
endfacet
facet normal 0 -1 0
outer loop
vertex 38.1 -50.4 0
vertex 45.5 -50.3 17.1
vertex 38.1 -50.4 17.1
endloop
endfacet
facet normal 1 0 0
outer loop
vertex 45.5 -50.3 0
vertex 45.5 -46.8 0
vertex 45.5 -46.8 17.1
endloop
endfacet
facet normal 1 0 -0
outer loop
vertex 45.5 -50.3 0
vertex 45.5 -46.8 17.1
vertex 45.5 -50.3 17.1
endloop
endfacet
facet normal -0.02 1 0
outer loop
vertex 45.5 -46.8 0
vertex 20.6 -47.4 0
vertex 20.6 -47.4 17.1
endloop
endfacet
facet normal -0.02 1 0
outer loop
vertex 45.5 -46.8 0
vertex 20.6 -47.4 17.1
vertex 45.5 -46.8 17.1
endloop
endfacet
facet normal -0.97 0.23 0
outer loop
vertex 20.6 -47.4 0
vertex 18.8 -55 0
vertex 18.8 -55 17.1
endloop
endfacet
facet normal -0.97 0.23 0
outer loop
vertex 20.6 -47.4 0
vertex 18.8 -55 17.1
vertex 20.6 -47.4 17.1
endloop
endfacet
facet normal 0.1 1 0
outer loop
vertex 18.8 -55 0
vertex 15.8 -54.7 0
vertex 15.8 -54.7 17.1
endloop
endfacet
facet normal 0.1 1 -0
outer loop
vertex 18.8 -55 0
vertex 15.8 -54.7 17.1
vertex 18.8 -55 17.1
endloop
endfacet
facet normal -1 -0.03 0
outer loop
vertex 15.8 -54.7 0
vertex 16.4 -74.4 0
vertex 16.4 -74.4 17.1
endloop
endfacet
facet normal -1 -0.03 0
outer loop
vertex 15.8 -54.7 0
vertex 16.4 -74.4 17.1
vertex 15.8 -54.7 17.1
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 18.8 -55 17.1
vertex 15.8 -54.7 17.1
vertex 16.4 -74.4 17.1
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 45.5 -46.8 17.1
vertex 20.6 -47.4 17.1
vertex 38.1 -50.4 17.1
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 38.1 -50.4 17.1
vertex 45.5 -50.3 17.1
vertex 45.5 -46.8 17.1
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 34.2 -54.7 17.1
vertex 38.1 -54.7 17.1
vertex 38.1 -50.4 17.1
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 37.6 -77.8 17.1
vertex 37.6 -73.2 17.1
vertex 34.3 -73.2 17.1
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 43.2 -84 17.1
vertex 43.2 -77.8 17.1
vertex 37.6 -77.8 17.1
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 38.1 -50.4 17.1
vertex 20.6 -47.4 17.1
vertex 34.2 -54.7 17.1
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 16.4 -74.4 17.1
vertex 43.2 -84 17.1
vertex 37.6 -77.8 17.1
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 18.8 -55 17.1
vertex 34.2 -54.7 17.1
vertex 20.6 -47.4 17.1
endloop
endfacet
facet normal -0 0 1
outer loop
vertex 16.4 -74.4 17.1
vertex 37.6 -77.8 17.1
vertex 34.3 -73.2 17.1
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 34.2 -54.7 17.1
vertex 18.8 -55 17.1
vertex 34.3 -73.2 17.1
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 16.4 -74.4 17.1
vertex 34.3 -73.2 17.1
vertex 18.8 -55 17.1
endloop
endfacet
facet normal 1 -0.03 0
outer loop
vertex 98.3 -51.9 0
vertex 98.4 -48.3 0
vertex 98.4 -48.3 111.9
endloop
endfacet
facet normal 1 -0.03 0
outer loop
vertex 98.3 -51.9 0
vertex 98.4 -48.3 111.9
vertex 98.3 -51.9 111.9
endloop
endfacet
facet normal 0.03 1 0
outer loop
vertex 98.4 -48.3 0
vertex 45.5 -46.8 0
vertex 45.5 -46.8 111.9
endloop
endfacet
facet normal 0.03 1 -0
outer loop
vertex 98.4 -48.3 0
vertex 45.5 -46.8 111.9
vertex 98.4 -48.3 111.9
endloop
endfacet
facet normal -1 -0 0
outer loop
vertex 45.5 -46.8 0
vertex 45.5 -50.3 0
vertex 45.5 -50.3 111.9
endloop
endfacet
facet normal -1 -0 0
outer loop
vertex 45.5 -46.8 0
vertex 45.5 -50.3 111.9
vertex 45.5 -46.8 111.9
endloop
endfacet
facet normal -0 1 0
outer loop
vertex 45.5 -50.3 0
vertex 38.1 -50.4 0
vertex 38.1 -50.4 111.9
endloop
endfacet
facet normal -0 1 0
outer loop
vertex 45.5 -50.3 0
vertex 38.1 -50.4 111.9
vertex 45.5 -50.3 111.9
endloop
endfacet
facet normal -1 -0 0
outer loop
vertex 38.1 -50.4 0
vertex 38.1 -54.7 0
vertex 38.1 -54.7 111.9
endloop
endfacet
facet normal -1 -0 0
outer loop
vertex 38.1 -50.4 0
vertex 38.1 -54.7 111.9
vertex 38.1 -50.4 111.9
endloop
endfacet
facet normal -0 1 0
outer loop
vertex 38.1 -54.7 0
vertex 34.2 -54.7 0
vertex 34.2 -54.7 111.9
endloop
endfacet
facet normal -0 1 0
outer loop
vertex 38.1 -54.7 0
vertex 34.2 -54.7 111.9
vertex 38.1 -54.7 111.9
endloop
endfacet
facet normal -1 -0 0
outer loop
vertex 34.2 -54.7 0
vertex 34.3 -73.2 0
vertex 34.3 -73.2 111.9
endloop
endfacet
facet normal -1 -0 0
outer loop
vertex 34.2 -54.7 0
vertex 34.3 -73.2 111.9
vertex 34.2 -54.7 111.9
endloop
endfacet
facet normal 0 -1 0
outer loop
vertex 34.3 -73.2 0
vertex 37.6 -73.2 0
vertex 37.6 -73.2 111.9
endloop
endfacet
facet normal 0 -1 0
outer loop
vertex 34.3 -73.2 0
vertex 37.6 -73.2 111.9
vertex 34.3 -73.2 111.9
endloop
endfacet
facet normal -1 -0 0
outer loop
vertex 37.6 -73.2 0
vertex 37.6 -77.8 0
vertex 37.6 -77.8 111.9
endloop
endfacet
facet normal -1 -0 0
outer loop
vertex 37.6 -73.2 0
vertex 37.6 -77.8 111.9
vertex 37.6 -73.2 111.9
endloop
endfacet
facet normal 0 -1 0
outer loop
vertex 37.6 -77.8 0
vertex 43.2 -77.8 0
vertex 43.2 -77.8 111.9
endloop
endfacet
facet normal 0 -1 0
outer loop
vertex 37.6 -77.8 0
vertex 43.2 -77.8 111.9
vertex 37.6 -77.8 111.9
endloop
endfacet
facet normal -1 -0 0
outer loop
vertex 43.2 -77.8 0
vertex 43.2 -84 0
vertex 43.2 -84 111.9
endloop
endfacet
facet normal -1 -0 0
outer loop
vertex 43.2 -77.8 0
vertex 43.2 -84 111.9
vertex 43.2 -77.8 111.9
endloop
endfacet
facet normal -0.01 -1 0
outer loop
vertex 43.2 -84 0
vertex 98 -84.6 0
vertex 98 -84.6 111.9
endloop
endfacet
facet normal -0.01 -1 0
outer loop
vertex 43.2 -84 0
vertex 98 -84.6 111.9
vertex 43.2 -84 111.9
endloop
endfacet
facet normal 1 0.04 0
outer loop
vertex 98 -84.6 0
vertex 97.8 -80.5 0
vertex 97.8 -80.5 111.9
endloop
endfacet
facet normal 1 0.04 -0
outer loop
vertex 98 -84.6 0
vertex 97.8 -80.5 111.9
vertex 98 -84.6 111.9
endloop
endfacet
facet normal 0.04 -1 0
outer loop
vertex 97.8 -80.5 0
vertex 102.9 -80.3 0
vertex 102.9 -80.3 111.9
endloop
endfacet
facet normal 0.04 -1 0
outer loop
vertex 97.8 -80.5 0
vertex 102.9 -80.3 111.9
vertex 97.8 -80.5 111.9
endloop
endfacet
facet normal 1 0.05 0
outer loop
vertex 102.9 -80.3 0
vertex 102.7 -75.9 0
vertex 102.7 -75.9 111.9
endloop
endfacet
facet normal 1 0.05 -0
outer loop
vertex 102.9 -80.3 0
vertex 102.7 -75.9 111.9
vertex 102.9 -80.3 111.9
endloop
endfacet
facet normal 0.03 -1 0
outer loop
vertex 102.7 -75.9 0
vertex 107.7 -75.7 0
vertex 107.7 -75.7 111.9
endloop
endfacet
facet normal 0.03 -1 0
outer loop
vertex 102.7 -75.9 0
vertex 107.7 -75.7 111.9
vertex 102.7 -75.9 111.9
endloop
endfacet
facet normal 1 0.01 0
outer loop
vertex 107.7 -75.7 0
vertex 107.5 -57.6 0
vertex 107.5 -57.6 111.9
endloop
endfacet
facet normal 1 0.01 -0
outer loop
vertex 107.7 -75.7 0
vertex 107.5 -57.6 111.9
vertex 107.7 -75.7 111.9
endloop
endfacet
facet normal -0.01 1 0
outer loop
vertex 107.5 -57.6 0
vertex 103.2 -57.7 0
vertex 103.2 -57.7 111.9
endloop
endfacet
facet normal -0.01 1 0
outer loop
vertex 107.5 -57.6 0
vertex 103.2 -57.7 111.9
vertex 107.5 -57.6 111.9
endloop
endfacet
facet normal 1 -0.04 0
outer loop
vertex 103.2 -57.7 0
vertex 103.4 -53.2 0
vertex 103.4 -53.2 111.9
endloop
endfacet
facet normal 1 -0.04 0
outer loop
vertex 103.2 -57.7 0
vertex 103.4 -53.2 111.9
vertex 103.2 -57.7 111.9
endloop
endfacet
facet normal 0.25 0.97 0
outer loop
vertex 103.4 -53.2 0
vertex 98.3 -51.9 0
vertex 98.3 -51.9 111.9
endloop
endfacet
facet normal 0.25 0.97 -0
outer loop
vertex 103.4 -53.2 0
vertex 98.3 -51.9 111.9
vertex 103.4 -53.2 111.9
endloop
endfacet
facet normal 0 -0 1
outer loop
vertex 103.2 -57.7 111.9
vertex 103.4 -53.2 111.9
vertex 98.3 -51.9 111.9
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 107.7 -75.7 111.9
vertex 107.5 -57.6 111.9
vertex 103.2 -57.7 111.9
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 97.8 -80.5 111.9
vertex 102.9 -80.3 111.9
vertex 102.7 -75.9 111.9
endloop
endfacet
facet normal -0 0 1
outer loop
vertex 43.2 -84 111.9
vertex 98 -84.6 111.9
vertex 97.8 -80.5 111.9
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 37.6 -73.2 111.9
vertex 37.6 -77.8 111.9
vertex 43.2 -77.8 111.9
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 34.2 -54.7 111.9
vertex 34.3 -73.2 111.9
vertex 37.6 -73.2 111.9
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 45.5 -50.3 111.9
vertex 38.1 -50.4 111.9
vertex 38.1 -54.7 111.9
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 98.4 -48.3 111.9
vertex 45.5 -46.8 111.9
vertex 45.5 -50.3 111.9
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 107.7 -75.7 111.9
vertex 103.2 -57.7 111.9
vertex 102.7 -75.9 111.9
endloop
endfacet
facet normal 0 -0 1
outer loop
vertex 43.2 -84 111.9
vertex 97.8 -80.5 111.9
vertex 43.2 -77.8 111.9
endloop
endfacet
facet normal -0 0 1
outer loop
vertex 34.2 -54.7 111.9
vertex 37.6 -73.2 111.9
vertex 38.1 -54.7 111.9
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 98.4 -48.3 111.9
vertex 45.5 -50.3 111.9
vertex 98.3 -51.9 111.9
endloop
endfacet
facet normal 0 -0 1
outer loop
vertex 102.7 -75.9 111.9
vertex 103.2 -57.7 111.9
vertex 97.8 -80.5 111.9
endloop
endfacet
facet normal -0 0 1
outer loop
vertex 43.2 -77.8 111.9
vertex 97.8 -80.5 111.9
vertex 45.5 -50.3 111.9
endloop
endfacet
facet normal -0 0 1
outer loop
vertex 38.1 -54.7 111.9
vertex 37.6 -73.2 111.9
vertex 45.5 -50.3 111.9
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 98.3 -51.9 111.9
vertex 45.5 -50.3 111.9
vertex 97.8 -80.5 111.9
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 98.3 -51.9 111.9
vertex 97.8 -80.5 111.9
vertex 103.2 -57.7 111.9
endloop
endfacet
facet normal 0 -0 1
outer loop
vertex 43.2 -77.8 111.9
vertex 45.5 -50.3 111.9
vertex 37.6 -73.2 111.9
endloop
endfacet
facet normal 0.01 1 0
outer loop
vertex 108.2 40.5 0
vertex 52.5 40.8 0
vertex 52.5 40.8 85.9
endloop
endfacet
facet normal 0.01 1 -0
outer loop
vertex 108.2 40.5 0
vertex 52.5 40.8 85.9
vertex 108.2 40.5 85.9
endloop
endfacet
facet normal 1 -0.02 0
outer loop
vertex 52.5 40.8 0
vertex 52.6 45.6 0
vertex 52.6 45.6 85.9
endloop
endfacet
facet normal 1 -0.02 0
outer loop
vertex 52.5 40.8 0
vertex 52.6 45.6 85.9
vertex 52.5 40.8 85.9
endloop
endfacet
facet normal 0.01 1 0
outer loop
vertex 52.6 45.6 0
vertex 26.7 45.9 0
vertex 26.7 45.9 85.9
endloop
endfacet
facet normal 0.01 1 -0
outer loop
vertex 52.6 45.6 0
vertex 26.7 45.9 85.9
vertex 52.6 45.6 85.9
endloop
endfacet
facet normal -1 -0 0
outer loop
vertex 26.7 45.9 0
vertex 26.7 41 0
vertex 26.7 41 85.9
endloop
endfacet
facet normal -1 -0 0
outer loop
vertex 26.7 45.9 0
vertex 26.7 41 85.9
vertex 26.7 45.9 85.9
endloop
endfacet
facet normal 0.01 1 0
outer loop
vertex 26.7 41 0
vertex 16.9 41.1 0
vertex 16.9 41.1 85.9
endloop
endfacet
facet normal 0.01 1 -0
outer loop
vertex 26.7 41 0
vertex 16.9 41.1 85.9
vertex 26.7 41 85.9
endloop
endfacet
facet normal -1 0.01 0
outer loop
vertex 16.9 41.1 0
vertex 16.7 7.7 0
vertex 16.7 7.7 85.9
endloop
endfacet
facet normal -1 0.01 0
outer loop
vertex 16.9 41.1 0
vertex 16.7 7.7 85.9
vertex 16.9 41.1 85.9
endloop
endfacet
facet normal -0 -1 0
outer loop
vertex 16.7 7.7 0
vertex 20.8 7.6 0
vertex 20.8 7.6 85.9
endloop
endfacet
facet normal -0 -1 0
outer loop
vertex 16.7 7.7 0
vertex 20.8 7.6 85.9
vertex 16.7 7.7 85.9
endloop
endfacet
facet normal -0.89 0.45 0
outer loop
vertex 20.8 7.6 0
vertex 17.1 0.4 0
vertex 17.1 0.4 85.9
endloop
endfacet
facet normal -0.89 0.45 0
outer loop
vertex 20.8 7.6 0
vertex 17.1 0.4 85.9
vertex 20.8 7.6 85.9
endloop
endfacet
facet normal -1 -0.09 0
outer loop
vertex 17.1 0.4 0
vertex 17.8 -7.4 0
vertex 17.8 -7.4 85.9
endloop
endfacet
facet normal -1 -0.09 0
outer loop
vertex 17.1 0.4 0
vertex 17.8 -7.4 85.9
vertex 17.1 0.4 85.9
endloop
endfacet
facet normal -0.78 -0.63 0
outer loop
vertex 17.8 -7.4 0
vertex 22 -12.6 0
vertex 22 -12.6 85.9
endloop
endfacet
facet normal -0.78 -0.63 0
outer loop
vertex 17.8 -7.4 0
vertex 22 -12.6 85.9
vertex 17.8 -7.4 85.9
endloop
endfacet
facet normal -0.35 -0.94 0
outer loop
vertex 22 -12.6 0
vertex 27.8 -14.7 0
vertex 27.8 -14.7 85.9
endloop
endfacet
facet normal -0.35 -0.94 0
outer loop
vertex 22 -12.6 0
vertex 27.8 -14.7 85.9
vertex 22 -12.6 85.9
endloop
endfacet
facet normal 0.01 -1 0
outer loop
vertex 27.8 -14.7 0
vertex 32.2 -14.6 0
vertex 32.2 -14.6 85.9
endloop
endfacet
facet normal 0.01 -1 0
outer loop
vertex 27.8 -14.7 0
vertex 32.2 -14.6 85.9
vertex 27.8 -14.7 85.9
endloop
endfacet
facet normal 0.47 -0.88 0
outer loop
vertex 32.2 -14.6 0
vertex 37.9 -11.6 0
vertex 37.9 -11.6 85.9
endloop
endfacet
facet normal 0.47 -0.88 0
outer loop
vertex 32.2 -14.6 0
vertex 37.9 -11.6 85.9
vertex 32.2 -14.6 85.9
endloop
endfacet
facet normal -0.99 -0.16 0
outer loop
vertex 37.9 -11.6 0
vertex 38.4 -15.4 0
vertex 38.4 -15.4 85.9
endloop
endfacet
facet normal -0.99 -0.16 0
outer loop
vertex 37.9 -11.6 0
vertex 38.4 -15.4 85.9
vertex 37.9 -11.6 85.9
endloop
endfacet
facet normal -0.02 -1 0
outer loop
vertex 38.4 -15.4 0
vertex 55.2 -15.7 0
vertex 55.2 -15.7 85.9
endloop
endfacet
facet normal -0.02 -1 0
outer loop
vertex 38.4 -15.4 0
vertex 55.2 -15.7 85.9
vertex 38.4 -15.4 85.9
endloop
endfacet
facet normal 1 0.01 0
outer loop
vertex 55.2 -15.7 0
vertex 55.2 -13.9 0
vertex 55.2 -13.9 85.9
endloop
endfacet
facet normal 1 0.01 -0
outer loop
vertex 55.2 -15.7 0
vertex 55.2 -13.9 85.9
vertex 55.2 -15.7 85.9
endloop
endfacet
facet normal -0.05 -1 0
outer loop
vertex 55.2 -13.9 0
vertex 66.1 -14.4 0
vertex 66.1 -14.4 85.9
endloop
endfacet
facet normal -0.05 -1 0
outer loop
vertex 55.2 -13.9 0
vertex 66.1 -14.4 85.9
vertex 55.2 -13.9 85.9
endloop
endfacet
facet normal -1 -0.02 0
outer loop
vertex 66.1 -14.4 0
vertex 66.1 -15.4 0
vertex 66.1 -15.4 85.9
endloop
endfacet
facet normal -1 -0.02 0
outer loop
vertex 66.1 -14.4 0
vertex 66.1 -15.4 85.9
vertex 66.1 -14.4 85.9
endloop
endfacet
facet normal -0.02 -1 0
outer loop
vertex 66.1 -15.4 0
vertex 95 -15.9 0
vertex 95 -15.9 85.9
endloop
endfacet
facet normal -0.02 -1 0
outer loop
vertex 66.1 -15.4 0
vertex 95 -15.9 85.9
vertex 66.1 -15.4 85.9
endloop
endfacet
facet normal 1 -0.01 0
outer loop
vertex 95 -15.9 0
vertex 95.1 -12.3 0
vertex 95.1 -12.3 85.9
endloop
endfacet
facet normal 1 -0.01 0
outer loop
vertex 95 -15.9 0
vertex 95.1 -12.3 85.9
vertex 95 -15.9 85.9
endloop
endfacet
facet normal -0.53 -0.85 0
outer loop
vertex 95.1 -12.3 0
vertex 99.2 -14.8 0
vertex 99.2 -14.8 85.9
endloop
endfacet
facet normal -0.53 -0.85 0
outer loop
vertex 95.1 -12.3 0
vertex 99.2 -14.8 85.9
vertex 95.1 -12.3 85.9
endloop
endfacet
facet normal 0.15 -0.99 0
outer loop
vertex 99.2 -14.8 0
vertex 104.2 -14 0
vertex 104.2 -14 85.9
endloop
endfacet
facet normal 0.15 -0.99 0
outer loop
vertex 99.2 -14.8 0
vertex 104.2 -14 85.9
vertex 99.2 -14.8 85.9
endloop
endfacet
facet normal 0.66 -0.75 0
outer loop
vertex 104.2 -14 0
vertex 106.7 -11.9 0
vertex 106.7 -11.9 85.9
endloop
endfacet
facet normal 0.66 -0.75 0
outer loop
vertex 104.2 -14 0
vertex 106.7 -11.9 85.9
vertex 104.2 -14 85.9
endloop
endfacet
facet normal 0.94 -0.33 0
outer loop
vertex 106.7 -11.9 0
vertex 107.5 -9.5 0
vertex 107.5 -9.5 85.9
endloop
endfacet
facet normal 0.94 -0.33 0
outer loop
vertex 106.7 -11.9 0
vertex 107.5 -9.5 85.9
vertex 106.7 -11.9 85.9
endloop
endfacet
facet normal 0.97 0.23 0
outer loop
vertex 107.5 -9.5 0
vertex 106.5 -5 0
vertex 106.5 -5 85.9
endloop
endfacet
facet normal 0.97 0.23 -0
outer loop
vertex 107.5 -9.5 0
vertex 106.5 -5 85.9
vertex 107.5 -9.5 85.9
endloop
endfacet
facet normal 0.73 0.68 0
outer loop
vertex 106.5 -5 0
vertex 104 -2.4 0
vertex 104 -2.4 85.9
endloop
endfacet
facet normal 0.73 0.68 -0
outer loop
vertex 106.5 -5 0
vertex 104 -2.4 85.9
vertex 106.5 -5 85.9
endloop
endfacet
facet normal -0.02 -1 0
outer loop
vertex 104 -2.4 0
vertex 108 -2.4 0
vertex 108 -2.4 85.9
endloop
endfacet
facet normal -0.02 -1 0
outer loop
vertex 104 -2.4 0
vertex 108 -2.4 85.9
vertex 104 -2.4 85.9
endloop
endfacet
facet normal 1 -0 0
outer loop
vertex 108 -2.4 0
vertex 108.2 40.5 0
vertex 108.2 40.5 85.9
endloop
endfacet
facet normal 1 -0 0
outer loop
vertex 108 -2.4 0
vertex 108.2 40.5 85.9
vertex 108 -2.4 85.9
endloop
endfacet
facet normal -0 0 1
outer loop
vertex 104 -2.4 85.9
vertex 108 -2.4 85.9
vertex 108.2 40.5 85.9
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 107.5 -9.5 85.9
vertex 106.5 -5 85.9
vertex 104.2 -14 85.9
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 104.2 -14 85.9
vertex 106.7 -11.9 85.9
vertex 107.5 -9.5 85.9
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 104 -2.4 85.9
vertex 95.1 -12.3 85.9
vertex 106.5 -5 85.9
endloop
endfacet
facet normal -0 -0 1
outer loop
vertex 66.1 -15.4 85.9
vertex 95 -15.9 85.9
vertex 66.1 -14.4 85.9
endloop
endfacet
facet normal -0 0 1
outer loop
vertex 38.4 -15.4 85.9
vertex 55.2 -15.7 85.9
vertex 55.2 -13.9 85.9
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 27.8 -14.7 85.9
vertex 32.2 -14.6 85.9
vertex 37.9 -11.6 85.9
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 17.8 -7.4 85.9
vertex 22 -12.6 85.9
vertex 27.8 -14.7 85.9
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 20.8 7.6 85.9
vertex 17.1 0.4 85.9
vertex 37.9 -11.6 85.9
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 16.9 41.1 85.9
vertex 16.7 7.7 85.9
vertex 20.8 7.6 85.9
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 52.6 45.6 85.9
vertex 26.7 45.9 85.9
vertex 26.7 41 85.9
endloop
endfacet
facet normal 0 -0 1
outer loop
vertex 104 -2.4 85.9
vertex 108.2 40.5 85.9
vertex 52.5 40.8 85.9
endloop
endfacet
facet normal 0 -0 1
outer loop
vertex 104.2 -14 85.9
vertex 106.5 -5 85.9
vertex 99.2 -14.8 85.9
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 95.1 -12.3 85.9
vertex 66.1 -14.4 85.9
vertex 95 -15.9 85.9
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 37.9 -11.6 85.9
vertex 38.4 -15.4 85.9
vertex 55.2 -13.9 85.9
endloop
endfacet
facet normal -0 -0 1
outer loop
vertex 17.8 -7.4 85.9
vertex 27.8 -14.7 85.9
vertex 17.1 0.4 85.9
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 26.7 41 85.9
vertex 16.9 41.1 85.9
vertex 20.8 7.6 85.9
endloop
endfacet
facet normal 0 -0 1
outer loop
vertex 52.5 40.8 85.9
vertex 52.6 45.6 85.9
vertex 26.7 41 85.9
endloop
endfacet
facet normal 0 -0 1
outer loop
vertex 99.2 -14.8 85.9
vertex 106.5 -5 85.9
vertex 95.1 -12.3 85.9
endloop
endfacet
facet normal -0 -0 1
outer loop
vertex 55.2 -13.9 85.9
vertex 66.1 -14.4 85.9
vertex 52.5 40.8 85.9
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 37.9 -11.6 85.9
vertex 17.1 0.4 85.9
vertex 27.8 -14.7 85.9
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 52.5 40.8 85.9
vertex 26.7 41 85.9
vertex 20.8 7.6 85.9
endloop
endfacet
facet normal 0 -0 1
outer loop
vertex 95.1 -12.3 85.9
vertex 104 -2.4 85.9
vertex 66.1 -14.4 85.9
endloop
endfacet
facet normal -0 0 1
outer loop
vertex 20.8 7.6 85.9
vertex 37.9 -11.6 85.9
vertex 52.5 40.8 85.9
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 52.5 40.8 85.9
vertex 66.1 -14.4 85.9
vertex 104 -2.4 85.9
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 55.2 -13.9 85.9
vertex 52.5 40.8 85.9
vertex 37.9 -11.6 85.9
endloop
endfacet
facet normal 0.05 1 0
outer loop
vertex -13.9 -85.6 0
vertex -19.5 -85.4 0
vertex -19.5 -85.4 4.8
endloop
endfacet
facet normal 0.05 1 -0
outer loop
vertex -13.9 -85.6 0
vertex -19.5 -85.4 4.8
vertex -13.9 -85.6 4.8
endloop
endfacet
facet normal -0.92 -0.4 0
outer loop
vertex -19.5 -85.4 0
vertex -16.1 -93.2 0
vertex -16.1 -93.2 4.8
endloop
endfacet
facet normal -0.92 -0.4 0
outer loop
vertex -19.5 -85.4 0
vertex -16.1 -93.2 4.8
vertex -19.5 -85.4 4.8
endloop
endfacet
facet normal -0.07 -1 0
outer loop
vertex -16.1 -93.2 0
vertex -10.5 -93.6 0
vertex -10.5 -93.6 4.8
endloop
endfacet
facet normal -0.07 -1 0
outer loop
vertex -16.1 -93.2 0
vertex -10.5 -93.6 4.8
vertex -16.1 -93.2 4.8
endloop
endfacet
facet normal 0.92 0.39 0
outer loop
vertex -10.5 -93.6 0
vertex -13.9 -85.6 0
vertex -13.9 -85.6 4.8
endloop
endfacet
facet normal 0.92 0.39 -0
outer loop
vertex -10.5 -93.6 0
vertex -13.9 -85.6 4.8
vertex -10.5 -93.6 4.8
endloop
endfacet
facet normal -0 0 1
outer loop
vertex -16.1 -93.2 4.8
vertex -10.5 -93.6 4.8
vertex -13.9 -85.6 4.8
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -13.9 -85.6 4.8
vertex -19.5 -85.4 4.8
vertex -16.1 -93.2 4.8
endloop
endfacet
facet normal 0.01 1 0
outer loop
vertex -63.7 -97.5 0
vertex -67.7 -97.5 0
vertex -67.7 -97.5 12.7
endloop
endfacet
facet normal 0.01 1 -0
outer loop
vertex -63.7 -97.5 0
vertex -67.7 -97.5 12.7
vertex -63.7 -97.5 12.7
endloop
endfacet
facet normal 1 -0.04 0
outer loop
vertex -67.7 -97.5 0
vertex -66.4 -63.7 0
vertex -66.4 -63.7 12.7
endloop
endfacet
facet normal 1 -0.04 0
outer loop
vertex -67.7 -97.5 0
vertex -66.4 -63.7 12.7
vertex -67.7 -97.5 12.7
endloop
endfacet
facet normal 0.23 0.97 0
outer loop
vertex -66.4 -63.7 0
vertex -92.8 -57.4 0
vertex -92.8 -57.4 12.7
endloop
endfacet
facet normal 0.23 0.97 -0
outer loop
vertex -66.4 -63.7 0
vertex -92.8 -57.4 12.7
vertex -66.4 -63.7 12.7
endloop
endfacet
facet normal -1 0.01 0
outer loop
vertex -92.8 -57.4 0
vertex -92.9 -58.9 0
vertex -92.9 -58.9 12.7
endloop
endfacet
facet normal -1 0.01 0
outer loop
vertex -92.8 -57.4 0
vertex -92.9 -58.9 12.7
vertex -92.8 -57.4 12.7
endloop
endfacet
facet normal 0.27 0.96 0
outer loop
vertex -92.9 -58.9 0
vertex -100.8 -56.6 0
vertex -100.8 -56.6 12.7
endloop
endfacet
facet normal 0.27 0.96 -0
outer loop
vertex -92.9 -58.9 0
vertex -100.8 -56.6 12.7
vertex -92.9 -58.9 12.7
endloop
endfacet
facet normal -1 0.01 0
outer loop
vertex -100.8 -56.6 0
vertex -101.2 -132 0
vertex -101.2 -132 12.7
endloop
endfacet
facet normal -1 0.01 0
outer loop
vertex -100.8 -56.6 0
vertex -101.2 -132 12.7
vertex -100.8 -56.6 12.7
endloop
endfacet
facet normal -0.74 -0.67 0
outer loop
vertex -101.2 -132 0
vertex -96.8 -136.9 0
vertex -96.8 -136.9 12.7
endloop
endfacet
facet normal -0.74 -0.67 0
outer loop
vertex -101.2 -132 0
vertex -96.8 -136.9 12.7
vertex -101.2 -132 12.7
endloop
endfacet
facet normal -0 -1 0
outer loop
vertex -96.8 -136.9 0
vertex -53 -137 0
vertex -53 -137 12.7
endloop
endfacet
facet normal -0 -1 0
outer loop
vertex -96.8 -136.9 0
vertex -53 -137 12.7
vertex -96.8 -136.9 12.7
endloop
endfacet
facet normal -1 0.01 0
outer loop
vertex -53 -137 0
vertex -53.1 -138 0
vertex -53.1 -138 12.7
endloop
endfacet
facet normal -1 0.01 0
outer loop
vertex -53 -137 0
vertex -53.1 -138 12.7
vertex -53 -137 12.7
endloop
endfacet
facet normal -0.01 -1 0
outer loop
vertex -53.1 -138 0
vertex -41.5 -138.1 0
vertex -41.5 -138.1 12.7
endloop
endfacet
facet normal -0.01 -1 0
outer loop
vertex -53.1 -138 0
vertex -41.5 -138.1 12.7
vertex -53.1 -138 12.7
endloop
endfacet
facet normal 1 -0.01 0
outer loop
vertex -41.5 -138.1 0
vertex -41.5 -137.1 0
vertex -41.5 -137.1 12.7
endloop
endfacet
facet normal 1 -0.01 0
outer loop
vertex -41.5 -138.1 0
vertex -41.5 -137.1 12.7
vertex -41.5 -138.1 12.7
endloop
endfacet
facet normal -0.01 -1 0
outer loop
vertex -41.5 -137.1 0
vertex -13.9 -137.3 0
vertex -13.9 -137.3 12.7
endloop
endfacet
facet normal -0.01 -1 0
outer loop
vertex -41.5 -137.1 0
vertex -13.9 -137.3 12.7
vertex -41.5 -137.1 12.7
endloop
endfacet
facet normal 0.75 -0.66 0
outer loop
vertex -13.9 -137.3 0
vertex -8.3 -131 0
vertex -8.3 -131 12.7
endloop
endfacet
facet normal 0.75 -0.66 0
outer loop
vertex -13.9 -137.3 0
vertex -8.3 -131 12.7
vertex -13.9 -137.3 12.7
endloop
endfacet
facet normal 1 -0.03 0
outer loop
vertex -8.3 -131 0
vertex -7.4 -106.1 0
vertex -7.4 -106.1 12.7
endloop
endfacet
facet normal 1 -0.03 0
outer loop
vertex -8.3 -131 0
vertex -7.4 -106.1 12.7
vertex -8.3 -131 12.7
endloop
endfacet
facet normal 0.31 0.95 0
outer loop
vertex -7.4 -106.1 0
vertex -18.1 -102.6 0
vertex -18.1 -102.6 12.7
endloop
endfacet
facet normal 0.31 0.95 -0
outer loop
vertex -7.4 -106.1 0
vertex -18.1 -102.6 12.7
vertex -7.4 -106.1 12.7
endloop
endfacet
facet normal 0 1 0
outer loop
vertex -18.1 -102.6 0
vertex -27.1 -102.6 0
vertex -27.1 -102.6 12.7
endloop
endfacet
facet normal 0 1 -0
outer loop
vertex -18.1 -102.6 0
vertex -27.1 -102.6 12.7
vertex -18.1 -102.6 12.7
endloop
endfacet
facet normal -1 -0 0
outer loop
vertex -27.1 -102.6 0
vertex -27.1 -106 0
vertex -27.1 -106 12.7
endloop
endfacet
facet normal -1 -0 0
outer loop
vertex -27.1 -102.6 0
vertex -27.1 -106 12.7
vertex -27.1 -102.6 12.7
endloop
endfacet
facet normal 0 1 0
outer loop
vertex -27.1 -106 0
vertex -58.8 -105.8 0
vertex -58.8 -105.8 12.7
endloop
endfacet
facet normal 0 1 -0
outer loop
vertex -27.1 -106 0
vertex -58.8 -105.8 12.7
vertex -27.1 -106 12.7
endloop
endfacet
facet normal 1 0.03 0
outer loop
vertex -58.8 -105.8 0
vertex -58.8 -102.8 0
vertex -58.8 -102.8 12.7
endloop
endfacet
facet normal 1 0.03 -0
outer loop
vertex -58.8 -105.8 0
vertex -58.8 -102.8 12.7
vertex -58.8 -105.8 12.7
endloop
endfacet
facet normal 0.74 0.68 0
outer loop
vertex -58.8 -102.8 0
vertex -63.7 -97.5 0
vertex -63.7 -97.5 12.7
endloop
endfacet
facet normal 0.74 0.68 -0
outer loop
vertex -58.8 -102.8 0
vertex -63.7 -97.5 12.7
vertex -58.8 -102.8 12.7
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -58.8 -105.8 12.7
vertex -58.8 -102.8 12.7
vertex -67.7 -97.5 12.7
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -18.1 -102.6 12.7
vertex -27.1 -102.6 12.7
vertex -27.1 -106 12.7
endloop
endfacet
facet normal 0 -0 1
outer loop
vertex -8.3 -131 12.7
vertex -7.4 -106.1 12.7
vertex -18.1 -102.6 12.7
endloop
endfacet
facet normal -0 0 1
outer loop
vertex -41.5 -137.1 12.7
vertex -13.9 -137.3 12.7
vertex -27.1 -106 12.7
endloop
endfacet
facet normal -0 0 1
outer loop
vertex -53.1 -138 12.7
vertex -41.5 -138.1 12.7
vertex -53 -137 12.7
endloop
endfacet
facet normal -0 0 1
outer loop
vertex -101.2 -132 12.7
vertex -96.8 -136.9 12.7
vertex -67.7 -97.5 12.7
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -92.9 -58.9 12.7
vertex -100.8 -56.6 12.7
vertex -101.2 -132 12.7
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -66.4 -63.7 12.7
vertex -92.8 -57.4 12.7
vertex -92.9 -58.9 12.7
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -63.7 -97.5 12.7
vertex -67.7 -97.5 12.7
vertex -58.8 -102.8 12.7
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -8.3 -131 12.7
vertex -18.1 -102.6 12.7
vertex -27.1 -106 12.7
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -41.5 -137.1 12.7
vertex -53 -137 12.7
vertex -41.5 -138.1 12.7
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -92.9 -58.9 12.7
vertex -101.2 -132 12.7
vertex -67.7 -97.5 12.7
endloop
endfacet
facet normal 0 -0 1
outer loop
vertex -67.7 -97.5 12.7
vertex -66.4 -63.7 12.7
vertex -92.9 -58.9 12.7
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -8.3 -131 12.7
vertex -27.1 -106 12.7
vertex -13.9 -137.3 12.7
endloop
endfacet
facet normal -0 -0 1
outer loop
vertex -53 -137 12.7
vertex -41.5 -137.1 12.7
vertex -58.8 -105.8 12.7
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -58.8 -105.8 12.7
vertex -67.7 -97.5 12.7
vertex -96.8 -136.9 12.7
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -27.1 -106 12.7
vertex -58.8 -105.8 12.7
vertex -41.5 -137.1 12.7
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -53 -137 12.7
vertex -58.8 -105.8 12.7
vertex -96.8 -136.9 12.7
endloop
endfacet
facet normal 0.01 1 0
outer loop
vertex -15.7 75.6 0
vertex -33.7 75.7 0
vertex -33.7 75.7 5.8
endloop
endfacet
facet normal 0.01 1 -0
outer loop
vertex -15.7 75.6 0
vertex -33.7 75.7 5.8
vertex -15.7 75.6 5.8
endloop
endfacet
facet normal -1 0.01 0
outer loop
vertex -33.7 75.7 0
vertex -33.8 67.8 0
vertex -33.8 67.8 5.8
endloop
endfacet
facet normal -1 0.01 0
outer loop
vertex -33.7 75.7 0
vertex -33.8 67.8 5.8
vertex -33.7 75.7 5.8
endloop
endfacet
facet normal -0.01 -1 0
outer loop
vertex -33.8 67.8 0
vertex -26.3 67.8 0
vertex -26.3 67.8 5.8
endloop
endfacet
facet normal -0.01 -1 0
outer loop
vertex -33.8 67.8 0
vertex -26.3 67.8 5.8
vertex -33.8 67.8 5.8
endloop
endfacet
facet normal -1 0.01 0
outer loop
vertex -26.3 67.8 0
vertex -26.3 64.1 0
vertex -26.3 64.1 5.8
endloop
endfacet
facet normal -1 0.01 0
outer loop
vertex -26.3 67.8 0
vertex -26.3 64.1 5.8
vertex -26.3 67.8 5.8
endloop
endfacet
facet normal -0.01 -1 0
outer loop
vertex -26.3 64.1 0
vertex -23.6 64 0
vertex -23.6 64 5.8
endloop
endfacet
facet normal -0.01 -1 0
outer loop
vertex -26.3 64.1 0
vertex -23.6 64 5.8
vertex -26.3 64.1 5.8
endloop
endfacet
facet normal -0.71 -0.7 0
outer loop
vertex -23.6 64 0
vertex -20.3 60.7 0
vertex -20.3 60.7 5.8
endloop
endfacet
facet normal -0.71 -0.7 0
outer loop
vertex -23.6 64 0
vertex -20.3 60.7 5.8
vertex -23.6 64 5.8
endloop
endfacet
facet normal -1 0 0
outer loop
vertex -20.3 60.7 0
vertex -20.3 57.8 0
vertex -20.3 57.8 5.8
endloop
endfacet
facet normal -1 0 0
outer loop
vertex -20.3 60.7 0
vertex -20.3 57.8 5.8
vertex -20.3 60.7 5.8
endloop
endfacet
facet normal -0 -1 0
outer loop
vertex -20.3 57.8 0
vertex -16.3 57.8 0
vertex -16.3 57.8 5.8
endloop
endfacet
facet normal -0 -1 0
outer loop
vertex -20.3 57.8 0
vertex -16.3 57.8 5.8
vertex -20.3 57.8 5.8
endloop
endfacet
facet normal -1 0 0
outer loop
vertex -16.3 57.8 0
vertex -16.3 50.3 0
vertex -16.3 50.3 5.8
endloop
endfacet
facet normal -1 0 0
outer loop
vertex -16.3 57.8 0
vertex -16.3 50.3 5.8
vertex -16.3 57.8 5.8
endloop
endfacet
facet normal -0 -1 0
outer loop
vertex -16.3 50.3 0
vertex -8.8 50.3 0
vertex -8.8 50.3 5.8
endloop
endfacet
facet normal -0 -1 0
outer loop
vertex -16.3 50.3 0
vertex -8.8 50.3 5.8
vertex -16.3 50.3 5.8
endloop
endfacet
facet normal 1 -0 0
outer loop
vertex -8.8 50.3 0
vertex -8.8 67.8 0
vertex -8.8 67.8 5.8
endloop
endfacet
facet normal 1 -0 0
outer loop
vertex -8.8 50.3 0
vertex -8.8 67.8 5.8
vertex -8.8 50.3 5.8
endloop
endfacet
facet normal 0 1 0
outer loop
vertex -8.8 67.8 0
vertex -12.5 67.8 0
vertex -12.5 67.8 5.8
endloop
endfacet
facet normal 0 1 -0
outer loop
vertex -8.8 67.8 0
vertex -12.5 67.8 5.8
vertex -8.8 67.8 5.8
endloop
endfacet
facet normal 0.72 0.69 0
outer loop
vertex -12.5 67.8 0
vertex -15.8 71.2 0
vertex -15.8 71.2 5.8
endloop
endfacet
facet normal 0.72 0.69 -0
outer loop
vertex -12.5 67.8 0
vertex -15.8 71.2 5.8
vertex -12.5 67.8 5.8
endloop
endfacet
facet normal 1 -0.01 0
outer loop
vertex -15.8 71.2 0
vertex -15.7 75.6 0
vertex -15.7 75.6 5.8
endloop
endfacet
facet normal 1 -0.01 0
outer loop
vertex -15.8 71.2 0
vertex -15.7 75.6 5.8
vertex -15.8 71.2 5.8
endloop
endfacet
facet normal 0 -0 1
outer loop
vertex -8.8 50.3 5.8
vertex -8.8 67.8 5.8
vertex -16.3 57.8 5.8
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -16.3 57.8 5.8
vertex -16.3 50.3 5.8
vertex -8.8 50.3 5.8
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -20.3 60.7 5.8
vertex -20.3 57.8 5.8
vertex -16.3 57.8 5.8
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -26.3 67.8 5.8
vertex -26.3 64.1 5.8
vertex -23.6 64 5.8
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -33.7 75.7 5.8
vertex -33.8 67.8 5.8
vertex -26.3 67.8 5.8
endloop
endfacet
facet normal 0 -0 1
outer loop
vertex -15.8 71.2 5.8
vertex -15.7 75.6 5.8
vertex -26.3 67.8 5.8
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -12.5 67.8 5.8
vertex -16.3 57.8 5.8
vertex -8.8 67.8 5.8
endloop
endfacet
facet normal -0 0 1
outer loop
vertex -26.3 67.8 5.8
vertex -23.6 64 5.8
vertex -15.8 71.2 5.8
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -33.7 75.7 5.8
vertex -26.3 67.8 5.8
vertex -15.7 75.6 5.8
endloop
endfacet
facet normal 0 -0 1
outer loop
vertex -16.3 57.8 5.8
vertex -12.5 67.8 5.8
vertex -20.3 60.7 5.8
endloop
endfacet
facet normal 0 -0 1
outer loop
vertex -20.3 60.7 5.8
vertex -15.8 71.2 5.8
vertex -23.6 64 5.8
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -15.8 71.2 5.8
vertex -20.3 60.7 5.8
vertex -12.5 67.8 5.8
endloop
endfacet
facet normal -0.01 -1 0
outer loop
vertex -30.9 100.8 0
vertex -7.6 100.5 0
vertex -7.6 100.5 9.8
endloop
endfacet
facet normal -0.01 -1 0
outer loop
vertex -30.9 100.8 0
vertex -7.6 100.5 9.8
vertex -30.9 100.8 9.8
endloop
endfacet
facet normal 1 -0.01 0
outer loop
vertex -7.6 100.5 0
vertex -7.4 113 0
vertex -7.4 113 9.8
endloop
endfacet
facet normal 1 -0.01 0
outer loop
vertex -7.6 100.5 0
vertex -7.4 113 9.8
vertex -7.6 100.5 9.8
endloop
endfacet
facet normal 0.01 1 0
outer loop
vertex -7.4 113 0
vertex -25.6 113.2 0
vertex -25.6 113.2 9.8
endloop
endfacet
facet normal 0.01 1 -0
outer loop
vertex -7.4 113 0
vertex -25.6 113.2 9.8
vertex -7.4 113 9.8
endloop
endfacet
facet normal -1 0.01 0
outer loop
vertex -25.6 113.2 0
vertex -25.6 112 0
vertex -25.6 112 9.8
endloop
endfacet
facet normal -1 0.01 0
outer loop
vertex -25.6 113.2 0
vertex -25.6 112 9.8
vertex -25.6 113.2 9.8
endloop
endfacet
facet normal 0.01 1 0
outer loop
vertex -25.6 112 0
vertex -30.9 112.1 0
vertex -30.9 112.1 9.8
endloop
endfacet
facet normal 0.01 1 -0
outer loop
vertex -25.6 112 0
vertex -30.9 112.1 9.8
vertex -25.6 112 9.8
endloop
endfacet
facet normal -1 -0 0
outer loop
vertex -30.9 112.1 0
vertex -30.9 100.8 0
vertex -30.9 100.8 9.8
endloop
endfacet
facet normal -1 -0 0
outer loop
vertex -30.9 112.1 0
vertex -30.9 100.8 9.8
vertex -30.9 112.1 9.8
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -25.6 112 9.8
vertex -30.9 112.1 9.8
vertex -30.9 100.8 9.8
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -7.4 113 9.8
vertex -25.6 113.2 9.8
vertex -25.6 112 9.8
endloop
endfacet
facet normal -0 0 1
outer loop
vertex -30.9 100.8 9.8
vertex -7.6 100.5 9.8
vertex -25.6 112 9.8
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -7.4 113 9.8
vertex -25.6 112 9.8
vertex -7.6 100.5 9.8
endloop
endfacet
facet normal 0.02 1 0
outer loop
vertex -7.6 100.5 0
vertex -26 100.8 0
vertex -26 100.8 9.8
endloop
endfacet
facet normal 0.02 1 -0
outer loop
vertex -7.6 100.5 0
vertex -26 100.8 9.8
vertex -7.6 100.5 9.8
endloop
endfacet
facet normal -1 0.02 0
outer loop
vertex -26 100.8 0
vertex -26 98.1 0
vertex -26 98.1 9.8
endloop
endfacet
facet normal -1 0.02 0
outer loop
vertex -26 100.8 0
vertex -26 98.1 9.8
vertex -26 100.8 9.8
endloop
endfacet
facet normal -0.02 -1 0
outer loop
vertex -26 98.1 0
vertex -4.8 97.8 0
vertex -4.8 97.8 9.8
endloop
endfacet
facet normal -0.02 -1 0
outer loop
vertex -26 98.1 0
vertex -4.8 97.8 9.8
vertex -26 98.1 9.8
endloop
endfacet
facet normal 1 -0.02 0
outer loop
vertex -4.8 97.8 0
vertex -4.6 112.9 0
vertex -4.6 112.9 9.8
endloop
endfacet
facet normal 1 -0.02 0
outer loop
vertex -4.8 97.8 0
vertex -4.6 112.9 9.8
vertex -4.8 97.8 9.8
endloop
endfacet
facet normal 0.01 1 0
outer loop
vertex -4.6 112.9 0
vertex -7.4 113 0
vertex -7.4 113 9.8
endloop
endfacet
facet normal 0.01 1 -0
outer loop
vertex -4.6 112.9 0
vertex -7.4 113 9.8
vertex -4.6 112.9 9.8
endloop
endfacet
facet normal -1 0.01 0
outer loop
vertex -7.4 113 0
vertex -7.6 100.5 0
vertex -7.6 100.5 9.8
endloop
endfacet
facet normal -1 0.01 0
outer loop
vertex -7.4 113 0
vertex -7.6 100.5 9.8
vertex -7.4 113 9.8
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -4.6 112.9 9.8
vertex -7.4 113 9.8
vertex -7.6 100.5 9.8
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -26 100.8 9.8
vertex -26 98.1 9.8
vertex -7.6 100.5 9.8
endloop
endfacet
facet normal 0 -0 1
outer loop
vertex -4.8 97.8 9.8
vertex -4.6 112.9 9.8
vertex -7.6 100.5 9.8
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -4.8 97.8 9.8
vertex -7.6 100.5 9.8
vertex -26 98.1 9.8
endloop
endfacet
facet normal 0.01 1 0
outer loop
vertex 108.3 96.1 0
vertex 17.3 96.8 0
vertex 17.3 96.8 14.7
endloop
endfacet
facet normal 0.01 1 -0
outer loop
vertex 108.3 96.1 0
vertex 17.3 96.8 14.7
vertex 108.3 96.1 14.7
endloop
endfacet
facet normal -1 0.01 0
outer loop
vertex 17.3 96.8 0
vertex 17.3 93.1 0
vertex 17.3 93.1 14.7
endloop
endfacet
facet normal -1 0.01 0
outer loop
vertex 17.3 96.8 0
vertex 17.3 93.1 14.7
vertex 17.3 96.8 14.7
endloop
endfacet
facet normal -0.01 -1 0
outer loop
vertex 17.3 93.1 0
vertex 108.2 92.4 0
vertex 108.2 92.4 14.7
endloop
endfacet
facet normal -0.01 -1 0
outer loop
vertex 17.3 93.1 0
vertex 108.2 92.4 14.7
vertex 17.3 93.1 14.7
endloop
endfacet
facet normal 1 -0.01 0
outer loop
vertex 108.2 92.4 0
vertex 108.3 96.1 0
vertex 108.3 96.1 14.7
endloop
endfacet
facet normal 1 -0.01 0
outer loop
vertex 108.2 92.4 0
vertex 108.3 96.1 14.7
vertex 108.2 92.4 14.7
endloop
endfacet
facet normal -0 0 1
outer loop
vertex 17.3 93.1 14.7
vertex 108.2 92.4 14.7
vertex 108.3 96.1 14.7
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 108.3 96.1 14.7
vertex 17.3 96.8 14.7
vertex 17.3 93.1 14.7
endloop
endfacet
facet normal -1 0.01 0
outer loop
vertex 89.7 68.4 0
vertex 89.6 54.4 0
vertex 89.6 54.4 16.1
endloop
endfacet
facet normal -1 0.01 0
outer loop
vertex 89.7 68.4 0
vertex 89.6 54.4 16.1
vertex 89.7 68.4 16.1
endloop
endfacet
facet normal -0.01 -1 0
outer loop
vertex 89.6 54.4 0
vertex 109.2 54.2 0
vertex 109.2 54.2 16.1
endloop
endfacet
facet normal -0.01 -1 0
outer loop
vertex 89.6 54.4 0
vertex 109.2 54.2 16.1
vertex 89.6 54.4 16.1
endloop
endfacet
facet normal 1 -0 0
outer loop
vertex 109.2 54.2 0
vertex 109.2 72.6 0
vertex 109.2 72.6 16.1
endloop
endfacet
facet normal 1 -0 0
outer loop
vertex 109.2 54.2 0
vertex 109.2 72.6 16.1
vertex 109.2 54.2 16.1
endloop
endfacet
facet normal 0.91 0.41 0
outer loop
vertex 109.2 72.6 0
vertex 108 75.1 0
vertex 108 75.1 16.1
endloop
endfacet
facet normal 0.91 0.41 -0
outer loop
vertex 109.2 72.6 0
vertex 108 75.1 16.1
vertex 109.2 72.6 16.1
endloop
endfacet
facet normal 0.37 0.93 0
outer loop
vertex 108 75.1 0
vertex 105.7 76.1 0
vertex 105.7 76.1 16.1
endloop
endfacet
facet normal 0.37 0.93 -0
outer loop
vertex 108 75.1 0
vertex 105.7 76.1 16.1
vertex 108 75.1 16.1
endloop
endfacet
facet normal 0.01 1 0
outer loop
vertex 105.7 76.1 0
vertex 77.7 76.3 0
vertex 77.7 76.3 16.1
endloop
endfacet
facet normal 0.01 1 -0
outer loop
vertex 105.7 76.1 0
vertex 77.7 76.3 16.1
vertex 105.7 76.1 16.1
endloop
endfacet
facet normal -1 -0.01 0
outer loop
vertex 77.7 76.3 0
vertex 77.8 72.9 0
vertex 77.8 72.9 16.1
endloop
endfacet
facet normal -1 -0.01 0
outer loop
vertex 77.7 76.3 0
vertex 77.8 72.9 16.1
vertex 77.7 76.3 16.1
endloop
endfacet
facet normal -0 -1 0
outer loop
vertex 77.8 72.9 0
vertex 81 72.9 0
vertex 81 72.9 16.1
endloop
endfacet
facet normal -0 -1 0
outer loop
vertex 77.8 72.9 0
vertex 81 72.9 16.1
vertex 77.8 72.9 16.1
endloop
endfacet
facet normal -1 0 0
outer loop
vertex 81 72.9 0
vertex 81 68.5 0
vertex 81 68.5 16.1
endloop
endfacet
facet normal -1 0 0
outer loop
vertex 81 72.9 0
vertex 81 68.5 16.1
vertex 81 72.9 16.1
endloop
endfacet
facet normal -0.01 -1 0
outer loop
vertex 81 68.5 0
vertex 89.7 68.4 0
vertex 89.7 68.4 16.1
endloop
endfacet
facet normal -0.01 -1 0
outer loop
vertex 81 68.5 0
vertex 89.7 68.4 16.1
vertex 81 68.5 16.1
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 81 72.9 16.1
vertex 81 68.5 16.1
vertex 89.7 68.4 16.1
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 77.7 76.3 16.1
vertex 77.8 72.9 16.1
vertex 81 72.9 16.1
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 108 75.1 16.1
vertex 105.7 76.1 16.1
vertex 109.2 72.6 16.1
endloop
endfacet
facet normal 0 -0 1
outer loop
vertex 109.2 54.2 16.1
vertex 109.2 72.6 16.1
vertex 89.7 68.4 16.1
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 89.7 68.4 16.1
vertex 89.6 54.4 16.1
vertex 109.2 54.2 16.1
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 77.7 76.3 16.1
vertex 81 72.9 16.1
vertex 105.7 76.1 16.1
endloop
endfacet
facet normal 0 0 1
outer loop
vertex 89.7 68.4 16.1
vertex 109.2 72.6 16.1
vertex 105.7 76.1 16.1
endloop
endfacet
facet normal 0 -0 1
outer loop
vertex 89.7 68.4 16.1
vertex 105.7 76.1 16.1
vertex 81 72.9 16.1
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -115 -143.1 -0.1
vertex 115 -143.1 -0.1
vertex 115 122.8 -0.1
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -115 -143.1 -0.1
vertex 115 122.8 -0.1
vertex -115 122.8 -0.1
endloop
endfacet
facet normal 1 0 0
outer loop
vertex -1 -2.5 0
vertex -1 2.5 0
vertex -1 2.5 1.9
endloop
endfacet
facet normal 1 0 0
outer loop
vertex -1 -2.5 0
vertex -1 2.5 1.9
vertex -1 -2.5 1.9
endloop
endfacet
facet normal 1 0 0
outer loop
vertex 1 -2.5 0
vertex 1 2.5 0
vertex 1 2.5 1.9
endloop
endfacet
facet normal 1 0 0
outer loop
vertex 1 -2.5 0
vertex 1 2.5 1.9
vertex 1 -2.5 1.9
endloop
endfacet
facet normal 0 -1 0
outer loop
vertex -1 -2.5 0
vertex 1 -2.5 0
vertex 1 -2.5 1.9
endloop
endfacet
facet normal 0 -1 0
outer loop
vertex -1 -2.5 0
vertex 1 -2.5 1.9
vertex -1 -2.5 1.9
endloop
endfacet
facet normal 0 -1 0
outer loop
vertex -1 2.5 0
vertex 1 2.5 0
vertex 1 2.5 1.9
endloop
endfacet
facet normal 0 -1 0
outer loop
vertex -1 2.5 0
vertex 1 2.5 1.9
vertex -1 2.5 1.9
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -1 -2.5 0
vertex 1 -2.5 0
vertex 1 2.5 0
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -1 -2.5 0
vertex 1 2.5 0
vertex -1 2.5 0
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -1 -2.5 1.9
vertex 1 -2.5 1.9
vertex 1 2.5 1.9
endloop
endfacet
facet normal 0 0 1
outer loop
vertex -1 -2.5 1.9
vertex 1 2.5 1.9
vertex -1 2.5 1.9
endloop
endfacet
endsolid p2_canyon
```

[![Open the full lidar canyon in GitHub's 3D viewer](https://img.shields.io/badge/3D%20viewer-full%20lidar%20canyon%20with%20trees%2C%20300%20m-d1495b?style=for-the-badge&logo=threedotjs&logoColor=white)](docs/readme/canyon_p2.stl)

<sub>The button opens the lidar surface itself (buildings and tree canopy on a 2 m grid, 300 m × 300 m) in GitHub's 3D viewer.</sub>

### A day in the life of each archetype

```mermaid
gantt
    title Where the four archetypes are on a weekday (weekends: at P3, or at P1 for A4)
    dateFormat HH:mm
    axisFormat %H:%M
    todayMarker off
    section A1 commuter
    driveway P3   :00:00, 08:00
    drive              :milestone, 08:00, 0d
    open lot P1        :08:00, 17:00
    drive              :milestone, 17:00, 0d
    driveway P3   :17:00, 23:59
    section A2 downtown street
    driveway P3   :00:00, 08:00
    drive              :milestone, 08:00, 0d
    canyon curb P2     :crit, 08:00, 17:00
    drive              :milestone, 17:00, 0d
    driveway P3   :17:00, 23:59
    section A3 downtown shaded
    driveway P3   :00:00, 08:00
    drive              :milestone, 08:00, 0d
    shade roof P5      :active, 08:00, 17:00
    drive              :milestone, 17:00, 0d
    driveway P3   :17:00, 23:59
    section A4 fleet, 100 km/day
    open lot P1        :00:00, 08:00
    curb P2            :crit, 08:00, 10:00
    open lot P1        :10:00, 12:00
    curb P2            :crit, 12:00, 14:00
    open lot P1        :14:00, 16:00
    curb P2            :crit, 16:00, 17:00
    open lot P1        :17:00, 23:59
```

<sub>Diamonds are trips (A4 also drives at 08, 10, 12, 14 and 16 h). A trip hour drives the first part of the hour and parks for the rest. Source: <a href="configs/schedules/archetypes.yaml">configs/schedules/archetypes.yaml</a>.</sub>

## The vehicle and its five PV facets

<table>
<tr>
<td width="50%"><img src="docs/readme/suv_beauty.webp" alt="Blender render of the SOLARIS P0 seven-seat electric SUV with PV on roof, hood and sides"></td>
<td width="25%"><img src="docs/readme/suv_facets_front.webp" alt="Front three-quarter view with each PV facet in its own colour"></td>
<td width="25%"><img src="docs/readme/suv_facets_rear.webp" alt="Rear three-quarter view with the tailgate and left side facets coloured"></td>
</tr>
</table>

| Facet | Colour above | Area (m²) | Tilt | Faces |
|---|---|---|---|---|
| Roof | amber | 4.4 | 2° | up |
| Hood | blue | 1.6 | 10° | forward |
| Tailgate | purple | 0.6 | 60° | rear |
| Left side | green | 2.5 | 85° | left |
| Right side | red | 2.5 | 85° | right |
| **Total** | | **11.6** | | |

The layout is the study's assumed design ([`configs/vehicle/solaris_p0.yaml`](configs/vehicle/solaris_p0.yaml)); roof only (4.4 m²) is reported as the lower bound. Each facet is sampled every 0.25 m, and the samples' shading feeds an electrical mismatch model with bypass diodes.

The SOLARIS vehicle from Blender, in 3D. Drag to rotate, scroll to zoom (a simplified copy of the model the Unity twin drives, 1,318 triangles):

```stl
solid solaris_p0
facet normal 0.63 -0.78 -0.01
outer loop
vertex 2.48 -0.93 0.86
vertex 2.42 -0.98 0.42
vertex 2.48 -0.93 0.42
endloop
endfacet
facet normal 0.17 0.64 -0.75
outer loop
vertex 2.42 0.78 0.25
vertex 2.32 0.79 0.24
vertex 2.42 0.98 0.42
endloop
endfacet
facet normal 0.94 0 -0.35
outer loop
vertex 2.51 0.69 0.36
vertex 2.48 -0.75 0.29
vertex 2.48 0.75 0.29
endloop
endfacet
facet normal 0.64 0 0.77
outer loop
vertex 2.42 -0.79 0.93
vertex 2.48 0.78 0.88
vertex 2.42 0.79 0.93
endloop
endfacet
facet normal 0.67 0.09 0.74
outer loop
vertex 2.2 0.96 1.27
vertex 2.32 0.86 1.18
vertex 2.32 0.97 1.16
endloop
endfacet
facet normal 0.06 -1 -0.05
outer loop
vertex -1.68 0.76 0.17
vertex -1.76 0.75 0.28
vertex -1.82 0.74 0.33
endloop
endfacet
facet normal 0.2 -0.98 -0.09
outer loop
vertex 2.39 -1.01 0.67
vertex 2.32 -1 0.42
vertex 2.42 -0.98 0.42
endloop
endfacet
facet normal -0.25 0 -0.97
outer loop
vertex -2.39 0.79 0.25
vertex -2.47 -0.78 0.27
vertex -2.47 0.78 0.27
endloop
endfacet
facet normal -0.05 -0.86 0.51
outer loop
vertex 2.42 0.84 1
vertex 2.31 0.81 0.94
vertex 2.42 0.79 0.93
endloop
endfacet
facet normal -0.05 0.86 0.51
outer loop
vertex 2.31 -0.81 0.94
vertex 2.42 -0.84 1
vertex 2.42 -0.79 0.93
endloop
endfacet
facet normal -0.98 -0.17 0
outer loop
vertex -2.49 -0.98 0.69
vertex -2.49 -0.93 1.04
vertex -2.51 -0.85 0.98
endloop
endfacet
facet normal 0.67 -0.09 0.74
outer loop
vertex 2.32 -0.86 1.18
vertex 2.2 -0.96 1.27
vertex 2.32 -0.97 1.16
endloop
endfacet
facet normal -0.98 0.05 0.17
outer loop
vertex -2.47 0.94 1.21
vertex -2.49 0.93 1.04
vertex -2.51 0.85 0.98
endloop
endfacet
facet normal -0.58 -0.21 -0.79
outer loop
vertex -1.76 -0.96 0.12
vertex -1.7 -0.91 0.06
vertex -1.63 -0.96 0.03
endloop
endfacet
facet normal 0 -1 0.08
outer loop
vertex 2.2 0.87 1.29
vertex 2.05 0.87 1.33
vertex 1.21 0.87 1.33
endloop
endfacet
facet normal 0.27 0.13 0.95
outer loop
vertex 2.05 0.95 1.32
vertex 2.2 0.87 1.29
vertex 2.2 0.96 1.27
endloop
endfacet
facet normal 0 0.65 -0.76
outer loop
vertex -1.15 0.8 0.24
vertex 1.14 1 0.42
vertex 1.15 0.8 0.24
endloop
endfacet
facet normal 0.41 0.86 -0.32
outer loop
vertex -1.22 0.98 0.2
vertex -1.22 0.96 0.16
vertex -1.29 0.97 0.08
endloop
endfacet
facet normal 0.24 0.04 -0.97
outer loop
vertex 1.41 0.96 0.57
vertex 1.51 0.76 0.59
vertex 1.37 0.76 0.55
endloop
endfacet
facet normal -0.99 0.03 0.16
outer loop
vertex -1.26 0.96 0.29
vertex -1.27 0.76 0.26
vertex -1.26 0.76 0.34
endloop
endfacet
facet normal 0.48 -0.83 0.29
outer loop
vertex 1.21 0.87 1.33
vertex 1.14 0.82 1.3
vertex 1.24 0.81 1.13
endloop
endfacet
facet normal 0.42 0.86 0.3
outer loop
vertex -1.2 0.96 0.49
vertex -1.2 0.98 0.44
vertex -1.3 0.97 0.6
endloop
endfacet
facet normal 0.09 0.86 -0.5
outer loop
vertex 1.52 0.97 0.6
vertex 1.41 0.96 0.57
vertex 1.31 0.98 0.58
endloop
endfacet
facet normal 0.47 0.83 0.29
outer loop
vertex 1.14 -0.82 1.31
vertex 1.21 -0.87 1.33
vertex 1.24 -0.81 1.13
endloop
endfacet
facet normal 0.1 -0.03 -0.99
outer loop
vertex 1.54 0.96 0.58
vertex 1.51 0.76 0.59
vertex 1.41 0.96 0.57
endloop
endfacet
facet normal -0.17 -0.99 -0.01
outer loop
vertex 1.77 0.74 0.5
vertex 1.75 0.75 0.44
vertex 1.76 0.75 0.26
endloop
endfacet
facet normal -0.49 0 -0.87
outer loop
vertex 2.49 -0.64 0.39
vertex 2.5 0.63 0.38
vertex 2.5 -0.63 0.38
endloop
endfacet
facet normal 0.2 0.98 -0.09
outer loop
vertex 2.32 1 0.42
vertex 2.39 1.01 0.67
vertex 2.42 0.98 0.42
endloop
endfacet
facet normal -0.29 0.03 -0.96
outer loop
vertex 1.54 -0.76 0.58
vertex 1.63 -0.96 0.55
vertex 1.51 -0.96 0.59
endloop
endfacet
facet normal 0.98 -0.05 0.2
outer loop
vertex 1.25 0.96 0.36
vertex 1.26 0.76 0.3
vertex 1.28 0.96 0.23
endloop
endfacet
facet normal -0.03 -0.97 -0.25
outer loop
vertex 1.68 0.74 0.6
vertex 1.52 0.75 0.6
vertex 1.63 0.76 0.55
endloop
endfacet
facet normal 0 0.98 0.19
outer loop
vertex 2.05 0.95 1.32
vertex 2.2 0.96 1.27
vertex -2.39 0.95 1.35
endloop
endfacet
facet normal -0.01 0 -1
outer loop
vertex -2.21 -0.9 1.29
vertex -2.43 0.93 1.29
vertex -2.21 0.9 1.29
endloop
endfacet
facet normal -0.14 -0.64 -0.76
outer loop
vertex -2.47 -0.98 0.42
vertex -2.39 -0.79 0.25
vertex -2.39 -0.99 0.42
endloop
endfacet
facet normal -0.19 -0.98 0.09
outer loop
vertex -2.47 -0.94 1.21
vertex -2.39 -1.01 0.69
vertex -2.39 -0.95 1.35
endloop
endfacet
facet normal 0.27 -0.13 0.95
outer loop
vertex 2.2 -0.87 1.29
vertex 2.05 -0.95 1.32
vertex 2.2 -0.96 1.27
endloop
endfacet
facet normal 0.97 0.24 0.01
outer loop
vertex 2.51 0.84 0.81
vertex 2.51 0.85 0.43
vertex 2.48 0.93 0.86
endloop
endfacet
facet normal -0.84 0 0.55
outer loop
vertex -2.47 -0.83 1.22
vertex -2.39 0.81 1.34
vertex -2.47 0.84 1.23
endloop
endfacet
facet normal 0.63 0.78 -0.01
outer loop
vertex 2.42 0.98 0.42
vertex 2.48 0.93 0.86
vertex 2.48 0.93 0.42
endloop
endfacet
facet normal -0.71 0 -0.71
outer loop
vertex -2.47 0.78 0.27
vertex -2.49 -0.76 0.3
vertex -2.49 0.76 0.3
endloop
endfacet
facet normal -0.49 -0.53 -0.7
outer loop
vertex -2.5 -0.95 0.42
vertex -2.47 -0.78 0.27
vertex -2.47 -0.98 0.42
endloop
endfacet
facet normal -0.66 0.75 0.08
outer loop
vertex -2.49 0.98 0.69
vertex -2.49 0.93 1.04
vertex -2.47 0.94 1.21
endloop
endfacet
facet normal -0.98 -0.04 -0.2
outer loop
vertex 1.16 -0.76 0.29
vertex 1.19 -0.96 0.21
vertex 1.16 -0.96 0.34
endloop
endfacet
facet normal -0.04 -0.99 -0.11
outer loop
vertex 1.64 -0.97 0.57
vertex 1.72 -0.96 0.46
vertex 1.68 -0.98 0.6
endloop
endfacet
facet normal 0.01 0 1
outer loop
vertex 1.14 0.82 1.3
vertex -2.39 -0.81 1.34
vertex 1.14 -0.82 1.31
endloop
endfacet
facet normal -0.05 -1 0.07
outer loop
vertex 1.78 0.74 0.2
vertex 1.76 0.75 0.26
vertex 1.65 0.74 0.11
endloop
endfacet
facet normal -0.95 -0.17 -0.27
outer loop
vertex -2.51 -0.87 0.43
vertex -2.49 -0.76 0.3
vertex -2.5 -0.95 0.42
endloop
endfacet
facet normal 0 -0.98 0.18
outer loop
vertex 0.98 -0.86 1.75
vertex -2.06 -0.95 1.29
vertex 1.19 -0.94 1.29
endloop
endfacet
facet normal -0.62 0 -0.78
outer loop
vertex 1.66 -1.02 0.67
vertex 1.71 1.01 0.64
vertex 1.79 -1.01 0.57
endloop
endfacet
facet normal 0.08 -0.02 -1
outer loop
vertex 1.54 -0.76 0.58
vertex 1.51 -0.96 0.59
vertex 1.42 -0.76 0.57
endloop
endfacet
facet normal -0.98 0.01 -0.2
outer loop
vertex -1.27 0.96 0.43
vertex -1.26 0.76 0.34
vertex -1.28 0.76 0.44
endloop
endfacet
facet normal 0.59 0 -0.8
outer loop
vertex 1.37 -1.02 0.69
vertex 1.21 1.01 0.57
vertex 1.36 1.02 0.68
endloop
endfacet
facet normal -0.89 -0.03 0.46
outer loop
vertex -1.32 0.96 0.18
vertex -1.27 0.76 0.26
vertex -1.26 0.96 0.29
endloop
endfacet
facet normal 1 0 0.02
outer loop
vertex 1.14 1 0.42
vertex 1.14 -1 0.42
vertex 1.15 -0.8 0.24
endloop
endfacet
facet normal 0.6 0 -0.8
outer loop
vertex -1.67 -1.02 0.67
vertex -1.78 1.01 0.58
vertex -1.65 1.02 0.67
endloop
endfacet
facet normal 0.89 0.04 0.46
outer loop
vertex 1.32 0.76 0.18
vertex 1.28 0.96 0.23
vertex 1.26 0.76 0.3
endloop
endfacet
facet normal 0.36 -0.9 -0.24
outer loop
vertex 2.5 -0.65 0.39
vertex 2.51 -0.64 0.39
vertex 2.5 -0.65 0.4
endloop
endfacet
facet normal 0.34 -0.24 0.91
outer loop
vertex 2.5 -0.64 0.55
vertex 2.51 -0.64 0.55
vertex 2.5 -0.63 0.55
endloop
endfacet
facet normal -0.34 -0.24 -0.91
outer loop
vertex 2.5 -0.64 0.39
vertex 2.49 -0.64 0.39
vertex 2.5 -0.63 0.38
endloop
endfacet
facet normal -0.33 -0.91 0.24
outer loop
vertex 2.5 -0.65 0.55
vertex 2.49 -0.64 0.55
vertex 2.5 -0.65 0.54
endloop
endfacet
facet normal 0.22 -0.69 0.69
outer loop
vertex 2.5 -0.65 0.55
vertex 2.51 -0.64 0.55
vertex 2.5 -0.64 0.55
endloop
endfacet
facet normal -0.37 -0.9 -0.24
outer loop
vertex 2.49 -0.64 0.39
vertex 2.5 -0.65 0.39
vertex 2.5 -0.65 0.4
endloop
endfacet
facet normal 0.34 0.24 -0.91
outer loop
vertex 2.5 0.64 0.39
vertex 2.51 0.64 0.39
vertex 2.5 0.63 0.38
endloop
endfacet
facet normal -0.36 -0.24 0.9
outer loop
vertex 2.49 -0.64 0.55
vertex 2.5 -0.64 0.55
vertex 2.5 -0.63 0.55
endloop
endfacet
facet normal 0.33 0.91 0.24
outer loop
vertex 2.5 0.65 0.55
vertex 2.51 0.64 0.55
vertex 2.5 0.65 0.54
endloop
endfacet
facet normal 0.37 0.9 -0.24
outer loop
vertex 2.51 0.64 0.39
vertex 2.5 0.65 0.39
vertex 2.5 0.65 0.4
endloop
endfacet
facet normal -0.36 0.24 -0.9
outer loop
vertex 2.49 0.64 0.39
vertex 2.5 0.64 0.39
vertex 2.5 0.63 0.38
endloop
endfacet
facet normal 0.24 0.69 -0.69
outer loop
vertex 2.5 0.65 0.39
vertex 2.51 0.64 0.39
vertex 2.5 0.64 0.39
endloop
endfacet
facet normal 0.36 0.24 0.9
outer loop
vertex 2.51 0.64 0.55
vertex 2.5 0.64 0.55
vertex 2.5 0.63 0.55
endloop
endfacet
facet normal -0.22 -0.69 0.69
outer loop
vertex 2.49 -0.64 0.55
vertex 2.5 -0.65 0.55
vertex 2.5 -0.64 0.55
endloop
endfacet
facet normal -0.34 0.91 0.24
outer loop
vertex 2.49 0.64 0.55
vertex 2.5 0.65 0.55
vertex 2.5 0.65 0.54
endloop
endfacet
facet normal -0.36 0.9 -0.24
outer loop
vertex 2.5 0.65 0.39
vertex 2.49 0.64 0.39
vertex 2.5 0.65 0.4
endloop
endfacet
facet normal -0.34 0.24 0.91
outer loop
vertex 2.5 0.64 0.55
vertex 2.49 0.64 0.55
vertex 2.5 0.63 0.55
endloop
endfacet
facet normal -0.22 0.69 0.69
outer loop
vertex 2.5 0.65 0.55
vertex 2.49 0.64 0.55
vertex 2.5 0.64 0.55
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 2.5 -0.63 0.38
vertex 2.5 -0.64 0.39
vertex 2.5 -0.64 0.39
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 2.5 -0.64 0.39
vertex 2.5 -0.65 0.39
vertex 2.5 -0.65 0.39
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 2.5 -0.65 0.39
vertex 2.5 -0.65 0.4
vertex 2.5 -0.65 0.4
endloop
endfacet
facet normal 1 0 0
outer loop
vertex 2.51 -0.64 0.55
vertex 2.51 0.64 0.39
vertex 2.51 0.64 0.55
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 2.5 -0.63 0.55
vertex 2.5 -0.64 0.55
vertex 2.5 -0.64 0.55
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 2.5 -0.64 0.55
vertex 2.5 -0.65 0.55
vertex 2.5 -0.65 0.55
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 2.5 -0.65 0.55
vertex 2.5 -0.65 0.54
vertex 2.5 -0.65 0.54
endloop
endfacet
facet normal 0.51 -0.86 0
outer loop
vertex 2.51 -0.64 0.55
vertex 2.5 -0.65 0.4
vertex 2.51 -0.64 0.39
endloop
endfacet
facet normal 0.49 0 -0.87
outer loop
vertex 2.51 0.64 0.39
vertex 2.5 -0.63 0.38
vertex 2.5 0.63 0.38
endloop
endfacet
facet normal -0.5 0.87 0
outer loop
vertex 2.5 0.65 0.4
vertex 2.49 0.64 0.55
vertex 2.5 0.65 0.54
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 2.5 0.63 0.38
vertex 2.5 0.64 0.39
vertex 2.5 0.64 0.39
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 2.5 0.64 0.39
vertex 2.5 0.65 0.39
vertex 2.5 0.65 0.39
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 2.5 0.65 0.39
vertex 2.5 0.65 0.4
vertex 2.5 0.65 0.4
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 2.5 0.63 0.55
vertex 2.5 0.64 0.55
vertex 2.5 0.64 0.55
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 2.5 0.64 0.55
vertex 2.5 0.65 0.55
vertex 2.5 0.65 0.55
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 2.5 0.65 0.55
vertex 2.5 0.65 0.54
vertex 2.5 0.65 0.54
endloop
endfacet
facet normal 0.49 0.87 0
outer loop
vertex 2.51 0.64 0.55
vertex 2.5 0.65 0.4
vertex 2.5 0.65 0.54
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 2.5 -0.63 0.38
vertex 2.5 0.63 0.38
vertex 2.5 -0.63 0.38
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 2.5 -0.65 0.4
vertex 2.5 -0.65 0.54
vertex 2.5 -0.65 0.4
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 2.5 0.63 0.55
vertex 2.5 -0.63 0.55
vertex 2.5 0.63 0.55
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 2.5 0.65 0.4
vertex 2.5 0.65 0.54
vertex 2.5 0.65 0.4
endloop
endfacet
facet normal 0.91 0.02 0.42
outer loop
vertex 0.98 0.86 1.75
vertex 1.19 0.8 1.3
vertex 1.19 0.94 1.29
endloop
endfacet
facet normal -0.2 -0.98 -0.05
outer loop
vertex -2.39 -1.01 0.69
vertex -2.47 -0.98 0.42
vertex -2.39 -0.99 0.42
endloop
endfacet
facet normal 0.91 -0.02 0.42
outer loop
vertex 1.19 -0.8 1.3
vertex 0.98 -0.86 1.75
vertex 1.19 -0.94 1.29
endloop
endfacet
facet normal 0.65 -0.66 0.39
outer loop
vertex 1.77 0.74 0.5
vertex 1.82 0.76 0.46
vertex 1.76 0.76 0.56
endloop
endfacet
facet normal -0.98 -0.02 0.2
outer loop
vertex -1.84 0.76 0.34
vertex -1.81 0.76 0.46
vertex -1.82 0.96 0.46
endloop
endfacet
facet normal -0.9 0 -0.44
outer loop
vertex -1.22 -1.01 0.59
vertex -1.14 1 0.42
vertex -1.14 -1 0.42
endloop
endfacet
facet normal -0.56 0.83 0.01
outer loop
vertex -1.83 0.97 0.27
vertex -1.84 0.96 0.33
vertex -1.81 0.98 0.41
endloop
endfacet
facet normal -0.76 0.52 0.39
outer loop
vertex -1.33 0.97 0.13
vertex -1.32 0.96 0.18
vertex -1.26 0.96 0.29
endloop
endfacet
facet normal 0.02 0.58 0.82
outer loop
vertex 0.98 0.79 1.79
vertex 0.98 0.86 1.75
vertex -2.06 0.86 1.82
endloop
endfacet
facet normal 0 1 -0.06
outer loop
vertex -1.14 1 0.42
vertex 1.21 1.01 0.57
vertex 1.14 1 0.42
endloop
endfacet
facet normal -0.5 0 0.87
outer loop
vertex 2.49 0.64 0.55
vertex 2.5 -0.63 0.55
vertex 2.5 0.63 0.55
endloop
endfacet
facet normal 0 0.98 0.19
outer loop
vertex 0.98 0.86 1.75
vertex -2.06 0.96 1.29
vertex -2.06 0.86 1.82
endloop
endfacet
facet normal -0.01 -1 -0.02
outer loop
vertex -2.39 -1.01 0.69
vertex -1.8 -1.01 0.55
vertex -1.67 -1.02 0.67
endloop
endfacet
facet normal -0.24 0.69 -0.69
outer loop
vertex 2.49 0.64 0.39
vertex 2.5 0.65 0.39
vertex 2.5 0.64 0.39
endloop
endfacet
facet normal -0.49 0.86 0.16
outer loop
vertex -2.06 0.96 1.29
vertex -2.21 0.81 1.61
vertex -2.06 0.86 1.82
endloop
endfacet
facet normal -0.49 -0.86 0.16
outer loop
vertex -2.21 -0.81 1.61
vertex -2.06 -0.95 1.29
vertex -2.06 -0.86 1.82
endloop
endfacet
facet normal -0.49 -0.87 0
outer loop
vertex 2.49 -0.64 0.55
vertex 2.5 -0.65 0.4
vertex 2.5 -0.65 0.54
endloop
endfacet
facet normal 0.15 0.95 0.27
outer loop
vertex -2.21 0.9 1.29
vertex -2.43 0.93 1.29
vertex -2.21 0.81 1.61
endloop
endfacet
facet normal 0.02 -0.58 0.81
outer loop
vertex -2.06 -0.86 1.82
vertex 0.98 -0.86 1.75
vertex 0.98 -0.79 1.79
endloop
endfacet
facet normal 0.15 -0.95 0.27
outer loop
vertex -2.43 -0.93 1.29
vertex -2.21 -0.9 1.29
vertex -2.21 -0.81 1.61
endloop
endfacet
facet normal 0.36 -0.24 -0.9
outer loop
vertex 2.51 -0.64 0.39
vertex 2.5 -0.64 0.39
vertex 2.5 -0.63 0.38
endloop
endfacet
facet normal 0.56 -0.83 -0.02
outer loop
vertex 1.18 0.97 1.45
vertex 1.19 0.98 1.35
vertex 1.2 0.98 1.44
endloop
endfacet
facet normal 0.01 -0.61 -0.79
outer loop
vertex 1.18 0.96 1.36
vertex 1.02 0.98 1.35
vertex 1.19 0.98 1.35
endloop
endfacet
facet normal -0.03 -0.63 0.78
outer loop
vertex 1.02 0.96 1.44
vertex 1.18 0.97 1.45
vertex 1.01 0.98 1.45
endloop
endfacet
facet normal -0.02 0.62 -0.79
outer loop
vertex 1.02 1.11 1.36
vertex 1.18 1.09 1.35
vertex 1.01 1.09 1.35
endloop
endfacet
facet normal -0.72 0.69 -0.07
outer loop
vertex 1.01 1.09 1.35
vertex 1.01 1.1 1.44
vertex 1.02 1.11 1.36
endloop
endfacet
facet normal -0.62 -0.78 0.01
outer loop
vertex 1.02 -1.1 1.35
vertex 1.01 -1.09 1.45
vertex 1 -1.09 1.36
endloop
endfacet
facet normal 0.02 0.61 0.79
outer loop
vertex 1.18 1.11 1.44
vertex 1.02 1.09 1.45
vertex 1.19 1.09 1.45
endloop
endfacet
facet normal 0.73 0.04 -0.68
outer loop
vertex 1.19 1.1 1.36
vertex 1.19 0.98 1.35
vertex 1.18 1.09 1.35
endloop
endfacet
facet normal -0.73 0.04 0.68
outer loop
vertex 1.01 1.1 1.44
vertex 1.01 0.98 1.45
vertex 1.02 1.09 1.45
endloop
endfacet
facet normal 0.63 -0.04 0.77
outer loop
vertex 1.2 0.98 1.44
vertex 1.19 1.09 1.45
vertex 1.18 0.97 1.45
endloop
endfacet
facet normal -0.03 0.03 -1
outer loop
vertex 1.18 1.09 1.35
vertex 1.02 0.98 1.35
vertex 1.01 1.09 1.35
endloop
endfacet
facet normal -0.02 1 0.07
outer loop
vertex 1.18 1.11 1.44
vertex 1.02 1.11 1.36
vertex 1.01 1.1 1.44
endloop
endfacet
facet normal 1 0.03 0.01
outer loop
vertex 1.2 0.98 1.44
vertex 1.19 1.1 1.36
vertex 1.19 1.09 1.45
endloop
endfacet
facet normal -1 0 0.01
outer loop
vertex 1.01 1.1 1.44
vertex 1.01 0.97 1.36
vertex 1.01 0.98 1.45
endloop
endfacet
facet normal -0.01 -0.05 1
outer loop
vertex 1.18 0.97 1.45
vertex 1.02 1.09 1.45
vertex 1.01 0.98 1.45
endloop
endfacet
facet normal 0.03 -1 0.04
outer loop
vertex 1.02 0.96 1.44
vertex 1.18 0.96 1.36
vertex 1.18 0.97 1.45
endloop
endfacet
facet normal 0.5 0.04 0.86
outer loop
vertex -1.34 0.76 0.64
vertex -1.28 0.96 0.59
vertex -1.38 0.96 0.66
endloop
endfacet
facet normal 0.34 -0.91 0.24
outer loop
vertex 2.51 -0.64 0.55
vertex 2.5 -0.65 0.55
vertex 2.5 -0.65 0.54
endloop
endfacet
facet normal 0.03 -0.57 -0.82
outer loop
vertex 1.18 -1.11 1.36
vertex 1.02 -1.1 1.35
vertex 1.19 -1.09 1.35
endloop
endfacet
facet normal -0.03 -0.63 0.78
outer loop
vertex 1.02 -1.11 1.44
vertex 1.18 -1.1 1.45
vertex 1.01 -1.09 1.45
endloop
endfacet
facet normal -0.59 0.03 0.8
outer loop
vertex 1 -0.98 1.44
vertex 1.01 -1.09 1.45
vertex 1.02 -0.97 1.45
endloop
endfacet
facet normal -0.8 0.6 0.03
outer loop
vertex 1.01 -0.98 1.35
vertex 1.02 -0.97 1.45
vertex 1.02 -0.97 1.36
endloop
endfacet
facet normal 0.64 -0.77 0
outer loop
vertex 1.18 -1.1 1.45
vertex 1.19 -1.09 1.35
vertex 1.2 -1.09 1.44
endloop
endfacet
facet normal -0.6 -0.04 -0.8
outer loop
vertex 1 -1.09 1.36
vertex 1.01 -0.98 1.35
vertex 1.02 -1.1 1.35
endloop
endfacet
facet normal -0.02 0 -1
outer loop
vertex 1.18 -0.98 1.35
vertex 1.02 -1.1 1.35
vertex 1.01 -0.98 1.35
endloop
endfacet
facet normal -0.79 -0.03 -0.61
outer loop
vertex 1.01 0.97 1.36
vertex 1.01 1.09 1.35
vertex 1.02 0.98 1.35
endloop
endfacet
facet normal -0.01 0.58 -0.81
outer loop
vertex 1.02 -0.97 1.36
vertex 1.18 -0.98 1.35
vertex 1.01 -0.98 1.35
endloop
endfacet
facet normal 0.03 0.63 0.78
outer loop
vertex 1.18 -0.96 1.44
vertex 1.02 -0.97 1.45
vertex 1.19 -0.98 1.45
endloop
endfacet
facet normal -0.03 1 0.03
outer loop
vertex 1.18 -0.96 1.44
vertex 1.02 -0.97 1.36
vertex 1.02 -0.97 1.45
endloop
endfacet
facet normal 0.64 -0.04 0.77
outer loop
vertex 1.2 -1.09 1.44
vertex 1.19 -0.98 1.45
vertex 1.18 -1.1 1.45
endloop
endfacet
facet normal 0.79 0.03 -0.61
outer loop
vertex 1.19 -0.97 1.36
vertex 1.19 -1.09 1.35
vertex 1.18 -0.98 1.35
endloop
endfacet
facet normal 0.17 0 0.99
outer loop
vertex 2.24 0.8 0.96
vertex 1.26 -0.8 1.13
vertex 2.24 -0.8 0.96
endloop
endfacet
facet normal -1 -0.03 0.04
outer loop
vertex 1 -0.98 1.44
vertex 1 -1.09 1.36
vertex 1.01 -1.09 1.45
endloop
endfacet
facet normal 0.03 -1 0.04
outer loop
vertex 1.02 -1.11 1.44
vertex 1.18 -1.11 1.36
vertex 1.18 -1.1 1.45
endloop
endfacet
facet normal 0 1 0
outer loop
vertex 1.26 -0.8 1.14
vertex 2.24 -0.8 0.96
vertex 1.26 -0.8 1.13
endloop
endfacet
facet normal 0 -0.01 1
outer loop
vertex 1.18 -1.1 1.45
vertex 1.02 -0.97 1.45
vertex 1.01 -1.09 1.45
endloop
endfacet
facet normal -0.17 0 -0.98
outer loop
vertex 2.24 0.8 0.96
vertex 1.26 -0.8 1.14
vertex 1.26 0.8 1.13
endloop
endfacet
facet normal 0.17 0 0.98
outer loop
vertex 1.24 0.81 1.13
vertex 2.25 -0.81 0.95
vertex 2.25 0.81 0.95
endloop
endfacet
facet normal -0.99 0 0.14
outer loop
vertex 2.25 0.81 0.95
vertex 2.25 -0.81 0.95
vertex 2.25 -0.81 0.96
endloop
endfacet
facet normal -0.02 0.84 -0.54
outer loop
vertex 1.55 -0.74 0.03
vertex 1.46 -0.76 0
vertex 1.42 -0.75 0.03
endloop
endfacet
facet normal -0.03 0 -1
outer loop
vertex -1.47 0.8 1.89
vertex 1.27 -0.8 1.8
vertex -1.47 -0.8 1.89
endloop
endfacet
facet normal 0.03 0 1
outer loop
vertex -1.47 0.8 1.89
vertex 1.27 -0.8 1.79
vertex 1.27 0.8 1.8
endloop
endfacet
facet normal 0 1 -0.09
outer loop
vertex 2 -1.03 0.69
vertex -2 -0.97 1.31
vertex 2 -0.97 1.31
endloop
endfacet
facet normal -0.99 0 -0.1
outer loop
vertex 1.28 -0.81 1.8
vertex 1.29 0.81 1.79
vertex 1.29 -0.81 1.79
endloop
endfacet
facet normal -0.03 0 -1
outer loop
vertex -1.49 0.81 1.89
vertex 1.28 -0.81 1.8
vertex -1.49 -0.81 1.89
endloop
endfacet
facet normal 0 1 0.09
outer loop
vertex -2 0.97 1.31
vertex 2 1.02 0.69
vertex -2 1.03 0.69
endloop
endfacet
facet normal 0 1 0.09
outer loop
vertex -2.01 1.02 0.68
vertex 2.01 0.96 1.32
vertex 2.01 1.02 0.68
endloop
endfacet
facet normal 0.03 0 1
outer loop
vertex -1.49 0.81 1.89
vertex 1.29 -0.81 1.79
vertex 1.29 0.81 1.79
endloop
endfacet
facet normal 0 -0.66 -0.75
outer loop
vertex -1.14 -1 0.42
vertex -1.15 -0.8 0.24
vertex 1.14 -1 0.42
endloop
endfacet
facet normal 0 -1 0.09
outer loop
vertex 2 -0.97 1.31
vertex -2 -1.02 0.69
vertex 2 -1.03 0.69
endloop
endfacet
facet normal -1 -0.01 0
outer loop
vertex 2.01 1.02 0.68
vertex 2.01 0.96 1.32
vertex 2.01 0.97 1.32
endloop
endfacet
facet normal 0 -1 -0.09
outer loop
vertex -2 1.03 0.69
vertex 2 0.97 1.31
vertex -2 0.97 1.31
endloop
endfacet
facet normal 0 -1 -0.09
outer loop
vertex -2.01 1.02 0.68
vertex 2.01 0.97 1.32
vertex -2.01 0.96 1.32
endloop
endfacet
facet normal 0.87 -0.01 -0.5
outer loop
vertex -2.23 -0.6 1.67
vertex -2.47 0.6 1.23
vertex -2.22 0.6 1.66
endloop
endfacet
facet normal 0 1 -0.09
outer loop
vertex 2.01 -1.02 0.68
vertex -2.01 -0.97 1.32
vertex 2.01 -0.96 1.32
endloop
endfacet
facet normal -0.5 0 -0.87
outer loop
vertex -2.22 0.6 1.66
vertex -2.22 -0.6 1.66
vertex -2.23 -0.6 1.67
endloop
endfacet
facet normal -0.86 0 0.51
outer loop
vertex -2.22 -0.6 1.66
vertex -2.47 0.6 1.23
vertex -2.47 -0.6 1.23
endloop
endfacet
facet normal 0 -1 0.09
outer loop
vertex 2.01 -1.02 0.68
vertex -2.01 -0.96 1.32
vertex -2.01 -1.02 0.68
endloop
endfacet
facet normal -0.87 0 0.5
outer loop
vertex -2.21 -0.61 1.67
vertex -2.47 0.61 1.22
vertex -2.47 -0.61 1.22
endloop
endfacet
facet normal 0.52 0 0.86
outer loop
vertex -2.47 -0.61 1.22
vertex -2.47 0.61 1.22
vertex -2.48 0.61 1.22
endloop
endfacet
facet normal -0.86 0.36 0.36
outer loop
vertex 1.34 -0.86 1.79
vertex 1.33 -0.87 1.78
vertex 1.34 -0.87 1.79
endloop
endfacet
facet normal -0.36 -0.89 0.29
outer loop
vertex 1.33 0.87 1.79
vertex 1.34 0.87 1.78
vertex 1.34 0.87 1.79
endloop
endfacet
facet normal 0.88 -0.36 0.3
outer loop
vertex 0.94 0.86 1.8
vertex 0.94 0.87 1.79
vertex 0.94 0.87 1.8
endloop
endfacet
facet normal 0.37 0.88 0.3
outer loop
vertex 0.95 -0.87 1.8
vertex 0.94 -0.87 1.79
vertex 0.94 -0.87 1.8
endloop
endfacet
facet normal -0.38 0.88 -0.28
outer loop
vertex 1.33 -0.87 1.79
vertex 1.34 -0.87 1.79
vertex 1.34 -0.87 1.79
endloop
endfacet
facet normal -0.89 -0.36 -0.28
outer loop
vertex 1.34 0.86 1.79
vertex 1.34 0.87 1.79
vertex 1.34 0.87 1.79
endloop
endfacet
facet normal 0.35 -0.87 -0.34
outer loop
vertex 0.95 0.87 1.8
vertex 0.94 0.87 1.81
vertex 0.94 0.87 1.8
endloop
endfacet
facet normal 0.87 0.36 -0.34
outer loop
vertex 0.94 -0.86 1.8
vertex 0.94 -0.87 1.81
vertex 0.94 -0.87 1.8
endloop
endfacet
facet normal 0.02 -0.85 0.52
outer loop
vertex 0.95 0.87 1.8
vertex 1.34 0.87 1.78
vertex 1.33 0.87 1.79
endloop
endfacet
facet normal 0.86 0 -0.51
outer loop
vertex -2.21 -0.61 1.67
vertex -2.48 0.61 1.22
vertex -2.21 0.61 1.67
endloop
endfacet
facet normal 0.02 0 1
outer loop
vertex 0.95 0.85 1.78
vertex 1.31 -0.85 1.77
vertex 1.31 0.85 1.77
endloop
endfacet
facet normal 0.29 -0.02 0.96
outer loop
vertex -1.47 0.76 0.68
vertex -1.34 0.76 0.64
vertex -1.38 0.96 0.66
endloop
endfacet
facet normal -0.83 0 0.55
outer loop
vertex 1.34 0.87 1.78
vertex 1.34 -0.86 1.79
vertex 1.34 0.86 1.79
endloop
endfacet
facet normal 1 0 -0.03
outer loop
vertex 0.95 -0.85 1.79
vertex 0.95 0.85 1.78
vertex 0.95 0.85 1.79
endloop
endfacet
facet normal 0.88 0 0.48
outer loop
vertex 0.94 -0.87 1.79
vertex 0.94 0.86 1.8
vertex 0.94 -0.86 1.8
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 1.33 -0.87 1.79
vertex 1.34 -0.87 1.79
vertex 1.34 -0.87 1.79
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 1.34 -0.87 1.79
vertex 1.34 -0.86 1.79
vertex 1.34 -0.86 1.79
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 1.33 0.87 1.79
vertex 1.34 0.87 1.79
vertex 1.34 0.87 1.79
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 1.34 0.87 1.79
vertex 1.34 0.86 1.79
vertex 1.34 0.86 1.79
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 0.94 0.86 1.8
vertex 0.94 0.87 1.8
vertex 0.94 0.87 1.8
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 0.94 0.87 1.8
vertex 0.95 0.87 1.8
vertex 0.95 0.87 1.8
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 0.95 -0.87 1.8
vertex 0.94 -0.87 1.8
vertex 0.94 -0.87 1.8
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 0.94 -0.87 1.8
vertex 0.94 -0.86 1.8
vertex 0.94 -0.86 1.8
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 0.95 -0.87 1.8
vertex 1.33 -0.87 1.79
vertex 1.33 -0.87 1.79
endloop
endfacet
facet normal -0.03 0 -1
outer loop
vertex 0.94 0.87 1.81
vertex 1.34 -0.87 1.79
vertex 0.94 -0.87 1.81
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 1.34 -0.86 1.79
vertex 1.34 0.86 1.79
vertex 1.34 0.86 1.79
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 1.33 0.87 1.79
vertex 0.95 0.87 1.8
vertex 0.95 0.87 1.8
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 0.94 0.86 1.8
vertex 0.94 -0.86 1.8
vertex 0.94 -0.86 1.8
endloop
endfacet
facet normal -0.03 0 -1
outer loop
vertex 0.95 0.85 1.79
vertex 1.31 -0.85 1.77
vertex 0.95 -0.85 1.79
endloop
endfacet
facet normal 0.03 0 1
outer loop
vertex 0.94 0.87 1.79
vertex 1.33 -0.87 1.78
vertex 1.34 0.87 1.78
endloop
endfacet
facet normal 0.84 0 -0.54
outer loop
vertex 0.94 0.87 1.81
vertex 0.94 -0.86 1.8
vertex 0.94 0.86 1.8
endloop
endfacet
facet normal -0.99 0 -0.14
outer loop
vertex -2.2 -0.81 1.86
vertex -2.2 0.81 1.85
vertex -2.2 -0.81 1.85
endloop
endfacet
facet normal -0.99 0 0.14
outer loop
vertex -2.2 0.81 1.85
vertex -2.2 -0.81 1.86
vertex -2.2 0.81 1.87
endloop
endfacet
facet normal 0.99 0 -0.14
outer loop
vertex -2.04 0.81 1.86
vertex -2.04 -0.81 1.85
vertex -2.04 0.81 1.85
endloop
endfacet
facet normal -0.01 0 1
outer loop
vertex -2.04 -0.81 1.87
vertex -2.2 0.81 1.87
vertex -2.2 -0.81 1.86
endloop
endfacet
facet normal 0.55 -0.03 0.84
outer loop
vertex -1.68 0.96 0.17
vertex -1.6 0.76 0.11
vertex -1.58 0.96 0.11
endloop
endfacet
facet normal 0.32 -0.92 0.24
outer loop
vertex 1.27 -0.96 0.25
vertex 1.19 -0.98 0.29
vertex 1.37 -0.98 0.05
endloop
endfacet
facet normal 0.99 0 0.14
outer loop
vertex -2.04 -0.81 1.85
vertex -2.04 0.81 1.86
vertex -2.04 -0.81 1.87
endloop
endfacet
facet normal 0.79 0.04 0.61
outer loop
vertex -1.24 0.76 0.56
vertex -1.2 0.96 0.49
vertex -1.28 0.96 0.59
endloop
endfacet
facet normal -0.71 -0.43 -0.56
outer loop
vertex -1.27 -0.96 0.43
vertex -1.24 -0.97 0.4
vertex -1.35 -0.96 0.54
endloop
endfacet
facet normal 0.32 -0.91 -0.27
outer loop
vertex 1.37 0.76 0.55
vertex 1.33 0.75 0.55
vertex 1.28 0.76 0.44
endloop
endfacet
facet normal 0.69 -0.06 -0.72
outer loop
vertex -1.72 -0.76 0.45
vertex -1.63 -0.96 0.55
vertex -1.7 -0.96 0.48
endloop
endfacet
facet normal 0.84 0.03 -0.55
outer loop
vertex 1.77 0.76 0.13
vertex 1.74 0.96 0.1
vertex 1.81 0.96 0.21
endloop
endfacet
facet normal -0.43 0.79 0.43
outer loop
vertex -1.76 -0.76 0.56
vertex -1.68 -0.74 0.6
vertex -1.78 -0.75 0.51
endloop
endfacet
facet normal 0.32 0.02 -0.95
outer loop
vertex -1.61 -0.76 0.56
vertex -1.54 -0.96 0.58
vertex -1.63 -0.96 0.55
endloop
endfacet
facet normal 0.03 0.81 0.58
outer loop
vertex 1.44 0.96 0.67
vertex 1.56 0.96 0.67
vertex 1.59 0.98 0.64
endloop
endfacet
facet normal -0.26 -0.97 -0.01
outer loop
vertex -1.21 -0.98 0.21
vertex -1.22 -0.98 0.48
vertex -1.24 -0.97 0.4
endloop
endfacet
facet normal -0.02 0.77 0.64
outer loop
vertex -1.56 -0.74 0.65
vertex -1.57 -0.76 0.67
vertex -1.43 -0.75 0.67
endloop
endfacet
facet normal -0.08 0.04 -1
outer loop
vertex -1.48 -0.76 0.59
vertex -1.43 -0.96 0.57
vertex -1.54 -0.96 0.58
endloop
endfacet
facet normal -0.18 -0.83 -0.53
outer loop
vertex 1.52 0.75 0.6
vertex 1.51 0.76 0.59
vertex 1.63 0.76 0.55
endloop
endfacet
facet normal 0.26 0.86 0.45
outer loop
vertex 1.59 0.98 0.64
vertex 1.66 0.96 0.64
vertex 1.72 0.97 0.58
endloop
endfacet
facet normal -0.27 0.03 -0.96
outer loop
vertex 1.54 0.96 0.58
vertex 1.63 0.76 0.55
vertex 1.51 0.76 0.59
endloop
endfacet
facet normal 0.21 0.89 0.41
outer loop
vertex -1.43 -0.75 0.67
vertex -1.34 -0.76 0.64
vertex -1.28 -0.74 0.57
endloop
endfacet
facet normal 0.13 0.98 -0.18
outer loop
vertex 1.31 0.98 0.58
vertex 1.41 0.96 0.57
vertex 1.31 0.96 0.5
endloop
endfacet
facet normal -0.84 -0.04 0.54
outer loop
vertex 1.19 -0.97 0.46
vertex 1.25 -0.97 0.57
vertex 1.24 -0.76 0.56
endloop
endfacet
facet normal 0.6 0.01 -0.8
outer loop
vertex -1.68 0.96 0.51
vertex -1.61 0.76 0.56
vertex -1.68 0.76 0.5
endloop
endfacet
facet normal -0.32 0.02 -0.95
outer loop
vertex -1.67 0.96 0.04
vertex -1.54 0.96 0
vertex -1.57 0.76 0.01
endloop
endfacet
facet normal -0.22 0.89 -0.41
outer loop
vertex -1.58 -0.75 0.01
vertex -1.68 -0.76 0.05
vertex -1.73 -0.74 0.12
endloop
endfacet
facet normal 0.41 -0.82 0.39
outer loop
vertex 1.77 0.74 0.5
vertex 1.76 0.76 0.56
vertex 1.68 0.74 0.6
endloop
endfacet
facet normal 0.9 0.03 -0.44
outer loop
vertex 1.26 -0.76 0.41
vertex 1.32 -0.96 0.51
vertex 1.26 -0.96 0.39
endloop
endfacet
facet normal 0.43 0.84 -0.33
outer loop
vertex -1.21 -0.76 0.17
vertex -1.3 -0.75 0.08
vertex -1.22 -0.74 0.2
endloop
endfacet
facet normal -0.32 0.01 -0.95
outer loop
vertex 1.32 0.9 0.05
vertex 1.44 0.96 0.01
vertex 1.44 0.76 0.01
endloop
endfacet
facet normal 0.83 -0.53 0.16
outer loop
vertex 1.83 0.75 0.36
vertex 1.84 0.76 0.34
vertex 1.82 0.76 0.46
endloop
endfacet
facet normal 0 0 -1
outer loop
vertex 1.44 0.76 0.01
vertex 1.44 0.96 0.01
vertex 1.55 0.75 0.01
endloop
endfacet
facet normal -0.88 0.09 0.47
outer loop
vertex -2.47 0.84 1.23
vertex -2.39 0.86 1.36
vertex -2.39 0.95 1.35
endloop
endfacet
facet normal 0.97 -0.01 0.23
outer loop
vertex -1.75 -0.76 0.34
vertex -1.73 -0.96 0.24
vertex -1.72 -0.76 0.23
endloop
endfacet
facet normal -0.92 0.04 0.39
outer loop
vertex -1.27 -0.76 0.24
vertex -1.31 -0.96 0.19
vertex -1.26 -0.96 0.3
endloop
endfacet
facet normal 0.56 -0.06 0.82
outer loop
vertex -1.71 -0.75 0.2
vertex -1.63 -0.96 0.13
vertex -1.58 -0.76 0.11
endloop
endfacet
facet normal -0.25 -0.97 0.06
outer loop
vertex 1.19 -0.97 0.46
vertex 1.19 -0.98 0.29
vertex 1.24 -0.98 0.5
endloop
endfacet
facet normal -0.5 0.83 -0.27
outer loop
vertex -1.73 -0.74 0.12
vertex -1.82 -0.76 0.22
vertex -1.81 -0.75 0.26
endloop
endfacet
facet normal -0.42 -0.88 0.21
outer loop
vertex 1.74 0.76 0.3
vertex 1.69 0.76 0.18
vertex 1.76 0.75 0.26
endloop
endfacet
facet normal -0.13 -0.99 0.01
outer loop
vertex 1.72 -0.96 0.46
vertex 1.77 -0.97 0.29
vertex 1.81 -0.98 0.27
endloop
endfacet
facet normal 0.57 -0.58 -0.58
outer loop
vertex 1.77 0.76 0.13
vertex 1.7 0.75 0.08
vertex 1.69 0.76 0.06
endloop
endfacet
facet normal 0.77 -0.03 0.64
outer loop
vertex 1.28 0.96 0.23
vertex 1.32 0.76 0.18
vertex 1.36 0.96 0.13
endloop
endfacet
facet normal 0.36 0.91 0.21
outer loop
vertex -1.22 -0.76 0.53
vertex -1.18 -0.75 0.43
vertex -1.28 -0.74 0.57
endloop
endfacet
facet normal 0.21 0.83 -0.51
outer loop
vertex 1.7 0.97 0.08
vertex 1.66 0.96 0.04
vertex 1.56 0.98 0.03
endloop
endfacet
facet normal -0.28 -0.03 0.96
outer loop
vertex 1.5 0.96 0.09
vertex 1.58 0.76 0.11
vertex 1.63 0.96 0.13
endloop
endfacet
facet normal 0.19 -0.98 -0.05
outer loop
vertex 1.32 -0.96 0.51
vertex 1.24 -0.98 0.5
vertex 1.24 -0.97 0.39
endloop
endfacet
facet normal 0.23 -0.81 -0.55
outer loop
vertex 1.55 0.75 0.01
vertex 1.69 0.76 0.06
vertex 1.7 0.75 0.08
endloop
endfacet
facet normal 0.09 -0.79 0.61
outer loop
vertex 1.38 0.75 0.1
vertex 1.52 0.76 0.09
vertex 1.4 0.76 0.12
endloop
endfacet
facet normal 0.08 -1 0.04
outer loop
vertex 1.82 -0.97 0.4
vertex 1.76 -0.97 0.53
vertex 1.68 -0.98 0.6
endloop
endfacet
facet normal -0.11 0 -0.99
outer loop
vertex -1.52 -1.01 0.71
vertex -1.53 1.01 0.7
vertex -1.37 1.02 0.69
endloop
endfacet
facet normal -0.02 0.85 -0.52
outer loop
vertex 0.95 -0.87 1.8
vertex 1.34 -0.87 1.79
vertex 1.33 -0.87 1.79
endloop
endfacet
facet normal -0.25 0.86 -0.45
outer loop
vertex 1.42 -0.75 0.03
vertex 1.32 -0.76 0.05
vertex 1.29 -0.74 0.11
endloop
endfacet
facet normal 0.02 0.86 0.51
outer loop
vertex 1.33 -0.87 1.78
vertex 0.95 -0.87 1.8
vertex 1.33 -0.87 1.79
endloop
endfacet
facet normal -0.24 -0.73 -0.64
outer loop
vertex 1.43 0.74 0.03
vertex 1.33 0.76 0.05
vertex 1.44 0.76 0.01
endloop
endfacet
facet normal 0.55 0.58 0.61
outer loop
vertex -1.22 -0.76 0.53
vertex -1.28 -0.74 0.57
vertex -1.34 -0.76 0.64
endloop
endfacet
facet normal -0.09 -0.83 -0.56
outer loop
vertex 1.37 -0.98 0.05
vertex 1.49 -0.96 0
vertex 1.54 -0.97 0.02
endloop
endfacet
facet normal 0.05 0.88 0.47
outer loop
vertex 1.52 -0.76 0.1
vertex 1.43 -0.75 0.08
vertex 1.42 -0.76 0.11
endloop
endfacet
facet normal -1 0 0.03
outer loop
vertex 1.27 0.8 1.8
vertex 1.27 -0.8 1.79
vertex 1.27 -0.8 1.8
endloop
endfacet
facet normal -0.17 0 -0.99
outer loop
vertex 1.24 0.81 1.13
vertex 2.25 -0.81 0.96
vertex 1.24 -0.81 1.13
endloop
endfacet
facet normal -0.51 -0.01 -0.86
outer loop
vertex -1.43 0.96 0.57
vertex -1.34 0.76 0.53
vertex -1.42 0.76 0.57
endloop
endfacet
facet normal 1 0.04 0.01
outer loop
vertex 1.2 -1.09 1.44
vertex 1.19 -0.97 1.36
vertex 1.19 -0.98 1.45
endloop
endfacet
facet normal 0.2 -0.91 -0.36
outer loop
vertex 1.24 -0.98 0.5
vertex 1.32 -0.96 0.51
vertex 1.45 -0.97 0.6
endloop
endfacet
facet normal 0.99 0.04 0.09
outer loop
vertex 1.26 -0.76 0.29
vertex 1.26 -0.96 0.39
vertex 1.27 -0.96 0.25
endloop
endfacet
facet normal 0.02 0.99 0.16
outer loop
vertex 1.55 -0.74 0.03
vertex 1.43 -0.75 0.08
vertex 1.6 -0.76 0.11
endloop
endfacet
facet normal -0.56 0.82 0.06
outer loop
vertex 1.19 -0.74 0.31
vertex 1.17 -0.76 0.4
vertex 1.2 -0.74 0.44
endloop
endfacet
facet normal -0.53 0.83 -0.17
outer loop
vertex 1.22 0.97 0.17
vertex 1.18 0.96 0.22
vertex 1.19 0.98 0.3
endloop
endfacet
facet normal -0.11 -0.97 -0.21
outer loop
vertex -1.42 0.76 0.57
vertex -1.34 0.76 0.53
vertex -1.32 0.74 0.59
endloop
endfacet
facet normal 0.22 -0.98 -0.05
outer loop
vertex 1.24 -0.97 0.39
vertex 1.24 -0.98 0.5
vertex 1.19 -0.98 0.29
endloop
endfacet
facet normal 0.03 -1 0.09
outer loop
vertex 1.5 -0.97 0.07
vertex 1.36 -0.97 0.12
vertex 1.37 -0.98 0.05
endloop
endfacet
facet normal -0.27 0.91 0.31
outer loop
vertex 1.55 -0.74 0.03
vertex 1.6 -0.76 0.11
vertex 1.72 -0.75 0.19
endloop
endfacet
facet normal -1 0 0
outer loop
vertex 2.49 0.64 0.55
vertex 2.49 -0.64 0.39
vertex 2.49 -0.64 0.55
endloop
endfacet
facet normal 0.33 -0.86 -0.38
outer loop
vertex 1.66 -0.98 0.06
vertex 1.73 -0.96 0.09
vertex 1.75 -0.98 0.15
endloop
endfacet
facet normal 0.92 0 0.39
outer loop
vertex 0.98 -0.79 1.79
vertex 1.19 0.8 1.3
vertex 0.98 0.79 1.79
endloop
endfacet
facet normal 0.2 0.03 -0.98
outer loop
vertex 1.42 -0.76 0.57
vertex 1.51 -0.96 0.59
vertex 1.4 -0.96 0.56
endloop
endfacet
facet normal -0.04 0.86 -0.51
outer loop
vertex -1.56 0.97 0.6
vertex -1.43 0.96 0.57
vertex -1.56 0.96 0.58
endloop
endfacet
facet normal 0.12 -0.64 0.76
outer loop
vertex 1.47 -0.96 0.68
vertex 1.55 -0.98 0.65
vertex 1.61 -0.95 0.66
endloop
endfacet
facet normal 0.45 0.05 0.89
outer loop
vertex 1.61 -0.95 0.66
vertex 1.71 -0.75 0.6
vertex 1.57 -0.76 0.67
endloop
endfacet
facet normal 1 0.04 -0.03
outer loop
vertex 1.84 -0.96 0.31
vertex 1.83 -0.76 0.25
vertex 1.83 -0.76 0.41
endloop
endfacet
facet normal -0.24 -0.69 -0.69
outer loop
vertex 2.5 -0.65 0.39
vertex 2.49 -0.64 0.39
vertex 2.5 -0.64 0.39
endloop
endfacet
facet normal 0.36 -0.67 0.65
outer loop
vertex 1.68 -0.98 0.6
vertex 1.72 -0.96 0.59
vertex 1.61 -0.95 0.66
endloop
endfacet
facet normal 0.44 0.9 0.01
outer loop
vertex -1.2 0.98 0.44
vertex -1.16 0.96 0.37
vertex -1.17 0.97 0.27
endloop
endfacet
facet normal 0.51 0.85 0.13
outer loop
vertex 1.79 -0.74 0.47
vertex 1.83 -0.76 0.41
vertex 1.81 -0.74 0.37
endloop
endfacet
facet normal -0.15 -0.85 -0.5
outer loop
vertex 1.64 -0.97 0.57
vertex 1.51 -0.96 0.59
vertex 1.63 -0.96 0.55
endloop
endfacet
facet normal -1 0 0.02
outer loop
vertex -1.14 -1 0.42
vertex -1.15 0.8 0.24
vertex -1.15 -0.8 0.24
endloop
endfacet
facet normal -0.08 1 0.04
outer loop
vertex -1.22 0.98 0.2
vertex -1.33 0.97 0.13
vertex -1.24 0.97 0.29
endloop
endfacet
facet normal 0.54 -0.02 0.84
outer loop
vertex -1.3 -0.97 0.61
vertex -1.34 -0.76 0.64
vertex -1.37 -0.96 0.65
endloop
endfacet
facet normal 0.2 0.01 0.98
outer loop
vertex 1.42 0.96 0.11
vertex 1.52 0.76 0.09
vertex 1.5 0.96 0.09
endloop
endfacet
facet normal -0.11 -0.48 0.87
outer loop
vertex -1.53 0.75 0.66
vertex -1.47 0.76 0.68
vertex -1.6 0.76 0.66
endloop
endfacet
facet normal -0.45 -0.84 0.3
outer loop
vertex -1.18 0.74 0.34
vertex -1.27 0.76 0.26
vertex -1.33 0.75 0.13
endloop
endfacet
facet normal -0.63 -0.68 0.38
outer loop
vertex -1.27 0.76 0.26
vertex -1.32 0.76 0.17
vertex -1.33 0.75 0.13
endloop
endfacet
facet normal 0.93 0.03 0.37
outer loop
vertex -1.18 -0.96 0.46
vertex -1.18 -0.75 0.43
vertex -1.22 -0.76 0.53
endloop
endfacet
facet normal -0.48 -0.88 -0.02
outer loop
vertex 1.74 -0.96 0.39
vertex 1.74 -0.96 0.29
vertex 1.77 -0.97 0.29
endloop
endfacet
facet normal -0.92 0.26 -0.29
outer loop
vertex 1.74 -0.96 0.39
vertex 1.77 -0.97 0.29
vertex 1.72 -0.96 0.46
endloop
endfacet
facet normal 0.61 0.74 -0.29
outer loop
vertex 1.8 -0.74 0.24
vertex 1.83 -0.76 0.25
vertex 1.77 -0.75 0.13
endloop
endfacet
facet normal -0.15 -0.98 -0.09
outer loop
vertex -1.24 0.75 0.37
vertex -1.18 0.74 0.34
vertex -1.32 0.74 0.59
endloop
endfacet
facet normal 0.58 0.81 -0.05
outer loop
vertex 1.81 -0.74 0.37
vertex 1.83 -0.76 0.25
vertex 1.8 -0.74 0.24
endloop
endfacet
facet normal -0.87 0 -0.49
outer loop
vertex 1.34 -0.87 1.79
vertex 1.34 0.86 1.79
vertex 1.34 -0.86 1.79
endloop
endfacet
facet normal 0.43 -0.8 0.42
outer loop
vertex 1.38 0.75 0.1
vertex 1.27 0.75 0.22
vertex 1.19 0.74 0.29
endloop
endfacet
facet normal -0.52 0.85 -0.08
outer loop
vertex 1.76 -0.75 0.33
vertex 1.74 -0.76 0.31
vertex 1.72 -0.76 0.44
endloop
endfacet
facet normal -1 0.02 -0.03
outer loop
vertex 1.74 -0.76 0.31
vertex 1.74 -0.96 0.29
vertex 1.74 -0.96 0.39
endloop
endfacet
facet normal -0.85 0 0.52
outer loop
vertex -2.43 0.8 1.3
vertex -2.2 -0.75 1.67
vertex -2.2 0.75 1.67
endloop
endfacet
facet normal -0.22 0.97 -0.05
outer loop
vertex -1.25 -0.76 0.34
vertex -1.28 -0.76 0.44
vertex -1.18 -0.74 0.32
endloop
endfacet
facet normal -0.98 -0.02 -0.19
outer loop
vertex -1.83 0.97 0.27
vertex -1.82 0.76 0.22
vertex -1.84 0.76 0.34
endloop
endfacet
facet normal 0.1 0.01 1
outer loop
vertex 1.42 -0.76 0.11
vertex 1.41 -0.96 0.11
vertex 1.55 -0.96 0.1
endloop
endfacet
facet normal -0.13 -0.98 0.13
outer loop
vertex -1.8 -0.98 0.44
vertex -1.61 -0.98 0.63
vertex -1.75 -0.97 0.56
endloop
endfacet
facet normal -0.62 -0.01 0.79
outer loop
vertex 1.6 -0.76 0.11
vertex 1.69 -0.96 0.18
vertex 1.69 -0.76 0.19
endloop
endfacet
facet normal -0.62 0.02 0.79
outer loop
vertex -1.76 0.96 0.56
vertex -1.74 0.76 0.58
vertex -1.65 0.96 0.65
endloop
endfacet
facet normal 0.93 -0.04 0.36
outer loop
vertex 2.48 -0.78 0.88
vertex 2.48 -0.93 0.86
vertex 2.51 -0.84 0.81
endloop
endfacet
facet normal 0.52 0.01 0.86
outer loop
vertex 1.72 -0.96 0.59
vertex 1.71 -0.75 0.6
vertex 1.61 -0.95 0.66
endloop
endfacet
facet normal -0.5 -0.83 0.25
outer loop
vertex 1.74 -0.96 0.29
vertex 1.69 -0.96 0.18
vertex 1.77 -0.97 0.29
endloop
endfacet
facet normal -0.78 -0.37 -0.51
outer loop
vertex 1.22 -0.97 0.16
vertex 1.19 -0.96 0.21
vertex 1.26 -0.96 0.1
endloop
endfacet
facet normal -0.85 -0.01 0.53
outer loop
vertex -1.74 0.76 0.58
vertex -1.82 0.96 0.46
vertex -1.81 0.76 0.46
endloop
endfacet
facet normal 0.5 0 0.87
outer loop
vertex 2.51 -0.64 0.55
vertex 2.5 0.63 0.55
vertex 2.5 -0.63 0.55
endloop
endfacet
facet normal 0.19 0.86 -0.48
outer loop
vertex 1.69 -0.75 0.07
vertex 1.61 -0.76 0.02
vertex 1.55 -0.74 0.03
endloop
endfacet
facet normal -0.23 0.81 0.53
outer loop
vertex 1.33 -0.76 0.63
vertex 1.43 -0.74 0.65
vertex 1.3 -0.75 0.6
endloop
endfacet
facet normal 0.2 -0.8 -0.57
outer loop
vertex 1.54 -0.97 0.02
vertex 1.61 -0.96 0.02
vertex 1.66 -0.98 0.06
endloop
endfacet
facet normal 0.39 0 0.92
outer loop
vertex 1.36 0.96 0.13
vertex 1.4 0.76 0.12
vertex 1.42 0.96 0.11
endloop
endfacet
facet normal 0.87 0.01 -0.5
outer loop
vertex -1.73 0.96 0.41
vertex -1.68 0.76 0.5
vertex -1.74 0.76 0.41
endloop
endfacet
facet normal -0.73 0.02 -0.69
outer loop
vertex 1.65 -0.76 0.53
vertex 1.72 -0.96 0.46
vertex 1.63 -0.96 0.55
endloop
endfacet
facet normal -0.2 -0.03 0.98
outer loop
vertex 1.52 -0.76 0.1
vertex 1.55 -0.96 0.1
vertex 1.6 -0.76 0.11
endloop
endfacet
facet normal -0.52 -0.05 0.85
outer loop
vertex -1.6 0.76 0.66
vertex -1.65 0.96 0.65
vertex -1.74 0.76 0.58
endloop
endfacet
facet normal 0.12 0.02 -0.99
outer loop
vertex 1.46 -0.76 0
vertex 1.61 -0.76 0.02
vertex 1.61 -0.96 0.02
endloop
endfacet
facet normal 0.89 0.01 0.45
outer loop
vertex 1.26 -0.76 0.29
vertex 1.32 -0.96 0.18
vertex 1.32 -0.76 0.17
endloop
endfacet
facet normal -0.25 0.88 0.41
outer loop
vertex -1.65 0.96 0.65
vertex -1.59 0.97 0.65
vertex -1.74 0.98 0.55
endloop
endfacet
facet normal -0.24 -0.89 0.38
outer loop
vertex 1.41 -0.97 0.65
vertex 1.33 -0.96 0.63
vertex 1.25 -0.97 0.57
endloop
endfacet
facet normal 0.1 0 0.99
outer loop
vertex 2.31 -0.81 0.94
vertex 2.42 -0.79 0.93
vertex 2.42 0.79 0.93
endloop
endfacet
facet normal 0.03 0.81 -0.58
outer loop
vertex 1.55 0.96 0
vertex 1.44 0.96 0.01
vertex 1.56 0.98 0.03
endloop
endfacet
facet normal 0.96 0.03 0.28
outer loop
vertex -1.17 0.76 0.4
vertex -1.16 0.96 0.37
vertex -1.2 0.96 0.49
endloop
endfacet
facet normal 0.91 0 -0.42
outer loop
vertex 1.21 1.01 0.57
vertex 1.14 -1 0.42
vertex 1.14 1 0.42
endloop
endfacet
facet normal 0.55 0 -0.84
outer loop
vertex 2.42 -0.78 0.25
vertex 2.48 0.75 0.29
vertex 2.48 -0.75 0.29
endloop
endfacet
facet normal -0.58 0.81 -0.13
outer loop
vertex 1.2 -0.75 0.2
vertex 1.16 -0.76 0.29
vertex 1.19 -0.74 0.31
endloop
endfacet
facet normal 1 0 -0.08
outer loop
vertex -1.74 0.76 0.3
vertex -1.73 0.96 0.41
vertex -1.74 0.76 0.41
endloop
endfacet
facet normal -0.63 -0.01 0.77
outer loop
vertex 1.24 -0.76 0.56
vertex 1.33 -0.96 0.63
vertex 1.33 -0.76 0.63
endloop
endfacet
facet normal 0.19 0.98 0.04
outer loop
vertex -1.73 0.96 0.41
vertex -1.76 0.97 0.29
vertex -1.81 0.98 0.41
endloop
endfacet
facet normal -0.98 0 0.18
outer loop
vertex -2.51 0.85 0.98
vertex -2.51 -0.85 0.98
vertex -2.47 0.84 1.23
endloop
endfacet
facet normal -0.87 -0.49 0.1
outer loop
vertex -1.26 -0.97 0.24
vertex -1.24 -0.97 0.4
vertex -1.26 -0.96 0.3
endloop
endfacet
facet normal -0.43 -0.55 0.71
outer loop
vertex -1.74 0.76 0.58
vertex -1.68 0.74 0.6
vertex -1.6 0.76 0.66
endloop
endfacet
facet normal -0.09 -0.99 0.09
outer loop
vertex 1.67 -0.97 0.13
vertex 1.66 -0.98 0.06
vertex 1.75 -0.98 0.15
endloop
endfacet
facet normal -0.81 -0.03 -0.58
outer loop
vertex -1.35 0.96 0.53
vertex -1.28 0.76 0.44
vertex -1.34 0.76 0.53
endloop
endfacet
facet normal 1 -0.02 0
outer loop
vertex -2.01 -0.97 1.32
vertex -2.01 -1.02 0.68
vertex -2.01 -0.96 1.32
endloop
endfacet
facet normal 0.13 -0.51 -0.85
outer loop
vertex 1.54 -0.97 0.02
vertex 1.49 -0.96 0
vertex 1.61 -0.96 0.02
endloop
endfacet
facet normal -0.62 0.14 -0.77
outer loop
vertex 1.33 0.97 0.05
vertex 1.32 0.9 0.05
vertex 1.24 0.96 0.13
endloop
endfacet
facet normal 0.1 0.99 -0.14
outer loop
vertex -1.29 0.97 0.08
vertex -1.47 0.98 0.02
vertex -1.22 0.98 0.2
endloop
endfacet
facet normal 0.63 -0.02 0.77
outer loop
vertex -1.24 0.76 0.56
vertex -1.28 0.96 0.59
vertex -1.34 0.76 0.64
endloop
endfacet
facet normal -1 0 0.02
outer loop
vertex 1.86 -1 0.42
vertex 1.85 0.8 0.24
vertex 1.85 -0.8 0.24
endloop
endfacet
facet normal 0.56 0 -0.83
outer loop
vertex 1.32 -0.76 0.51
vertex 1.4 -0.96 0.56
vertex 1.32 -0.96 0.51
endloop
endfacet
facet normal 0.01 0.83 0.56
outer loop
vertex 1.57 -0.76 0.67
vertex 1.58 -0.74 0.65
vertex 1.43 -0.74 0.65
endloop
endfacet
facet normal -0.12 -0.02 0.99
outer loop
vertex -1.6 0.76 0.66
vertex -1.47 0.76 0.68
vertex -1.51 0.96 0.68
endloop
endfacet
facet normal 0.29 0.03 -0.96
outer loop
vertex -1.56 0.96 0.58
vertex -1.52 0.76 0.58
vertex -1.61 0.76 0.56
endloop
endfacet
facet normal 0.2 0.85 0.49
outer loop
vertex -1.44 0.98 0.65
vertex -1.38 0.96 0.66
vertex -1.3 0.97 0.6
endloop
endfacet
facet normal -0.1 0.01 -0.99
outer loop
vertex -1.43 0.96 0.57
vertex -1.42 0.76 0.57
vertex -1.52 0.76 0.58
endloop
endfacet
facet normal 0.42 0.85 0.32
outer loop
vertex 1.71 -0.75 0.6
vertex 1.78 -0.76 0.53
vertex 1.79 -0.74 0.47
endloop
endfacet
facet normal 0.09 -0.9 -0.43
outer loop
vertex 1.45 -0.97 0.6
vertex 1.4 -0.96 0.56
vertex 1.51 -0.96 0.59
endloop
endfacet
facet normal -1 0.04 -0.09
outer loop
vertex -1.25 -0.76 0.34
vertex -1.26 -0.96 0.3
vertex -1.27 -0.96 0.43
endloop
endfacet
facet normal -0.43 0.85 0.3
outer loop
vertex 1.2 -0.74 0.44
vertex 1.24 -0.76 0.56
vertex 1.3 -0.75 0.6
endloop
endfacet
facet normal 0.43 0.53 0.73
outer loop
vertex -1.28 0.96 0.59
vertex -1.3 0.97 0.6
vertex -1.38 0.96 0.66
endloop
endfacet
facet normal -0.01 -0.97 0.25
outer loop
vertex -1.5 0.74 0.07
vertex -1.6 0.76 0.11
vertex -1.64 0.74 0.05
endloop
endfacet
facet normal 0.4 -0.89 0.2
outer loop
vertex 1.26 0.76 0.3
vertex 1.27 0.75 0.22
vertex 1.32 0.76 0.18
endloop
endfacet
facet normal 0.43 -0.72 0.54
outer loop
vertex -1.36 0.75 0.63
vertex -1.24 0.76 0.56
vertex -1.34 0.76 0.64
endloop
endfacet
facet normal 0.19 0.98 0.08
outer loop
vertex -1.18 -0.74 0.32
vertex -1.28 -0.74 0.57
vertex -1.18 -0.75 0.43
endloop
endfacet
facet normal 0.49 0.03 -0.87
outer loop
vertex -1.29 0.97 0.08
vertex -1.37 0.76 0.02
vertex -1.39 0.96 0.02
endloop
endfacet
facet normal 0.93 0.04 -0.36
outer loop
vertex -1.18 0.76 0.22
vertex -1.22 0.96 0.16
vertex -1.17 0.97 0.27
endloop
endfacet
facet normal 0.1 0.92 0.38
outer loop
vertex 1.36 0.96 0.13
vertex 1.5 0.96 0.09
vertex 1.3 0.98 0.11
endloop
endfacet
facet normal 0.73 -0.69 0.03
outer loop
vertex -1.18 0.74 0.34
vertex -1.16 0.76 0.31
vertex -1.17 0.76 0.4
endloop
endfacet
facet normal 0.6 -0.79 -0.12
outer loop
vertex -1.18 0.74 0.34
vertex -1.18 0.76 0.22
vertex -1.16 0.76 0.31
endloop
endfacet
facet normal 0.61 -0.78 -0.12
outer loop
vertex -1.18 0.76 0.22
vertex -1.18 0.74 0.34
vertex -1.2 0.75 0.21
endloop
endfacet
facet normal 0.99 0.02 -0.14
outer loop
vertex 1.26 0.76 0.3
vertex 1.27 0.96 0.42
vertex 1.28 0.76 0.44
endloop
endfacet
facet normal -0.22 0.92 0.33
outer loop
vertex -1.33 0.97 0.13
vertex -1.43 0.96 0.1
vertex -1.32 0.96 0.18
endloop
endfacet
facet normal -0.54 -0.01 0.84
outer loop
vertex -1.43 0.96 0.1
vertex -1.32 0.76 0.17
vertex -1.32 0.96 0.18
endloop
endfacet
facet normal 0.98 0 0.18
outer loop
vertex 1.84 0.96 0.35
vertex 1.82 0.76 0.46
vertex 1.84 0.76 0.34
endloop
endfacet
facet normal 0.06 -0.99 0.13
outer loop
vertex 1.52 0.76 0.09
vertex 1.38 0.75 0.1
vertex 1.43 0.74 0.03
endloop
endfacet
facet normal 0.11 0.05 -0.99
outer loop
vertex -1.54 0.96 0
vertex -1.39 0.96 0.02
vertex -1.47 0.76 0
endloop
endfacet
facet normal 0.23 0.91 0.35
outer loop
vertex -1.58 0.96 0.11
vertex -1.67 0.97 0.13
vertex -1.68 0.96 0.17
endloop
endfacet
facet normal 0.18 0.88 -0.43
outer loop
vertex -1.29 0.97 0.08
vertex -1.39 0.96 0.02
vertex -1.47 0.98 0.02
endloop
endfacet
facet normal 0.19 -0.86 -0.47
outer loop
vertex -1.47 0.75 0.02
vertex -1.37 0.76 0.02
vertex -1.3 0.74 0.09
endloop
endfacet
facet normal -0.15 0.98 -0.12
outer loop
vertex -1.28 -0.74 0.57
vertex -1.28 -0.76 0.44
vertex -1.36 -0.76 0.55
endloop
endfacet
facet normal 0.22 -0.95 -0.22
outer loop
vertex -1.61 -0.98 0.63
vertex -1.8 -0.98 0.44
vertex -1.63 -0.96 0.55
endloop
endfacet
facet normal 0.03 1 0.08
outer loop
vertex -1.67 0.97 0.13
vertex -1.5 0.97 0.07
vertex -1.65 0.98 0.06
endloop
endfacet
facet normal 0.18 -0.66 -0.73
outer loop
vertex -1.47 0.75 0.02
vertex -1.47 0.76 0
vertex -1.37 0.76 0.02
endloop
endfacet
facet normal 0.06 0.98 0.19
outer loop
vertex -1.28 -0.74 0.57
vertex -1.56 -0.74 0.65
vertex -1.43 -0.75 0.67
endloop
endfacet
facet normal -0.42 0.72 -0.54
outer loop
vertex -1.74 0.96 0.1
vertex -1.65 0.98 0.06
vertex -1.67 0.96 0.04
endloop
endfacet
facet normal 0.05 -1 -0.01
outer loop
vertex 1.27 0.75 0.22
vertex 1.2 0.74 0.45
vertex 1.19 0.74 0.29
endloop
endfacet
facet normal 0.01 0.91 0.42
outer loop
vertex -1.5 0.97 0.07
vertex -1.58 0.96 0.11
vertex -1.43 0.96 0.1
endloop
endfacet
facet normal 0.88 -0.02 0.48
outer loop
vertex -1.74 0.96 0.29
vertex -1.68 0.76 0.17
vertex -1.68 0.96 0.17
endloop
endfacet
facet normal -0.09 0.89 -0.46
outer loop
vertex -1.47 0.98 0.02
vertex -1.54 0.96 0
vertex -1.65 0.98 0.06
endloop
endfacet
facet normal -0.03 0.99 -0.11
outer loop
vertex 1.29 -0.74 0.11
vertex 1.55 -0.74 0.03
vertex 1.42 -0.75 0.03
endloop
endfacet
facet normal 0.17 -0.78 0.6
outer loop
vertex -1.5 0.74 0.07
vertex -1.52 0.76 0.1
vertex -1.6 0.76 0.11
endloop
endfacet
facet normal 0.64 0.01 0.77
outer loop
vertex -1.24 -0.96 0.56
vertex -1.34 -0.76 0.64
vertex -1.3 -0.97 0.61
endloop
endfacet
facet normal -0.26 -0.68 -0.68
outer loop
vertex -1.64 0.74 0.05
vertex -1.68 0.76 0.05
vertex -1.57 0.76 0.01
endloop
endfacet
facet normal -0.67 -0.03 0.74
outer loop
vertex -1.67 -0.96 0.63
vertex -1.76 -0.76 0.56
vertex -1.75 -0.97 0.56
endloop
endfacet
facet normal 0.43 0.84 -0.32
outer loop
vertex 1.74 0.96 0.1
vertex 1.7 0.97 0.08
vertex 1.79 0.98 0.21
endloop
endfacet
facet normal 0.45 0.57 -0.68
outer loop
vertex 2.42 0.98 0.42
vertex 2.48 0.93 0.42
vertex 2.42 0.78 0.25
endloop
endfacet
facet normal 0.72 0.03 -0.69
outer loop
vertex -1.29 0.97 0.08
vertex -1.22 0.96 0.16
vertex -1.24 0.76 0.13
endloop
endfacet
facet normal -0.66 -0.74 -0.12
outer loop
vertex -1.82 0.74 0.33
vertex -1.84 0.76 0.34
vertex -1.82 0.76 0.22
endloop
endfacet
facet normal 0.76 0.06 -0.65
outer loop
vertex 1.31 0.96 0.5
vertex 1.37 0.76 0.55
vertex 1.28 0.76 0.44
endloop
endfacet
facet normal -0.53 0.83 0.16
outer loop
vertex -1.82 -0.76 0.46
vertex -1.78 -0.75 0.51
vertex -1.81 -0.74 0.37
endloop
endfacet
facet normal 0.94 0.04 -0.35
outer loop
vertex -1.72 -0.76 0.45
vertex -1.7 -0.96 0.48
vertex -1.74 -0.96 0.37
endloop
endfacet
facet normal -0.62 -0.77 0.12
outer loop
vertex -1.8 -0.98 0.44
vertex -1.82 -0.96 0.45
vertex -1.83 -0.97 0.33
endloop
endfacet
facet normal -0.84 -0.03 -0.55
outer loop
vertex 1.23 -0.76 0.13
vertex 1.26 -0.96 0.1
vertex 1.19 -0.96 0.21
endloop
endfacet
facet normal 0.53 -0.82 -0.23
outer loop
vertex -1.76 -0.97 0.37
vertex -1.74 -0.96 0.37
vertex -1.7 -0.96 0.48
endloop
endfacet
facet normal -0.57 -0.76 0.31
outer loop
vertex -1.75 -0.97 0.56
vertex -1.82 -0.96 0.45
vertex -1.8 -0.98 0.44
endloop
endfacet
facet normal -0.53 0.79 -0.3
outer loop
vertex -1.77 -0.76 0.13
vertex -1.82 -0.76 0.22
vertex -1.73 -0.74 0.12
endloop
endfacet
facet normal 0.15 -0.77 -0.62
outer loop
vertex 1.37 0.76 0.55
vertex 1.51 0.76 0.59
vertex 1.52 0.75 0.6
endloop
endfacet
facet normal 0.2 0.97 0.11
outer loop
vertex -1.65 0.98 0.06
vertex -1.76 0.97 0.29
vertex -1.67 0.97 0.13
endloop
endfacet
facet normal -0.11 0.99 -0.06
outer loop
vertex 1.19 0.98 0.3
vertex 1.3 0.98 0.11
vertex 1.22 0.97 0.17
endloop
endfacet
facet normal -0.22 -0.64 0.74
outer loop
vertex 1.42 0.74 0.65
vertex 1.47 0.76 0.68
vertex 1.35 0.76 0.64
endloop
endfacet
facet normal 0.56 -0.22 -0.8
outer loop
vertex 1.4 -0.96 0.56
vertex 1.45 -0.97 0.6
vertex 1.32 -0.96 0.51
endloop
endfacet
facet normal -0.8 -0.02 -0.6
outer loop
vertex -1.36 -0.76 0.55
vertex -1.27 -0.96 0.43
vertex -1.35 -0.96 0.54
endloop
endfacet
facet normal -0.87 -0.01 0.5
outer loop
vertex -1.82 -0.96 0.45
vertex -1.76 -0.76 0.56
vertex -1.82 -0.76 0.46
endloop
endfacet
facet normal -0.11 0.98 -0.14
outer loop
vertex 1.79 -0.74 0.47
vertex 1.72 -0.75 0.48
vertex 1.59 -0.75 0.59
endloop
endfacet
facet normal -0.42 0.02 -0.91
outer loop
vertex -1.36 -0.76 0.55
vertex -1.35 -0.96 0.54
vertex -1.43 -0.96 0.57
endloop
endfacet
facet normal 0.25 -0.56 0.79
outer loop
vertex -1.36 0.75 0.63
vertex -1.34 0.76 0.64
vertex -1.47 0.76 0.68
endloop
endfacet
facet normal -0.71 0.01 -0.71
outer loop
vertex -1.76 -0.96 0.12
vertex -1.77 -0.76 0.13
vertex -1.7 -0.91 0.06
endloop
endfacet
facet normal -0.86 -0.03 0.51
outer loop
vertex 1.25 0.75 0.57
vertex 1.18 0.96 0.46
vertex 1.17 0.76 0.43
endloop
endfacet
facet normal 0.86 -0.06 0.5
outer loop
vertex 2.32 -0.97 1.16
vertex 2.42 -0.96 0.99
vertex 2.42 -0.84 1
endloop
endfacet
facet normal -0.04 -0.88 -0.47
outer loop
vertex -1.48 -0.97 0.6
vertex -1.54 -0.96 0.58
vertex -1.43 -0.96 0.57
endloop
endfacet
facet normal -0.36 0.03 -0.93
outer loop
vertex -1.68 -0.76 0.05
vertex -1.58 -0.75 0.01
vertex -1.63 -0.96 0.03
endloop
endfacet
facet normal 0.92 0.28 0.29
outer loop
vertex -1.72 -0.76 0.23
vertex -1.63 -0.96 0.13
vertex -1.71 -0.75 0.2
endloop
endfacet
facet normal 0.58 0.8 -0.13
outer loop
vertex 1.84 0.96 0.35
vertex 1.81 0.96 0.21
vertex 1.79 0.98 0.21
endloop
endfacet
facet normal -0.23 0.8 0.55
outer loop
vertex -1.67 -0.76 0.63
vertex -1.56 -0.74 0.65
vertex -1.68 -0.74 0.6
endloop
endfacet
facet normal -0.66 0.01 -0.75
outer loop
vertex 1.65 0.96 0.53
vertex 1.68 0.76 0.51
vertex 1.63 0.76 0.55
endloop
endfacet
facet normal 0.98 0.02 -0.18
outer loop
vertex 1.82 0.76 0.22
vertex 1.81 0.96 0.21
vertex 1.84 0.96 0.35
endloop
endfacet
facet normal 0.27 0.96 -0.02
outer loop
vertex -1.22 0.98 0.2
vertex -1.2 0.98 0.44
vertex -1.17 0.97 0.27
endloop
endfacet
facet normal -0.1 -0.98 0.18
outer loop
vertex -1.33 -0.97 0.14
vertex -1.47 -0.97 0.09
vertex -1.47 -0.98 0.03
endloop
endfacet
facet normal 0.38 0.89 0.26
outer loop
vertex 1.72 0.97 0.58
vertex 1.78 0.96 0.53
vertex 1.81 0.97 0.45
endloop
endfacet
facet normal -0.02 -0.83 -0.55
outer loop
vertex 0.95 0.87 1.8
vertex 1.34 0.87 1.79
vertex 0.94 0.87 1.81
endloop
endfacet
facet normal 0.6 -0.72 0.36
outer loop
vertex -1.22 -0.98 0.48
vertex -1.18 -0.96 0.46
vertex -1.24 -0.96 0.56
endloop
endfacet
facet normal -0.09 0.99 0.07
outer loop
vertex 1.79 0.98 0.21
vertex 1.65 0.97 0.12
vertex 1.74 0.97 0.24
endloop
endfacet
facet normal -0.86 0.02 -0.51
outer loop
vertex 1.68 0.76 0.51
vertex 1.71 0.96 0.46
vertex 1.73 0.76 0.42
endloop
endfacet
facet normal -0.36 -0.01 0.93
outer loop
vertex 1.33 -0.96 0.63
vertex 1.43 -0.76 0.67
vertex 1.33 -0.76 0.63
endloop
endfacet
facet normal 0.75 -0.64 0.14
outer loop
vertex -1.18 -0.97 0.37
vertex -1.16 -0.96 0.34
vertex -1.18 -0.96 0.46
endloop
endfacet
facet normal 0.56 0.82 -0.15
outer loop
vertex -1.18 -0.74 0.32
vertex -1.17 -0.76 0.3
vertex -1.22 -0.74 0.2
endloop
endfacet
facet normal -0.98 -0.02 0.2
outer loop
vertex -1.27 -0.76 0.24
vertex -1.26 -0.96 0.3
vertex -1.25 -0.76 0.34
endloop
endfacet
facet normal -0.05 0.99 -0.1
outer loop
vertex 1.58 -0.74 0.65
vertex 1.59 -0.75 0.59
vertex 1.42 -0.76 0.57
endloop
endfacet
facet normal 0.63 0.35 0.69
outer loop
vertex 1.78 0.96 0.53
vertex 1.72 0.97 0.58
vertex 1.66 0.96 0.64
endloop
endfacet
facet normal 0.16 -0.98 0.08
outer loop
vertex -1.32 0.74 0.59
vertex -1.18 0.74 0.34
vertex -1.21 0.75 0.5
endloop
endfacet
facet normal 0.95 0.06 0.29
outer loop
vertex 1.82 0.76 0.46
vertex 1.84 0.96 0.35
vertex 1.78 0.96 0.53
endloop
endfacet
facet normal -0.97 -0.04 0.22
outer loop
vertex 1.16 -0.96 0.34
vertex 1.19 -0.97 0.46
vertex 1.17 -0.76 0.4
endloop
endfacet
facet normal -0.47 0.87 -0.15
outer loop
vertex 1.75 0.98 0.45
vertex 1.74 0.96 0.37
vertex 1.71 0.96 0.46
endloop
endfacet
facet normal 0.5 0.01 -0.86
outer loop
vertex 1.61 -0.76 0.02
vertex 1.73 -0.96 0.09
vertex 1.61 -0.96 0.02
endloop
endfacet
facet normal 1 0 0.02
outer loop
vertex -1.85 0.8 0.24
vertex -1.86 -1 0.42
vertex -1.85 -0.8 0.25
endloop
endfacet
facet normal 0.73 0.04 -0.68
outer loop
vertex -1.32 -0.76 0.05
vertex -1.21 -0.76 0.17
vertex -1.24 -0.96 0.12
endloop
endfacet
facet normal -0.63 0 0.78
outer loop
vertex -1.39 -0.76 0.12
vertex -1.31 -0.96 0.19
vertex -1.32 -0.76 0.18
endloop
endfacet
facet normal 0.19 0.84 -0.51
outer loop
vertex -1.3 -0.75 0.08
vertex -1.32 -0.76 0.05
vertex -1.47 -0.74 0.02
endloop
endfacet
facet normal 0.2 -0.84 -0.5
outer loop
vertex -1.47 -0.98 0.03
vertex -1.4 -0.96 0.01
vertex -1.3 -0.97 0.08
endloop
endfacet
facet normal -0.31 -0.01 0.95
outer loop
vertex -1.47 -0.76 0.09
vertex -1.42 -0.96 0.11
vertex -1.39 -0.76 0.12
endloop
endfacet
facet normal 0.05 -0.96 0.27
outer loop
vertex 1.42 0.74 0.65
vertex 1.68 0.74 0.6
vertex 1.58 0.76 0.67
endloop
endfacet
facet normal 0.64 0.01 0.77
outer loop
vertex 1.76 0.76 0.56
vertex 1.66 0.96 0.64
vertex 1.67 0.76 0.63
endloop
endfacet
facet normal 0.1 -0.67 -0.73
outer loop
vertex -1.47 -0.98 0.03
vertex -1.51 -0.96 0
vertex -1.4 -0.96 0.01
endloop
endfacet
facet normal 0.91 0.03 0.42
outer loop
vertex 1.8 -0.96 0.5
vertex 1.83 -0.76 0.41
vertex 1.78 -0.76 0.53
endloop
endfacet
facet normal -0.44 -0.9 -0.04
outer loop
vertex -1.27 -0.96 0.43
vertex -1.26 -0.96 0.3
vertex -1.24 -0.97 0.4
endloop
endfacet
facet normal -0.01 0 -1
outer loop
vertex -2.04 0.81 1.85
vertex -2.2 -0.81 1.85
vertex -2.2 0.81 1.85
endloop
endfacet
facet normal -0.47 -0.01 -0.88
outer loop
vertex -1.68 -0.76 0.05
vertex -1.63 -0.96 0.03
vertex -1.7 -0.91 0.06
endloop
endfacet
facet normal -0.05 0.98 0.21
outer loop
vertex 1.59 0.98 0.64
vertex 1.31 0.98 0.58
vertex 1.44 0.96 0.67
endloop
endfacet
facet normal -0.18 0.89 -0.41
outer loop
vertex 1.59 -0.75 0.59
vertex 1.65 -0.76 0.53
vertex 1.54 -0.76 0.58
endloop
endfacet
facet normal -0.33 0.87 -0.36
outer loop
vertex 1.22 0.97 0.17
vertex 1.3 0.98 0.11
vertex 1.33 0.97 0.05
endloop
endfacet
facet normal -0.04 -1 -0.07
outer loop
vertex -1.47 -0.98 0.03
vertex -1.77 -0.98 0.17
vertex -1.63 -0.97 0.04
endloop
endfacet
facet normal -0.41 0.85 0.33
outer loop
vertex 1.65 0.97 0.12
vertex 1.63 0.96 0.13
vertex 1.73 0.96 0.25
endloop
endfacet
facet normal -0.77 -0.06 0.63
outer loop
vertex 1.63 0.96 0.13
vertex 1.69 0.76 0.18
vertex 1.73 0.96 0.25
endloop
endfacet
facet normal -0.5 0.81 0.3
outer loop
vertex 1.18 0.96 0.46
vertex 1.29 0.97 0.59
vertex 1.19 0.97 0.42
endloop
endfacet
facet normal -0.38 -0.85 0.37
outer loop
vertex -1.68 0.74 0.6
vertex -1.74 0.76 0.58
vertex -1.78 0.75 0.51
endloop
endfacet
facet normal 0.54 -0.01 0.84
outer loop
vertex 1.32 -0.76 0.17
vertex 1.41 -0.96 0.11
vertex 1.42 -0.76 0.11
endloop
endfacet
facet normal 0.05 1 -0.07
outer loop
vertex -1.47 -0.74 0.02
vertex -1.22 -0.74 0.2
vertex -1.3 -0.75 0.08
endloop
endfacet
facet normal -1 0.02 0.01
outer loop
vertex 1.16 -0.96 0.34
vertex 1.17 -0.76 0.4
vertex 1.16 -0.76 0.29
endloop
endfacet
facet normal 0.86 0.06 0.5
outer loop
vertex 2.42 0.84 1
vertex 2.42 0.96 0.99
vertex 2.32 0.97 1.16
endloop
endfacet
facet normal -0.33 0.03 -0.94
outer loop
vertex 1.32 -0.76 0.05
vertex 1.46 -0.76 0
vertex 1.36 -0.96 0.03
endloop
endfacet
facet normal 0.91 -0.38 0.18
outer loop
vertex 1.26 0.76 0.3
vertex 1.24 0.75 0.37
vertex 1.27 0.75 0.22
endloop
endfacet
facet normal 0.88 0.27 -0.39
outer loop
vertex 2.48 0.75 0.29
vertex 2.48 0.93 0.42
vertex 2.51 0.85 0.43
endloop
endfacet
facet normal 0.87 -0.28 -0.41
outer loop
vertex 2.51 -0.84 0.41
vertex 2.48 -0.93 0.42
vertex 2.48 -0.75 0.29
endloop
endfacet
facet normal 0.23 -0.83 0.5
outer loop
vertex 2.48 0.78 0.88
vertex 2.42 0.84 1
vertex 2.42 0.79 0.93
endloop
endfacet
facet normal 0.23 0.83 0.5
outer loop
vertex 2.42 -0.79 0.93
vertex 2.42 -0.84 1
vertex 2.48 -0.78 0.88
endloop
endfacet
facet normal 0.15 -0.96 0.22
outer loop
vertex 2.42 0.84 1
vertex 2.32 0.86 1.18
vertex 2.31 0.81 0.94
endloop
endfacet
facet normal 0 1 0.08
outer loop
vertex 1.21 -0.87 1.33
vertex 2.05 -0.87 1.33
vertex 2.2 -0.87 1.29
endloop
endfacet
facet normal 0.15 0.96 0.22
outer loop
vertex 2.31 -0.81 0.94
vertex 2.32 -0.86 1.18
vertex 2.42 -0.84 1
endloop
endfacet
facet normal 0.86 0 0.51
outer loop
vertex 1.24 -0.81 1.13
vertex 1.24 0.81 1.13
vertex 1.14 0.82 1.3
endloop
endfacet
facet normal 0.03 -0.98 0.18
outer loop
vertex 2.31 0.81 0.94
vertex 2.2 0.87 1.29
vertex 1.24 0.81 1.13
endloop
endfacet
facet normal 0.03 0.98 0.18
outer loop
vertex 2.2 -0.87 1.29
vertex 2.31 -0.81 0.94
vertex 1.24 -0.81 1.13
endloop
endfacet
facet normal -0.2 0.98 -0.05
outer loop
vertex -2.47 0.98 0.42
vertex -2.39 1.01 0.69
vertex -2.39 0.99 0.42
endloop
endfacet
facet normal 0.02 0 1
outer loop
vertex 0.98 0.79 1.79
vertex -2.06 -0.79 1.86
vertex 0.98 -0.79 1.79
endloop
endfacet
facet normal 0 0 -1
outer loop
vertex -1.15 -0.8 0.24
vertex -1.15 0.8 0.24
vertex 1.15 -0.8 0.24
endloop
endfacet
facet normal 0.97 -0.24 0
outer loop
vertex 2.51 -0.84 0.41
vertex 2.51 -0.84 0.81
vertex 2.48 -0.93 0.86
endloop
endfacet
facet normal -0.72 -0.68 -0.15
outer loop
vertex 1.19 -0.98 0.29
vertex 1.16 -0.96 0.34
vertex 1.19 -0.96 0.21
endloop
endfacet
facet normal 0 -1 -0.06
outer loop
vertex -1.14 -1 0.42
vertex 1.14 -1 0.42
vertex 1.22 -1.01 0.57
endloop
endfacet
facet normal -0.05 1 -0.02
outer loop
vertex -1.81 0.98 0.41
vertex -1.65 0.98 0.06
vertex -1.78 0.97 0.17
endloop
endfacet
facet normal 0.95 0 0.33
outer loop
vertex 2.48 -0.78 0.88
vertex 2.51 0.84 0.81
vertex 2.48 0.78 0.88
endloop
endfacet
facet normal 0.01 1 -0.02
outer loop
vertex 2.39 1.01 0.67
vertex 1.8 1.01 0.55
vertex 1.71 1.01 0.64
endloop
endfacet
facet normal -0.19 0.98 0.09
outer loop
vertex -2.39 1.01 0.69
vertex -2.47 0.94 1.21
vertex -2.39 0.95 1.35
endloop
endfacet
facet normal -0.98 0.17 0
outer loop
vertex -2.49 0.93 1.04
vertex -2.49 0.98 0.69
vertex -2.51 0.85 0.98
endloop
endfacet
facet normal -0.91 0 -0.42
outer loop
vertex 1.79 -1.01 0.57
vertex 1.86 1 0.42
vertex 1.86 -1 0.42
endloop
endfacet
facet normal 0.24 0 -0.97
outer loop
vertex -1.67 -1.02 0.67
vertex -1.53 1.01 0.7
vertex -1.52 -1.01 0.71
endloop
endfacet
facet normal 0.9 0 -0.44
outer loop
vertex -1.8 -1.01 0.55
vertex -1.86 1 0.42
vertex -1.78 1.01 0.58
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 2.5 -0.63 0.38
vertex 2.5 -0.63 0.38
vertex 2.5 -0.64 0.39
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 2.5 -0.64 0.39
vertex 2.5 -0.64 0.39
vertex 2.5 -0.65 0.39
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 2.5 -0.65 0.39
vertex 2.5 -0.65 0.39
vertex 2.5 -0.65 0.4
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 2.5 -0.63 0.55
vertex 2.5 -0.63 0.55
vertex 2.5 -0.64 0.55
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 2.5 -0.64 0.55
vertex 2.5 -0.64 0.55
vertex 2.5 -0.65 0.55
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 2.5 -0.65 0.55
vertex 2.5 -0.65 0.55
vertex 2.5 -0.65 0.54
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 2.5 0.63 0.38
vertex 2.5 0.63 0.38
vertex 2.5 0.64 0.39
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 2.5 0.64 0.39
vertex 2.5 0.64 0.39
vertex 2.5 0.65 0.39
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 2.5 0.65 0.39
vertex 2.5 0.65 0.39
vertex 2.5 0.65 0.4
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 2.5 0.63 0.55
vertex 2.5 0.63 0.55
vertex 2.5 0.64 0.55
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 2.5 0.64 0.55
vertex 2.5 0.64 0.55
vertex 2.5 0.65 0.55
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 2.5 0.65 0.55
vertex 2.5 0.65 0.55
vertex 2.5 0.65 0.54
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 2.5 -0.63 0.38
vertex 2.5 0.63 0.38
vertex 2.5 0.63 0.38
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 2.5 -0.65 0.4
vertex 2.5 -0.65 0.54
vertex 2.5 -0.65 0.54
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 2.5 0.63 0.55
vertex 2.5 -0.63 0.55
vertex 2.5 -0.63 0.55
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 2.5 0.65 0.4
vertex 2.5 0.65 0.54
vertex 2.5 0.65 0.54
endloop
endfacet
facet normal 0.89 0.27 0.38
outer loop
vertex 0.98 0.86 1.75
vertex 0.98 0.79 1.79
vertex 1.19 0.8 1.3
endloop
endfacet
facet normal 0.88 -0.27 0.38
outer loop
vertex 1.19 -0.8 1.3
vertex 0.98 -0.79 1.79
vertex 0.98 -0.86 1.75
endloop
endfacet
facet normal -0.66 -0.75 0.08
outer loop
vertex -2.49 -0.93 1.04
vertex -2.49 -0.98 0.69
vertex -2.47 -0.94 1.21
endloop
endfacet
facet normal 0.01 -0.39 0.92
outer loop
vertex -2.39 0.81 1.34
vertex 1.21 0.87 1.33
vertex -2.39 0.86 1.36
endloop
endfacet
facet normal 0.65 0.43 -0.63
outer loop
vertex 2.42 0.78 0.25
vertex 2.48 0.93 0.42
vertex 2.48 0.75 0.29
endloop
endfacet
facet normal -0.8 0 0.6
outer loop
vertex -2.2 -0.75 1.67
vertex -2.06 0.79 1.86
vertex -2.2 0.75 1.67
endloop
endfacet
facet normal -0.35 0.9 0.25
outer loop
vertex -2.06 0.96 1.29
vertex -2.21 0.9 1.29
vertex -2.21 0.81 1.61
endloop
endfacet
facet normal -0.35 -0.9 0.25
outer loop
vertex -2.21 -0.81 1.61
vertex -2.21 -0.9 1.29
vertex -2.06 -0.95 1.29
endloop
endfacet
facet normal -0.82 0.02 0.57
outer loop
vertex -2.21 0.81 1.61
vertex -2.43 0.93 1.29
vertex -2.43 0.8 1.3
endloop
endfacet
facet normal -0.82 -0.01 0.57
outer loop
vertex -2.43 -0.8 1.3
vertex -2.43 -0.93 1.29
vertex -2.21 -0.81 1.61
endloop
endfacet
facet normal -0.84 -0.21 0.5
outer loop
vertex -2.47 0.84 1.23
vertex -2.39 0.81 1.34
vertex -2.39 0.86 1.36
endloop
endfacet
facet normal -0.35 0.88 0.31
outer loop
vertex 1.33 -0.87 1.79
vertex 1.34 -0.87 1.79
vertex 1.33 -0.87 1.78
endloop
endfacet
facet normal -0.88 -0.37 0.3
outer loop
vertex 1.34 0.86 1.79
vertex 1.34 0.87 1.79
vertex 1.34 0.87 1.78
endloop
endfacet
facet normal 0.37 -0.87 0.31
outer loop
vertex 0.95 0.87 1.8
vertex 0.94 0.87 1.8
vertex 0.94 0.87 1.79
endloop
endfacet
facet normal 0.9 0.37 0.25
outer loop
vertex 0.94 -0.86 1.8
vertex 0.94 -0.87 1.8
vertex 0.94 -0.87 1.79
endloop
endfacet
facet normal -0.89 0.37 -0.26
outer loop
vertex 1.34 -0.86 1.79
vertex 1.34 -0.87 1.79
vertex 1.34 -0.87 1.79
endloop
endfacet
facet normal -0.38 -0.89 -0.26
outer loop
vertex 1.33 0.87 1.79
vertex 1.34 0.87 1.79
vertex 1.34 0.87 1.79
endloop
endfacet
facet normal 0.87 -0.37 -0.33
outer loop
vertex 0.94 0.86 1.8
vertex 0.94 0.87 1.8
vertex 0.94 0.87 1.81
endloop
endfacet
facet normal 0.35 0.88 -0.32
outer loop
vertex 0.95 -0.87 1.8
vertex 0.94 -0.87 1.8
vertex 0.94 -0.87 1.81
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 1.33 -0.87 1.79
vertex 1.33 -0.87 1.79
vertex 1.34 -0.87 1.79
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 1.34 -0.87 1.79
vertex 1.34 -0.87 1.79
vertex 1.34 -0.86 1.79
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 1.33 0.87 1.79
vertex 1.33 0.87 1.79
vertex 1.34 0.87 1.79
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 1.34 0.87 1.79
vertex 1.34 0.87 1.79
vertex 1.34 0.86 1.79
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 0.94 0.86 1.8
vertex 0.94 0.86 1.8
vertex 0.94 0.87 1.8
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 0.94 0.87 1.8
vertex 0.94 0.87 1.8
vertex 0.95 0.87 1.8
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 0.95 -0.87 1.8
vertex 0.95 -0.87 1.8
vertex 0.94 -0.87 1.8
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 0.94 -0.87 1.8
vertex 0.94 -0.87 1.8
vertex 0.94 -0.86 1.8
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 0.95 -0.87 1.8
vertex 0.95 -0.87 1.8
vertex 1.33 -0.87 1.79
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 1.34 -0.86 1.79
vertex 1.34 -0.86 1.79
vertex 1.34 0.86 1.79
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 1.33 0.87 1.79
vertex 1.33 0.87 1.79
vertex 0.95 0.87 1.8
endloop
endfacet
facet normal 0 0 0
outer loop
vertex 0.94 0.86 1.8
vertex 0.94 0.86 1.8
vertex 0.94 -0.86 1.8
endloop
endfacet
facet normal 0.96 0.1 -0.27
outer loop
vertex 2.48 0.75 0.29
vertex 2.51 0.85 0.43
vertex 2.51 0.69 0.36
endloop
endfacet
facet normal -0.98 0.02 0.18
outer loop
vertex -2.47 0.84 1.23
vertex -2.47 0.94 1.21
vertex -2.51 0.85 0.98
endloop
endfacet
facet normal 0.64 -0.77 -0.01
outer loop
vertex 2.39 -1.01 0.67
vertex 2.42 -0.98 0.42
vertex 2.48 -0.93 0.86
endloop
endfacet
facet normal 0.01 0.16 0.99
outer loop
vertex -2.39 0.95 1.35
vertex -2.39 0.86 1.36
vertex 1.21 0.87 1.33
endloop
endfacet
facet normal 0 0.11 0.99
outer loop
vertex 1.21 0.87 1.33
vertex 2.05 0.87 1.33
vertex 2.05 0.95 1.32
endloop
endfacet
facet normal 0.01 0.07 1
outer loop
vertex 1.21 0.87 1.33
vertex 2.05 0.95 1.32
vertex -2.39 0.95 1.35
endloop
endfacet
facet normal 0.13 0.65 -0.75
outer loop
vertex 2.32 0.79 0.24
vertex 2.32 1 0.42
vertex 2.42 0.98 0.42
endloop
endfacet
facet normal 0.98 -0.01 -0.22
outer loop
vertex 2.51 0.69 0.36
vertex 2.51 -0.84 0.41
vertex 2.48 -0.75 0.29
endloop
endfacet
facet normal 0.65 -0.43 -0.62
outer loop
vertex 2.48 -0.93 0.42
vertex 2.42 -0.78 0.25
vertex 2.48 -0.75 0.29
endloop
endfacet
facet normal 0.53 -0.84 0.07
outer loop
vertex 2.48 -0.93 0.86
vertex 2.42 -0.96 0.99
vertex 2.39 -1.01 0.67
endloop
endfacet
facet normal 0.63 0 0.78
outer loop
vertex 2.42 -0.79 0.93
vertex 2.48 -0.78 0.88
vertex 2.48 0.78 0.88
endloop
endfacet
facet normal 0.67 0.09 0.74
outer loop
vertex 2.2 0.96 1.27
vertex 2.2 0.87 1.29
vertex 2.32 0.86 1.18
endloop
endfacet
facet normal 1 0 -0.02
outer loop
vertex 1.19 -0.94 1.29
vertex 1.19 0.94 1.29
vertex 1.19 -0.8 1.3
endloop
endfacet
facet normal 1 0 -0.02
outer loop
vertex 1.19 -0.8 1.3
vertex 1.19 0.94 1.29
vertex 1.19 0.8 1.3
endloop
endfacet
facet normal 0.43 -0.86 0.27
outer loop
vertex -1.82 0.74 0.33
vertex -1.64 0.74 0.05
vertex -1.68 0.76 0.17
endloop
endfacet
facet normal 0.12 -0.98 0.17
outer loop
vertex -1.64 0.74 0.05
vertex -1.6 0.76 0.11
vertex -1.68 0.76 0.17
endloop
endfacet
facet normal 0.22 -0.97 0.11
outer loop
vertex 2.42 -0.96 0.99
vertex 2.32 -0.97 1.16
vertex 2.39 -1.01 0.67
endloop
endfacet
facet normal -0.24 0 -0.97
outer loop
vertex -2.39 0.79 0.25
vertex -2.39 -0.79 0.25
vertex -2.47 -0.78 0.27
endloop
endfacet
facet normal -0.98 -0.19 0.01
outer loop
vertex -2.51 -0.85 0.98
vertex -2.51 -0.87 0.43
vertex -2.49 -0.98 0.69
endloop
endfacet
facet normal -0.98 -0.2 0.01
outer loop
vertex -2.51 -0.87 0.43
vertex -2.5 -0.95 0.42
vertex -2.49 -0.98 0.69
endloop
endfacet
facet normal 0.67 -0.09 0.74
outer loop
vertex 2.32 -0.86 1.18
vertex 2.2 -0.87 1.29
vertex 2.2 -0.96 1.27
endloop
endfacet
facet normal -0.02 -0.64 -0.77
outer loop
vertex -2.39 -0.99 0.42
vertex -2.39 -0.79 0.25
vertex -1.85 -0.8 0.25
endloop
endfacet
facet normal -0.01 -0.66 -0.75
outer loop
vertex -1.86 -1 0.42
vertex -2.39 -0.99 0.42
vertex -1.85 -0.8 0.25
endloop
endfacet
facet normal 0.04 0.99 -0.11
outer loop
vertex -1.68 -0.74 0.6
vertex -1.56 -0.74 0.65
vertex -1.64 -0.75 0.57
endloop
endfacet
facet normal 0.08 0.99 -0.15
outer loop
vertex -1.56 -0.74 0.65
vertex -1.48 -0.76 0.59
vertex -1.64 -0.75 0.57
endloop
endfacet
facet normal 0.04 0.99 -0.11
outer loop
vertex -1.68 -0.74 0.6
vertex -1.64 -0.75 0.57
vertex -1.72 -0.76 0.45
endloop
endfacet
facet normal -0.98 -0.02 0.18
outer loop
vertex -2.51 -0.85 0.98
vertex -2.47 -0.94 1.21
vertex -2.47 -0.83 1.22
endloop
endfacet
facet normal -0.76 -0.34 -0.55
outer loop
vertex -2.47 -0.78 0.27
vertex -2.5 -0.95 0.42
vertex -2.49 -0.76 0.3
endloop
endfacet
facet normal -0.7 -0.71 -0.06
outer loop
vertex -2.49 -0.98 0.69
vertex -2.5 -0.95 0.42
vertex -2.47 -0.98 0.42
endloop
endfacet
facet normal 0.53 0.84 0.07
outer loop
vertex 2.39 1.01 0.67
vertex 2.42 0.96 0.99
vertex 2.48 0.93 0.86
endloop
endfacet
facet normal -0.88 -0.09 0.46
outer loop
vertex -2.39 -0.86 1.36
vertex -2.47 -0.83 1.22
vertex -2.39 -0.95 1.35
endloop
endfacet
facet normal -0.87 -0.05 0.49
outer loop
vertex -2.47 -0.83 1.22
vertex -2.47 -0.94 1.21
vertex -2.39 -0.95 1.35
endloop
endfacet
facet normal 0 -0.98 0.19
outer loop
vertex -2.39 -0.95 1.35
vertex 2.2 -0.96 1.27
vertex 2.05 -0.95 1.32
endloop
endfacet
facet normal 0.26 0.11 0.96
outer loop
vertex 2.05 0.95 1.32
vertex 2.05 0.87 1.33
vertex 2.2 0.87 1.29
endloop
endfacet
facet normal 0 0.66 -0.75
outer loop
vertex -1.15 0.8 0.24
vertex -1.14 1 0.42
vertex 1.14 1 0.42
endloop
endfacet
facet normal -0.14 -0.98 0.15
outer loop
vertex 1.42 0.74 0.65
vertex 1.25 0.75 0.57
vertex 1.2 0.74 0.45
endloop
endfacet
facet normal 0.11 0 -0.99
outer loop
vertex 2.42 0.78 0.25
vertex 2.42 -0.78 0.25
vertex 2.32 -0.79 0.24
endloop
endfacet
facet normal 0.1 0 -1
outer loop
vertex 2.32 -0.79 0.24
vertex 2.32 0.79 0.24
vertex 2.42 0.78 0.25
endloop
endfacet
facet normal 0 -0.99 0.1
outer loop
vertex 2.2 -0.96 1.27
vertex -2.39 -0.95 1.35
vertex -1.38 -1.02 0.69
endloop
endfacet
facet normal -0.01 -1 0.09
outer loop
vertex -2.39 -0.95 1.35
vertex -2.39 -1.01 0.69
vertex -1.67 -1.02 0.67
endloop
endfacet
facet normal -0.01 -1 0.09
outer loop
vertex -1.67 -1.02 0.67
vertex -1.52 -1.01 0.71
vertex -2.39 -0.95 1.35
endloop
endfacet
facet normal 0.05 -0.99 0.09
outer loop
vertex 2.32 -0.97 1.16
vertex 2.2 -0.96 1.27
vertex 2.39 -1.01 0.67
endloop
endfacet
facet normal 0.01 -1 0.08
outer loop
vertex 1.66 -1.02 0.67
vertex 2.39 -1.01 0.67
vertex 2.2 -0.96 1.27
endloop
endfacet
facet normal 0.01 -1 0.08
outer loop
vertex 1.53 -1.01 0.7
vertex 1.66 -1.02 0.67
vertex 2.2 -0.96 1.27
endloop
endfacet
facet normal 0 -0.99 0.11
outer loop
vertex -2.39 -0.95 1.35
vertex -1.52 -1.01 0.71
vertex -1.38 -1.02 0.69
endloop
endfacet
facet normal 0 -1 0.09
outer loop
vertex 1.37 -1.02 0.69
vertex 1.53 -1.01 0.7
vertex 2.2 -0.96 1.27
endloop
endfacet
facet normal 0 -1 0.09
outer loop
vertex -1.38 -1.02 0.69
vertex 1.37 -1.02 0.69
vertex 2.2 -0.96 1.27
endloop
endfacet
facet normal 0.51 0.76 0.4
outer loop
vertex -1.3 0.97 0.6
vertex -1.28 0.96 0.59
vertex -1.2 0.96 0.49
endloop
endfacet
facet normal 0.05 0.97 -0.23
outer loop
vertex 1.31 0.98 0.58
vertex 1.59 0.98 0.64
vertex 1.52 0.97 0.6
endloop
endfacet
facet normal 0.13 0.98 0.16
outer loop
vertex 1.58 -0.74 0.65
vertex 1.71 -0.75 0.6
vertex 1.79 -0.74 0.47
endloop
endfacet
facet normal -0.26 0.96 -0.13
outer loop
vertex 1.29 -0.74 0.11
vertex 1.2 -0.75 0.2
vertex 1.19 -0.74 0.31
endloop
endfacet
facet normal -0.76 0.39 0.52
outer loop
vertex -2.21 0.81 1.61
vertex -2.43 0.8 1.3
vertex -2.2 0.75 1.67
endloop
endfacet
facet normal -0.79 0.35 0.51
outer loop
vertex -2.2 0.75 1.67
vertex -2.06 0.79 1.86
vertex -2.06 0.86 1.82
endloop
endfacet
facet normal -0.79 0.37 0.5
outer loop
vertex -2.06 0.86 1.82
vertex -2.21 0.81 1.61
vertex -2.2 0.75 1.67
endloop
endfacet
facet normal -0.22 -0.98 -0.01
outer loop
vertex 1.78 0.74 0.2
vertex 1.77 0.74 0.5
vertex 1.76 0.75 0.26
endloop
endfacet
facet normal -0.51 0 -0.86
outer loop
vertex 2.49 -0.64 0.39
vertex 2.49 0.64 0.39
vertex 2.5 0.63 0.38
endloop
endfacet
facet normal -0.02 -0.99 0.13
outer loop
vertex -1.5 0.74 0.07
vertex -1.3 0.74 0.09
vertex -1.33 0.75 0.13
endloop
endfacet
facet normal -0.32 -0.41 0.85
outer loop
vertex 1.5 -0.97 0.07
vertex 1.67 -0.97 0.13
vertex 1.55 -0.96 0.1
endloop
endfacet
facet normal 0.17 -0.64 -0.75
outer loop
vertex 2.42 -0.78 0.25
vertex 2.42 -0.98 0.42
vertex 2.32 -0.79 0.24
endloop
endfacet
facet normal 0.13 -0.65 -0.75
outer loop
vertex 2.42 -0.98 0.42
vertex 2.32 -1 0.42
vertex 2.32 -0.79 0.24
endloop
endfacet
facet normal 0 0 -1
outer loop
vertex -2.06 0.96 1.29
vertex 1.19 0.94 1.29
vertex 1.19 -0.94 1.29
endloop
endfacet
facet normal 0 0 -1
outer loop
vertex 1.19 -0.94 1.29
vertex -2.06 -0.95 1.29
vertex -2.06 0.96 1.29
endloop
endfacet
facet normal 0 0 -1
outer loop
vertex -2.06 -0.95 1.29
vertex -2.21 -0.9 1.29
vertex -2.06 0.96 1.29
endloop
endfacet
facet normal -0.01 0 -1
outer loop
vertex -2.21 -0.9 1.29
vertex -2.43 -0.93 1.29
vertex -2.43 0.93 1.29
endloop
endfacet
facet normal 0 0 -1
outer loop
vertex -2.21 0.9 1.29
vertex -2.06 0.96 1.29
vertex -2.21 -0.9 1.29
endloop
endfacet
facet normal 0.05 -1 -0.07
outer loop
vertex -1.21 -0.98 0.21
vertex -1.47 -0.98 0.03
vertex -1.3 -0.97 0.08
endloop
endfacet
facet normal -0.28 -0.96 0.07
outer loop
vertex -2.47 -0.94 1.21
vertex -2.49 -0.98 0.69
vertex -2.39 -1.01 0.69
endloop
endfacet
facet normal 0.22 0.97 0.11
outer loop
vertex 2.39 1.01 0.67
vertex 2.32 0.97 1.16
vertex 2.42 0.96 0.99
endloop
endfacet
facet normal 0.26 -0.11 0.96
outer loop
vertex 2.2 -0.87 1.29
vertex 2.05 -0.87 1.33
vertex 2.05 -0.95 1.32
endloop
endfacet
facet normal 0.95 0.32 -0.01
outer loop
vertex 2.48 0.93 0.42
vertex 2.48 0.93 0.86
vertex 2.51 0.85 0.43
endloop
endfacet
facet normal -0.84 0 0.54
outer loop
vertex -2.47 -0.83 1.22
vertex -2.39 -0.81 1.34
vertex -2.39 0.81 1.34
endloop
endfacet
facet normal 0.64 0.77 -0.01
outer loop
vertex 2.42 0.98 0.42
vertex 2.39 1.01 0.67
vertex 2.48 0.93 0.86
endloop
endfacet
facet normal -0.28 -0.58 -0.76
outer loop
vertex -2.39 -0.79 0.25
vertex -2.47 -0.98 0.42
vertex -2.47 -0.78 0.27
endloop
endfacet
facet normal 0.86 -0.23 -0.45
outer loop
vertex 1.33 0.75 0.55
vertex 1.24 0.75 0.37
vertex 1.28 0.76 0.44
endloop
endfacet
facet normal -0.7 0 -0.72
outer loop
vertex -2.47 0.78 0.27
vertex -2.47 -0.78 0.27
vertex -2.49 -0.76 0.3
endloop
endfacet
facet normal 0.84 0.01 0.54
outer loop
vertex 1.27 -0.96 0.25
vertex 1.36 -0.97 0.12
vertex 1.32 -0.96 0.18
endloop
endfacet
facet normal 0.01 0.45 0.89
outer loop
vertex 1.14 -0.82 1.31
vertex -2.39 -0.81 1.34
vertex 1.21 -0.87 1.33
endloop
endfacet
facet normal 0.01 0.39 0.92
outer loop
vertex -2.39 -0.81 1.34
vertex -2.39 -0.86 1.36
vertex 1.21 -0.87 1.33
endloop
endfacet
facet normal -0.95 0.17 -0.28
outer loop
vertex -2.49 0.76 0.3
vertex -2.51 0.87 0.42
vertex -2.5 0.95 0.42
endloop
endfacet
facet normal -0.04 -0.99 -0.12
outer loop
vertex 1.68 -0.98 0.6
vertex 1.55 -0.98 0.65
vertex 1.64 -0.97 0.57
endloop
endfacet
facet normal 0.01 0 1
outer loop
vertex 1.14 0.82 1.3
vertex -2.39 0.81 1.34
vertex -2.39 -0.81 1.34
endloop
endfacet
facet normal -0.98 -0.01 -0.2
outer loop
vertex -1.28 -0.76 0.44
vertex -1.25 -0.76 0.34
vertex -1.27 -0.96 0.43
endloop
endfacet
facet normal 0 -0.98 0.19
outer loop
vertex 0.98 -0.86 1.75
vertex -2.06 -0.86 1.82
vertex -2.06 -0.95 1.29
endloop
endfacet
facet normal 1 0 0.04
outer loop
vertex 1.15 0.8 0.24
vertex 1.14 1 0.42
vertex 1.15 -0.8 0.24
endloop
endfacet
facet normal -0.99 -0.03 -0.11
outer loop
vertex -1.27 0.96 0.43
vertex -1.26 0.96 0.29
vertex -1.26 0.76 0.34
endloop
endfacet
facet normal -0.99 -0.04 -0.16
outer loop
vertex 1.72 -0.76 0.44
vertex 1.74 -0.76 0.31
vertex 1.74 -0.96 0.39
endloop
endfacet
facet normal -0.24 0 -0.97
outer loop
vertex 1.66 -1.02 0.67
vertex 1.53 -1.01 0.7
vertex 1.55 1.01 0.7
endloop
endfacet
facet normal 0.6 0 -0.8
outer loop
vertex 1.37 -1.02 0.69
vertex 1.22 -1.01 0.57
vertex 1.21 1.01 0.57
endloop
endfacet
facet normal -0.85 0.01 0.53
outer loop
vertex -1.32 0.96 0.18
vertex -1.32 0.76 0.17
vertex -1.27 0.76 0.26
endloop
endfacet
facet normal -0.34 -0.02 0.94
outer loop
vertex -1.47 -0.76 0.09
vertex -1.47 -0.97 0.09
vertex -1.42 -0.96 0.11
endloop
endfacet
facet normal -0.89 0.02 0.45
outer loop
vertex 1.69 -0.96 0.18
vertex 1.74 -0.96 0.29
vertex 1.69 -0.76 0.19
endloop
endfacet
facet normal -0.54 0 -0.84
outer loop
vertex -1.22 -1.01 0.59
vertex -1.38 -1.02 0.69
vertex -1.37 1.02 0.69
endloop
endfacet
facet normal -0.38 0 -0.93
outer loop
vertex 1.66 -1.02 0.67
vertex 1.55 1.01 0.7
vertex 1.71 1.01 0.64
endloop
endfacet
facet normal 0.24 -0.69 -0.69
outer loop
vertex 2.5 -0.65 0.39
vertex 2.5 -0.64 0.39
vertex 2.51 -0.64 0.39
endloop
endfacet
facet normal -0.7 0.71 -0.06
outer loop
vertex -2.5 0.95 0.42
vertex -2.49 0.98 0.69
vertex -2.47 0.98 0.42
endloop
endfacet
facet normal 1 0 0
outer loop
vertex 2.51 -0.64 0.55
vertex 2.51 -0.64 0.39
vertex 2.51 0.64 0.39
endloop
endfacet
facet normal 0.5 -0.87 0
outer loop
vertex 2.51 -0.64 0.55
vertex 2.5 -0.65 0.54
vertex 2.5 -0.65 0.4
endloop
endfacet
facet normal 0.51 0 -0.86
outer loop
vertex 2.51 0.64 0.39
vertex 2.51 -0.64 0.39
vertex 2.5 -0.63 0.38
endloop
endfacet
facet normal -0.51 0.86 0
outer loop
vertex 2.5 0.65 0.4
vertex 2.49 0.64 0.39
vertex 2.49 0.64 0.55
endloop
endfacet
facet normal 0.52 0.86 0
outer loop
vertex 2.51 0.64 0.55
vertex 2.51 0.64 0.39
vertex 2.5 0.65 0.4
endloop
endfacet
facet normal -0.28 -0.96 -0.02
outer loop
vertex -2.39 -1.01 0.69
vertex -2.49 -0.98 0.69
vertex -2.47 -0.98 0.42
endloop
endfacet
facet normal -0.03 -1 0.07
outer loop
vertex 1.24 -0.98 0.5
vertex 1.55 -0.98 0.65
vertex 1.41 -0.97 0.65
endloop
endfacet
facet normal -0.15 -0.97 0.2
outer loop
vertex 1.41 -0.97 0.65
vertex 1.25 -0.97 0.57
vertex 1.24 -0.98 0.5
endloop
endfacet
facet normal -0.36 -0.9 0.23
outer loop
vertex 1.25 -0.97 0.57
vertex 1.19 -0.97 0.46
vertex 1.24 -0.98 0.5
endloop
endfacet
facet normal -0.99 0 0.17
outer loop
vertex -1.82 0.96 0.46
vertex -1.84 0.96 0.33
vertex -1.84 0.76 0.34
endloop
endfacet
facet normal -0.9 0 -0.44
outer loop
vertex -1.22 -1.01 0.59
vertex -1.22 1.01 0.58
vertex -1.14 1 0.42
endloop
endfacet
facet normal -0.73 0.67 0.12
outer loop
vertex -1.84 0.96 0.33
vertex -1.82 0.96 0.46
vertex -1.81 0.98 0.41
endloop
endfacet
facet normal 0.98 0 -0.17
outer loop
vertex 1.26 -0.8 1.14
vertex 1.26 -0.8 1.13
vertex 1.26 0.8 1.13
endloop
endfacet
facet normal -0.53 0.79 0.31
outer loop
vertex -1.24 0.97 0.29
vertex -1.33 0.97 0.13
vertex -1.26 0.96 0.29
endloop
endfacet
facet normal 0.98 0 0.18
outer loop
vertex -1.18 -0.96 0.46
vertex -1.16 -0.96 0.34
vertex -1.18 -0.75 0.43
endloop
endfacet
facet normal 0.07 0.99 -0.08
outer loop
vertex 1.7 0.97 0.08
vertex 1.56 0.98 0.03
vertex 1.79 0.98 0.21
endloop
endfacet
facet normal 0.02 0.55 0.84
outer loop
vertex -2.06 0.79 1.86
vertex 0.98 0.79 1.79
vertex -2.06 0.86 1.82
endloop
endfacet
facet normal 0 1 -0.04
outer loop
vertex -1.22 1.01 0.58
vertex -1.37 1.02 0.69
vertex 1.21 1.01 0.57
endloop
endfacet
facet normal 0 1 -0.04
outer loop
vertex -1.37 1.02 0.69
vertex 1.36 1.02 0.68
vertex 1.21 1.01 0.57
endloop
endfacet
facet normal 0 1 -0.05
outer loop
vertex -1.14 1 0.42
vertex -1.22 1.01 0.58
vertex 1.21 1.01 0.57
endloop
endfacet
facet normal -0.52 0 0.85
outer loop
vertex 2.49 0.64 0.55
vertex 2.49 -0.64 0.55
vertex 2.5 -0.63 0.55
endloop
endfacet
facet normal 0 0.98 0.18
outer loop
vertex 0.98 0.86 1.75
vertex 1.19 0.94 1.29
vertex -2.06 0.96 1.29
endloop
endfacet
facet normal -0.02 -1 -0.05
outer loop
vertex -2.39 -1.01 0.69
vertex -2.39 -0.99 0.42
vertex -1.86 -1 0.42
endloop
endfacet
facet normal -0.02 -1 -0.05
outer loop
vertex -2.39 -1.01 0.69
vertex -1.86 -1 0.42
vertex -1.8 -1.01 0.55
endloop
endfacet
facet normal 0.12 0 -0.99
outer loop
vertex 1.53 -1.01 0.7
vertex 1.37 -1.02 0.69
vertex 1.55 1.01 0.7
endloop
endfacet
facet normal -0.4 -0.03 -0.91
outer loop
vertex 1.54 -0.76 0.58
vertex 1.65 -0.76 0.53
vertex 1.63 -0.96 0.55
endloop
endfacet
facet normal -0.99 0 -0.12
outer loop
vertex -2.51 -0.87 0.43
vertex -2.51 0.87 0.42
vertex -2.49 -0.76 0.3
endloop
endfacet
facet normal -0.99 0 -0.13
outer loop
vertex -2.49 0.76 0.3
vertex -2.49 -0.76 0.3
vertex -2.51 0.87 0.42
endloop
endfacet
facet normal 0.11 -0.99 -0.05
outer loop
vertex -1.18 0.74 0.34
vertex -1.3 0.74 0.09
vertex -1.2 0.75 0.21
endloop
endfacet
facet normal -0.01 1 0.09
outer loop
vertex -1.65 1.02 0.67
vertex -2.39 1.01 0.69
vertex -2.39 0.95 1.35
endloop
endfacet
facet normal 0 0.99 0.1
outer loop
vertex -2.39 0.95 1.35
vertex 2.2 0.96 1.27
vertex -1.37 1.02 0.69
endloop
endfacet
facet normal 0.05 0.99 0.09
outer loop
vertex 2.2 0.96 1.27
vertex 2.32 0.97 1.16
vertex 2.39 1.01 0.67
endloop
endfacet
facet normal 0.01 1 0.08
outer loop
vertex 2.39 1.01 0.67
vertex 1.55 1.01 0.7
vertex 2.2 0.96 1.27
endloop
endfacet
facet normal -0.01 1 0.09
outer loop
vertex -1.53 1.01 0.7
vertex -1.65 1.02 0.67
vertex -2.39 0.95 1.35
endloop
endfacet
facet normal 0 0.99 0.11
outer loop
vertex -1.37 1.02 0.69
vertex -1.53 1.01 0.7
vertex -2.39 0.95 1.35
endloop
endfacet
facet normal -0.01 1 0.1
outer loop
vertex 2.2 0.96 1.27
vertex 1.55 1.01 0.7
vertex 1.36 1.02 0.68
endloop
endfacet
facet normal 0 1 0.09
outer loop
vertex 1.36 1.02 0.68
vertex -1.37 1.02 0.69
vertex 2.2 0.96 1.27
endloop
endfacet
facet normal -0.79 -0.35 0.51
outer loop
vertex -2.06 -0.86 1.82
vertex -2.06 -0.79 1.86
vertex -2.2 -0.75 1.67
endloop
endfacet
facet normal -0.76 -0.39 0.52
outer loop
vertex -2.2 -0.75 1.67
vertex -2.43 -0.8 1.3
vertex -2.21 -0.81 1.61
endloop
endfacet
facet normal -0.79 -0.37 0.5
outer loop
vertex -2.2 -0.75 1.67
vertex -2.21 -0.81 1.61
vertex -2.06 -0.86 1.82
endloop
endfacet
facet normal -0.52 -0.86 0
outer loop
vertex 2.49 -0.64 0.55
vertex 2.49 -0.64 0.39
vertex 2.5 -0.65 0.4
endloop
endfacet
facet normal 0.02 -0.56 0.83
outer loop
vertex -2.06 -0.79 1.86
vertex -2.06 -0.86 1.82
vertex 0.98 -0.79 1.79
endloop
endfacet
facet normal 0.82 -0.57 0.03
outer loop
vertex 1.18 0.97 1.45
vertex 1.18 0.96 1.36
vertex 1.19 0.98 1.35
endloop
endfacet
facet normal -0.02 -0.81 -0.59
outer loop
vertex 1.18 0.96 1.36
vertex 1.01 0.97 1.36
vertex 1.02 0.98 1.35
endloop
endfacet
facet normal 0.02 0.8 -0.6
outer loop
vertex 1.02 1.11 1.36
vertex 1.19 1.1 1.36
vertex 1.18 1.09 1.35
endloop
endfacet
facet normal -0.72 -0.69 0.07
outer loop
vertex 1.01 0.97 1.36
vertex 1.02 0.96 1.44
vertex 1.01 0.98 1.45
endloop
endfacet
facet normal -0.76 -0.65 -0.01
outer loop
vertex 1.02 -1.1 1.35
vertex 1.02 -1.11 1.44
vertex 1.01 -1.09 1.45
endloop
endfacet
facet normal -0.02 0.8 0.6
outer loop
vertex 1.18 1.11 1.44
vertex 1.01 1.1 1.44
vertex 1.02 1.09 1.45
endloop
endfacet
facet normal 0.02 -0.04 -1
outer loop
vertex 1.18 1.09 1.35
vertex 1.19 0.98 1.35
vertex 1.02 0.98 1.35
endloop
endfacet
facet normal 0.03 1 -0.05
outer loop
vertex 1.18 1.11 1.44
vertex 1.19 1.1 1.36
vertex 1.02 1.11 1.36
endloop
endfacet
facet normal 1 0 -0.04
outer loop
vertex 1.2 0.98 1.44
vertex 1.19 0.98 1.35
vertex 1.19 1.1 1.36
endloop
endfacet
facet normal -1 0.01 -0.01
outer loop
vertex 1.01 1.1 1.44
vertex 1.01 1.09 1.35
vertex 1.01 0.97 1.36
endloop
endfacet
facet normal 0.03 0 1
outer loop
vertex 1.18 0.97 1.45
vertex 1.19 1.09 1.45
vertex 1.02 1.09 1.45
endloop
endfacet
facet normal -0.02 -1 -0.07
outer loop
vertex 1.02 0.96 1.44
vertex 1.01 0.97 1.36
vertex 1.18 0.96 1.36
endloop
endfacet
facet normal 0.79 0.61 0.06
outer loop
vertex 1.19 1.1 1.36
vertex 1.18 1.11 1.44
vertex 1.19 1.09 1.45
endloop
endfacet
facet normal -0.63 0.78 0
outer loop
vertex 1.01 -0.98 1.35
vertex 1 -0.98 1.44
vertex 1.02 -0.97 1.45
endloop
endfacet
facet normal 0.77 -0.64 0.02
outer loop
vertex 1.18 -1.1 1.45
vertex 1.18 -1.11 1.36
vertex 1.19 -1.09 1.35
endloop
endfacet
facet normal 0.72 0.69 0.07
outer loop
vertex 1.19 -0.97 1.36
vertex 1.18 -0.96 1.44
vertex 1.19 -0.98 1.45
endloop
endfacet
facet normal 0.01 -0.03 -1
outer loop
vertex 1.18 -0.98 1.35
vertex 1.19 -1.09 1.35
vertex 1.02 -1.1 1.35
endloop
endfacet
facet normal 0.02 0.81 -0.59
outer loop
vertex 1.02 -0.97 1.36
vertex 1.19 -0.97 1.36
vertex 1.18 -0.98 1.35
endloop
endfacet
facet normal 0.02 1 -0.07
outer loop
vertex 1.18 -0.96 1.44
vertex 1.19 -0.97 1.36
vertex 1.02 -0.97 1.36
endloop
endfacet
facet normal 0.17 0 0.98
outer loop
vertex 2.24 0.8 0.96
vertex 1.26 0.8 1.13
vertex 1.26 -0.8 1.13
endloop
endfacet
facet normal -1 0.03 -0.04
outer loop
vertex 1 -0.98 1.44
vertex 1.01 -0.98 1.35
vertex 1 -1.09 1.36
endloop
endfacet
facet normal -0.02 -1 -0.06
outer loop
vertex 1.02 -1.11 1.44
vertex 1.02 -1.1 1.35
vertex 1.18 -1.11 1.36
endloop
endfacet
facet normal 0.01 0 1
outer loop
vertex 1.18 -1.1 1.45
vertex 1.19 -0.98 1.45
vertex 1.02 -0.97 1.45
endloop
endfacet
facet normal -0.18 0 -0.98
outer loop
vertex 2.24 0.8 0.96
vertex 2.24 -0.8 0.96
vertex 1.26 -0.8 1.14
endloop
endfacet
facet normal 0.18 0 0.98
outer loop
vertex 1.24 0.81 1.13
vertex 1.24 -0.81 1.13
vertex 2.25 -0.81 0.95
endloop
endfacet
facet normal 0 1 0
outer loop
vertex -1.47 -0.8 1.89
vertex 1.27 -0.8 1.8
vertex 1.27 -0.8 1.79
endloop
endfacet
facet normal -0.01 1 -0.04
outer loop
vertex 1.24 -0.81 1.13
vertex 2.25 -0.81 0.96
vertex 2.25 -0.81 0.95
endloop
endfacet
facet normal -0.03 0 -1
outer loop
vertex -1.47 0.8 1.89
vertex 1.27 0.8 1.8
vertex 1.27 -0.8 1.8
endloop
endfacet
facet normal 0.04 0 1
outer loop
vertex -1.47 0.8 1.89
vertex -1.47 -0.8 1.89
vertex 1.27 -0.8 1.79
endloop
endfacet
facet normal 0 1 -0.08
outer loop
vertex 2 -1.03 0.69
vertex -2 -1.02 0.69
vertex -2 -0.97 1.31
endloop
endfacet
facet normal 0 1 -0.02
outer loop
vertex -1.49 -0.81 1.89
vertex 1.28 -0.81 1.8
vertex 1.29 -0.81 1.79
endloop
endfacet
facet normal -0.03 0 -1
outer loop
vertex -1.49 0.81 1.89
vertex 1.29 0.81 1.79
vertex 1.28 -0.81 1.8
endloop
endfacet
facet normal 0 1 0.08
outer loop
vertex -2 0.97 1.31
vertex 2 0.97 1.31
vertex 2 1.02 0.69
endloop
endfacet
facet normal 0 1 0.09
outer loop
vertex -2.01 1.02 0.68
vertex -2.01 0.96 1.32
vertex 2.01 0.96 1.32
endloop
endfacet
facet normal 0.04 0 1
outer loop
vertex -1.49 0.81 1.89
vertex -1.49 -0.81 1.89
vertex 1.29 -0.81 1.79
endloop
endfacet
facet normal 0 -0.66 -0.75
outer loop
vertex -1.15 -0.8 0.24
vertex 1.15 -0.8 0.24
vertex 1.14 -1 0.42
endloop
endfacet
facet normal 0 -1 0.08
outer loop
vertex 2 -0.97 1.31
vertex -2 -0.97 1.31
vertex -2 -1.02 0.69
endloop
endfacet
facet normal 0 -1 -0.08
outer loop
vertex -2 1.03 0.69
vertex 2 1.02 0.69
vertex 2 0.97 1.31
endloop
endfacet
facet normal 0 -1 -0.08
outer loop
vertex -2.01 1.02 0.68
vertex 2.01 1.02 0.68
vertex 2.01 0.97 1.32
endloop
endfacet
facet normal 0 0.08 -1
outer loop
vertex -2.01 0.96 1.32
vertex 2.01 0.97 1.32
vertex 2.01 0.96 1.32
endloop
endfacet
facet normal 0.25 -0.56 0.79
outer loop
vertex 1.36 -0.97 0.12
vertex 1.5 -0.97 0.07
vertex 1.41 -0.96 0.11
endloop
endfacet
facet normal 0 -0.07 -1
outer loop
vertex 2.01 -0.96 1.32
vertex -2.01 -0.97 1.32
vertex -2.01 -0.96 1.32
endloop
endfacet
facet normal 0.87 0 -0.49
outer loop
vertex -2.23 -0.6 1.67
vertex -2.47 -0.6 1.23
vertex -2.47 0.6 1.23
endloop
endfacet
facet normal 0 1 -0.08
outer loop
vertex 2.01 -1.02 0.68
vertex -2.01 -1.02 0.68
vertex -2.01 -0.97 1.32
endloop
endfacet
facet normal 0 1 0
outer loop
vertex -2.47 -0.6 1.23
vertex -2.23 -0.6 1.67
vertex -2.22 -0.6 1.66
endloop
endfacet
facet normal -0.87 0 0.5
outer loop
vertex -2.22 -0.6 1.66
vertex -2.22 0.6 1.66
vertex -2.47 0.6 1.23
endloop
endfacet
facet normal 0 -1 0.09
outer loop
vertex 2.01 -1.02 0.68
vertex 2.01 -0.96 1.32
vertex -2.01 -0.96 1.32
endloop
endfacet
facet normal -0.87 0 0.49
outer loop
vertex -2.21 -0.61 1.67
vertex -2.21 0.61 1.67
vertex -2.47 0.61 1.22
endloop
endfacet
facet normal 0.02 -0.84 0.54
outer loop
vertex 0.95 0.87 1.8
vertex 0.94 0.87 1.79
vertex 1.34 0.87 1.78
endloop
endfacet
facet normal 0.87 0 -0.5
outer loop
vertex -2.21 -0.61 1.67
vertex -2.47 -0.61 1.22
vertex -2.48 0.61 1.22
endloop
endfacet
facet normal 0.03 0 1
outer loop
vertex 0.95 0.85 1.78
vertex 0.95 -0.85 1.79
vertex 1.31 -0.85 1.77
endloop
endfacet
facet normal 0.18 0.03 0.98
outer loop
vertex -1.38 0.96 0.66
vertex -1.51 0.96 0.68
vertex -1.47 0.76 0.68
endloop
endfacet
facet normal -0.81 0 0.58
outer loop
vertex 1.34 0.87 1.78
vertex 1.33 -0.87 1.78
vertex 1.34 -0.86 1.79
endloop
endfacet
facet normal -0.64 0.6 -0.49
outer loop
vertex -1.78 0.97 0.17
vertex -1.74 0.96 0.1
vertex -1.79 0.96 0.17
endloop
endfacet
facet normal 0.86 0 0.51
outer loop
vertex 0.94 -0.87 1.79
vertex 0.94 0.87 1.79
vertex 0.94 0.86 1.8
endloop
endfacet
facet normal 0 -1 0
outer loop
vertex 0.95 0.85 1.79
vertex 0.95 0.85 1.78
vertex 1.31 0.85 1.77
endloop
endfacet
facet normal -0.04 0 -1
outer loop
vertex 0.94 0.87 1.81
vertex 1.34 0.87 1.79
vertex 1.34 -0.87 1.79
endloop
endfacet
facet normal -0.05 0 -1
outer loop
vertex 0.95 0.85 1.79
vertex 1.31 0.85 1.77
vertex 1.31 -0.85 1.77
endloop
endfacet
facet normal 0.04 0 1
outer loop
vertex 0.94 0.87 1.79
vertex 0.94 -0.87 1.79
vertex 1.33 -0.87 1.78
endloop
endfacet
facet normal 0.82 0 -0.57
outer loop
vertex 0.94 0.87 1.81
vertex 0.94 -0.87 1.81
vertex 0.94 -0.86 1.8
endloop
endfacet
facet normal 0.01 -0.99 0.11
outer loop
vertex -2.2 -0.81 1.86
vertex -2.04 -0.81 1.85
vertex -2.04 -0.81 1.87
endloop
endfacet
facet normal -0.01 -0.99 -0.11
outer loop
vertex -2.04 -0.81 1.85
vertex -2.2 -0.81 1.86
vertex -2.2 -0.81 1.85
endloop
endfacet
facet normal -0.01 0.99 0.11
outer loop
vertex -2.04 0.81 1.86
vertex -2.2 0.81 1.85
vertex -2.2 0.81 1.87
endloop
endfacet
facet normal 0.01 0.99 -0.11
outer loop
vertex -2.2 0.81 1.85
vertex -2.04 0.81 1.86
vertex -2.04 0.81 1.85
endloop
endfacet
facet normal 0.01 0 1
outer loop
vertex -2.04 -0.81 1.87
vertex -2.04 0.81 1.86
vertex -2.2 0.81 1.87
endloop
endfacet
facet normal -0.05 -1 -0.05
outer loop
vertex 1.43 0.74 0.03
vertex 1.19 0.74 0.29
vertex 1.3 0.75 0.08
endloop
endfacet
facet normal -0.23 -0.96 -0.14
outer loop
vertex 1.19 0.75 0.21
vertex 1.3 0.75 0.08
vertex 1.19 0.74 0.29
endloop
endfacet
facet normal -0.23 -0.97 -0.03
outer loop
vertex -1.77 -0.98 0.17
vertex -1.8 -0.98 0.44
vertex -1.83 -0.97 0.33
endloop
endfacet
facet normal -0.79 0.01 -0.62
outer loop
vertex -1.79 0.96 0.17
vertex -1.74 0.96 0.1
vertex -1.76 0.76 0.13
endloop
endfacet
facet normal -0.98 0 0.18
outer loop
vertex -1.82 -0.76 0.46
vertex -1.84 -0.76 0.34
vertex -1.82 -0.96 0.45
endloop
endfacet
facet normal -0.99 -0.03 0.12
outer loop
vertex -1.84 -0.76 0.34
vertex -1.83 -0.97 0.33
vertex -1.82 -0.96 0.45
endloop
endfacet
facet normal -0.63 -0.78 0.04
outer loop
vertex 1.17 0.76 0.3
vertex 1.19 0.74 0.29
vertex 1.17 0.76 0.43
endloop
endfacet
facet normal -0.56 -0.83 0.05
outer loop
vertex 1.19 0.74 0.29
vertex 1.2 0.74 0.45
vertex 1.17 0.76 0.43
endloop
endfacet
facet normal -0.65 -0.68 0.35
outer loop
vertex 1.2 0.74 0.45
vertex 1.25 0.75 0.57
vertex 1.17 0.76 0.43
endloop
endfacet
facet normal -0.94 0.01 -0.34
outer loop
vertex -1.83 0.97 0.27
vertex -1.79 0.96 0.17
vertex -1.82 0.76 0.22
endloop
endfacet
facet normal 0.59 0 0.81
outer loop
vertex -1.68 0.96 0.17
vertex -1.68 0.76 0.17
vertex -1.6 0.76 0.11
endloop
endfacet
facet normal -0.06 -1 -0.06
outer loop
vertex 1.77 0.74 0.5
vertex 1.68 0.74 0.6
vertex 1.75 0.75 0.44
endloop
endfacet
facet normal -0.17 -0.98 -0.11
outer loop
vertex 1.68 0.74 0.6
vertex 1.63 0.76 0.55
vertex 1.75 0.75 0.44
endloop
endfacet
facet normal -0.01 -1 0.08
outer loop
vertex 1.36 -0.97 0.12
vertex 1.27 -0.96 0.25
vertex 1.37 -0.98 0.05
endloop
endfacet
facet normal 0.86 -0.03 0.51
outer loop
vertex -1.24 -0.96 0.56
vertex -1.18 -0.96 0.46
vertex -1.22 -0.76 0.53
endloop
endfacet
facet normal -0.67 0.68 -0.3
outer loop
vertex -1.79 0.96 0.17
vertex -1.83 0.97 0.27
vertex -1.78 0.97 0.17
endloop
endfacet
facet normal 0.19 -0.04 -0.98
outer loop
vertex -1.61 -0.76 0.56
vertex -1.48 -0.76 0.59
vertex -1.54 -0.96 0.58
endloop
endfacet
facet normal 0.72 -0.03 -0.69
outer loop
vertex -1.72 -0.76 0.45
vertex -1.61 -0.76 0.56
vertex -1.63 -0.96 0.55
endloop
endfacet
facet normal 0.02 -0.99 -0.11
outer loop
vertex -1.47 -0.98 0.66
vertex -1.61 -0.98 0.63
vertex -1.48 -0.97 0.6
endloop
endfacet
facet normal 0.01 -0.99 -0.16
outer loop
vertex -1.48 -0.97 0.6
vertex -1.61 -0.98 0.63
vertex -1.63 -0.96 0.55
endloop
endfacet
facet normal 0.87 0 -0.49
outer loop
vertex 1.82 0.76 0.22
vertex 1.77 0.76 0.13
vertex 1.81 0.96 0.21
endloop
endfacet
facet normal -0.47 0.68 0.56
outer loop
vertex -1.76 -0.76 0.56
vertex -1.67 -0.76 0.63
vertex -1.68 -0.74 0.6
endloop
endfacet
facet normal -0.26 -0.87 0.42
outer loop
vertex 1.25 0.75 0.57
vertex 1.42 0.74 0.65
vertex 1.35 0.76 0.64
endloop
endfacet
facet normal 0.37 0 0.93
outer loop
vertex 1.58 0.76 0.67
vertex 1.67 0.76 0.63
vertex 1.66 0.96 0.64
endloop
endfacet
facet normal 0.14 0.55 -0.82
outer loop
vertex -1.64 -0.75 0.57
vertex -1.48 -0.76 0.59
vertex -1.61 -0.76 0.56
endloop
endfacet
facet normal -0.03 1 0.09
outer loop
vertex -1.74 0.98 0.55
vertex -1.59 0.97 0.65
vertex -1.44 0.98 0.65
endloop
endfacet
facet normal -0.11 -0.99 0.01
outer loop
vertex -1.24 -0.97 0.4
vertex -1.26 -0.97 0.24
vertex -1.21 -0.98 0.21
endloop
endfacet
facet normal 0 0.03 1
outer loop
vertex 1.44 0.96 0.67
vertex 1.47 0.76 0.68
vertex 1.56 0.96 0.67
endloop
endfacet
facet normal 0.08 -0.01 1
outer loop
vertex 1.47 0.76 0.68
vertex 1.58 0.76 0.67
vertex 1.56 0.96 0.67
endloop
endfacet
facet normal 0.21 -0.98 0.02
outer loop
vertex -1.8 -0.98 0.44
vertex -1.77 -0.98 0.17
vertex -1.76 -0.97 0.37
endloop
endfacet
facet normal 0.3 -0.95 0.02
outer loop
vertex -1.77 -0.98 0.17
vertex -1.73 -0.96 0.24
vertex -1.76 -0.97 0.37
endloop
endfacet
facet normal 0.15 -0.99 -0.01
outer loop
vertex -1.76 -0.97 0.37
vertex -1.7 -0.96 0.48
vertex -1.8 -0.98 0.44
endloop
endfacet
facet normal 0.6 -0.53 0.6
outer loop
vertex 1.27 0.75 0.22
vertex 1.38 0.75 0.1
vertex 1.32 0.76 0.18
endloop
endfacet
facet normal 0.41 0 -0.91
outer loop
vertex -1.32 -0.95 0.05
vertex -1.4 -0.96 0.01
vertex -1.32 -0.76 0.05
endloop
endfacet
facet normal -0.12 0.99 -0.04
outer loop
vertex -1.73 -0.74 0.12
vertex -1.81 -0.75 0.26
vertex -1.81 -0.74 0.37
endloop
endfacet
facet normal -0.82 -0.02 0.57
outer loop
vertex -1.27 -0.76 0.24
vertex -1.32 -0.76 0.18
vertex -1.31 -0.96 0.19
endloop
endfacet
facet normal 0.94 0.16 0.29
outer loop
vertex 1.78 0.96 0.53
vertex 1.84 0.96 0.35
vertex 1.81 0.97 0.45
endloop
endfacet
facet normal -0.69 0 -0.73
outer loop
vertex 1.24 0.96 0.13
vertex 1.32 0.9 0.05
vertex 1.24 0.76 0.12
endloop
endfacet
facet normal -0.85 -0.03 0.53
outer loop
vertex 1.24 -0.76 0.56
vertex 1.2 -0.76 0.49
vertex 1.19 -0.97 0.46
endloop
endfacet
facet normal 0.51 -0.03 -0.86
outer loop
vertex -1.68 0.96 0.51
vertex -1.56 0.96 0.58
vertex -1.61 0.76 0.56
endloop
endfacet
facet normal 0.15 0.88 -0.45
outer loop
vertex -1.74 0.98 0.55
vertex -1.44 0.98 0.65
vertex -1.56 0.97 0.6
endloop
endfacet
facet normal 0.03 0.98 -0.2
outer loop
vertex -1.44 0.98 0.65
vertex -1.43 0.96 0.57
vertex -1.56 0.97 0.6
endloop
endfacet
facet normal 0.09 0.98 -0.2
outer loop
vertex -1.56 0.97 0.6
vertex -1.68 0.96 0.51
vertex -1.74 0.98 0.55
endloop
endfacet
facet normal -0.37 -0.01 -0.93
outer loop
vertex -1.68 0.76 0.05
vertex -1.67 0.96 0.04
vertex -1.57 0.76 0.01
endloop
endfacet
facet normal 0.46 -0.7 0.55
outer loop
vertex 1.76 0.76 0.56
vertex 1.67 0.76 0.63
vertex 1.68 0.74 0.6
endloop
endfacet
facet normal 0.25 0.01 0.97
outer loop
vertex -1.46 -0.96 0.68
vertex -1.37 -0.96 0.65
vertex -1.43 -0.75 0.67
endloop
endfacet
facet normal 0.32 0.03 0.95
outer loop
vertex -1.37 -0.96 0.65
vertex -1.34 -0.76 0.64
vertex -1.43 -0.75 0.67
endloop
endfacet
facet normal -0.95 -0.04 -0.31
outer loop
vertex 1.19 0.75 0.21
vertex 1.17 0.76 0.3
vertex 1.18 0.96 0.22
endloop
endfacet
facet normal 0.06 0.98 0.18
outer loop
vertex -1.47 -0.74 0.02
vertex -1.61 -0.75 0.1
vertex -1.47 -0.76 0.09
endloop
endfacet
facet normal -0.39 0.74 0.55
outer loop
vertex -1.22 0.98 0.2
vertex -1.47 0.98 0.02
vertex -1.33 0.97 0.13
endloop
endfacet
facet normal -0.03 0.99 0.1
outer loop
vertex -1.47 0.98 0.02
vertex -1.5 0.97 0.07
vertex -1.33 0.97 0.13
endloop
endfacet
facet normal -0.1 -0.83 -0.55
outer loop
vertex -1.52 0.75 0.6
vertex -1.52 0.76 0.58
vertex -1.42 0.76 0.57
endloop
endfacet
facet normal -0.1 0.99 0.06
outer loop
vertex -1.81 -0.74 0.37
vertex -1.78 -0.75 0.51
vertex -1.68 -0.74 0.6
endloop
endfacet
facet normal 0.86 -0.01 -0.51
outer loop
vertex 1.26 -0.76 0.41
vertex 1.32 -0.76 0.51
vertex 1.32 -0.96 0.51
endloop
endfacet
facet normal 0.52 -0.84 0.18
outer loop
vertex 1.77 0.74 0.5
vertex 1.83 0.75 0.36
vertex 1.82 0.76 0.46
endloop
endfacet
facet normal -0.35 -0.02 -0.93
outer loop
vertex 1.33 0.76 0.05
vertex 1.32 0.9 0.05
vertex 1.44 0.76 0.01
endloop
endfacet
facet normal 0.3 0.05 -0.95
outer loop
vertex 1.55 0.96 0
vertex 1.66 0.96 0.04
vertex 1.6 0.8 0.01
endloop
endfacet
facet normal 0.6 -0.79 0.11
outer loop
vertex -1.73 -0.96 0.24
vertex -1.74 -0.96 0.37
vertex -1.76 -0.97 0.37
endloop
endfacet
facet normal -0.02 -0.01 -1
outer loop
vertex 1.44 0.96 0.01
vertex 1.55 0.96 0
vertex 1.55 0.75 0.01
endloop
endfacet
facet normal 0.01 -0.99 -0.1
outer loop
vertex 1.66 -0.98 0.06
vertex 1.37 -0.98 0.05
vertex 1.54 -0.97 0.02
endloop
endfacet
facet normal -0.32 0.65 -0.69
outer loop
vertex 1.52 0.97 0.6
vertex 1.65 0.96 0.53
vertex 1.54 0.96 0.58
endloop
endfacet
facet normal -0.87 0.06 0.49
outer loop
vertex -2.47 0.94 1.21
vertex -2.47 0.84 1.23
vertex -2.39 0.95 1.35
endloop
endfacet
facet normal -0.99 -0.04 0.11
outer loop
vertex 1.74 0.76 0.3
vertex 1.74 0.96 0.37
vertex 1.73 0.96 0.25
endloop
endfacet
facet normal -0.56 0.83 -0.04
outer loop
vertex -1.81 -0.74 0.37
vertex -1.81 -0.75 0.26
vertex -1.84 -0.76 0.34
endloop
endfacet
facet normal 0.99 0.03 0.14
outer loop
vertex -1.75 -0.76 0.34
vertex -1.74 -0.96 0.37
vertex -1.73 -0.96 0.24
endloop
endfacet
facet normal -0.67 0.02 -0.74
outer loop
vertex 1.23 -0.76 0.13
vertex 1.32 -0.76 0.05
vertex 1.26 -0.96 0.1
endloop
endfacet
facet normal 0.45 -0.01 -0.89
outer loop
vertex 1.6 0.8 0.01
vertex 1.66 0.96 0.04
vertex 1.69 0.76 0.06
endloop
endfacet
facet normal -0.22 -0.95 0.21
outer loop
vertex -1.27 -0.76 0.24
vertex -1.39 -0.76 0.12
vertex -1.32 -0.76 0.18
endloop
endfacet
facet normal -0.69 -0.54 0.48
outer loop
vertex 1.65 0.74 0.11
vertex 1.76 0.75 0.26
vertex 1.69 0.76 0.18
endloop
endfacet
facet normal 0.53 0.49 -0.69
outer loop
vertex 1.74 0.96 0.1
vertex 1.66 0.96 0.04
vertex 1.7 0.97 0.08
endloop
endfacet
facet normal -0.59 -0.78 -0.23
outer loop
vertex 1.81 -0.98 0.27
vertex 1.68 -0.98 0.6
vertex 1.72 -0.96 0.46
endloop
endfacet
facet normal 0.86 -0.02 -0.51
outer loop
vertex -1.18 -0.96 0.22
vertex -1.24 -0.96 0.12
vertex -1.21 -0.76 0.17
endloop
endfacet
facet normal -0.32 -0.02 -0.95
outer loop
vertex -1.48 -0.76 0.59
vertex -1.36 -0.76 0.55
vertex -1.43 -0.96 0.57
endloop
endfacet
facet normal 0.59 -0.73 -0.34
outer loop
vertex 1.82 0.76 0.22
vertex 1.78 0.74 0.2
vertex 1.77 0.76 0.13
endloop
endfacet
facet normal 0.45 -0.83 -0.34
outer loop
vertex 1.78 0.74 0.2
vertex 1.7 0.75 0.08
vertex 1.77 0.76 0.13
endloop
endfacet
facet normal 0.03 -1 -0.09
outer loop
vertex -1.68 0.75 0.54
vertex -1.52 0.75 0.6
vertex -1.68 0.74 0.6
endloop
endfacet
facet normal 0.95 0.04 -0.31
outer loop
vertex -1.17 -0.76 0.3
vertex -1.18 -0.96 0.22
vertex -1.21 -0.76 0.17
endloop
endfacet
facet normal -0.37 -0.76 -0.53
outer loop
vertex 1.26 -0.96 0.1
vertex 1.36 -0.96 0.03
vertex 1.37 -0.98 0.05
endloop
endfacet
facet normal -0.31 -0.88 -0.37
outer loop
vertex 1.37 -0.98 0.05
vertex 1.22 -0.97 0.16
vertex 1.26 -0.96 0.1
endloop
endfacet
facet normal 0.21 0.74 -0.64
outer loop
vertex 1.66 0.96 0.04
vertex 1.55 0.96 0
vertex 1.56 0.98 0.03
endloop
endfacet
facet normal -0.28 -0.36 0.89
outer loop
vertex 1.41 -0.97 0.65
vertex 1.47 -0.96 0.68
vertex 1.33 -0.96 0.63
endloop
endfacet
facet normal -0.16 -0.65 0.75
outer loop
vertex 1.58 0.76 0.11
vertex 1.52 0.76 0.09
vertex 1.65 0.74 0.11
endloop
endfacet
facet normal -0.17 0.69 0.71
outer loop
vertex 1.65 0.97 0.12
vertex 1.5 0.96 0.09
vertex 1.63 0.96 0.13
endloop
endfacet
facet normal 0.17 -0.83 0.53
outer loop
vertex 1.5 0.96 0.09
vertex 1.36 0.96 0.13
vertex 1.42 0.96 0.11
endloop
endfacet
facet normal 0.22 0.98 -0.02
outer loop
vertex 1.19 -0.74 0.31
vertex 1.2 -0.74 0.44
vertex 1.26 -0.76 0.41
endloop
endfacet
facet normal 0.13 0.99 0.05
outer loop
vertex 1.24 -0.75 0.28
vertex 1.19 -0.74 0.31
vertex 1.26 -0.76 0.41
endloop
endfacet
facet normal 0.14 -0.01 -0.99
outer loop
vertex 1.55 0.75 0.01
vertex 1.55 0.96 0
vertex 1.6 0.8 0.01
endloop
endfacet
facet normal 0 -1 0.07
outer loop
vertex -1.68 0.74 0.6
vertex -1.32 0.74 0.59
vertex -1.53 0.75 0.66
endloop
endfacet
facet normal 0.02 -0.99 0.13
outer loop
vertex -1.32 0.74 0.59
vertex -1.36 0.75 0.63
vertex -1.53 0.75 0.66
endloop
endfacet
facet normal 0.07 -1 0.03
outer loop
vertex 1.68 -0.98 0.6
vertex 1.81 -0.98 0.27
vertex 1.82 -0.97 0.4
endloop
endfacet
facet normal -0.08 1 0.01
outer loop
vertex 1.81 -0.74 0.37
vertex 1.8 -0.74 0.24
vertex 1.72 -0.75 0.19
endloop
endfacet
facet normal -0.15 0.99 0.04
outer loop
vertex 1.76 -0.75 0.33
vertex 1.81 -0.74 0.37
vertex 1.72 -0.75 0.19
endloop
endfacet
facet normal -0.5 0.67 -0.55
outer loop
vertex 1.32 -0.76 0.05
vertex 1.23 -0.76 0.13
vertex 1.29 -0.74 0.11
endloop
endfacet
facet normal 0.21 0.02 0.98
outer loop
vertex 1.42 0.96 0.11
vertex 1.4 0.76 0.12
vertex 1.52 0.76 0.09
endloop
endfacet
facet normal -0.06 -0.78 -0.63
outer loop
vertex 1.43 0.74 0.03
vertex 1.44 0.76 0.01
vertex 1.55 0.75 0.01
endloop
endfacet
facet normal -0.14 0 -0.99
outer loop
vertex -1.37 1.02 0.69
vertex -1.38 -1.02 0.69
vertex -1.52 -1.01 0.71
endloop
endfacet
facet normal -0.02 0.84 -0.54
outer loop
vertex 0.95 -0.87 1.8
vertex 0.94 -0.87 1.81
vertex 1.34 -0.87 1.79
endloop
endfacet
facet normal -0.65 -0.04 -0.76
outer loop
vertex 1.24 0.76 0.12
vertex 1.32 0.9 0.05
vertex 1.33 0.76 0.05
endloop
endfacet
facet normal 0.02 0.83 0.55
outer loop
vertex 1.33 -0.87 1.78
vertex 0.94 -0.87 1.79
vertex 0.95 -0.87 1.8
endloop
endfacet
facet normal -0.19 0.98 0.01
outer loop
vertex -1.2 0.98 0.44
vertex -1.22 0.98 0.2
vertex -1.24 0.97 0.29
endloop
endfacet
facet normal -0.1 0.99 -0.01
outer loop
vertex -1.26 0.97 0.46
vertex -1.2 0.98 0.44
vertex -1.24 0.97 0.29
endloop
endfacet
facet normal -0.24 -0.81 -0.54
outer loop
vertex 1.43 0.74 0.03
vertex 1.3 0.75 0.08
vertex 1.33 0.76 0.05
endloop
endfacet
facet normal -0.02 0.82 -0.57
outer loop
vertex -1.32 0.74 0.59
vertex -1.68 0.74 0.6
vertex -1.52 0.75 0.6
endloop
endfacet
facet normal -0.06 -0.9 -0.43
outer loop
vertex -1.52 0.75 0.6
vertex -1.42 0.76 0.57
vertex -1.32 0.74 0.59
endloop
endfacet
facet normal -0.15 -0.73 -0.67
outer loop
vertex 1.37 -0.98 0.05
vertex 1.36 -0.96 0.03
vertex 1.49 -0.96 0
endloop
endfacet
facet normal 0.29 -0.87 0.4
outer loop
vertex 1.4 0.76 0.12
vertex 1.32 0.76 0.18
vertex 1.38 0.75 0.1
endloop
endfacet
facet normal -0.56 -0.49 -0.67
outer loop
vertex 1.33 0.76 0.05
vertex 1.3 0.75 0.08
vertex 1.24 0.76 0.12
endloop
endfacet
facet normal -0.38 -0.88 -0.27
outer loop
vertex 1.3 0.75 0.08
vertex 1.19 0.75 0.21
vertex 1.24 0.76 0.12
endloop
endfacet
facet normal -0.55 0.05 0.83
outer loop
vertex 1.63 0.96 0.13
vertex 1.58 0.76 0.11
vertex 1.69 0.76 0.18
endloop
endfacet
facet normal -0.05 0.04 -1
outer loop
vertex -1.45 -0.76 0.01
vertex -1.51 -0.96 0
vertex -1.58 -0.75 0.01
endloop
endfacet
facet normal -0.28 -0.01 0.96
outer loop
vertex 1.35 0.96 0.65
vertex 1.35 0.76 0.64
vertex 1.47 0.76 0.68
endloop
endfacet
facet normal -0.27 0 0.96
outer loop
vertex 1.47 0.76 0.68
vertex 1.44 0.96 0.67
vertex 1.35 0.96 0.65
endloop
endfacet
facet normal -0.17 0 -0.98
outer loop
vertex 1.24 0.81 1.13
vertex 2.25 0.81 0.95
vertex 2.25 -0.81 0.96
endloop
endfacet
facet normal -0.49 0 -0.87
outer loop
vertex -1.43 0.96 0.57
vertex -1.35 0.96 0.53
vertex -1.34 0.76 0.53
endloop
endfacet
facet normal -0.59 0.73 0.36
outer loop
vertex -1.82 0.96 0.46
vertex -1.76 0.96 0.56
vertex -1.74 0.98 0.55
endloop
endfacet
facet normal -0.75 0.41 -0.52
outer loop
vertex -1.24 0.75 0.37
vertex -1.34 0.76 0.53
vertex -1.28 0.76 0.44
endloop
endfacet
facet normal 1 0 -0.06
outer loop
vertex 1.2 -1.09 1.44
vertex 1.19 -1.09 1.35
vertex 1.19 -0.97 1.36
endloop
endfacet
facet normal 0.82 0.55 0.14
outer loop
vertex 1.28 0.97 0.2
vertex 1.25 0.96 0.36
vertex 1.28 0.96 0.23
endloop
endfacet
facet normal -0.66 -0.73 -0.16
outer loop
vertex 1.19 0.75 0.21
vertex 1.19 0.74 0.29
vertex 1.17 0.76 0.3
endloop
endfacet
facet normal -0.48 0.85 0.24
outer loop
vertex -1.74 0.98 0.55
vertex -1.81 0.98 0.41
vertex -1.82 0.96 0.46
endloop
endfacet
facet normal 0.1 0.94 0.32
outer loop
vertex 1.55 -0.74 0.03
vertex 1.29 -0.74 0.11
vertex 1.43 -0.75 0.08
endloop
endfacet
facet normal 0.07 0.98 0.18
outer loop
vertex 1.29 -0.74 0.11
vertex 1.32 -0.76 0.17
vertex 1.43 -0.75 0.08
endloop
endfacet
facet normal 0.85 0 0.53
outer loop
vertex -1.24 0.76 0.56
vertex -1.21 0.75 0.5
vertex -1.2 0.96 0.49
endloop
endfacet
facet normal 0.4 -0.43 -0.81
outer loop
vertex 1.55 -0.98 0.65
vertex 1.24 -0.98 0.5
vertex 1.45 -0.97 0.6
endloop
endfacet
facet normal -0.81 -0.59 -0.05
outer loop
vertex 1.76 0.75 0.26
vertex 1.75 0.75 0.44
vertex 1.74 0.76 0.3
endloop
endfacet
facet normal -0.64 -0.77 -0.07
outer loop
vertex 1.75 0.75 0.44
vertex 1.73 0.76 0.42
vertex 1.74 0.76 0.3
endloop
endfacet
facet normal 0.14 -0.99 0
outer loop
vertex -1.22 -0.98 0.48
vertex -1.21 -0.98 0.21
vertex -1.18 -0.97 0.37
endloop
endfacet
facet normal -0.68 0.73 0.01
outer loop
vertex 1.16 -0.76 0.29
vertex 1.17 -0.76 0.4
vertex 1.19 -0.74 0.31
endloop
endfacet
facet normal -0.49 -0.87 0.06
outer loop
vertex 1.19 -0.98 0.29
vertex 1.19 -0.97 0.46
vertex 1.16 -0.96 0.34
endloop
endfacet
facet normal -0.95 -0.01 0.32
outer loop
vertex 1.2 -0.76 0.49
vertex 1.17 -0.76 0.4
vertex 1.19 -0.97 0.46
endloop
endfacet
facet normal 0.18 0.97 -0.17
outer loop
vertex 1.77 -0.75 0.13
vertex 1.69 -0.75 0.07
vertex 1.8 -0.74 0.24
endloop
endfacet
facet normal 0.09 0.99 -0.11
outer loop
vertex 1.8 -0.74 0.24
vertex 1.69 -0.75 0.07
vertex 1.55 -0.74 0.03
endloop
endfacet
facet normal -0.74 0.67 0.06
outer loop
vertex 1.74 0.96 0.37
vertex 1.74 0.97 0.24
vertex 1.73 0.96 0.25
endloop
endfacet
facet normal 0.71 0.03 0.7
outer loop
vertex 1.71 -0.75 0.6
vertex 1.72 -0.96 0.59
vertex 1.78 -0.76 0.53
endloop
endfacet
facet normal 0.78 -0.01 0.63
outer loop
vertex 1.72 -0.96 0.59
vertex 1.8 -0.96 0.5
vertex 1.78 -0.76 0.53
endloop
endfacet
facet normal 0.27 -0.89 -0.36
outer loop
vertex -1.68 0.75 0.54
vertex -1.68 0.76 0.5
vertex -1.61 0.76 0.56
endloop
endfacet
facet normal 0.54 0.78 0.31
outer loop
vertex 1.32 -0.76 0.17
vertex 1.24 -0.75 0.28
vertex 1.26 -0.76 0.29
endloop
endfacet
facet normal -0.68 0.72 -0.13
outer loop
vertex 1.18 0.96 0.22
vertex 1.16 0.96 0.34
vertex 1.19 0.98 0.3
endloop
endfacet
facet normal 0.94 -0.01 0.33
outer loop
vertex 1.8 -0.96 0.5
vertex 1.84 -0.96 0.39
vertex 1.83 -0.76 0.41
endloop
endfacet
facet normal -0.19 0.87 0.45
outer loop
vertex 1.35 0.96 0.65
vertex 1.44 0.96 0.67
vertex 1.29 0.97 0.59
endloop
endfacet
facet normal 0.55 -0.78 -0.31
outer loop
vertex 1.32 -0.96 0.51
vertex 1.24 -0.97 0.39
vertex 1.26 -0.96 0.39
endloop
endfacet
facet normal -0.45 0.65 0.62
outer loop
vertex 1.72 -0.75 0.19
vertex 1.6 -0.76 0.11
vertex 1.69 -0.76 0.19
endloop
endfacet
facet normal 0.19 -0.98 -0.04
outer loop
vertex 1.27 -0.96 0.25
vertex 1.24 -0.97 0.39
vertex 1.19 -0.98 0.29
endloop
endfacet
facet normal -0.56 0.48 0.68
outer loop
vertex 1.24 -0.76 0.56
vertex 1.33 -0.76 0.63
vertex 1.3 -0.75 0.6
endloop
endfacet
facet normal -0.95 0 -0.32
outer loop
vertex 1.74 -0.96 0.39
vertex 1.72 -0.96 0.46
vertex 1.72 -0.76 0.44
endloop
endfacet
facet normal -0.84 0.21 0.5
outer loop
vertex -2.47 -0.83 1.22
vertex -2.39 -0.86 1.36
vertex -2.39 -0.81 1.34
endloop
endfacet
facet normal -0.01 -0.95 0.31
outer loop
vertex 1.37 -0.98 0.05
vertex 1.66 -0.98 0.06
vertex 1.5 -0.97 0.07
endloop
endfacet
facet normal -0.05 1 0.06
outer loop
vertex 1.43 -0.74 0.65
vertex 1.2 -0.74 0.44
vertex 1.3 -0.75 0.6
endloop
endfacet
facet normal -0.25 0.92 0.29
outer loop
vertex 1.8 -0.74 0.24
vertex 1.55 -0.74 0.03
vertex 1.72 -0.75 0.19
endloop
endfacet
facet normal -0.74 -0.48 0.47
outer loop
vertex 1.67 -0.97 0.13
vertex 1.77 -0.97 0.29
vertex 1.69 -0.96 0.18
endloop
endfacet
facet normal 0.37 -0.64 -0.68
outer loop
vertex 1.66 -0.98 0.06
vertex 1.61 -0.96 0.02
vertex 1.73 -0.96 0.09
endloop
endfacet
facet normal 0.4 0.71 0.58
outer loop
vertex 1.42 -0.76 0.11
vertex 1.43 -0.75 0.08
vertex 1.32 -0.76 0.17
endloop
endfacet
facet normal -1 0 0
outer loop
vertex 2.49 0.64 0.55
vertex 2.49 0.64 0.39
vertex 2.49 -0.64 0.39
endloop
endfacet
facet normal -0.02 0.86 0.52
outer loop
vertex -1.44 0.98 0.65
vertex -1.59 0.97 0.65
vertex -1.51 0.96 0.68
endloop
endfacet
facet normal 0.92 0 0.39
outer loop
vertex 0.98 -0.79 1.79
vertex 1.19 -0.8 1.3
vertex 1.19 0.8 1.3
endloop
endfacet
facet normal 0.21 -0.82 0.54
outer loop
vertex 1.55 -0.98 0.65
vertex 1.68 -0.98 0.6
vertex 1.61 -0.95 0.66
endloop
endfacet
facet normal -0.36 0.89 -0.27
outer loop
vertex -1.26 0.97 0.46
vertex -1.27 0.96 0.43
vertex -1.35 0.96 0.53
endloop
endfacet
facet normal 0 0 -1
outer loop
vertex 1.85 -0.8 0.24
vertex 1.85 0.8 0.24
vertex 2.32 -0.79 0.24
endloop
endfacet
facet normal 0 0 -1
outer loop
vertex 2.32 -0.79 0.24
vertex 1.85 0.8 0.24
vertex 2.32 0.79 0.24
endloop
endfacet
facet normal 1 0.01 0.02
outer loop
vertex 1.84 -0.96 0.39
vertex 1.84 -0.96 0.31
vertex 1.83 -0.76 0.41
endloop
endfacet
facet normal -0.15 -0.43 -0.89
outer loop
vertex 1.64 -0.97 0.57
vertex 1.45 -0.97 0.6
vertex 1.51 -0.96 0.59
endloop
endfacet
facet normal -0.36 0.89 -0.28
outer loop
vertex 1.72 -0.75 0.48
vertex 1.72 -0.76 0.44
vertex 1.65 -0.76 0.53
endloop
endfacet
facet normal 0.17 -0.8 -0.58
outer loop
vertex -1.61 0.76 0.56
vertex -1.52 0.76 0.58
vertex -1.52 0.75 0.6
endloop
endfacet
facet normal 0.31 -0.56 -0.77
outer loop
vertex -1.52 0.75 0.6
vertex -1.68 0.75 0.54
vertex -1.61 0.76 0.56
endloop
endfacet
facet normal 0.29 0.7 0.65
outer loop
vertex 1.57 -0.76 0.67
vertex 1.71 -0.75 0.6
vertex 1.58 -0.74 0.65
endloop
endfacet
facet normal 0.66 0.75 -0.07
outer loop
vertex -1.76 0.97 0.29
vertex -1.73 0.96 0.41
vertex -1.74 0.96 0.29
endloop
endfacet
facet normal -0.23 -0.9 0.37
outer loop
vertex 1.69 -0.96 0.18
vertex 1.55 -0.96 0.1
vertex 1.67 -0.97 0.13
endloop
endfacet
facet normal -1 0 0.02
outer loop
vertex -1.14 -1 0.42
vertex -1.14 1 0.42
vertex -1.15 0.8 0.24
endloop
endfacet
facet normal 0.68 0.67 0.31
outer loop
vertex 1.78 -0.76 0.53
vertex 1.83 -0.76 0.41
vertex 1.79 -0.74 0.47
endloop
endfacet
facet normal 0.5 -0.83 -0.23
outer loop
vertex 1.81 -0.98 0.27
vertex 1.75 -0.98 0.15
vertex 1.81 -0.96 0.2
endloop
endfacet
facet normal -0.23 0.03 0.97
outer loop
vertex -1.6 0.76 0.66
vertex -1.51 0.96 0.68
vertex -1.65 0.96 0.65
endloop
endfacet
facet normal 0.63 -0.59 0.5
outer loop
vertex 1.8 -0.96 0.5
vertex 1.72 -0.96 0.59
vertex 1.76 -0.97 0.53
endloop
endfacet
facet normal -0.12 -0.99 0.06
outer loop
vertex -1.3 0.74 0.09
vertex -1.18 0.74 0.34
vertex -1.33 0.75 0.13
endloop
endfacet
facet normal -0.13 -0.99 -0.05
outer loop
vertex -1.27 0.76 0.26
vertex -1.18 0.74 0.34
vertex -1.24 0.75 0.37
endloop
endfacet
facet normal 0.12 -0.04 0.99
outer loop
vertex 1.47 -0.96 0.68
vertex 1.61 -0.95 0.66
vertex 1.57 -0.76 0.67
endloop
endfacet
facet normal 0.51 -0.83 0.23
outer loop
vertex 1.76 -0.97 0.53
vertex 1.82 -0.97 0.4
vertex 1.8 -0.96 0.5
endloop
endfacet
facet normal 0.71 -0.66 0.25
outer loop
vertex 1.8 -0.96 0.5
vertex 1.82 -0.97 0.4
vertex 1.84 -0.96 0.39
endloop
endfacet
facet normal 0 -1 -0.06
outer loop
vertex -1.3 0.74 0.09
vertex -1.5 0.74 0.07
vertex -1.47 0.75 0.02
endloop
endfacet
facet normal -0.93 -0.03 0.37
outer loop
vertex 1.74 -0.76 0.31
vertex 1.69 -0.76 0.19
vertex 1.74 -0.96 0.29
endloop
endfacet
facet normal -0.31 -0.94 -0.15
outer loop
vertex -1.32 0.74 0.59
vertex -1.34 0.76 0.53
vertex -1.24 0.75 0.37
endloop
endfacet
facet normal 0.3 0.89 -0.34
outer loop
vertex 1.2 -0.74 0.44
vertex 1.43 -0.74 0.65
vertex 1.32 -0.76 0.51
endloop
endfacet
facet normal 0.18 0.98 -0.1
outer loop
vertex 1.32 -0.76 0.51
vertex 1.26 -0.76 0.41
vertex 1.2 -0.74 0.44
endloop
endfacet
facet normal 0.14 0.96 -0.22
outer loop
vertex 1.43 -0.74 0.65
vertex 1.42 -0.76 0.57
vertex 1.32 -0.76 0.51
endloop
endfacet
facet normal -0.95 0.01 -0.33
outer loop
vertex 1.16 -0.76 0.29
vertex 1.2 -0.75 0.2
vertex 1.19 -0.96 0.21
endloop
endfacet
facet normal 0.72 0.7 -0.02
outer loop
vertex 1.83 -0.76 0.41
vertex 1.83 -0.76 0.25
vertex 1.81 -0.74 0.37
endloop
endfacet
facet normal -0.85 0 -0.52
outer loop
vertex 1.34 -0.87 1.79
vertex 1.34 0.87 1.79
vertex 1.34 0.86 1.79
endloop
endfacet
facet normal 0.32 -0.89 0.31
outer loop
vertex 1.19 0.74 0.29
vertex 1.43 0.74 0.03
vertex 1.38 0.75 0.1
endloop
endfacet
facet normal -0.74 0.64 -0.2
outer loop
vertex 1.72 -0.75 0.48
vertex 1.76 -0.75 0.33
vertex 1.72 -0.76 0.44
endloop
endfacet
facet normal -0.7 0.69 0.21
outer loop
vertex 1.76 -0.75 0.33
vertex 1.72 -0.75 0.19
vertex 1.74 -0.76 0.31
endloop
endfacet
facet normal 0.71 -0.7 0.02
outer loop
vertex 1.84 -0.96 0.39
vertex 1.82 -0.97 0.4
vertex 1.84 -0.96 0.31
endloop
endfacet
facet normal 0.59 -0.81 -0.03
outer loop
vertex 1.82 -0.97 0.4
vertex 1.81 -0.98 0.27
vertex 1.84 -0.96 0.31
endloop
endfacet
facet normal -0.85 0 0.52
outer loop
vertex -2.43 0.8 1.3
vertex -2.43 -0.8 1.3
vertex -2.2 -0.75 1.67
endloop
endfacet
facet normal 0.72 -0.67 -0.18
outer loop
vertex 1.84 -0.96 0.31
vertex 1.81 -0.98 0.27
vertex 1.81 -0.96 0.2
endloop
endfacet
facet normal -0.2 0.98 0.06
outer loop
vertex -1.18 -0.74 0.32
vertex -1.22 -0.74 0.2
vertex -1.25 -0.76 0.34
endloop
endfacet
facet normal -0.23 0.97 0.05
outer loop
vertex -1.22 -0.74 0.2
vertex -1.27 -0.76 0.24
vertex -1.25 -0.76 0.34
endloop
endfacet
facet normal -0.99 -0.01 -0.15
outer loop
vertex -1.84 0.96 0.33
vertex -1.83 0.97 0.27
vertex -1.84 0.76 0.34
endloop
endfacet
facet normal 0.2 0.97 0.12
outer loop
vertex 1.3 0.98 0.11
vertex 1.19 0.98 0.3
vertex 1.28 0.97 0.2
endloop
endfacet
facet normal 0.15 0.99 0.07
outer loop
vertex 1.19 0.98 0.3
vertex 1.25 0.96 0.36
vertex 1.28 0.97 0.2
endloop
endfacet
facet normal 0.01 -1 -0.03
outer loop
vertex 1.86 -1 0.42
vertex 2.32 -1 0.42
vertex 2.39 -1.01 0.67
endloop
endfacet
facet normal 0.02 -1 -0.05
outer loop
vertex 1.79 -1.01 0.57
vertex 1.86 -1 0.42
vertex 2.39 -1.01 0.67
endloop
endfacet
facet normal 0.01 -1 -0.02
outer loop
vertex 2.39 -1.01 0.67
vertex 1.66 -1.02 0.67
vertex 1.79 -1.01 0.57
endloop
endfacet
facet normal 0.12 0.03 0.99
outer loop
vertex 1.52 -0.76 0.1
vertex 1.42 -0.76 0.11
vertex 1.55 -0.96 0.1
endloop
endfacet
facet normal -0.52 0.05 0.85
outer loop
vertex 1.6 -0.76 0.11
vertex 1.55 -0.96 0.1
vertex 1.69 -0.96 0.18
endloop
endfacet
facet normal 0.38 -0.9 -0.19
outer loop
vertex -1.68 0.74 0.6
vertex -1.82 0.74 0.33
vertex -1.74 0.76 0.41
endloop
endfacet
facet normal 0.16 -0.99 0.06
outer loop
vertex -1.82 0.74 0.33
vertex -1.76 0.75 0.28
vertex -1.74 0.76 0.41
endloop
endfacet
facet normal 0.02 -1 -0.09
outer loop
vertex -1.74 0.76 0.41
vertex -1.68 0.75 0.54
vertex -1.68 0.74 0.6
endloop
endfacet
facet normal -0.86 -0.02 0.51
outer loop
vertex -1.74 0.76 0.58
vertex -1.76 0.96 0.56
vertex -1.82 0.96 0.46
endloop
endfacet
facet normal -0.47 0.86 0.19
outer loop
vertex 1.74 -0.76 0.31
vertex 1.72 -0.75 0.19
vertex 1.69 -0.76 0.19
endloop
endfacet
facet normal 0.99 0.04 0.09
outer loop
vertex -1.18 -0.75 0.43
vertex -1.16 -0.96 0.34
vertex -1.17 -0.76 0.3
endloop
endfacet
facet normal -0.02 -0.85 0.53
outer loop
vertex 1.41 -0.97 0.65
vertex 1.55 -0.98 0.65
vertex 1.47 -0.96 0.68
endloop
endfacet
facet normal -0.48 -0.78 -0.41
outer loop
vertex 1.64 -0.97 0.57
vertex 1.63 -0.96 0.55
vertex 1.72 -0.96 0.46
endloop
endfacet
facet normal -0.08 -1 0.05
outer loop
vertex -1.82 0.74 0.33
vertex -1.68 0.74 0.6
vertex -1.78 0.75 0.51
endloop
endfacet
facet normal 0.52 0 0.85
outer loop
vertex 2.51 -0.64 0.55
vertex 2.51 0.64 0.55
vertex 2.5 0.63 0.55
endloop
endfacet
facet normal -0.23 0.75 0.62
outer loop
vertex 1.33 -0.76 0.63
vertex 1.43 -0.76 0.67
vertex 1.43 -0.74 0.65
endloop
endfacet
facet normal 0.59 0.04 0.81
outer loop
vertex 1.36 0.96 0.13
vertex 1.32 0.76 0.18
vertex 1.4 0.76 0.12
endloop
endfacet
facet normal 0.87 0.01 -0.49
outer loop
vertex -1.73 0.96 0.41
vertex -1.68 0.96 0.51
vertex -1.68 0.76 0.5
endloop
endfacet
facet normal 0.08 0.65 -0.75
outer loop
vertex 1.61 -0.76 0.02
vertex 1.46 -0.76 0
vertex 1.55 -0.74 0.03
endloop
endfacet
facet normal 0.65 -0.67 -0.35
outer loop
vertex -1.74 0.76 0.41
vertex -1.68 0.76 0.5
vertex -1.68 0.75 0.54
endloop
endfacet
facet normal -0.79 -0.03 -0.62
outer loop
vertex 1.65 -0.76 0.53
vertex 1.72 -0.76 0.44
vertex 1.72 -0.96 0.46
endloop
endfacet
facet normal 0.14 0.03 -0.99
outer loop
vertex 1.61 -0.96 0.02
vertex 1.49 -0.96 0
vertex 1.46 -0.76 0
endloop
endfacet
facet normal 0.46 -0.72 0.52
outer loop
vertex -1.36 0.75 0.63
vertex -1.32 0.74 0.59
vertex -1.21 0.75 0.5
endloop
endfacet
facet normal 0.13 0.67 0.73
outer loop
vertex -1.51 0.96 0.68
vertex -1.38 0.96 0.66
vertex -1.44 0.98 0.65
endloop
endfacet
facet normal -0.88 -0.03 -0.48
outer loop
vertex -1.82 -0.96 0.24
vertex -1.82 -0.76 0.22
vertex -1.76 -0.96 0.12
endloop
endfacet
facet normal -0.87 -0.01 -0.5
outer loop
vertex -1.82 -0.76 0.22
vertex -1.77 -0.76 0.13
vertex -1.76 -0.96 0.12
endloop
endfacet
facet normal -0.23 -0.02 -0.97
outer loop
vertex 1.49 -0.96 0
vertex 1.36 -0.96 0.03
vertex 1.46 -0.76 0
endloop
endfacet
facet normal -0.02 -1 -0.09
outer loop
vertex 1.45 -0.97 0.6
vertex 1.64 -0.97 0.57
vertex 1.55 -0.98 0.65
endloop
endfacet
facet normal -0.29 0.48 -0.83
outer loop
vertex 1.42 -0.75 0.03
vertex 1.46 -0.76 0
vertex 1.32 -0.76 0.05
endloop
endfacet
facet normal 0.84 -0.06 0.54
outer loop
vertex 1.26 -0.76 0.29
vertex 1.27 -0.96 0.25
vertex 1.32 -0.96 0.18
endloop
endfacet
facet normal 0.34 -0.26 -0.9
outer loop
vertex 1.69 0.76 0.06
vertex 1.55 0.75 0.01
vertex 1.6 0.8 0.01
endloop
endfacet
facet normal 0.67 0 -0.74
outer loop
vertex -1.78 1.01 0.58
vertex -1.67 -1.02 0.67
vertex -1.8 -1.01 0.55
endloop
endfacet
facet normal 0.69 0.72 -0.06
outer loop
vertex 1.24 -0.75 0.28
vertex 1.26 -0.76 0.41
vertex 1.26 -0.76 0.29
endloop
endfacet
facet normal -0.59 -0.02 -0.81
outer loop
vertex 1.32 -0.76 0.05
vertex 1.36 -0.96 0.03
vertex 1.26 -0.96 0.1
endloop
endfacet
facet normal 0.11 0 0.99
outer loop
vertex 2.42 0.79 0.93
vertex 2.31 0.81 0.94
vertex 2.31 -0.81 0.94
endloop
endfacet
facet normal 0.17 0 0.98
outer loop
vertex 2.31 0.81 0.94
vertex 1.24 0.81 1.13
vertex 2.31 -0.81 0.94
endloop
endfacet
facet normal 0.18 0 0.98
outer loop
vertex 1.24 0.81 1.13
vertex 1.24 -0.81 1.13
vertex 2.31 -0.81 0.94
endloop
endfacet
facet normal -0.4 0.81 -0.43
outer loop
vertex 1.24 0.96 0.13
vertex 1.22 0.97 0.17
vertex 1.33 0.97 0.05
endloop
endfacet
facet normal 0.37 -0.48 0.79
outer loop
vertex -1.77 -0.98 0.17
vertex -1.47 -0.98 0.03
vertex -1.63 -0.97 0.11
endloop
endfacet
facet normal 0.06 -0.98 0.2
outer loop
vertex -1.63 -0.97 0.11
vertex -1.47 -0.98 0.03
vertex -1.47 -0.97 0.09
endloop
endfacet
facet normal 0.08 -0.87 0.49
outer loop
vertex -1.47 0.76 0.68
vertex -1.53 0.75 0.66
vertex -1.36 0.75 0.63
endloop
endfacet
facet normal 0.94 -0.01 0.35
outer loop
vertex -1.21 0.75 0.5
vertex -1.17 0.76 0.4
vertex -1.2 0.96 0.49
endloop
endfacet
facet normal 0.9 0 -0.43
outer loop
vertex 1.21 1.01 0.57
vertex 1.22 -1.01 0.57
vertex 1.14 -1 0.42
endloop
endfacet
facet normal 0.54 0 -0.84
outer loop
vertex 2.42 -0.78 0.25
vertex 2.42 0.78 0.25
vertex 2.48 0.75 0.29
endloop
endfacet
facet normal -0.26 0.89 0.38
outer loop
vertex -1.22 -0.74 0.2
vertex -1.47 -0.74 0.02
vertex -1.39 -0.76 0.12
endloop
endfacet
facet normal -0.16 0.98 0.15
outer loop
vertex -1.27 -0.76 0.24
vertex -1.22 -0.74 0.2
vertex -1.39 -0.76 0.12
endloop
endfacet
facet normal -0.04 0.98 0.19
outer loop
vertex -1.47 -0.74 0.02
vertex -1.47 -0.76 0.09
vertex -1.39 -0.76 0.12
endloop
endfacet
facet normal 1 -0.01 -0.06
outer loop
vertex -1.74 0.96 0.29
vertex -1.73 0.96 0.41
vertex -1.74 0.76 0.3
endloop
endfacet
facet normal -0.69 -0.71 0.13
outer loop
vertex -1.24 0.75 0.37
vertex -1.26 0.76 0.34
vertex -1.27 0.76 0.26
endloop
endfacet
facet normal -0.65 -0.02 0.76
outer loop
vertex 1.24 -0.76 0.56
vertex 1.25 -0.97 0.57
vertex 1.33 -0.96 0.63
endloop
endfacet
facet normal 0.2 0.97 -0.1
outer loop
vertex -1.81 0.98 0.41
vertex -1.74 0.98 0.55
vertex -1.73 0.96 0.41
endloop
endfacet
facet normal 0.16 0.98 -0.11
outer loop
vertex -1.73 0.96 0.41
vertex -1.74 0.98 0.55
vertex -1.68 0.96 0.51
endloop
endfacet
facet normal -0.01 0.71 -0.71
outer loop
vertex -1.45 -0.76 0.01
vertex -1.58 -0.75 0.01
vertex -1.47 -0.74 0.02
endloop
endfacet
facet normal -0.98 0 0.18
outer loop
vertex -2.51 -0.85 0.98
vertex -2.47 -0.83 1.22
vertex -2.47 0.84 1.23
endloop
endfacet
facet normal -0.88 -0.02 -0.48
outer loop
vertex 1.24 0.76 0.12
vertex 1.19 0.75 0.21
vertex 1.18 0.96 0.22
endloop
endfacet
facet normal -0.87 -0.01 -0.49
outer loop
vertex 1.18 0.96 0.22
vertex 1.24 0.96 0.13
vertex 1.24 0.76 0.12
endloop
endfacet
facet normal -0.03 -1 0.08
outer loop
vertex 1.67 -0.97 0.13
vertex 1.5 -0.97 0.07
vertex 1.66 -0.98 0.06
endloop
endfacet
facet normal -0.59 -0.8 0.12
outer loop
vertex -1.84 0.76 0.34
vertex -1.82 0.74 0.33
vertex -1.81 0.76 0.46
endloop
endfacet
facet normal -0.47 -0.87 0.12
outer loop
vertex -1.82 0.74 0.33
vertex -1.78 0.75 0.51
vertex -1.81 0.76 0.46
endloop
endfacet
facet normal 0.41 -0.91 -0.06
outer loop
vertex 1.24 0.75 0.37
vertex 1.26 0.76 0.3
vertex 1.28 0.76 0.44
endloop
endfacet
facet normal 0.07 1 0.05
outer loop
vertex 1.72 0.97 0.58
vertex 1.81 0.97 0.45
vertex 1.75 0.98 0.45
endloop
endfacet
facet normal 0.06 1 0.05
outer loop
vertex 1.75 0.98 0.45
vertex 1.59 0.98 0.64
vertex 1.72 0.97 0.58
endloop
endfacet
facet normal 0.12 0 -0.99
outer loop
vertex 1.36 1.02 0.68
vertex 1.55 1.01 0.7
vertex 1.37 -1.02 0.69
endloop
endfacet
facet normal 0.8 -0.01 -0.6
outer loop
vertex 1.81 -0.96 0.2
vertex 1.73 -0.96 0.09
vertex 1.77 -0.75 0.13
endloop
endfacet
facet normal -0.79 -0.01 -0.61
outer loop
vertex -1.35 0.96 0.53
vertex -1.27 0.96 0.43
vertex -1.28 0.76 0.44
endloop
endfacet
facet normal -0.79 -0.35 0.49
outer loop
vertex -1.78 0.75 0.51
vertex -1.74 0.76 0.58
vertex -1.81 0.76 0.46
endloop
endfacet
facet normal 0.68 -0.73 0.08
outer loop
vertex 1.24 -0.97 0.39
vertex 1.27 -0.96 0.25
vertex 1.26 -0.96 0.39
endloop
endfacet
facet normal -0.21 0.43 0.88
outer loop
vertex -1.65 0.96 0.65
vertex -1.51 0.96 0.68
vertex -1.59 0.97 0.65
endloop
endfacet
facet normal -0.66 -0.02 -0.75
outer loop
vertex -1.76 0.76 0.13
vertex -1.74 0.96 0.1
vertex -1.68 0.76 0.05
endloop
endfacet
facet normal -0.62 0.01 -0.79
outer loop
vertex -1.74 0.96 0.1
vertex -1.67 0.96 0.04
vertex -1.68 0.76 0.05
endloop
endfacet
facet normal 1 -0.03 -0.06
outer loop
vertex 1.26 -0.76 0.29
vertex 1.26 -0.76 0.41
vertex 1.26 -0.96 0.39
endloop
endfacet
facet normal -0.45 0.7 0.56
outer loop
vertex -1.76 0.96 0.56
vertex -1.65 0.96 0.65
vertex -1.74 0.98 0.55
endloop
endfacet
facet normal 0.01 -0.66 -0.75
outer loop
vertex 2.32 -0.79 0.24
vertex 2.32 -1 0.42
vertex 1.85 -0.8 0.24
endloop
endfacet
facet normal 0.01 -0.66 -0.75
outer loop
vertex 2.32 -1 0.42
vertex 1.86 -1 0.42
vertex 1.85 -0.8 0.24
endloop
endfacet
facet normal 0.33 -0.12 -0.94
outer loop
vertex -1.48 -0.97 0.6
vertex -1.63 -0.96 0.55
vertex -1.54 -0.96 0.58
endloop
endfacet
facet normal -0.77 0.46 0.44
outer loop
vertex -1.82 -0.76 0.46
vertex -1.76 -0.76 0.56
vertex -1.78 -0.75 0.51
endloop
endfacet
facet normal -0.56 0.42 -0.72
outer loop
vertex 1.59 -0.75 0.59
vertex 1.72 -0.75 0.48
vertex 1.65 -0.76 0.53
endloop
endfacet
facet normal -1 0 0.02
outer loop
vertex 1.86 -1 0.42
vertex 1.86 1 0.42
vertex 1.85 0.8 0.24
endloop
endfacet
facet normal 0.54 -0.01 -0.84
outer loop
vertex 1.32 -0.76 0.51
vertex 1.42 -0.76 0.57
vertex 1.4 -0.96 0.56
endloop
endfacet
facet normal 1 -0.01 0.03
outer loop
vertex -1.17 0.76 0.4
vertex -1.16 0.76 0.31
vertex -1.16 0.96 0.37
endloop
endfacet
facet normal -0.18 -0.85 0.5
outer loop
vertex -1.68 0.74 0.6
vertex -1.53 0.75 0.66
vertex -1.6 0.76 0.66
endloop
endfacet
facet normal -0.02 0.75 0.66
outer loop
vertex 1.43 -0.74 0.65
vertex 1.43 -0.76 0.67
vertex 1.57 -0.76 0.67
endloop
endfacet
facet normal -0.02 0.03 1
outer loop
vertex 1.57 -0.76 0.67
vertex 1.43 -0.76 0.67
vertex 1.47 -0.96 0.68
endloop
endfacet
facet normal 0.6 -0.67 -0.43
outer loop
vertex 1.81 -0.96 0.2
vertex 1.75 -0.98 0.15
vertex 1.73 -0.96 0.09
endloop
endfacet
facet normal -0.03 -0.03 -1
outer loop
vertex -1.52 0.76 0.58
vertex -1.56 0.96 0.58
vertex -1.43 0.96 0.57
endloop
endfacet
facet normal 0.08 0.32 -0.94
outer loop
vertex 1.42 -0.76 0.57
vertex 1.59 -0.75 0.59
vertex 1.54 -0.76 0.58
endloop
endfacet
facet normal -0.5 0.81 0.32
outer loop
vertex 1.2 -0.76 0.49
vertex 1.24 -0.76 0.56
vertex 1.2 -0.74 0.44
endloop
endfacet
facet normal -0.07 -1 -0.05
outer loop
vertex -1.64 0.74 0.05
vertex -1.82 0.74 0.33
vertex -1.77 0.75 0.15
endloop
endfacet
facet normal -0.75 0.51 -0.42
outer loop
vertex 1.24 0.96 0.13
vertex 1.18 0.96 0.22
vertex 1.22 0.97 0.17
endloop
endfacet
facet normal 0.32 0.89 0.31
outer loop
vertex 1.28 0.96 0.23
vertex 1.36 0.96 0.13
vertex 1.28 0.97 0.2
endloop
endfacet
facet normal -0.03 -0.98 -0.2
outer loop
vertex 1.68 0.74 0.6
vertex 1.42 0.74 0.65
vertex 1.52 0.75 0.6
endloop
endfacet
facet normal 0.02 -1 -0.08
outer loop
vertex 1.52 0.75 0.6
vertex 1.42 0.74 0.65
vertex 1.33 0.75 0.55
endloop
endfacet
facet normal 0.36 -0.71 -0.61
outer loop
vertex -1.3 0.74 0.09
vertex -1.37 0.76 0.02
vertex -1.29 0.76 0.08
endloop
endfacet
facet normal 0.87 -0.01 -0.5
outer loop
vertex -1.18 0.76 0.22
vertex -1.24 0.76 0.13
vertex -1.22 0.96 0.16
endloop
endfacet
facet normal 0.33 -0.87 0.35
outer loop
vertex -1.36 0.75 0.63
vertex -1.21 0.75 0.5
vertex -1.24 0.76 0.56
endloop
endfacet
facet normal 0.35 0.78 -0.53
outer loop
vertex -1.56 0.97 0.6
vertex -1.56 0.96 0.58
vertex -1.68 0.96 0.51
endloop
endfacet
facet normal 1 0.03 -0.09
outer loop
vertex -1.17 0.97 0.27
vertex -1.16 0.96 0.37
vertex -1.16 0.76 0.31
endloop
endfacet
facet normal 0.98 0 -0.2
outer loop
vertex -1.16 0.76 0.31
vertex -1.18 0.76 0.22
vertex -1.17 0.97 0.27
endloop
endfacet
facet normal 0.5 0.02 -0.86
outer loop
vertex -1.29 0.97 0.08
vertex -1.29 0.76 0.08
vertex -1.37 0.76 0.02
endloop
endfacet
facet normal 0.88 -0.01 -0.48
outer loop
vertex 1.27 0.96 0.42
vertex 1.31 0.96 0.5
vertex 1.28 0.76 0.44
endloop
endfacet
facet normal -0.45 -0.89 -0.09
outer loop
vertex -1.28 0.76 0.44
vertex -1.26 0.76 0.34
vertex -1.24 0.75 0.37
endloop
endfacet
facet normal -0.1 0.93 -0.34
outer loop
vertex -1.56 -0.74 0.65
vertex -1.28 -0.74 0.57
vertex -1.48 -0.76 0.59
endloop
endfacet
facet normal -0.09 0.95 -0.29
outer loop
vertex -1.28 -0.74 0.57
vertex -1.36 -0.76 0.55
vertex -1.48 -0.76 0.59
endloop
endfacet
facet normal 0.73 0.65 0.22
outer loop
vertex -1.2 0.98 0.44
vertex -1.2 0.96 0.49
vertex -1.16 0.96 0.37
endloop
endfacet
facet normal 0.1 0.94 0.33
outer loop
vertex 1.56 0.98 0.03
vertex 1.3 0.98 0.11
vertex 1.5 0.96 0.09
endloop
endfacet
facet normal 0.19 0.98 0.11
outer loop
vertex 1.28 0.97 0.2
vertex 1.36 0.96 0.13
vertex 1.3 0.98 0.11
endloop
endfacet
facet normal 0.21 0.98 -0.04
outer loop
vertex -1.75 -0.76 0.34
vertex -1.81 -0.74 0.37
vertex -1.72 -0.76 0.45
endloop
endfacet
facet normal 0.3 0.94 -0.17
outer loop
vertex -1.81 -0.74 0.37
vertex -1.68 -0.74 0.6
vertex -1.72 -0.76 0.45
endloop
endfacet
facet normal -0.49 0.53 -0.7
outer loop
vertex -2.47 0.78 0.27
vertex -2.5 0.95 0.42
vertex -2.47 0.98 0.42
endloop
endfacet
facet normal 0.25 0.97 0.08
outer loop
vertex -1.73 -0.74 0.12
vertex -1.81 -0.74 0.37
vertex -1.71 -0.75 0.2
endloop
endfacet
facet normal 0.27 0.96 0.09
outer loop
vertex -1.71 -0.75 0.2
vertex -1.81 -0.74 0.37
vertex -1.75 -0.76 0.34
endloop
endfacet
facet normal -0.23 -0.91 0.35
outer loop
vertex -1.32 0.76 0.17
vertex -1.42 0.76 0.11
vertex -1.33 0.75 0.13
endloop
endfacet
facet normal 0.55 -0.83 0.13
outer loop
vertex -1.21 0.75 0.5
vertex -1.18 0.74 0.34
vertex -1.17 0.76 0.4
endloop
endfacet
facet normal -0.55 0.83 0.03
outer loop
vertex 1.19 0.98 0.3
vertex 1.16 0.96 0.34
vertex 1.19 0.97 0.42
endloop
endfacet
facet normal 0.61 0.75 -0.27
outer loop
vertex -1.17 0.97 0.27
vertex -1.22 0.96 0.16
vertex -1.22 0.98 0.2
endloop
endfacet
facet normal -0.44 -0.89 -0.11
outer loop
vertex -1.77 -0.98 0.17
vertex -1.83 -0.97 0.33
vertex -1.82 -0.96 0.24
endloop
endfacet
facet normal 0.96 0.11 -0.27
outer loop
vertex 1.25 0.96 0.36
vertex 1.27 0.96 0.42
vertex 1.26 0.76 0.3
endloop
endfacet
facet normal -0.68 0.73 -0.08
outer loop
vertex -1.27 0.96 0.43
vertex -1.26 0.97 0.46
vertex -1.26 0.96 0.29
endloop
endfacet
facet normal -0.68 0.73 -0.08
outer loop
vertex -1.26 0.97 0.46
vertex -1.24 0.97 0.29
vertex -1.26 0.96 0.29
endloop
endfacet
facet normal -0.09 1 0.04
outer loop
vertex 1.19 0.98 0.3
vertex 1.19 0.97 0.42
vertex 1.31 0.98 0.58
endloop
endfacet
facet normal -0.17 0.98 0.1
outer loop
vertex 1.19 0.97 0.42
vertex 1.29 0.97 0.59
vertex 1.31 0.98 0.58
endloop
endfacet
facet normal -0.08 -1 -0.06
outer loop
vertex 1.37 -0.98 0.05
vertex 1.19 -0.98 0.29
vertex 1.22 -0.97 0.16
endloop
endfacet
facet normal -0.82 0.56 0.15
outer loop
vertex 1.16 0.96 0.34
vertex 1.18 0.96 0.46
vertex 1.19 0.97 0.42
endloop
endfacet
facet normal 0.04 0.05 1
outer loop
vertex -1.57 -0.76 0.67
vertex -1.46 -0.96 0.68
vertex -1.43 -0.75 0.67
endloop
endfacet
facet normal 0.06 -0.98 -0.19
outer loop
vertex 1.65 0.74 0.11
vertex 1.43 0.74 0.03
vertex 1.55 0.75 0.01
endloop
endfacet
facet normal 0.03 -0.99 -0.15
outer loop
vertex 1.55 0.75 0.01
vertex 1.7 0.75 0.08
vertex 1.65 0.74 0.11
endloop
endfacet
facet normal -0.11 0.02 0.99
outer loop
vertex -1.43 0.96 0.1
vertex -1.52 0.76 0.1
vertex -1.42 0.76 0.11
endloop
endfacet
facet normal 0.65 -0.67 -0.37
outer loop
vertex -1.18 0.76 0.22
vertex -1.2 0.75 0.21
vertex -1.24 0.76 0.13
endloop
endfacet
facet normal 0.42 -0.85 -0.31
outer loop
vertex -1.2 0.75 0.21
vertex -1.3 0.74 0.09
vertex -1.24 0.76 0.13
endloop
endfacet
facet normal -0.54 -0.01 0.84
outer loop
vertex -1.43 0.96 0.1
vertex -1.42 0.76 0.11
vertex -1.32 0.76 0.17
endloop
endfacet
facet normal -0.15 -0.89 0.44
outer loop
vertex 1.43 0.74 0.03
vertex 1.65 0.74 0.11
vertex 1.52 0.76 0.09
endloop
endfacet
facet normal 0.08 0.87 -0.49
outer loop
vertex 1.52 0.97 0.6
vertex 1.54 0.96 0.58
vertex 1.41 0.96 0.57
endloop
endfacet
facet normal 0.49 -0.71 -0.5
outer loop
vertex -1.3 0.74 0.09
vertex -1.29 0.76 0.08
vertex -1.24 0.76 0.13
endloop
endfacet
facet normal 0.09 0.97 0.24
outer loop
vertex -1.47 -0.74 0.02
vertex -1.73 -0.74 0.12
vertex -1.61 -0.75 0.1
endloop
endfacet
facet normal 0.07 0.99 0.13
outer loop
vertex -1.73 -0.74 0.12
vertex -1.71 -0.75 0.2
vertex -1.61 -0.75 0.1
endloop
endfacet
facet normal -0.08 0.97 -0.23
outer loop
vertex 1.44 0.96 0.01
vertex 1.33 0.97 0.05
vertex 1.3 0.98 0.11
endloop
endfacet
facet normal -0.06 0.98 -0.21
outer loop
vertex 1.56 0.98 0.03
vertex 1.44 0.96 0.01
vertex 1.3 0.98 0.11
endloop
endfacet
facet normal 0.08 -1 0.01
outer loop
vertex 1.77 0.74 0.5
vertex 1.78 0.74 0.2
vertex 1.83 0.75 0.36
endloop
endfacet
facet normal -0.33 0.94 -0.13
outer loop
vertex -1.28 -0.74 0.57
vertex -1.18 -0.74 0.32
vertex -1.28 -0.76 0.44
endloop
endfacet
facet normal -1 -0.04 0.07
outer loop
vertex 1.17 0.76 0.3
vertex 1.17 0.76 0.43
vertex 1.16 0.96 0.34
endloop
endfacet
facet normal -0.28 -0.59 0.76
outer loop
vertex -1.5 0.74 0.07
vertex -1.33 0.75 0.13
vertex -1.42 0.76 0.11
endloop
endfacet
facet normal 0.09 0.59 -0.8
outer loop
vertex -1.39 0.96 0.02
vertex -1.54 0.96 0
vertex -1.47 0.98 0.02
endloop
endfacet
facet normal -0.29 0.35 0.89
outer loop
vertex -1.33 0.97 0.13
vertex -1.5 0.97 0.07
vertex -1.43 0.96 0.1
endloop
endfacet
facet normal 0.28 0.43 0.86
outer loop
vertex -1.5 0.97 0.07
vertex -1.67 0.97 0.13
vertex -1.58 0.96 0.11
endloop
endfacet
facet normal 0.24 -0.93 -0.26
outer loop
vertex -1.7 -0.96 0.48
vertex -1.63 -0.96 0.55
vertex -1.8 -0.98 0.44
endloop
endfacet
facet normal -0.05 -0.68 -0.74
outer loop
vertex -1.47 0.76 0
vertex -1.47 0.75 0.02
vertex -1.57 0.76 0.01
endloop
endfacet
facet normal -0.09 -0.85 -0.51
outer loop
vertex -1.47 0.75 0.02
vertex -1.64 0.74 0.05
vertex -1.57 0.76 0.01
endloop
endfacet
facet normal 0.02 0.99 0.13
outer loop
vertex -1.47 0.98 0.02
vertex -1.65 0.98 0.06
vertex -1.5 0.97 0.07
endloop
endfacet
facet normal 0.09 1 -0.02
outer loop
vertex 1.19 -0.74 0.31
vertex 1.24 -0.75 0.28
vertex 1.32 -0.76 0.17
endloop
endfacet
facet normal 0.22 0.97 0.11
outer loop
vertex 1.19 -0.74 0.31
vertex 1.32 -0.76 0.17
vertex 1.29 -0.74 0.11
endloop
endfacet
facet normal -0.05 -0.88 0.48
outer loop
vertex -1.42 0.76 0.11
vertex -1.52 0.76 0.1
vertex -1.5 0.74 0.07
endloop
endfacet
facet normal 0.04 -0.05 1
outer loop
vertex -1.52 0.76 0.1
vertex -1.43 0.96 0.1
vertex -1.58 0.96 0.11
endloop
endfacet
facet normal 0.38 0.86 -0.33
outer loop
vertex -1.64 -0.75 0.57
vertex -1.61 -0.76 0.56
vertex -1.72 -0.76 0.45
endloop
endfacet
facet normal -0.38 0.83 -0.41
outer loop
vertex -1.74 0.96 0.1
vertex -1.78 0.97 0.17
vertex -1.65 0.98 0.06
endloop
endfacet
facet normal 0.28 -0.96 0.06
outer loop
vertex 1.27 0.75 0.22
vertex 1.24 0.75 0.37
vertex 1.2 0.74 0.45
endloop
endfacet
facet normal 0.9 0.01 0.44
outer loop
vertex -1.74 0.96 0.29
vertex -1.74 0.76 0.3
vertex -1.68 0.76 0.17
endloop
endfacet
facet normal -0.23 0.71 -0.66
outer loop
vertex -1.65 0.98 0.06
vertex -1.54 0.96 0
vertex -1.67 0.96 0.04
endloop
endfacet
facet normal 0.29 -0.9 -0.32
outer loop
vertex 1.42 0.74 0.65
vertex 1.2 0.74 0.45
vertex 1.33 0.75 0.55
endloop
endfacet
facet normal 0.67 0.04 0.74
outer loop
vertex -1.24 -0.96 0.56
vertex -1.22 -0.76 0.53
vertex -1.34 -0.76 0.64
endloop
endfacet
facet normal 0.07 -1 -0.04
outer loop
vertex 1.24 0.75 0.37
vertex 1.33 0.75 0.55
vertex 1.2 0.74 0.45
endloop
endfacet
facet normal 0.86 -0.03 0.51
outer loop
vertex 1.76 0.76 0.56
vertex 1.82 0.76 0.46
vertex 1.78 0.96 0.53
endloop
endfacet
facet normal -0.64 -0.01 0.77
outer loop
vertex -1.67 -0.96 0.63
vertex -1.67 -0.76 0.63
vertex -1.76 -0.76 0.56
endloop
endfacet
facet normal -0.43 -0.76 -0.49
outer loop
vertex -1.76 0.76 0.13
vertex -1.68 0.76 0.05
vertex -1.77 0.75 0.15
endloop
endfacet
facet normal -0.36 -0.82 -0.44
outer loop
vertex -1.68 0.76 0.05
vertex -1.64 0.74 0.05
vertex -1.77 0.75 0.15
endloop
endfacet
facet normal 0.21 0.01 0.98
outer loop
vertex -1.58 0.96 0.11
vertex -1.6 0.76 0.11
vertex -1.52 0.76 0.1
endloop
endfacet
facet normal -0.88 -0.03 -0.48
outer loop
vertex -1.82 0.76 0.22
vertex -1.79 0.96 0.17
vertex -1.76 0.76 0.13
endloop
endfacet
facet normal 0.55 0.76 -0.36
outer loop
vertex 1.79 0.98 0.21
vertex 1.81 0.96 0.21
vertex 1.74 0.96 0.1
endloop
endfacet
facet normal -0.68 0.72 -0.11
outer loop
vertex 1.75 0.98 0.45
vertex 1.79 0.98 0.21
vertex 1.74 0.96 0.37
endloop
endfacet
facet normal -0.08 0.99 0.08
outer loop
vertex 1.74 0.97 0.24
vertex 1.74 0.96 0.37
vertex 1.79 0.98 0.21
endloop
endfacet
facet normal 0.01 -1 -0.06
outer loop
vertex -1.47 0.75 0.02
vertex -1.5 0.74 0.07
vertex -1.64 0.74 0.05
endloop
endfacet
facet normal -0.26 0.91 0.33
outer loop
vertex 1.79 0.98 0.21
vertex 1.56 0.98 0.03
vertex 1.65 0.97 0.12
endloop
endfacet
facet normal -0.08 0.98 0.15
outer loop
vertex 1.56 0.98 0.03
vertex 1.5 0.96 0.09
vertex 1.65 0.97 0.12
endloop
endfacet
facet normal -0.53 0.42 0.74
outer loop
vertex 1.25 0.96 0.58
vertex 1.35 0.96 0.65
vertex 1.29 0.97 0.59
endloop
endfacet
facet normal -0.77 -0.47 -0.42
outer loop
vertex -1.76 0.76 0.13
vertex -1.77 0.75 0.15
vertex -1.82 0.76 0.22
endloop
endfacet
facet normal 0.71 0.03 -0.7
outer loop
vertex -1.24 0.76 0.13
vertex -1.29 0.76 0.08
vertex -1.29 0.97 0.08
endloop
endfacet
facet normal -0.47 -0.87 -0.15
outer loop
vertex -1.77 0.75 0.15
vertex -1.82 0.74 0.33
vertex -1.82 0.76 0.22
endloop
endfacet
facet normal -0.68 0.72 0.13
outer loop
vertex -1.81 -0.74 0.37
vertex -1.84 -0.76 0.34
vertex -1.82 -0.76 0.46
endloop
endfacet
facet normal -0.57 0 0.82
outer loop
vertex 1.35 0.96 0.65
vertex 1.25 0.96 0.58
vertex 1.35 0.76 0.64
endloop
endfacet
facet normal -0.62 -0.03 0.78
outer loop
vertex 1.25 0.96 0.58
vertex 1.25 0.75 0.57
vertex 1.35 0.76 0.64
endloop
endfacet
facet normal 0.1 -0.98 0.14
outer loop
vertex -1.73 -0.96 0.24
vertex -1.77 -0.98 0.17
vertex -1.63 -0.97 0.11
endloop
endfacet
facet normal 0.88 0.05 -0.46
outer loop
vertex 1.83 -0.76 0.25
vertex 1.81 -0.96 0.2
vertex 1.77 -0.75 0.13
endloop
endfacet
facet normal 0.98 -0.02 -0.21
outer loop
vertex -1.75 -0.76 0.34
vertex -1.72 -0.76 0.45
vertex -1.74 -0.96 0.37
endloop
endfacet
facet normal -0.09 -0.99 0.06
outer loop
vertex -1.26 -0.97 0.24
vertex -1.33 -0.97 0.14
vertex -1.21 -0.98 0.21
endloop
endfacet
facet normal 0.77 -0.63 -0.08
outer loop
vertex -1.74 0.76 0.41
vertex -1.76 0.75 0.28
vertex -1.74 0.76 0.3
endloop
endfacet
facet normal 0.69 0.73 0.02
outer loop
vertex -1.18 -0.75 0.43
vertex -1.17 -0.76 0.3
vertex -1.18 -0.74 0.32
endloop
endfacet
facet normal 0.49 -0.83 0.27
outer loop
vertex -1.76 0.75 0.28
vertex -1.68 0.76 0.17
vertex -1.74 0.76 0.3
endloop
endfacet
facet normal -0.87 0 -0.49
outer loop
vertex 1.2 -0.75 0.2
vertex 1.23 -0.76 0.13
vertex 1.19 -0.96 0.21
endloop
endfacet
facet normal 0.13 -0.01 -0.99
outer loop
vertex -1.4 -0.96 0.01
vertex -1.51 -0.96 0
vertex -1.45 -0.76 0.01
endloop
endfacet
facet normal 0.67 0.65 0.37
outer loop
vertex -1.68 0.96 0.17
vertex -1.67 0.97 0.13
vertex -1.74 0.96 0.29
endloop
endfacet
facet normal 0.56 0.76 0.33
outer loop
vertex -1.67 0.97 0.13
vertex -1.76 0.97 0.29
vertex -1.74 0.96 0.29
endloop
endfacet
facet normal 0.23 -0.58 -0.78
outer loop
vertex 1.52 0.75 0.6
vertex 1.33 0.75 0.55
vertex 1.37 0.76 0.55
endloop
endfacet
facet normal -0.28 -0.86 0.43
outer loop
vertex -1.75 -0.97 0.56
vertex -1.61 -0.98 0.63
vertex -1.67 -0.96 0.63
endloop
endfacet
facet normal 0.75 -0.57 0.34
outer loop
vertex -1.65 0.98 0.06
vertex -1.81 0.98 0.41
vertex -1.76 0.97 0.29
endloop
endfacet
facet normal -0.76 0.02 -0.65
outer loop
vertex -1.36 -0.76 0.55
vertex -1.28 -0.76 0.44
vertex -1.27 -0.96 0.43
endloop
endfacet
facet normal 0.45 -0.57 -0.68
outer loop
vertex 2.42 -0.98 0.42
vertex 2.42 -0.78 0.25
vertex 2.48 -0.93 0.42
endloop
endfacet
facet normal -0.84 -0.04 0.54
outer loop
vertex -1.82 -0.96 0.45
vertex -1.75 -0.97 0.56
vertex -1.76 -0.76 0.56
endloop
endfacet
facet normal 0.33 0.02 0.94
outer loop
vertex 1.58 0.76 0.67
vertex 1.66 0.96 0.64
vertex 1.56 0.96 0.67
endloop
endfacet
facet normal -0.09 0.99 -0.1
outer loop
vertex 1.58 -0.74 0.65
vertex 1.79 -0.74 0.47
vertex 1.59 -0.75 0.59
endloop
endfacet
facet normal -0.37 -0.01 0.93
outer loop
vertex -1.57 -0.96 0.67
vertex -1.57 -0.76 0.67
vertex -1.67 -0.96 0.63
endloop
endfacet
facet normal -0.36 -0.01 0.93
outer loop
vertex -1.57 -0.76 0.67
vertex -1.67 -0.76 0.63
vertex -1.67 -0.96 0.63
endloop
endfacet
facet normal -0.15 0.97 -0.18
outer loop
vertex -1.44 0.98 0.65
vertex -1.2 0.98 0.44
vertex -1.26 0.97 0.46
endloop
endfacet
facet normal -0.23 0.94 -0.25
outer loop
vertex -1.43 0.96 0.57
vertex -1.44 0.98 0.65
vertex -1.26 0.97 0.46
endloop
endfacet
facet normal -0.26 -0.71 0.65
outer loop
vertex -1.67 -0.96 0.63
vertex -1.61 -0.98 0.63
vertex -1.57 -0.96 0.67
endloop
endfacet
facet normal -0.67 0.04 -0.74
outer loop
vertex -1.77 -0.76 0.13
vertex -1.68 -0.76 0.05
vertex -1.7 -0.91 0.06
endloop
endfacet
facet normal -0.02 -0.7 0.71
outer loop
vertex -1.57 -0.96 0.67
vertex -1.47 -0.98 0.66
vertex -1.46 -0.96 0.68
endloop
endfacet
facet normal -0.85 -0.02 0.52
outer loop
vertex 1.25 0.75 0.57
vertex 1.25 0.96 0.58
vertex 1.18 0.96 0.46
endloop
endfacet
facet normal 0 -0.84 0.54
outer loop
vertex 1.42 0.74 0.65
vertex 1.58 0.76 0.67
vertex 1.47 0.76 0.68
endloop
endfacet
facet normal -0.08 -0.85 0.52
outer loop
vertex -1.61 -0.98 0.63
vertex -1.47 -0.98 0.66
vertex -1.57 -0.96 0.67
endloop
endfacet
facet normal 0.86 -0.05 0.5
outer loop
vertex 2.32 -0.86 1.18
vertex 2.32 -0.97 1.16
vertex 2.42 -0.84 1
endloop
endfacet
facet normal 0.91 -0.05 0.42
outer loop
vertex 2.42 -0.96 0.99
vertex 2.48 -0.93 0.86
vertex 2.42 -0.84 1
endloop
endfacet
facet normal 0.91 -0.04 0.41
outer loop
vertex 2.48 -0.93 0.86
vertex 2.48 -0.78 0.88
vertex 2.42 -0.84 1
endloop
endfacet
facet normal 0.2 -0.83 0.52
outer loop
vertex -1.47 -0.98 0.66
vertex -1.3 -0.97 0.61
vertex -1.37 -0.96 0.65
endloop
endfacet
facet normal 0.75 0 0.66
outer loop
vertex -1.72 -0.76 0.23
vertex -1.73 -0.96 0.24
vertex -1.63 -0.96 0.13
endloop
endfacet
facet normal 0.24 0.66 0.71
outer loop
vertex 1.59 0.98 0.64
vertex 1.56 0.96 0.67
vertex 1.66 0.96 0.64
endloop
endfacet
facet normal 0.09 -0.99 0.13
outer loop
vertex -1.47 -0.98 0.66
vertex -1.22 -0.98 0.48
vertex -1.3 -0.97 0.61
endloop
endfacet
facet normal -0.23 0.8 0.56
outer loop
vertex -1.67 -0.76 0.63
vertex -1.57 -0.76 0.67
vertex -1.56 -0.74 0.65
endloop
endfacet
facet normal -0.07 -0.02 -1
outer loop
vertex -1.47 0.76 0
vertex -1.57 0.76 0.01
vertex -1.54 0.96 0
endloop
endfacet
facet normal 0.49 -0.85 -0.21
outer loop
vertex 1.25 0.96 0.36
vertex 1.31 0.96 0.5
vertex 1.27 0.96 0.42
endloop
endfacet
facet normal 0.98 0.02 -0.18
outer loop
vertex 1.84 0.76 0.34
vertex 1.82 0.76 0.22
vertex 1.84 0.96 0.35
endloop
endfacet
facet normal -0.4 -0.41 -0.82
outer loop
vertex -1.35 -0.96 0.54
vertex -1.48 -0.97 0.6
vertex -1.43 -0.96 0.57
endloop
endfacet
facet normal -0.3 -0.86 0.41
outer loop
vertex -1.47 -0.98 0.03
vertex -1.21 -0.98 0.21
vertex -1.33 -0.97 0.14
endloop
endfacet
facet normal 0.05 1 0.06
outer loop
vertex -1.44 0.98 0.65
vertex -1.3 0.97 0.6
vertex -1.2 0.98 0.44
endloop
endfacet
facet normal -0.39 -0.03 -0.92
outer loop
vertex 1.54 0.96 0.58
vertex 1.65 0.96 0.53
vertex 1.63 0.76 0.55
endloop
endfacet
facet normal -0.02 -0.86 -0.51
outer loop
vertex 0.95 0.87 1.8
vertex 1.33 0.87 1.79
vertex 1.34 0.87 1.79
endloop
endfacet
facet normal 0.44 -0.83 0.34
outer loop
vertex -1.3 -0.97 0.61
vertex -1.22 -0.98 0.48
vertex -1.24 -0.96 0.56
endloop
endfacet
facet normal -0.77 -0.02 -0.64
outer loop
vertex 1.65 0.96 0.53
vertex 1.71 0.96 0.46
vertex 1.68 0.76 0.51
endloop
endfacet
facet normal -0.66 -0.58 0.48
outer loop
vertex -1.33 -0.97 0.14
vertex -1.26 -0.97 0.24
vertex -1.31 -0.96 0.19
endloop
endfacet
facet normal -0.31 -0.03 0.95
outer loop
vertex 1.33 -0.96 0.63
vertex 1.47 -0.96 0.68
vertex 1.43 -0.76 0.67
endloop
endfacet
facet normal 0.55 -0.82 0.16
outer loop
vertex -1.22 -0.98 0.48
vertex -1.18 -0.97 0.37
vertex -1.18 -0.96 0.46
endloop
endfacet
facet normal -0.98 0.01 0.18
outer loop
vertex 1.18 0.96 0.46
vertex 1.16 0.96 0.34
vertex 1.17 0.76 0.43
endloop
endfacet
facet normal 0.64 0.74 -0.21
outer loop
vertex -1.17 -0.76 0.3
vertex -1.21 -0.76 0.17
vertex -1.22 -0.74 0.2
endloop
endfacet
facet normal -0.94 -0.02 -0.35
outer loop
vertex 1.71 0.96 0.46
vertex 1.74 0.96 0.37
vertex 1.73 0.76 0.42
endloop
endfacet
facet normal 0 0.98 -0.2
outer loop
vertex 1.43 -0.74 0.65
vertex 1.58 -0.74 0.65
vertex 1.42 -0.76 0.57
endloop
endfacet
facet normal 0.33 0.04 -0.94
outer loop
vertex -1.45 -0.76 0.01
vertex -1.32 -0.76 0.05
vertex -1.4 -0.96 0.01
endloop
endfacet
facet normal -0.65 0.24 -0.72
outer loop
vertex 1.75 0.75 0.44
vertex 1.63 0.76 0.55
vertex 1.68 0.76 0.51
endloop
endfacet
facet normal 0.54 -0.84 -0.08
outer loop
vertex -1.18 -0.97 0.37
vertex -1.21 -0.98 0.21
vertex -1.16 -0.96 0.34
endloop
endfacet
facet normal 0 0.99 -0.13
outer loop
vertex 1.52 0.97 0.6
vertex 1.59 0.98 0.64
vertex 1.65 0.96 0.53
endloop
endfacet
facet normal -0.41 0.84 -0.34
outer loop
vertex 1.59 0.98 0.64
vertex 1.75 0.98 0.45
vertex 1.65 0.96 0.53
endloop
endfacet
facet normal -0.48 0.75 -0.45
outer loop
vertex 1.65 0.96 0.53
vertex 1.75 0.98 0.45
vertex 1.71 0.96 0.46
endloop
endfacet
facet normal -0.99 0.04 -0.1
outer loop
vertex 1.74 0.96 0.37
vertex 1.74 0.76 0.3
vertex 1.73 0.76 0.42
endloop
endfacet
facet normal 0.64 -0.76 -0.13
outer loop
vertex -1.18 -0.96 0.22
vertex -1.16 -0.96 0.34
vertex -1.21 -0.98 0.21
endloop
endfacet
facet normal -0.42 -0.87 -0.25
outer loop
vertex 1.75 0.75 0.44
vertex 1.68 0.76 0.51
vertex 1.73 0.76 0.42
endloop
endfacet
facet normal 0.98 -0.02 -0.18
outer loop
vertex -1.16 -0.96 0.34
vertex -1.18 -0.96 0.22
vertex -1.17 -0.76 0.3
endloop
endfacet
facet normal 0.51 0.01 -0.86
outer loop
vertex 1.61 -0.76 0.02
vertex 1.69 -0.75 0.07
vertex 1.73 -0.96 0.09
endloop
endfacet
facet normal 1 0 0.02
outer loop
vertex -1.85 0.8 0.24
vertex -1.86 1 0.42
vertex -1.86 -1 0.42
endloop
endfacet
facet normal -0.44 -0.88 0.19
outer loop
vertex -1.26 -0.97 0.24
vertex -1.26 -0.96 0.3
vertex -1.31 -0.96 0.19
endloop
endfacet
facet normal 0.24 0 -0.97
outer loop
vertex -1.37 0.76 0.02
vertex -1.47 0.76 0
vertex -1.39 0.96 0.02
endloop
endfacet
facet normal 0.67 0 -0.74
outer loop
vertex -1.24 -0.96 0.12
vertex -1.32 -0.95 0.05
vertex -1.32 -0.76 0.05
endloop
endfacet
facet normal 0.63 -0.69 -0.37
outer loop
vertex -1.18 -0.96 0.22
vertex -1.21 -0.98 0.21
vertex -1.24 -0.96 0.12
endloop
endfacet
facet normal 0.44 -0.83 -0.34
outer loop
vertex -1.21 -0.98 0.21
vertex -1.3 -0.97 0.08
vertex -1.24 -0.96 0.12
endloop
endfacet
facet normal -0.07 -0.01 1
outer loop
vertex -1.57 -0.76 0.67
vertex -1.57 -0.96 0.67
vertex -1.46 -0.96 0.68
endloop
endfacet
facet normal -0.57 0.05 0.82
outer loop
vertex -1.39 -0.76 0.12
vertex -1.42 -0.96 0.11
vertex -1.31 -0.96 0.19
endloop
endfacet
facet normal 0.63 0.51 -0.59
outer loop
vertex -1.21 -0.76 0.17
vertex -1.32 -0.76 0.05
vertex -1.3 -0.75 0.08
endloop
endfacet
facet normal -0.25 -0.9 0.36
outer loop
vertex -1.31 -0.96 0.19
vertex -1.42 -0.96 0.11
vertex -1.33 -0.97 0.14
endloop
endfacet
facet normal 0.27 -0.78 0.57
outer loop
vertex 1.58 0.76 0.67
vertex 1.68 0.74 0.6
vertex 1.67 0.76 0.63
endloop
endfacet
facet normal -0.45 0.82 -0.34
outer loop
vertex 1.2 -0.75 0.2
vertex 1.29 -0.74 0.11
vertex 1.23 -0.76 0.13
endloop
endfacet
facet normal 0.57 -0.52 -0.64
outer loop
vertex -1.32 -0.95 0.05
vertex -1.24 -0.96 0.12
vertex -1.3 -0.97 0.08
endloop
endfacet
facet normal 0.66 0.05 -0.75
outer loop
vertex 1.69 -0.75 0.07
vertex 1.77 -0.75 0.13
vertex 1.73 -0.96 0.09
endloop
endfacet
facet normal 0.2 0.8 -0.56
outer loop
vertex -1.32 -0.76 0.05
vertex -1.45 -0.76 0.01
vertex -1.47 -0.74 0.02
endloop
endfacet
facet normal 0.97 -0.02 -0.23
outer loop
vertex 1.84 -0.96 0.31
vertex 1.81 -0.96 0.2
vertex 1.83 -0.76 0.25
endloop
endfacet
facet normal 0.3 -0.73 -0.62
outer loop
vertex -1.3 -0.97 0.08
vertex -1.4 -0.96 0.01
vertex -1.32 -0.95 0.05
endloop
endfacet
facet normal 0.29 0.9 0.33
outer loop
vertex -1.61 -0.75 0.1
vertex -1.71 -0.75 0.2
vertex -1.58 -0.76 0.11
endloop
endfacet
facet normal 0.04 -0.9 0.43
outer loop
vertex 1.5 -0.97 0.07
vertex 1.55 -0.96 0.1
vertex 1.41 -0.96 0.11
endloop
endfacet
facet normal -0.32 -0.17 0.93
outer loop
vertex -1.42 -0.96 0.11
vertex -1.47 -0.97 0.09
vertex -1.33 -0.97 0.14
endloop
endfacet
facet normal -0.09 0.97 -0.23
outer loop
vertex -1.47 -0.74 0.02
vertex -1.58 -0.75 0.01
vertex -1.73 -0.74 0.12
endloop
endfacet
facet normal -0.98 0.01 -0.18
outer loop
vertex 1.16 0.96 0.34
vertex 1.18 0.96 0.22
vertex 1.17 0.76 0.3
endloop
endfacet
facet normal -0.08 -1 0.05
outer loop
vertex 1.77 -0.97 0.29
vertex 1.67 -0.97 0.13
vertex 1.75 -0.98 0.15
endloop
endfacet
facet normal -0.11 -0.99 0.05
outer loop
vertex 1.75 -0.98 0.15
vertex 1.81 -0.98 0.27
vertex 1.77 -0.97 0.29
endloop
endfacet
facet normal 0.67 0.04 0.74
outer loop
vertex 1.76 0.76 0.56
vertex 1.78 0.96 0.53
vertex 1.66 0.96 0.64
endloop
endfacet
facet normal 0.06 0.63 0.78
outer loop
vertex -1.47 -0.76 0.09
vertex -1.61 -0.75 0.1
vertex -1.58 -0.76 0.11
endloop
endfacet
facet normal 0.26 0.97 0
outer loop
vertex 1.81 0.97 0.45
vertex 1.84 0.96 0.35
vertex 1.79 0.98 0.21
endloop
endfacet
facet normal 0.07 1 0.01
outer loop
vertex 1.79 0.98 0.21
vertex 1.75 0.98 0.45
vertex 1.81 0.97 0.45
endloop
endfacet
facet normal -0.51 0.64 -0.57
outer loop
vertex -1.68 -0.76 0.05
vertex -1.77 -0.76 0.13
vertex -1.73 -0.74 0.12
endloop
endfacet
facet normal -0.15 -0.68 -0.72
outer loop
vertex -1.63 -0.96 0.03
vertex -1.51 -0.96 0
vertex -1.63 -0.97 0.04
endloop
endfacet
facet normal -0.07 -0.83 -0.56
outer loop
vertex -1.51 -0.96 0
vertex -1.47 -0.98 0.03
vertex -1.63 -0.97 0.04
endloop
endfacet
facet normal -0.22 -0.01 -0.98
outer loop
vertex -1.63 -0.96 0.03
vertex -1.58 -0.75 0.01
vertex -1.51 -0.96 0
endloop
endfacet
facet normal -0.9 0.04 0.44
outer loop
vertex 1.69 0.76 0.18
vertex 1.74 0.76 0.3
vertex 1.73 0.96 0.25
endloop
endfacet
facet normal 0.01 0 -1
outer loop
vertex -2.04 0.81 1.85
vertex -2.04 -0.81 1.85
vertex -2.2 -0.81 1.85
endloop
endfacet
facet normal 0.64 -0.76 -0.12
outer loop
vertex 1.84 0.76 0.34
vertex 1.83 0.75 0.36
vertex 1.82 0.76 0.22
endloop
endfacet
facet normal 0.55 -0.83 -0.12
outer loop
vertex 1.83 0.75 0.36
vertex 1.78 0.74 0.2
vertex 1.82 0.76 0.22
endloop
endfacet
facet normal -0.09 0.96 0.26
outer loop
vertex 1.29 0.97 0.59
vertex 1.44 0.96 0.67
vertex 1.31 0.98 0.58
endloop
endfacet
facet normal 0.09 -0.85 0.52
outer loop
vertex -1.63 -0.97 0.11
vertex -1.47 -0.97 0.09
vertex -1.63 -0.96 0.13
endloop
endfacet
facet normal -0.77 0.62 -0.15
outer loop
vertex -1.82 -0.76 0.22
vertex -1.84 -0.76 0.34
vertex -1.81 -0.75 0.26
endloop
endfacet
facet normal 0.24 0.04 0.97
outer loop
vertex -1.58 -0.76 0.11
vertex -1.63 -0.96 0.13
vertex -1.47 -0.97 0.09
endloop
endfacet
facet normal -0.43 -0.68 -0.59
outer loop
vertex -1.63 -0.96 0.03
vertex -1.63 -0.97 0.04
vertex -1.76 -0.96 0.12
endloop
endfacet
facet normal -0.34 -0.85 -0.4
outer loop
vertex -1.63 -0.97 0.04
vertex -1.77 -0.98 0.17
vertex -1.76 -0.96 0.12
endloop
endfacet
facet normal 0.69 -0.02 -0.72
outer loop
vertex 1.77 0.76 0.13
vertex 1.69 0.76 0.06
vertex 1.74 0.96 0.1
endloop
endfacet
facet normal -0.46 0.81 0.36
outer loop
vertex 1.74 0.97 0.24
vertex 1.65 0.97 0.12
vertex 1.73 0.96 0.25
endloop
endfacet
facet normal -0.35 0.08 -0.93
outer loop
vertex 1.44 0.96 0.01
vertex 1.32 0.9 0.05
vertex 1.33 0.97 0.05
endloop
endfacet
facet normal -0.99 -0.02 -0.13
outer loop
vertex -1.83 -0.97 0.33
vertex -1.84 -0.76 0.34
vertex -1.82 -0.96 0.24
endloop
endfacet
facet normal -0.98 0.01 -0.18
outer loop
vertex -1.84 -0.76 0.34
vertex -1.82 -0.76 0.22
vertex -1.82 -0.96 0.24
endloop
endfacet
facet normal -0.26 -0.89 -0.36
outer loop
vertex -1.22 -0.98 0.48
vertex -1.47 -0.98 0.66
vertex -1.35 -0.96 0.54
endloop
endfacet
facet normal -0.14 -0.99 -0.05
outer loop
vertex -1.24 -0.97 0.4
vertex -1.22 -0.98 0.48
vertex -1.35 -0.96 0.54
endloop
endfacet
facet normal 0.02 -0.99 -0.11
outer loop
vertex -1.47 -0.98 0.66
vertex -1.48 -0.97 0.6
vertex -1.35 -0.96 0.54
endloop
endfacet
facet normal 0.49 -0.78 0.4
outer loop
vertex -1.63 -0.97 0.11
vertex -1.63 -0.96 0.13
vertex -1.73 -0.96 0.24
endloop
endfacet
facet normal -0.09 1 -0.02
outer loop
vertex 1.79 -0.74 0.47
vertex 1.81 -0.74 0.37
vertex 1.72 -0.75 0.48
endloop
endfacet
facet normal -0.1 0.99 -0.03
outer loop
vertex 1.72 -0.75 0.48
vertex 1.81 -0.74 0.37
vertex 1.76 -0.75 0.33
endloop
endfacet
facet normal -0.55 0.76 0.35
outer loop
vertex 1.18 0.96 0.46
vertex 1.25 0.96 0.58
vertex 1.29 0.97 0.59
endloop
endfacet
facet normal -0.29 -0.03 0.96
outer loop
vertex 1.5 0.96 0.09
vertex 1.52 0.76 0.09
vertex 1.58 0.76 0.11
endloop
endfacet
facet normal 0.97 0 0.23
outer loop
vertex -1.71 -0.75 0.2
vertex -1.75 -0.76 0.34
vertex -1.72 -0.76 0.23
endloop
endfacet
facet normal -0.24 -0.9 0.36
outer loop
vertex 1.69 0.76 0.18
vertex 1.58 0.76 0.11
vertex 1.65 0.74 0.11
endloop
endfacet
facet normal -0.7 0.67 0.24
outer loop
vertex 1.17 -0.76 0.4
vertex 1.2 -0.76 0.49
vertex 1.2 -0.74 0.44
endloop
endfacet
facet normal 0.61 0.02 -0.79
outer loop
vertex 1.66 0.96 0.04
vertex 1.74 0.96 0.1
vertex 1.69 0.76 0.06
endloop
endfacet
facet normal -0.71 -0.59 -0.38
outer loop
vertex -1.76 -0.96 0.12
vertex -1.77 -0.98 0.17
vertex -1.82 -0.96 0.24
endloop
endfacet
facet normal 0.58 0.01 0.82
outer loop
vertex 1.32 -0.76 0.17
vertex 1.32 -0.96 0.18
vertex 1.41 -0.96 0.11
endloop
endfacet
facet normal 0.06 -1 -0.08
outer loop
vertex 1.78 0.74 0.2
vertex 1.65 0.74 0.11
vertex 1.7 0.75 0.08
endloop
endfacet
facet normal 0.86 0.05 0.5
outer loop
vertex 2.32 0.97 1.16
vertex 2.32 0.86 1.18
vertex 2.42 0.84 1
endloop
endfacet
facet normal 0.91 0.04 0.41
outer loop
vertex 2.42 0.84 1
vertex 2.48 0.78 0.88
vertex 2.48 0.93 0.86
endloop
endfacet
facet normal 0.91 0.05 0.42
outer loop
vertex 2.48 0.93 0.86
vertex 2.42 0.96 0.99
vertex 2.42 0.84 1
endloop
endfacet
facet normal -0.02 -1 0.01
outer loop
vertex -2.48 0.61 1.22
vertex -2.47 0.61 1.22
vertex -2.21 0.61 1.67
endloop
endfacet
facet normal 0.86 0 0.51
outer loop
vertex 1.14 0.82 1.3
vertex 1.14 -0.82 1.31
vertex 1.24 -0.81 1.13
endloop
endfacet
facet normal 0.16 -0.96 0.22
outer loop
vertex 2.32 0.86 1.18
vertex 2.2 0.87 1.29
vertex 2.31 0.81 0.94
endloop
endfacet
facet normal 0.01 -0.97 0.26
outer loop
vertex 2.2 0.87 1.29
vertex 1.21 0.87 1.33
vertex 1.24 0.81 1.13
endloop
endfacet
facet normal 0.01 -0.16 0.99
outer loop
vertex -2.39 -0.86 1.36
vertex -2.39 -0.95 1.35
vertex 1.21 -0.87 1.33
endloop
endfacet
facet normal 0.01 -0.07 1
outer loop
vertex -2.39 -0.95 1.35
vertex 2.05 -0.95 1.32
vertex 1.21 -0.87 1.33
endloop
endfacet
facet normal 0 -0.11 0.99
outer loop
vertex 2.05 -0.95 1.32
vertex 2.05 -0.87 1.33
vertex 1.21 -0.87 1.33
endloop
endfacet
facet normal 0.01 0.97 0.26
outer loop
vertex 1.24 -0.81 1.13
vertex 1.21 -0.87 1.33
vertex 2.2 -0.87 1.29
endloop
endfacet
facet normal 0.16 0.96 0.22
outer loop
vertex 2.2 -0.87 1.29
vertex 2.32 -0.86 1.18
vertex 2.31 -0.81 0.94
endloop
endfacet
facet normal 0.22 0.69 0.69
outer loop
vertex 2.5 0.65 0.55
vertex 2.5 0.64 0.55
vertex 2.51 0.64 0.55
endloop
endfacet
facet normal -1 0 0.03
outer loop
vertex -2.43 0.93 1.29
vertex -2.43 -0.93 1.29
vertex -2.43 0.8 1.3
endloop
endfacet
facet normal -1 0 0.01
outer loop
vertex -2.43 -0.8 1.3
vertex -2.43 0.8 1.3
vertex -2.43 -0.93 1.29
endloop
endfacet
facet normal -0.28 0.96 -0.02
outer loop
vertex -2.47 0.98 0.42
vertex -2.49 0.98 0.69
vertex -2.39 1.01 0.69
endloop
endfacet
facet normal 0.02 0 1
outer loop
vertex 0.98 0.79 1.79
vertex -2.06 0.79 1.86
vertex -2.06 -0.79 1.86
endloop
endfacet
facet normal 0.01 0.66 -0.75
outer loop
vertex 2.32 1 0.42
vertex 2.32 0.79 0.24
vertex 1.85 0.8 0.24
endloop
endfacet
facet normal 0.01 0.66 -0.75
outer loop
vertex 1.86 1 0.42
vertex 2.32 1 0.42
vertex 1.85 0.8 0.24
endloop
endfacet
facet normal -0.02 0 -1
outer loop
vertex -2.39 -0.79 0.25
vertex -2.39 0.79 0.25
vertex -1.85 0.8 0.24
endloop
endfacet
facet normal -0.02 0 -1
outer loop
vertex -1.85 0.8 0.24
vertex -1.85 -0.8 0.25
vertex -2.39 -0.79 0.25
endloop
endfacet
facet normal 0 0 -1
outer loop
vertex 1.15 0.8 0.24
vertex 1.15 -0.8 0.24
vertex -1.15 0.8 0.24
endloop
endfacet
facet normal 0.96 -0.28 -0.01
outer loop
vertex 2.48 -0.93 0.86
vertex 2.48 -0.93 0.42
vertex 2.51 -0.84 0.41
endloop
endfacet
facet normal -0.53 -0.83 -0.18
outer loop
vertex 1.22 -0.97 0.16
vertex 1.19 -0.98 0.29
vertex 1.19 -0.96 0.21
endloop
endfacet
facet normal 0 -1 -0.04
outer loop
vertex 1.37 -1.02 0.69
vertex -1.38 -1.02 0.69
vertex -1.22 -1.01 0.59
endloop
endfacet
facet normal 0 -1 -0.04
outer loop
vertex 1.22 -1.01 0.57
vertex 1.37 -1.02 0.69
vertex -1.22 -1.01 0.59
endloop
endfacet
facet normal 0 -1 -0.05
outer loop
vertex 1.22 -1.01 0.57
vertex -1.22 -1.01 0.59
vertex -1.14 -1 0.42
endloop
endfacet
facet normal 0.17 -0.7 0.69
outer loop
vertex -1.47 -0.98 0.66
vertex -1.37 -0.96 0.65
vertex -1.46 -0.96 0.68
endloop
endfacet
facet normal -0.23 0.97 -0.05
outer loop
vertex -1.78 0.97 0.17
vertex -1.83 0.97 0.27
vertex -1.81 0.98 0.41
endloop
endfacet
facet normal -0.02 1 -0.05
outer loop
vertex -2.39 0.99 0.42
vertex -2.39 1.01 0.69
vertex -1.86 1 0.42
endloop
endfacet
facet normal -0.02 1 -0.04
outer loop
vertex -1.78 1.01 0.58
vertex -1.86 1 0.42
vertex -2.39 1.01 0.69
endloop
endfacet
facet normal -0.01 1 -0.02
outer loop
vertex -2.39 1.01 0.69
vertex -1.65 1.02 0.67
vertex -1.78 1.01 0.58
endloop
endfacet
facet normal 0.94 0 0.33
outer loop
vertex 2.48 -0.78 0.88
vertex 2.51 -0.84 0.81
vertex 2.51 0.84 0.81
endloop
endfacet
facet normal 0.01 1 -0.04
outer loop
vertex 2.39 1.01 0.67
vertex 2.32 1 0.42
vertex 1.86 1 0.42
endloop
endfacet
facet normal 0.01 1 0.02
outer loop
vertex 1.71 1.01 0.64
vertex 1.55 1.01 0.7
vertex 2.39 1.01 0.67
endloop
endfacet
facet normal 0.02 1 -0.05
outer loop
vertex 2.39 1.01 0.67
vertex 1.86 1 0.42
vertex 1.8 1.01 0.55
endloop
endfacet
facet normal -0.02 0.64 -0.77
outer loop
vertex -2.39 0.79 0.25
vertex -2.39 0.99 0.42
vertex -1.85 0.8 0.24
endloop
endfacet
facet normal -0.01 0.66 -0.75
outer loop
vertex -2.39 0.99 0.42
vertex -1.86 1 0.42
vertex -1.85 0.8 0.24
endloop
endfacet
facet normal -0.28 0.96 0.07
outer loop
vertex -2.39 1.01 0.69
vertex -2.49 0.98 0.69
vertex -2.47 0.94 1.21
endloop
endfacet
facet normal 0.94 0.03 0.35
outer loop
vertex 2.51 0.84 0.81
vertex 2.48 0.93 0.86
vertex 2.48 0.78 0.88
endloop
endfacet
facet normal -0.29 0.58 -0.76
outer loop
vertex -2.47 0.78 0.27
vertex -2.47 0.98 0.42
vertex -2.39 0.79 0.25
endloop
endfacet
facet normal -0.98 0.19 0.01
outer loop
vertex -2.5 0.95 0.42
vertex -2.51 0.87 0.42
vertex -2.49 0.98 0.69
endloop
endfacet
facet normal -0.98 0.19 0.01
outer loop
vertex -2.51 0.87 0.42
vertex -2.51 0.85 0.98
vertex -2.49 0.98 0.69
endloop
endfacet
facet normal -0.77 0.34 -0.54
outer loop
vertex -2.49 0.76 0.3
vertex -2.5 0.95 0.42
vertex -2.47 0.78 0.27
endloop
endfacet
facet normal -0.4 -0.64 -0.66
outer loop
vertex -1.43 0.96 0.57
vertex -1.26 0.97 0.46
vertex -1.35 0.96 0.53
endloop
endfacet
facet normal 1 0 0
outer loop
vertex 2.51 -0.84 0.41
vertex 2.51 0.69 0.36
vertex 2.51 0.84 0.81
endloop
endfacet
facet normal 1 0 0
outer loop
vertex 2.51 0.69 0.36
vertex 2.51 0.85 0.43
vertex 2.51 0.84 0.81
endloop
endfacet
facet normal 1 0 0
outer loop
vertex 2.51 0.84 0.81
vertex 2.51 -0.84 0.81
vertex 2.51 -0.84 0.41
endloop
endfacet
facet normal -1 0 0
outer loop
vertex -2.51 0.87 0.42
vertex -2.51 -0.87 0.43
vertex -2.51 -0.85 0.98
endloop
endfacet
facet normal -1 0 0
outer loop
vertex -2.51 -0.85 0.98
vertex -2.51 0.85 0.98
vertex -2.51 0.87 0.42
endloop
endfacet
facet normal 0.4 -0.81 0.42
outer loop
vertex 1.68 -0.98 0.6
vertex 1.76 -0.97 0.53
vertex 1.72 -0.96 0.59
endloop
endfacet
facet normal -0.7 0 -0.72
outer loop
vertex 1.79 -1.01 0.57
vertex 1.71 1.01 0.64
vertex 1.8 1.01 0.55
endloop
endfacet
facet normal -0.58 0 -0.81
outer loop
vertex -1.22 -1.01 0.59
vertex -1.37 1.02 0.69
vertex -1.22 1.01 0.58
endloop
endfacet
facet normal 0.58 -0.04 -0.82
outer loop
vertex 1.31 0.96 0.5
vertex 1.41 0.96 0.57
vertex 1.37 0.76 0.55
endloop
endfacet
facet normal 0.12 -0.03 0.99
outer loop
vertex -1.47 -0.97 0.09
vertex -1.47 -0.76 0.09
vertex -1.58 -0.76 0.11
endloop
endfacet
facet normal -0.91 0 -0.41
outer loop
vertex 1.79 -1.01 0.57
vertex 1.8 1.01 0.55
vertex 1.86 1 0.42
endloop
endfacet
facet normal 0.25 0 -0.97
outer loop
vertex -1.67 -1.02 0.67
vertex -1.65 1.02 0.67
vertex -1.53 1.01 0.7
endloop
endfacet
facet normal 0.92 0 -0.4
outer loop
vertex -1.8 -1.01 0.55
vertex -1.86 -1 0.42
vertex -1.86 1 0.42
endloop
endfacet
facet normal -0.98 -0.04 0.17
outer loop
vertex -2.47 -0.94 1.21
vertex -2.51 -0.85 0.98
vertex -2.49 -0.93 1.04
endloop
endfacet
facet normal -0.2 -0.04 0.98
outer loop
vertex 1.6 -0.76 0.11
vertex 1.43 -0.75 0.08
vertex 1.52 -0.76 0.1
endloop
endfacet
facet normal 0.01 -0.45 0.89
outer loop
vertex -2.39 0.81 1.34
vertex 1.14 0.82 1.3
vertex 1.21 0.87 1.33
endloop
endfacet
facet normal 0.35 0.92 -0.15
outer loop
vertex 1.19 0.98 0.3
vertex 1.31 0.98 0.58
vertex 1.25 0.96 0.36
endloop
endfacet
facet normal 0.34 0.93 -0.15
outer loop
vertex 1.31 0.98 0.58
vertex 1.31 0.96 0.5
vertex 1.25 0.96 0.36
endloop
endfacet
facet normal -0.14 0.64 -0.76
outer loop
vertex -2.39 0.79 0.25
vertex -2.47 0.98 0.42
vertex -2.39 0.99 0.42
endloop
endfacet
facet normal -0.8 0 0.6
outer loop
vertex -2.2 -0.75 1.67
vertex -2.06 -0.79 1.86
vertex -2.06 0.79 1.86
endloop
endfacet
facet normal 0.28 -0.88 0.39
outer loop
vertex 1.41 -0.96 0.11
vertex 1.32 -0.96 0.18
vertex 1.36 -0.97 0.12
endloop
endfacet
endsolid solaris_p0
```

[![Open the full Blender model in GitHub's 3D viewer](https://img.shields.io/badge/3D%20viewer-full%20Blender%20model%2C%2033%2C900%20triangles-2a9d8f?style=for-the-badge&logo=blender&logoColor=white)](docs/readme/solaris_p0_vehicle.stl)

<sub>Built by <a href="twin/blender/build_solaris_p0.py">twin/blender/build_solaris_p0.py</a> around the exact facets of the configuration; the shading engine itself uses the facets, not this mesh.</sub>

## Architecture

```mermaid
flowchart LR
    subgraph SRC["Public data"]
        L["USGS 3DEP lidar<br/>5.28 billion points"]
        N["NAIP 2021<br/>near-infrared"]
        O["Overture buildings<br/>OSM roads, bridges"]
        W["NSRDB weather<br/>TMY + 5-min 2023"]
        G["NGS survey marks"]
        M["Mapillary<br/>street panoramas"]
    end
    subgraph GEO["City model (geom_*)"]
        R["0.5 m DSM / DTM / height above ground"]
        C["classes: ground, building, tree"]
        MS["surface mesh + tree mesh<br/>(GLB tiles)"]
    end
    subgraph MOVE["Vehicle in the city"]
        RT["route selection<br/>by sky view factor"]
        SU["SUMO traffic<br/>120 trips, 1 s"]
        PK["5 parking sites"]
        VF["5 facets,<br/>0.25 m samples"]
    end
    subgraph ENG["Shading and PV engine"]
        SH["horizon masks, sky view,<br/>Embree ray casts, tree τ"]
        PV["facet irradiance, Faiman<br/>temperature, mismatch"]
    end
    CM["SOLARIS conference model v1.1.0<br/>hour-by-hour state of charge"]
    EX["experiments E0-E8"]
    P["paper/main.pdf<br/>(macros + figures)"]
    U["Unity 6 + Cesium twin<br/>Google 3D Tiles"]
    X["cross-checks:<br/>SOLWEIG, Mapillary"]

    L --> R
    N --> C
    O --> C
    R --> C --> MS
    G -. "check" .-> R
    O --> RT
    MS --> SH
    RT --> SU --> SH
    PK --> SH
    VF --> SH
    W --> PV
    SH --> PV --> CM --> EX --> P
    MS --> U
    SU --> U
    U -. "E8 agreement" .-> EX
    X -. "E1, E4, E8" .-> EX
    M --> X
```

Python computes every reported number. The Unity twin, SOLWEIG and the Mapillary panoramas are independent checks only.

<details>
<summary>The Snakemake pipeline, stage by stage</summary>

```mermaid
flowchart TB
    subgraph P1["P1 conference baseline"]
        e0["e0_measured: Table B0, 3 cities"]
    end
    subgraph P2["P2 weather"]
        w["weather_tmy, weather_conus_5min, weather_check"]
    end
    subgraph P3["P3 geometry"]
        g1["geom_aoi, geom_lidar_fetch, geom_lidar_rasters, geom_dem"]
        g2["geom_naip, geom_overture, geom_osm, geom_covered"]
        g3["geom_model, geom_freshness, geom_dsm, geom_meshes"]
        g4["geom_enu_origin, geom_ground_control, geom_summary"]
        g1 --> g3
        g2 --> g3 --> g4
    end
    subgraph EXP["P4-P8 experiments"]
        rt["routes_select, sumo_traces"]
        fs["facet_samples"]
        e1["e1_verification"]
        e2["e2_facets"]
        e3["e3_driving"]
        e4["e4_parking"]
        e6["e6_mismatch"]
        e5["e5_annual"]
        e7["e7_facets, e7_inversion"]
        e8["e8_export, e8_unity, e8_twin_agreement,<br/>e8_mapillary_fetch, e8_mapillary_svf"]
        rt --> e3 & e8
        fs --> e2 & e3 & e4
        e3 & e4 --> e6
        e3 & e4 & e6 --> e5
        e5 & e6 --> e7
    end
    paper["paper_macros, paper_figures, paper"]
    P2 --> EXP
    P3 --> EXP
    e0 --> e5
    EXP --> paper
    e0 --> paper
```

</details>

## The model in two equations

The conference model's PV harvest, with the irradiance $G$ replaced by what facet $f$ actually receives:

$$
E_{\mathrm{pv}}=A\,\eta_{\mathrm{pv}}\,\kappa_{\mathrm{pv}}\,\frac{G}{1000}\left[1+\beta\,(T_c-25)\right]
$$

$$
G_f=\bar v_{b,f}\,G_{b,f}+\mathrm{SVF}_f\,G_{d,f}+\bar v_{h,f}\,G_{h,f}+G_{g,f}
$$

The Perez model splits sunlight into beam $G_b$, isotropic sky $G_d$, horizon band $G_h$ and ground reflection $G_g$. $\bar v_{b,f}$ is the mean beam state over the facet's samples (1 if the ray to the sun is clear, $\tau = 0.03$ through tree canopy, 0 behind a building), $\mathrm{SVF}_f$ the facet's cosine-weighted sky view factor with trees counted as partly transparent, and $\bar v_{h,f}$ the same over the lowest 6° of sky. All three view terms are 1 in open sky; on covered road all four terms are 0. Cell temperature follows Faiman, $T_c=T_a+G_f/(u_0+u_1 w)$, with the vehicle speed added to the wind $w$. The conference design equation, extended with a shading factor per archetype and solved for the skin area, stays within 2.6 % of the full simulation (3.3 % if the vehicle mass is held fixed).

## Experiments

<details>
<summary><b>E0 - Reproduce the conference baseline</b> (Phoenix 0.832, Lucknow 0.713, London 0.517)</summary>

The conference code v1.1.0 is kept byte-identical in [`src/solaris/legacy/`](src/solaris/legacy/) (SHA-256 checked by a pre-commit hook), and the refactored core reproduces every output. Table B0 gives self-sufficiency, grid charges, design area and range for three cities on satellite typical years. Code: [`experiments/e0_reproduce/run.py`](experiments/e0_reproduce/run.py).

</details>

<details>
<summary><b>E1 - Verify the shading engine</b> (40 of 40 tests, 98.0-99.3 % agreement with SOLWEIG)</summary>

Engine tests cover sun position, transposition, shadow length and canyon sky view factor. The raster horizon and the mesh ray caster agree on the beam state for 99.6 % of 1,000 points at 43 sun positions, with a mean sky-view difference of 0.008. SOLWEIG shadow maps agree on 98.0-99.3 % of pixels at 12 times. Code: [`experiments/e1_verify/run.py`](experiments/e1_verify/run.py).

<img src="docs/readme/fig_aoi.png" width="70%" alt="Study area map with building and tree heights and the routes coloured by sky view factor">

</details>

<details>
<summary><b>E2 - Facet orientation</b> (the five facets harvest 0.805 of a flat skin)</summary>

The sides are nearly vertical, so they collect far less than a roof of the same area. The five facets harvest 0.805 of the PV energy of the same 11.6 m² laid flat (self-sufficiency 0.836 for the flat skin with Faiman cooling); the thermoelectric and suspension terms do not change. Code: [`experiments/e2_facets/run.py`](experiments/e2_facets/run.py).

<img src="docs/readme/fig_facets.png" width="55%" alt="Paper figure 3: the five-facet skin drawn from two views">

</details>

<details>
<summary><b>E3 - Driving shade</b> (R-DENSE keeps 0.71 of the open-sky energy)</summary>

Every facet sample is shaded once per second along all 120 trips, each driven on 21 March, June, September and December. R-OPEN and R-MIXED lose least; the high-rise core of R-DENSE keeps 0.71 of the open-sky energy, and the two tunnel trips keep 0.67 and 0.79. Code: [`experiments/e3_driving/run.py`](experiments/e3_driving/run.py).

<img src="docs/readme/fig_tod.png" width="55%" alt="Paper figure: driving shade by route and time of day">

</details>

<details>
<summary><b>E4 - Parking shade</b> (P1 0.94, P4 0.88, P5 0.64, P3 0.45, P2 0.32)</summary>

Each site is evaluated every five minutes for a year at four headings (two at the curb). The canyon curb P2 keeps 0.32 of the open-sky energy. SOLWEIG site maps agree on at least 96.7 % of pixels. Code: [`experiments/e4_parking/run.py`](experiments/e4_parking/run.py).

</details>

<details>
<summary><b>E5 - A full year for four archetypes</b> (the loss waterfall)</summary>

| Step | A1 commuter | A2 downtown street | A3 downtown shaded | A4 fleet |
|---|---|---|---|---|
| Conference baseline | 0.832 | 0.832 | 0.832 | 0.419 |
| Facet orientation | 0.677 | 0.678 | 0.676 | 0.345 |
| Parking shade | 0.552 | 0.308 | 0.420 | 0.271 |
| Driving shade (buildings, trees) | 0.542 | 0.290 | 0.402 | 0.261 |
| Electrical mismatch | **0.512** | **0.256** | **0.335** | **0.257** |

A4 drives 100 km/day, so its baseline is lower. Code: [`experiments/e5_annual/run.py`](experiments/e5_annual/run.py).

<img src="docs/readme/fig_waterfall.png" width="75%" alt="Paper figure: self-sufficiency waterfall for the four archetypes">

</details>

<details>
<summary><b>E6 - Electrical mismatch</b> (0.96 in the canyon, 0.56-0.73 under the tree at P3)</summary>

Partial shade costs more than its area: each facet is one module on its own MPPT input with three bypass-diode substrings, and one shaded cell already pushes its substring through the diode. Energy-weighted, the mismatch factor is 0.96 on the R-DENSE trips and at the curb, where whole facets fall into building shadow, but 0.56 to 0.73 in the dappled shade of the tree at P3. Code: [`experiments/e6_mismatch/run.py`](experiments/e6_mismatch/run.py).

<img src="docs/readme/fig_fmm.png" width="55%" alt="Paper figure: mismatch factor against shaded fraction">

</details>

<details>
<summary><b>E7 - Shading-aware design equation</b> (within 2.6 % of the simulation)</summary>

The conference design equation is extended with the archetype's shading factors and solved for the skin area that reaches a target self-sufficiency; a sweep over area (8 to 20 m²), layout (roof, roof + hood, full skin), κ and the four archetypes checks it against the full simulation. Code: [`experiments/e7_inversion/run.py`](experiments/e7_inversion/run.py).

<img src="docs/readme/fig_nomograph.png" width="75%" alt="Paper figure: design nomograph">

</details>

<details>
<summary><b>E8 - Cross-verification</b> (Unity 99.1 %, Mapillary sky view MAE 0.054)</summary>

The Unity twin ray-casts the same trips independently and agrees with the Python engine on 99.1 % of 15.5 million sample-seconds. Sky view factors from seven Mapillary street panoramas match the engine with a mean absolute error of 0.054 (r = 0.92). Code: [`experiments/e8_validation/run.py`](experiments/e8_validation/run.py).

<img src="docs/readme/fig_validation.png" width="75%" alt="Paper figure: Unity agreement and Mapillary sky view comparison">

</details>

## Reproduce

Everything runs natively on Windows 11 (Linux works the same way). Install [Miniforge](https://conda-forge.org/download/), then in a Miniforge Prompt:

```bat
git clone https://github.com/jarvisxys/solaris-vipv.git
cd solaris-vipv
conda env create -f environment.yml
conda activate solaris
projsync --file us_noaa_g2018u0.tif
```

```bash
pytest -q            # 568 regression and verification tests
snakemake -n         # dry run of the whole DAG
snakemake -c8 all    # fetch, build the city, run E0-E8, write the paper
snakemake -c1 paper  # only rebuild paper/main.pdf from results/ (needs pdflatex)
```

Input data is public but not redistributed (about 30 GB of lidar and imagery). [`data/README.md`](data/README.md) lists every source and the rule that fetches it; NSRDB downloads need a free NREL API key. The summary tables in `results/` are committed, so the paper builds without the raw data.

The Unity project in [`twin/unity/`](twin/unity/) (Unity 6.3 LTS, Cesium for Unity) reads the exchange files in [`twin/exchange/`](twin/exchange/); streaming Google tiles needs your own Cesium ion token.

<details>
<summary>Repository layout</summary>

| Path | Contents |
|---|---|
| `configs/` | `base.yaml` (conference parameters, frozen), site, vehicle, schedules, experiments, paper |
| `src/solaris/` | `legacy/` (conference code, byte-identical), `core/`, `weather/`, `geometry/`, `vehicle/`, `trajectory/`, `shading/`, `pv/`, `twin_io/`, `paper.py` |
| `geom/` | QGIS review helper for the building-change step |
| `routes/v1`, `routes/v2` | frozen route and parking GeoJSON with SHA-256 manifests (v2 is used; v1 was selected on a surface model with power-line artefacts) |
| `experiments/` | `e0_reproduce/` ... `e8_validation/` |
| `results/` | summary tables and JSON (large outputs are not committed) |
| `twin/` | Unity project, Blender build scripts for the vehicle, Python-Unity exchange schema |
| `paper/` | journal LaTeX, generated macros and figures, `main.pdf` |
| `docs/readme/` | the images and 3D files of this page; `make_figures.py` and `blender_renders.py` rebuild them |
| `PAPER_CHANGELOG.md` | every decision that changed a reported number |

</details>

## Data and attributions

| Source | Use | License |
|---|---|---|
| USGS 3DEP lidar (AZ_MaricopaPinal_2020_B20) | city geometry | public domain |
| USDA NAIP 2021 | tree/building separation (NDVI) | public domain |
| NREL NSRDB (TMY-2023, 5-min 2023) | weather | NREL terms of use |
| NGS survey marks | ground check | public domain |
| Overture Maps buildings | building changes | ODbL |
| OpenStreetMap | roads, bridges, tunnels, SUMO network | ODbL, © OpenStreetMap contributors |
| Mapillary | street panoramas for sky view | CC BY-SA 4.0 |
| Google Photorealistic 3D Tiles via Cesium ion | Unity visuals only (screenshots above keep the on-screen attribution) | Google Maps Platform terms |
| SOLWEIG / UMEP | external cross-check only, never linked | GPL-3.0 |

## Citation

If you use this code, please cite the archived release and the conference paper (the journal paper is under review):

```bibtex
@software{kumar_solaris_twin_2026,
  author    = {Kumar, Aditya and Gaikwad, Anandsagar and Deo, Arjun},
  title     = {{SOLARIS-Twin: Digital twin pipeline for shading-aware assessment of vehicle-integrated photovoltaics}},
  version   = {v2.0.0-journal},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.23896001},
  url       = {https://doi.org/10.5281/zenodo.23896001}
}

@inproceedings{gaikwad_solaris_2026,
  author    = {Gaikwad, Anandsagar and Kumar, Aditya and Deo, Arjun},
  title     = {{SOLARIS}: A first-principles, drive-cycle- and climate-resolved methodology and open toolkit for assessing solar-assisted heavy electric vehicles},
  booktitle = {IEEE Transportation Electrification Conference and Expo, Asia-Pacific (ITEC-AP 2026)},
  address   = {Busan, Republic of Korea},
  year      = {2026},
  note      = {Accepted}
}
```

GitHub's "Cite this repository" button reads [`CITATION.cff`](CITATION.cff).

## Authors

- **Aditya Kumar**, Rajiv Gandhi Institute of Petroleum Technology (RGIPT), [ORCID 0009-0003-5178-0465](https://orcid.org/0009-0003-5178-0465), corresponding author
- **Anandsagar Gaikwad**, RGIPT, [ORCID 0009-0001-6545-1705](https://orcid.org/0009-0001-6545-1705)
- **Arjun Deo**, RGIPT Bengaluru Campus

The conference toolkit lives at [Anandsagar18/Solaris](https://github.com/Anandsagar18/Solaris). An AI assistant (Claude, Anthropic) helped write and debug code and draft text; the authors designed the study, checked every result and are responsible for the content.

## License

[MIT](LICENSE). SOLWEIG/UMEP (GPL-3.0) is only ever called as an external tool.
