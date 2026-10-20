// SOLARIS-Twin visual: installers for the Playback scene (menu "SOLARIS Visual").
// Visual only: never touches E8.unity, the analysis geometry, layers Buildings/Trees or the
// physics settings. Playback.unity is gitignored, so every feature installs from code.
using System;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.UIElements;
using Object = UnityEngine.Object;

namespace SolarisTwin.Visual.Editor
{
    public static class VisualSetup
    {
        public const string PlaybackScene = "Assets/Scenes/Playback.unity";
        const string UiDir = "Assets/SolarisTwin/Visual/UI";
        const string ThemePath = UiDir + "/SolarisRuntimeTheme.tss";
        const string PanelPath = UiDir + "/HudPanelSettings.asset";

        /// Layer "Visual" in the first free user slot from 10 up (8 and 9 stay Buildings/Trees).
        public static int EnsureVisualLayer()
        {
            int have = LayerMask.NameToLayer("Visual");
            if (have >= 0) return have;
            var tm = new SerializedObject(AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/TagManager.asset")[0]);
            var layers = tm.FindProperty("layers");
            for (int i = 10; i < 32; i++)
            {
                var p = layers.GetArrayElementAtIndex(i);
                if (string.IsNullOrEmpty(p.stringValue))
                {
                    p.stringValue = "Visual";
                    tm.ApplyModifiedPropertiesWithoutUndo();
                    AssetDatabase.SaveAssets();
                    Debug.Log($"[VisualSetup] layer {i} = Visual");
                    return i;
                }
            }
            throw new InvalidOperationException("no free user layer for Visual");
        }

        static PanelSettings HudPanelSettings()
        {
            Directory.CreateDirectory(UiDir);
            if (!File.Exists(ThemePath))
            {
                File.WriteAllText(ThemePath, "@import url(\"unity-theme://default\");\n");
                AssetDatabase.ImportAsset(ThemePath);
            }
            var ps = AssetDatabase.LoadAssetAtPath<PanelSettings>(PanelPath);
            if (ps == null)
            {
                ps = ScriptableObject.CreateInstance<PanelSettings>();
                AssetDatabase.CreateAsset(ps, PanelPath);
            }
            ps.themeStyleSheet = AssetDatabase.LoadAssetAtPath<ThemeStyleSheet>(ThemePath);
            ps.scaleMode = PanelScaleMode.ScaleWithScreenSize;
            ps.referenceResolution = new Vector2Int(1920, 1080);
            ps.screenMatchMode = PanelScreenMatchMode.MatchWidthOrHeight;
            ps.match = 0.5f;
            EditorUtility.SetDirty(ps);
            AssetDatabase.SaveAssets();
            return ps;
        }

        static void OpenPlayback()
        {
            var active = EditorSceneManager.GetActiveScene();
            if (active.path == PlaybackScene) return;
            if (!Application.isBatchMode && !EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo())
                throw new OperationCanceledException();
            EditorSceneManager.OpenScene(PlaybackScene, OpenSceneMode.Single);
        }

        static void SetLayer(GameObject go, int layer)
        {
            foreach (var t in go.GetComponentsInChildren<Transform>(true)) t.gameObject.layer = layer;
        }

        [MenuItem("SOLARIS Visual/1 Install dashboard HUD (Playback)")]
        public static void InstallDashboard()
        {
            OpenPlayback();
            int visual = EnsureVisualLayer();
            var player = Object.FindFirstObjectByType<TrajectoryPlayer>();
            if (player == null || player.car == null)
                throw new InvalidOperationException("Playback.unity has no TrajectoryPlayer with a car");
            var driver = Object.FindFirstObjectByType<VehicleDriver>();

            // old display pieces off (kept in the scene, not deleted)
            foreach (var old in Object.FindObjectsByType<PvHud>(FindObjectsInactive.Include, FindObjectsSortMode.None))
                old.enabled = false;
            foreach (var old in Object.FindObjectsByType<ShadeMarkers>(FindObjectsInactive.Include, FindObjectsSortMode.None))
                old.enabled = false;

            var lit = player.car.GetComponent<FacetLitShare>();
            if (lit == null) lit = player.car.gameObject.AddComponent<FacetLitShare>();
            lit.player = player;

            var go = GameObject.Find("Visual_Dashboard");
            if (go == null) go = new GameObject("Visual_Dashboard");
            var doc = go.GetComponent<UIDocument>();
            if (doc == null) doc = go.AddComponent<UIDocument>();
            doc.panelSettings = HudPanelSettings();
            doc.sortingOrder = 10;
            var hud = go.GetComponent<DashboardHud>();
            if (hud == null) hud = go.AddComponent<DashboardHud>();
            hud.player = player;
            hud.litShare = lit;
            hud.driver = driver;
            SetLayer(go, visual);

            var scene = player.gameObject.scene;
            EditorSceneManager.MarkSceneDirty(scene);
            EditorSceneManager.SaveScene(scene);
            Debug.Log("[VisualSetup] dashboard HUD installed in Playback.unity (PvHud and ShadeMarkers disabled)");
        }

        public static void InstallDashboardBatch() => Batch(InstallDashboard);

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
