// SOLARIS-Twin visual: Unity Recorder preset for Figure 3 and the Figure 3 scene switch.
// Recorder Window -> (top-right menu) Load Recorder List -> Visual/Recorder/Figure3_RecorderList:
//   Figure3_still_4K   Image Sequence, PNG, 3840 x 2160, Game View (photo mode keeps only the
//                      credits; Cesium's own credits stay, as the Google tiles require)
//   Figure3_chase_1080 Movie, MP4 H.264 High, 1920 x 1080 (off by default; guide Sec. 14)
// Both: 30 fps constant, manual start/stop, files in Recordings/figure3 (gitignored).
using System;
using UnityEditor;
using UnityEditor.Recorder;
using UnityEditor.Recorder.Encoder;
using UnityEditor.Recorder.Input;
using UnityEditor.SceneManagement;
using UnityEngine;
using Object = UnityEngine.Object;

namespace SolarisTwin.Visual.Editor
{
    public static class VisualRecorder
    {
        public const string PresetPath = "Assets/SolarisTwin/Visual/Recorder/Figure3_RecorderList.asset";

        [MenuItem("SOLARIS Visual/Figure 3: write Recorder preset")]
        public static void WritePreset()
        {
            System.IO.Directory.CreateDirectory("Assets/SolarisTwin/Visual/Recorder");
            var list = ScriptableObject.CreateInstance<RecorderControllerSettings>();
            list.SetRecordModeToManual();
            list.FrameRatePlayback = FrameRatePlayback.Constant;
            list.FrameRate = 30f;
            list.CapFrameRate = true;

            var still = ScriptableObject.CreateInstance<ImageRecorderSettings>();
            still.name = "Figure3_still_4K";
            still.Enabled = true;
            still.OutputFormat = ImageRecorderSettings.ImageRecorderOutputFormat.PNG;
            still.CaptureAlpha = false;
            still.imageInputSettings = new GameViewInputSettings { OutputWidth = 3840, OutputHeight = 2160 };
            still.OutputFile = "Recordings/figure3/fig3_R-DENSE_0800_1221_<Frame>";
            list.AddRecorderSettings(still);

            var movie = ScriptableObject.CreateInstance<MovieRecorderSettings>();
            movie.name = "Figure3_chase_1080";
            movie.Enabled = false;
            movie.EncoderSettings = new CoreEncoderSettings
            {
                Codec = CoreEncoderSettings.OutputCodec.MP4,
                EncodingQuality = CoreEncoderSettings.VideoEncodingQuality.High,
            };
            movie.ImageInputSettings = new GameViewInputSettings { OutputWidth = 1920, OutputHeight = 1080 };
            movie.CaptureAudio = false;
            movie.OutputFile = "Recordings/figure3/fig3_R-DENSE_0800_1221_chase";
            list.AddRecorderSettings(movie);

            RecorderControllerSettingsPreset.SaveAtPath(list, PresetPath);
            AssetDatabase.SaveAssets();
            Debug.Log($"[VisualRecorder] wrote {PresetPath}");
        }

        public static void WritePresetBatch() => Run(WritePreset);

        static TrajectoryPlayer OpenPlayback()
        {
            if (EditorSceneManager.GetActiveScene().path != VisualSetup.PlaybackScene)
                EditorSceneManager.OpenScene(VisualSetup.PlaybackScene, OpenSceneMode.Single);
            var player = Object.FindFirstObjectByType<TrajectoryPlayer>();
            if (player == null) throw new InvalidOperationException("Playback.unity has no TrajectoryPlayer");
            return player;
        }

        static void SetFigure3(bool on)
        {
            var player = OpenPlayback();
            var d = Object.FindFirstObjectByType<Figure3Director>(FindObjectsInactive.Include);
            if (d == null) throw new InvalidOperationException("run SOLARIS Visual -> 7 first");
            d.enabled = on;
            player.fixedFps = on ? 30 : 0; // the Recorder's frame rate; 0 = wall clock for viewing
            // analysis geometry (guide Sec. 12): shadows only for the figure, so the shadows on the
            // skin are exactly the analysed ones; hidden again for normal playback. Renderers only.
            if (on) SolarisTwin.Editor.TwinSetup.GeometryShadowsOnly();
            else SolarisTwin.Editor.TwinSetup.GeometryHidden();
            var scene = player.gameObject.scene;
            EditorSceneManager.MarkSceneDirty(scene);
            EditorSceneManager.SaveScene(scene);
            Debug.Log($"[VisualRecorder] Figure 3 mode {(on ? "on" : "off")} (TrajectoryPlayer.fixedFps = {player.fixedFps})");
        }

        [MenuItem("SOLARIS Visual/Figure 3: on (R-DENSE 08:00, 21 Dec, 08:03:52)")]
        public static void Figure3On() => SetFigure3(true);

        [MenuItem("SOLARIS Visual/Figure 3: off (normal playback)")]
        public static void Figure3Off() => SetFigure3(false);

        static void Run(Action a)
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
