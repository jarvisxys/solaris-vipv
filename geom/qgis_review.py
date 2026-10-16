"""Build data/derived/p3_review.qgz: the P3 rasters and the freshness candidates over current
imagery, for the visual checks (done-when) and the freshness confirmations.

Run with QGIS's own Python (not the solaris env):
    "C:\\Program Files\\QGIS 3.44.15\\bin\\python-qgis-ltr.bat" geom\\qgis_review.py
"""

from pathlib import Path

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsCategorizedSymbolRenderer,
    QgsColorRampShader,
    QgsCoordinateReferenceSystem,
    QgsFillSymbol,
    QgsHillshadeRenderer,
    QgsMarkerSymbol,
    QgsPalettedRasterRenderer,
    QgsPalLayerSettings,
    QgsProject,
    QgsRasterLayer,
    QgsRasterShader,
    QgsRendererCategory,
    QgsSingleBandPseudoColorRenderer,
    QgsTextFormat,
    QgsVectorLayer,
    QgsVectorLayerSimpleLabeling,
)
from qgis.PyQt.QtGui import QColor

REPO = Path(__file__).resolve().parents[1]
D = REPO / "data" / "derived"
OUT = D / "p3_review.qgz"
IMAGERY = (
    "type=xyz&zmin=0&zmax=19&url=https://server.arcgisonline.com/ArcGIS/rest/services/"
    "World_Imagery/MapServer/tile/%7Bz%7D/%7By%7D/%7Bx%7D"
)


def raster(path, name):
    lyr = QgsRasterLayer(str(path), name)
    if not lyr.isValid():
        raise RuntimeError(f"cannot open {path}")
    return lyr


def hillshade(lyr):
    r = QgsHillshadeRenderer(lyr.dataProvider(), 1, 315, 40)
    r.setZFactor(1.0)
    r.setMultiDirectional(True)
    lyr.setRenderer(r)
    return lyr


def ramp(lyr, stops, alpha_zero=True):
    sh = QgsColorRampShader()
    sh.setColorRampType(QgsColorRampShader.Interpolated)
    items = [QgsColorRampShader.ColorRampItem(v, QColor(c), f"{v:g}") for v, c in stops]
    if alpha_zero:
        items[0] = QgsColorRampShader.ColorRampItem(stops[0][0], QColor(0, 0, 0, 0), "0")
    sh.setColorRampItemList(items)
    rs = QgsRasterShader()
    rs.setRasterShaderFunction(sh)
    lyr.setRenderer(QgsSingleBandPseudoColorRenderer(lyr.dataProvider(), 1, rs))
    return lyr


def classes(lyr):
    cl = [
        QgsPalettedRasterRenderer.Class(0, QColor(0, 0, 0, 0), "ground"),
        QgsPalettedRasterRenderer.Class(1, QColor("#d7301f"), "building"),
        QgsPalettedRasterRenderer.Class(2, QColor("#1a9850"), "tree"),
    ]
    lyr.setRenderer(QgsPalettedRasterRenderer(lyr.dataProvider(), 1, cl))
    lyr.renderer().setOpacity(0.6)
    return lyr


def candidates(path):
    lyr = QgsVectorLayer(f"{path}|layername=candidates", "freshness candidates", "ogr")
    cats = []
    for kind, color in (("added", "#2c7fb8"), ("demolished", "#e7298a")):
        sym = QgsFillSymbol.createSimple(
            {"color": "0,0,0,0", "outline_color": color, "outline_width": "0.8"}
        )
        cats.append(QgsRendererCategory(kind, sym, kind))
    lyr.setRenderer(QgsCategorizedSymbolRenderer("kind", cats))
    pal = QgsPalLayerSettings()
    pal.fieldName = "id"
    fmt = QgsTextFormat()
    fmt.setSize(9)
    fmt.buffer().setEnabled(True)
    pal.setFormat(fmt)
    lyr.setLabeling(QgsVectorLayerSimpleLabeling(pal))
    lyr.setLabelsEnabled(True)
    return lyr


def main():
    app = QgsApplication([], False)
    app.initQgis()
    p = QgsProject.instance()
    p.setCrs(QgsCoordinateReferenceSystem("EPSG:26912"))
    p.setFilePathStorage(Qgis.FilePathType.Relative)
    layers = [
        QgsRasterLayer(IMAGERY, "Esri World Imagery (current)", "wms"),
        hillshade(raster(D / "dem.tif", "dem.tif (hillshade)")),
        hillshade(raster(D / "dsm.tif", "dsm.tif (hillshade)")),
        classes(raster(D / "classes.tif", "classes (building / tree)")),
        ramp(
            raster(D / "cdsm.tif", "cdsm.tif (canopy m)"),
            [(0, "#ffffff"), (3, "#c7e9c0"), (12, "#41ab5d"), (30, "#00441b")],
        ),
        ramp(
            raster(D / "dsm_holes.tif", "dsm holes (no return)"),
            [(0, "#000000"), (1, "#00ffff")],
        ),
    ]
    aoi = QgsVectorLayer(str(D / "aoi.geojson"), "AOI", "ogr")
    aoi.setRenderer(aoi.renderer().clone())
    aoi.renderer().setSymbol(
        QgsFillSymbol.createSimple(
            {"color": "0,0,0,0", "outline_color": "#ffff00", "outline_width": "1"}
        )
    )
    gcp_csv = (REPO / "results" / "p3" / "table_ground_control.csv").as_uri()
    gcp = QgsVectorLayer(
        f"{gcp_csv}?delimiter=,&xField=E_m&yField=N_m&crs=EPSG:26912",
        "NGS ground control",
        "delimitedtext",
    )
    gcp.renderer().setSymbol(
        QgsMarkerSymbol.createSimple({"name": "triangle", "color": "#ffff00", "size": "3"})
    )
    layers += [aoi, gcp, candidates(D / "freshness_candidates.gpkg")]
    # Hide the slow full-area hillshades by default; imagery + candidates is the review view.
    for lyr in layers:
        p.addMapLayer(lyr)
    root = p.layerTreeRoot()
    for name in ("dem.tif (hillshade)", "dsm holes (no return)"):
        root.findLayer(p.mapLayersByName(name)[0].id()).setItemVisibilityChecked(False)
    p.write(str(OUT))
    print(OUT)
    app.exitQgis()


if __name__ == "__main__":
    main()
