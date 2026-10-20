# SOLARIS-Twin pipeline DAG: data -> geometry -> experiments -> figures.
#   dry run:     snakemake -n
#   full build:  snakemake -c8 all
# Rules are added phase by phase (workflow guide, Sec. 7). Every number that
# reaches paper/ must come from a rule in this file.

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(workflow.basedir) / "src"))

LEGACY = "src/solaris/legacy/solaris_v1.py"
LEGACY_SUMS = "src/solaris/legacy/SHA256SUMS"
CORE_SRC = sorted(str(f) for f in Path("src/solaris/core").glob("*.py"))
E0_CFG = "configs/experiments/e0.yaml"
E0 = yaml.safe_load(Path(E0_CFG).read_text(encoding="utf-8"))
SITE_CFG = "configs/site/phoenix.yaml"
ROUTES = "routes/" + yaml.safe_load(Path(SITE_CFG).read_text(encoding="utf-8"))["routes"]["version"]
WEATHER_SRC = sorted(str(f) for f in Path("src/solaris/weather").glob("*.py"))
DD = "data/derived"


def geom(step):
    """Settings a geometry step depends on, as a Snakemake params value: the rule reruns
    when they change, not on every edit of configs/site/phoenix.yaml."""
    import json

    from solaris.geometry.build import step_params

    return json.dumps(step_params(step), sort_keys=True)


def nsrdb_raw(kind):
    from solaris.weather import raw_path

    return raw_path(kind, root=".").as_posix()


def experiment(name):
    """Load experiments/<name>/run.py in-process. Rules use run: rather than script:
    because Snakemake's script: launches python through cmd without quoting its path,
    which breaks under a user profile containing a space."""
    import importlib.util

    path = Path(workflow.basedir) / "experiments" / name / "run.py"
    spec = importlib.util.spec_from_file_location(f"experiments.{name}.run", path)
    run_py = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run_py)
    return run_py


rule all:
    input:
        "results/p0/legacy_sha256.ok",
        E0["b0"]["out_table"],
        E0["b0"]["out_pareto"],
        "results/p2/summary_weather.json",
        "results/p3/summary_geometry.json",
        "results/e1/table_e1.csv",
        "results/e2/summary_e2.json",
        "twin/exchange/facet_samples.csv",
        "results/e3/summary_e3.json",
        "results/e4/summary_e4.json",
        "results/e6/summary_e6.json",
        "results/e5/summary_e5.json",
        "results/e8/summary_e8_unity.json",
        "results/e8/summary_e8_svf.json",


# ---------------------------------------------------------------- P0 bootstrap
rule legacy_sha256:
    """Stop the whole DAG if the conference code is no longer byte-identical."""
    input:
        LEGACY,
        LEGACY_SUMS,
    output:
        "results/p0/legacy_sha256.ok",
    run:
        from solaris.integrity import recorded_hashes, verify_legacy

        problems = verify_legacy()
        if problems:
            raise ValueError("legacy code changed:\n" + "\n".join(problems))
        Path(output[0]).write_text(
            "".join(f"{h}  {n}\n" for n, h in recorded_hashes().items()), encoding="ascii"
        )


# ---------------------------------------------------------------- P1 / E0
rule e0_measured:
    """Table B0: conference metrics on the measured NSRDB TMY (Phoenix), next to the
    reproduced synthetic values and the numbers printed in the conference paper."""
    input:
        tmy=E0["inputs"]["tmy_phoenix"]["path"],
        base="configs/base.yaml",
        e0=E0_CFG,
        legacy_ok="results/p0/legacy_sha256.ok",
        code=CORE_SRC,
    output:
        table=E0["b0"]["out_table"],
        pareto=E0["b0"]["out_pareto"],
    run:
        experiment("e0_reproduce").main(input.tmy, output.table, output.pareto)


# ---------------------------------------------------------------- P2 weather
# Downloads need NREL_API_KEY (and NREL_API_EMAIL, else git user.email). They have no
# inputs on purpose: editing configs/site/phoenix.yaml must not trigger a re-download.
# Delete the cached CSV to fetch it again.
rule weather_tmy:
    """NSRDB GOES TMY v4, tmy-2023, hourly, local standard time."""
    output:
        nsrdb_raw("tmy"),
    run:
        from solaris.weather import download

        download("tmy", output[0])


rule weather_conus_5min:
    """NSRDB GOES CONUS v4, 2023, 5-min, local standard time (E5 sub-hourly sensitivity)."""
    output:
        nsrdb_raw("conus_5min"),
    run:
        from solaris.weather import download

        download("conus_5min", output[0])


rule weather_check:
    """Minute convention, no DST, row counts, provenance; the downloaded TMY must equal the
    TMY pinned for E0."""
    input:
        tmy=nsrdb_raw("tmy"),
        conus=nsrdb_raw("conus_5min"),
        e0_tmy=E0["inputs"]["tmy_phoenix"]["path"],
        site=SITE_CFG,
        code=WEATHER_SRC,
    output:
        "results/p2/summary_weather.json",
    run:
        import json

        from solaris.weather import summary

        s = summary(input.tmy, input.conus, input.e0_tmy)
        Path(output[0]).write_text(json.dumps(s, indent=2) + "\n", encoding="utf-8", newline="\n")


# ---------------------------------------------------------------- P3 geometry
# Workflow guide Sec. 2, steps 1-8; layout and run times in geom/README.md. Downloads cache
# under data/raw and are never refetched; per-tile steps cache per tile and reset when
# their settings (params) change. Long step: snakemake -c1 geom_lidar_fetch (hours).
rule geom_aoi:
    """Step 1: AOI = bounding box of the route and parking seeds + 1 km, 500 m tiles."""
    params:
        geom("aoi"),
    output:
        aoi=f"{DD}/aoi.geojson",
        tiles=f"{DD}/tiles.csv",
    run:
        from solaris.geometry.build import step_aoi

        step_aoi()


rule geom_lidar_fetch:
    """Step 2a: USGS 3DEP EPT -> cleaned LAZ per tile (EPSG:26912, NAVD88, no noise)."""
    input:
        f"{DD}/tiles.csv",
    params:
        geom("fetch"),
    output:
        "data/raw/lidar/tiles/MANIFEST.json",
    run:
        from solaris.geometry.build import _log, run_step_subprocess, write_json
        from solaris.site import site_config

        run_step_subprocess("fetch")
        write_json(output[0], {"ept": site_config()["lidar"]["ept"], "tiles": _log("fetch")})


rule geom_lidar_rasters:
    """Step 2b: 0.5 m DSM (max Z, all returns), DTM (ground IDW), HAG per tile + mosaics."""
    input:
        "data/raw/lidar/tiles/MANIFEST.json",
    params:
        geom("rasterize"),
    output:
        dtm_raw=f"{DD}/lidar/dtm_raw.tif",
        dsm=f"{DD}/lidar/dsm_lidar.vrt",
        hag=f"{DD}/lidar/hag_lidar.vrt",
    run:
        from solaris.geometry.build import run_step_subprocess, step_lidar_mosaics

        run_step_subprocess("rasterize")
        step_lidar_mosaics()


rule geom_dem:
    """Step 3: FillNodata on the DTM -> dem.tif."""
    input:
        f"{DD}/lidar/dtm_raw.tif",
    params:
        geom("dem"),
    output:
        f"{DD}/dem.tif",
    run:
        from solaris.geometry.build import step_dem

        step_dem()


rule geom_naip:
    """NAIP four-band imagery for NDVI (year closest to the lidar flights)."""
    params:
        geom("naip"),
    output:
        f"{DD}/naip.vrt",
    run:
        from solaris.geometry.build import step_naip

        step_naip()


rule geom_overture:
    """Current building footprints (Overture Maps, latest release at first fetch)."""
    output:
        "data/raw/overture/buildings.gpkg",
    run:
        from solaris.geometry import sources
        from solaris.geometry.crs import aoi
        from solaris.site import site_config

        sources.fetch_overture_buildings(aoi(site_config()), output[0])


rule geom_osm:
    """OSM ways tagged bridge, tunnel or covered."""
    output:
        "data/raw/osm/covered_ways.gpkg",
    run:
        from solaris.geometry import sources
        from solaris.geometry.crs import aoi
        from solaris.site import site_config

        sources.fetch_osm_covered(aoi(site_config()), output[0])


rule geom_covered:
    """Step 6: road and rail bridges, tunnels and covered ways as polygons."""
    input:
        "data/raw/osm/covered_ways.gpkg",
    params:
        geom("covered"),
    output:
        f"{DD}/covered.gpkg",
    run:
        from solaris.geometry.build import step_covered

        step_covered()


rule geom_model:
    """Steps 4-5: building/tree split (nDSM, NDVI, footprints) and the model rasters."""
    input:
        dsm=f"{DD}/lidar/dsm_lidar.vrt",
        dem=f"{DD}/dem.tif",
        naip=f"{DD}/naip.vrt",
        footprints="data/raw/overture/buildings.gpkg",
    params:
        geom("model"),
    output:
        classes=f"{DD}/classes.tif",
        dsm=f"{DD}/dsm_lidar_epoch.tif",
        cdsm=f"{DD}/cdsm.tif",
        holes=f"{DD}/dsm_holes.tif",
    run:
        from solaris.geometry.build import run_step_subprocess, step_model_mosaics

        run_step_subprocess("model")
        step_model_mosaics()


rule geom_enu_origin:
    """Unity origin: DEM ground at Central Ave & Washington St, NAVD88 -> ellipsoid."""
    input:
        f"{DD}/dem.tif",
    params:
        geom("meshes"),
    output:
        "twin/exchange/enu_origin.json",
    run:
        from solaris.geometry.build import step_enu_origin

        step_enu_origin()


rule geom_freshness:
    """Step 8: candidates for buildings added or demolished since the lidar, per route."""
    input:
        classes=f"{DD}/classes.tif",
        dsm=f"{DD}/dsm_lidar_epoch.tif",
        dem=f"{DD}/dem.tif",
        footprints="data/raw/overture/buildings.gpkg",
        covered=f"{DD}/covered.gpkg",
    params:
        geom("freshness"),
    output:
        table="results/p3/table_freshness.csv",
        gpkg=f"{DD}/freshness_candidates.gpkg",
    run:
        from solaris.geometry.build import step_freshness

        step_freshness(output.table)


rule geom_dsm:
    """dsm.tif = lidar-epoch building DSM + confirmed freshness changes."""
    input:
        dsm=f"{DD}/dsm_lidar_epoch.tif",
        dem=f"{DD}/dem.tif",
        candidates=f"{DD}/freshness_candidates.gpkg",
        confirmations="configs/site/freshness_v1.yaml",
    output:
        f"{DD}/dsm.tif",
    run:
        from solaris.geometry.build import step_dsm

        step_dsm()


rule geom_meshes:
    """Step 7: surface and tree .glb tiles in ENU, Delatin to 0.25 m."""
    input:
        dsm=f"{DD}/dsm.tif",
        cdsm=f"{DD}/cdsm.tif",
        dem=f"{DD}/dem.tif",
        origin="twin/exchange/enu_origin.json",
    params:
        geom("meshes"),
    output:
        f"{DD}/tiles/MANIFEST.json",
    run:
        from solaris.geometry.build import run_step_subprocess, step_mesh_manifest

        run_step_subprocess("meshes")
        step_mesh_manifest()


rule geom_ground_control:
    """NGS marks (adjusted position and NAVD88 height) in every frame, DEM residuals."""
    input:
        dem=f"{DD}/dem.tif",
        origin="twin/exchange/enu_origin.json",
    output:
        "results/p3/table_ground_control.csv",
    run:
        from solaris.geometry.build import step_ground_control

        step_ground_control(output[0])


rule geom_summary:
    """Provenance and checks: results/p3/summary_geometry.json."""
    input:
        gcp="results/p3/table_ground_control.csv",
        fresh="results/p3/table_freshness.csv",
        meshes=f"{DD}/tiles/MANIFEST.json",
        classes=f"{DD}/classes.tif",
        holes=f"{DD}/dsm_holes.tif",
        covered=f"{DD}/covered.gpkg",
        dsm=f"{DD}/dsm.tif",
    output:
        "results/p3/summary_geometry.json",
    run:
        from solaris.geometry.build import step_summary

        step_summary(input.gcp, input.fresh, output[0])


# ---------------------------------------------------------------- P4 / E1
rule e1_verification:
    """E1: sun position, transposition, shadow length, canyon SVF, raster vs mesh engine on
    1,000 downtown points, SOLWEIG shadow maps (UMEP via qgis_process, external)."""
    input:
        cfg="configs/experiments/e1.yaml",
        site=SITE_CFG,
        dsm=f"{DD}/dsm.tif",
        dem=f"{DD}/dem.tif",
        cdsm=f"{DD}/cdsm.tif",
        classes=f"{DD}/classes.tif",
        holes=f"{DD}/dsm_holes.tif",
        meshes=f"{DD}/tiles/MANIFEST.json",
        origin="twin/exchange/enu_origin.json",
        code=sorted(str(f) for f in Path("src/solaris/shading").glob("*.py")),
    output:
        table="results/e1/table_e1.csv",
        summary="results/e1/summary_e1.json",
    run:
        experiment("e1_verify").main(output.table, output.summary)


# ---------------------------------------------------------------- P5 / E2
VEHICLE_CFG = "configs/vehicle/solaris_p0.yaml"


rule facet_samples:
    """twin/exchange/facet_samples.csv: facet sample points on a 0.25 m grid (body frame)."""
    input:
        VEHICLE_CFG,
    output:
        "twin/exchange/facet_samples.csv",
    run:
        experiment("e2_facets").write_facet_samples(output[0])


rule e2_facets:
    """E2: facet orientation, open sky. Cases 2a-2d on the measured TMY; 2b = 2a +/- 0.5 %."""
    input:
        vehicle=VEHICLE_CFG,
        base="configs/base.yaml",
        tmy=nsrdb_raw("tmy"),
        e0_tmy=E0["inputs"]["tmy_phoenix"]["path"],
        b0=E0["b0"]["out_table"],
        code=sorted(str(f) for f in Path("src/solaris/pv").glob("*.py"))
        + sorted(str(f) for f in Path("src/solaris/vehicle").glob("*.py"))
        + CORE_SRC,
    output:
        table="results/e2/table_e2.csv",
        facets="results/e2/table_e2_facets.csv",
        summary="results/e2/summary_e2.json",
    run:
        experiment("e2_facets").main(output.table, output.facets, output.summary)


# ---------------------------------------------------------------- P6 / E3, E4
def script(path):
    """Load a repo script (not under experiments/) in-process, like experiment()."""
    import importlib.util

    p = Path(workflow.basedir) / path
    spec = importlib.util.spec_from_file_location(p.stem, p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RASTERS = [f"{DD}/dsm.tif", f"{DD}/dem.tif", f"{DD}/cdsm.tif", f"{DD}/classes.tif"]


rule routes_select:
    """Guide Sec. 3: routes by measured SVF; frozen in routes/<version> with a SHA-256 MANIFEST.
    A frozen version is never rewritten (the script refuses); a change is routes/v2."""
    input:
        RASTERS,
        covered=f"{DD}/covered.gpkg",
        tmy=nsrdb_raw("tmy"),
    output:
        f"{ROUTES}/MANIFEST.json",
    run:
        script("routes/select_routes.py").main()


rule sumo_traces:
    """SUMO (separate 'sumo' env): network from OSM, three demand seeds, 1 Hz ego traces."""
    input:
        f"{ROUTES}/MANIFEST.json",
        covered=f"{DD}/covered.gpkg",
    output:
        "results/p6/table_traces.csv",
    run:
        from solaris.site import site_config
        from solaris.trajectory.sumo import build_traces

        build_traces(site_config(), ROUTES, f"{DD}/trajectories", output[0])


rule e3_driving:
    """E3: 360 trips, cases A/B/C, clear sky and TMY day."""
    input:
        RASTERS,
        traces="results/p6/table_traces.csv",
        cfg="configs/experiments/e3.yaml",
        vehicle=VEHICLE_CFG,
    output:
        trips="results/e3/table_e3_trips.csv",
        table="results/e3/table_e3_summary.csv",
        tod="results/e3/table_e3_tod.csv",
        summary="results/e3/summary_e3.json",
    run:
        experiment("e3_driving").main(output.trips, output.table, output.tod, output.summary)


rule e4_parking:
    """E4: P1-P5 x 4 headings, 5-min daylight steps, F_park; SOLWEIG check at P1-P3."""
    input:
        RASTERS,
        sites=f"{ROUTES}/MANIFEST.json",
        cfg="configs/experiments/e4.yaml",
        vehicle=VEHICLE_CFG,
    output:
        table="results/e4/table_e4.csv",
        sites="results/e4/table_e4_sites.csv",
        summary="results/e4/summary_e4.json",
    run:
        experiment("e4_parking").main(output.table, output.sites, output.summary)


# ---------------------------------------------------------------- P7 / E6, E5
SCHED_CFG = "configs/schedules/archetypes.yaml"
ELEC_CFG = "configs/vehicle/electrical_p0.yaml"
PV_SRC = sorted(str(f) for f in Path("src/solaris/pv").glob("*.py"))


rule e6_mismatch:
    """E6: bishop88 strings with bypass diodes, one MPPT per facet; F_mm on all R-DENSE trips
    and P2/P3 parked; fit F_mm(s) for the last E5 waterfall step."""
    input:
        RASTERS,
        traces="results/p6/table_traces.csv",
        e3="results/e3/summary_e3.json",
        e4="results/e4/summary_e4.json",
        cfg="configs/experiments/e6.yaml",
        sched=SCHED_CFG,
        vehicle=VEHICLE_CFG,
        electrical=ELEC_CFG,
        code=PV_SRC + ["src/solaris/shading/parked.py"],
    output:
        table="results/e6/table_e6.csv",
        fit="results/e6/fit_fmm.json",
        summary="results/e6/summary_e6.json",
        fig="results/e6/fig11_fmm.png",
    run:
        experiment("e6_mismatch").main(output.table, output.fit, output.summary, output.fig)


rule e5_annual:
    """E5: archetypes A1-A4, driving at 1 s and parking at 5 min binned into the 8760-h SoC
    loop (energy balance to 0.1 %), loss waterfall B0 -> ... -> mismatch; 2023 5-min check.
    Long run (~2 h): launch detached."""
    input:
        RASTERS,
        traces="results/p6/table_traces.csv",
        e3="results/e3/summary_e3.json",
        e4="results/e4/summary_e4.json",
        fit="results/e6/fit_fmm.json",
        b0=E0["b0"]["out_table"],
        tmy=nsrdb_raw("tmy"),
        conus=nsrdb_raw("conus_5min"),
        cfg="configs/experiments/e5.yaml",
        sched=SCHED_CFG,
        vehicle=VEHICLE_CFG,
        code=PV_SRC
        + CORE_SRC
        + ["src/solaris/annual.py", "src/solaris/shading/parked.py", "src/solaris/trajectory/schedules.py"],
    output:
        table="results/e5/table_e5.csv",
        hourly="results/e5/table_e5_hourly.csv.gz",
        summary="results/e5/summary_e5.json",
        waterfall="results/e5/fig10_waterfall.png",
        soc="results/e5/fig9_soc.png",
    run:
        experiment("e5_annual").main(
            output.table, output.hourly, output.summary, output.waterfall, output.soc
        )


# ---------------------------------------------------------------- P8 / E8
# Unity runs headless (twin/unity/README.md); the editor path comes from env UNITY_EDITOR or
# configs/experiments/e8.yaml. Mapillary needs MAPILLARY_TOKEN (user environment).
E8_CFG = "configs/experiments/e8.yaml"
UNITY_PROJ = "twin/unity/SOLARIS-Twin"
# Only the C# that can change E8 numbers (scene build, I/O, probe, ground control, batch);
# display scripts (Runtime/* playback, Visual/**) never re-trigger the Unity run.
UNITY_SRC = [
    f"{UNITY_PROJ}/Assets/SolarisTwin/{f}"
    for f in (
        "Editor/TwinBatch.cs",
        "Editor/TwinSetup.cs",
        "Runtime/TwinIO.cs",
        "Runtime/VisibilityProbe.cs",
        "Runtime/GroundControlCheck.cs",
    )
]
TWIN_IO_SRC = sorted(str(f) for f in Path("src/solaris/twin_io").glob("*.py"))


rule e8_export:
    """Python -> Unity: 120 R-DENSE trajectories in ENU, tiles into Assets/Geometry, five
    ground-control marks, the PV overlay for the render."""
    input:
        RASTERS,
        traces="results/p6/table_traces.csv",
        samples="twin/exchange/facet_samples.csv",
        tiles=f"{DD}/tiles/MANIFEST.json",
        gcp="results/p3/table_ground_control.csv",
        cfg=E8_CFG,
        e3="configs/experiments/e3.yaml",
        code=TWIN_IO_SRC,
    output:
        "twin/exchange/export_manifest.json",
    run:
        experiment("e8_validation").export(output[0])


rule e8_unity:
    """Unity batch: import tiles, build E8.unity, ground-control gate, probe every record."""
    input:
        export="twin/exchange/export_manifest.json",
        packages=f"{UNITY_PROJ}/Packages/manifest.json",
        code=UNITY_SRC,
    output:
        f"{DD}/e8/unity/unity_run.txt",
    run:
        experiment("e8_validation").run_unity(output[0])


rule e8_twin_agreement:
    """E8: Unity vs Python raster engine (and Embree on the same meshes); gates 97 % / 2 pp."""
    input:
        RASTERS,
        unity=f"{DD}/e8/unity/unity_run.txt",
        export="twin/exchange/export_manifest.json",
        cfg=E8_CFG,
        code=TWIN_IO_SRC,
    output:
        trips="results/e8/table_e8_trips.csv",
        clusters="results/e8/table_e8_clusters.csv",
        summary="results/e8/summary_e8_unity.json",
        fig="results/e8/fig13a_twin_agreement.png",
    run:
        experiment("e8_validation").twin_agreement(
            output.trips, output.clusters, output.summary, output.fig
        )


rule e8_mapillary_fetch:
    """Mapillary panoramas near R-DENSE and R-MIXED and their sky segmentation (cached)."""
    input:
        f"{ROUTES}/MANIFEST.json",
        cfg=E8_CFG,
    output:
        "data/raw/mapillary/MANIFEST.json",
    run:
        experiment("e8_validation").mapillary_fetch(output[0])


rule e8_mapillary_svf:
    """E8: panorama sky view factor vs the engine (MAE, RMSE, R2)."""
    input:
        RASTERS,
        manifest="data/raw/mapillary/MANIFEST.json",
        cfg=E8_CFG,
        code="src/solaris/imagery/mapillary.py",
    output:
        table="results/e8/table_e8_svf.csv",
        summary="results/e8/summary_e8_svf.json",
        fig="results/e8/fig13b_svf.png",
    run:
        experiment("e8_validation").mapillary_svf(
            input.manifest, output.table, output.summary, output.fig
        )


# ---------------------------------------------------------------- planned rules
# P9  E7   e7_inversion, figures, paper
