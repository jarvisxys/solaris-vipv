// SOLARIS-Twin: editor setup (menu "SOLARIS"), the scripted parts of workflow guide Sec. 6.
//
//   1 Layers           Buildings (8) and Trees (9); physics queries hit back faces.
//   2 Analysis scene   every tile listed in twin/exchange/unity_geometry.json (imported from
//                      Assets/Geometry by glTFast) under root "AnalysisGeometry": layer per
//                      tile, a MeshCollider per mesh, static. glTF is right-handed, Unity
//                      left-handed; the importer's flip is detected from the tile bounds and
//                      undone on the root so the scene is x east, y up, z north.
//                      Saved as Assets/Scenes/E8.unity (the scene TwinBatch opens).
//   3 SUV prefab       5.1 x 2.0 x 1.8 m box, no collider, facet samples as children.
//   4 Ground control   raycast check of the five surveyed marks (Console).
//   5 Playback scene   E8 scene + SUV + TrajectoryPlayer + sun + chase camera + PV overlay,
//                      saved as Assets/Scenes/Playback.unity (renders; display only).
//   6 Display mode     AnalysisGeometry visible / shadows only / hidden (colliders kept).
//   7 Controls         real-time playback, drive mode and shade dots on an existing scene.
// Batch entries: SolarisTwin.Editor.TwinSetup.BuildAnalysisSceneBatch, PlaybackSceneBatch.
using System;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using Object = UnityEngine.Object;

namespace SolarisTwin.Editor
{
    [Serializable]
    public class GeoTile
    {
        public string tile;
        public string layer;
        public string asset;
        public float[] bbox_min;
        public float[] bbox_max;
    }

    [Serializable]
    public class GeoManifest
    {
        public GeoTile[] tiles;
    }

    public static class TwinSetup
    {
        public const string AnalysisScene = "Assets/Scenes/E8.unity";
        public const string PlaybackScene = "Assets/Scenes/Playback.unity";
        public const string SuvPrefab = "Assets/SolarisTwin/Prefabs/SUV.prefab";
        static readonly string[] Layers = { "Buildings", "Trees" };

        static string Exchange(string name) => Path.Combine(TwinPaths.Exchange, name);

        [MenuItem("SOLARIS/1 Create layers and physics settings")]
        public static void EnsureLayers()
        {
            var tm = new SerializedObject(AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/TagManager.asset")[0]);
            var layers = tm.FindProperty("layers");
            for (int k = 0; k < Layers.Length; k++)
            {
                int slot = 8 + k;
                var p = layers.GetArrayElementAtIndex(slot);
                if (p.stringValue != Layers[k])
                {
                    if (!string.IsNullOrEmpty(p.stringValue))
                        throw new InvalidOperationException($"layer {slot} is '{p.stringValue}', expected free");
                    p.stringValue = Layers[k];
                }
            }
            tm.ApplyModifiedPropertiesWithoutUndo();
            var dm = new SerializedObject(AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/DynamicsManager.asset")[0]);
            var bf = dm.FindProperty("m_QueriesHitBackfaces");
            if (bf != null)
            {
                bf.boolValue = true;
                dm.ApplyModifiedPropertiesWithoutUndo();
            }
            Physics.queriesHitBackfaces = true;
            AssetDatabase.SaveAssets();
            Debug.Log("[TwinSetup] layers Buildings=8, Trees=9; queriesHitBackfaces on");
        }

        static void SetLayer(GameObject go, int layer)
        {
            foreach (var t in go.GetComponentsInChildren<Transform>(true)) t.gameObject.layer = layer;
        }

        /// +1: importer kept glTF x (flipped z) -> no rotation; -1: importer flipped x -> 180 deg.
        static int DetectFlip(GameObject go, GeoTile t)
        {
            var mf = go.GetComponentInChildren<MeshFilter>();
            var b = mf.sharedMesh.bounds;
            var c = mf.transform.localToWorldMatrix.MultiplyPoint3x4(b.center);
            float gx = (t.bbox_min[0] + t.bbox_max[0]) / 2f, gz = (t.bbox_min[2] + t.bbox_max[2]) / 2f;
            if (Mathf.Abs(c.x + gx) < 1f && Mathf.Abs(c.z - gz) < 1f) return -1;
            if (Mathf.Abs(c.x - gx) < 1f && Mathf.Abs(c.z + gz) < 1f) return +1;
            throw new InvalidOperationException(
                $"tile {t.tile}: imported centre ({c.x:F1}, {c.z:F1}) matches neither glTF axis convention ({gx:F1}, {gz:F1})");
        }

        [MenuItem("SOLARIS/2 Build analysis scene (E8)")]
        public static void BuildAnalysisScene()
        {
            EnsureLayers();
            var man = JsonUtility.FromJson<GeoManifest>(File.ReadAllText(Exchange("unity_geometry.json")));
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var root = new GameObject("AnalysisGeometry");
            int flip = 0, n = 0;
            var flags = StaticEditorFlags.BatchingStatic | StaticEditorFlags.OccluderStatic |
                        StaticEditorFlags.OccludeeStatic;
            foreach (var t in man.tiles)
            {
                var asset = AssetDatabase.LoadAssetAtPath<GameObject>(t.asset);
                if (asset == null) throw new FileNotFoundException($"not imported: {t.asset}");
                var go = (GameObject)Object.Instantiate(asset, root.transform);
                go.name = $"{t.layer}_{t.tile}";
                if (flip == 0) flip = DetectFlip(go, t);
                SetLayer(go, LayerMask.NameToLayer(t.layer));
                foreach (var mf in go.GetComponentsInChildren<MeshFilter>(true))
                    mf.gameObject.AddComponent<MeshCollider>().sharedMesh = mf.sharedMesh;
                foreach (var tr in go.GetComponentsInChildren<Transform>(true))
                    GameObjectUtility.SetStaticEditorFlags(tr.gameObject, flags);
                n++;
            }
            root.transform.rotation = flip < 0 ? Quaternion.Euler(0f, 180f, 0f) : Quaternion.identity;
            var sun = new GameObject("Sun").AddComponent<Light>();
            sun.type = LightType.Directional;
            sun.shadows = LightShadows.Soft;
            Directory.CreateDirectory("Assets/Scenes");
            EditorSceneManager.SaveScene(scene, AnalysisScene);
            Debug.Log($"[TwinSetup] {n} tiles, importer flip {(flip < 0 ? "x" : "z")}, saved {AnalysisScene}");
        }

        public static void BuildAnalysisSceneBatch() => Batch(BuildAnalysisScene);

        [MenuItem("SOLARIS/3 Create SUV prefab with facet samples")]
        public static GameObject CreateVehiclePrefab()
        {
            var suv = new GameObject("SUV");
            var body = GameObject.CreatePrimitive(PrimitiveType.Cube);
            body.name = "Body";
            Object.DestroyImmediate(body.GetComponent<Collider>()); // rays must never hit the car
            body.transform.SetParent(suv.transform, false);
            body.transform.localScale = new Vector3(2.0f, 1.8f, 5.1f);
            body.transform.localPosition = new Vector3(0f, 0.9f, 0f);
            var loader = suv.AddComponent<FacetSampleLoader>();
            loader.Load();
            Directory.CreateDirectory(Path.GetDirectoryName(SuvPrefab));
            var prefab = PrefabUtility.SaveAsPrefabAsset(suv, SuvPrefab);
            Object.DestroyImmediate(suv);
            Debug.Log($"[TwinSetup] saved {SuvPrefab}");
            return prefab;
        }

        [MenuItem("SOLARIS/4 Ground-control check")]
        public static bool RunGroundControl()
        {
            Physics.queriesHitBackfaces = true;
            var res = GroundControlCheck.Run(TwinIO.ReadGroundControl(Exchange("ground_control.csv")));
            foreach (var r in res)
            {
                string msg = $"[GroundControl] {r.mark.id}: delta {r.delta:+0.000;-0.000} m";
                if (r.pass) Debug.Log(msg + " ok");
                else Debug.LogError(msg + " FAIL");
            }
            bool ok = GroundControlCheck.AllPass(res);
            Debug.Log(ok ? "[GroundControl] all marks within 0.5 m" : "[GroundControl] FAILED");
            return ok;
        }

        [MenuItem("SOLARIS/5 Build playback scene (render)")]
        public static void BuildPlaybackScene()
        {
            var scene = EditorSceneManager.OpenScene(AnalysisScene, OpenSceneMode.Single);
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(SuvPrefab) ?? CreateVehiclePrefab();
            var suv = (GameObject)PrefabUtility.InstantiatePrefab(prefab);
            var sun = GameObject.Find("Sun").GetComponent<Light>();
            var player = new GameObject("TrajectoryPlayer").AddComponent<TrajectoryPlayer>();
            player.car = suv.transform;
            player.sun = sun;
            var cam = new GameObject("ChaseCamera");
            cam.tag = "MainCamera";
            var c = cam.AddComponent<Camera>();
            c.farClipPlane = 6000f;
            cam.AddComponent<ChaseCamera>().target = suv.transform;
            cam.AddComponent<PvHud>().player = player;
            AddControls(player, suv.transform);
            EditorSceneManager.SaveScene(scene, PlaybackScene);
            Debug.Log($"[TwinSetup] saved {PlaybackScene}");
        }

        /// Real-time playback settings, manual driving and live shade dots on the skin.
        static void AddControls(TrajectoryPlayer player, Transform suv)
        {
            player.speed = 1f;
            player.fixedFps = 0;
            player.waitForTiles = true;
            var drv = player.GetComponent<VehicleDriver>();
            if (drv == null) drv = player.gameObject.AddComponent<VehicleDriver>();
            drv.player = player;
            drv.car = suv;
            var dots = suv.GetComponent<ShadeMarkers>();
            if (dots == null) dots = suv.gameObject.AddComponent<ShadeMarkers>();
            dots.player = player;
        }

        [MenuItem("SOLARIS/7 Add playback and driving controls to the open scene")]
        public static void AddControlsToOpenScene()
        {
            var player = Object.FindFirstObjectByType<TrajectoryPlayer>();
            if (player == null || player.car == null)
            {
                Debug.LogError("[TwinSetup] open Playback.unity first (needs a TrajectoryPlayer with its car)");
                return;
            }
            AddControls(player, player.car);
            EditorSceneManager.MarkSceneDirty(player.gameObject.scene);
            EditorSceneManager.SaveScene(player.gameObject.scene);
            Debug.Log("[TwinSetup] added real-time playback, drive mode (Tab) and shade dots (M); scene saved");
        }

        public static void PlaybackSceneBatch() => Batch(BuildPlaybackScene);

        // 6: how AnalysisGeometry is drawn; colliders are never touched.
        [MenuItem("SOLARIS/6 Analysis geometry: visible")]
        public static void GeometryVisible() => SetGeometryMode(true, ShadowCastingMode.On);

        [MenuItem("SOLARIS/6 Analysis geometry: shadows only")]
        public static void GeometryShadowsOnly() => SetGeometryMode(true, ShadowCastingMode.ShadowsOnly);

        [MenuItem("SOLARIS/6 Analysis geometry: hidden (colliders kept)")]
        public static void GeometryHidden() => SetGeometryMode(false, ShadowCastingMode.Off);

        static void SetGeometryMode(bool enabled, ShadowCastingMode shadows)
        {
            var root = GameObject.Find("AnalysisGeometry");
            if (root == null)
            {
                Debug.LogError("[TwinSetup] no AnalysisGeometry in the open scene");
                return;
            }
            foreach (var r in root.GetComponentsInChildren<MeshRenderer>(true))
            {
                r.enabled = enabled;
                r.shadowCastingMode = shadows;
            }
            EditorSceneManager.MarkSceneDirty(root.scene);
        }

        static void Batch(Action a)
        {
            int code = 0;
            try { a(); }
            catch (Exception e)
            {
                Debug.LogException(e);
                code = 1;
            }
            finally { EditorApplication.Exit(code); }
        }
    }
}
