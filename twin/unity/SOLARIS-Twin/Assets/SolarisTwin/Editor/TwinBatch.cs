// SOLARIS-Twin: headless E8 runs (workflow guide Sec. 6, step 10).
//
//   Unity.exe -batchmode -nographics -projectPath twin/unity/SOLARIS-Twin
//     -executeMethod SolarisTwin.Editor.TwinBatch.Run
//     -trajectory <csv | directory of trajectory_*.csv> -out <csv(.gz) | directory>
//     -samples <facet_samples.csv> -gcp <ground_control.csv> [-scene Assets/Scenes/E8.unity]
//     [-resume] -logFile -
//
// Opens the analysis scene, turns on back-face hits, runs the ground-control gate (exit 2
// if any mark is off by more than 0.5 m) and probes every record of every trajectory. In
// directory mode each trajectory_<x>.csv gives visibility_<x>.csv.gz. Exit 0 = success.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using Debug = UnityEngine.Debug;

namespace SolarisTwin.Editor
{
    public static class TwinBatch
    {
        static Dictionary<string, string> Args()
        {
            var a = Environment.GetCommandLineArgs();
            var d = new Dictionary<string, string>();
            for (int i = 0; i < a.Length; i++)
            {
                if (!a[i].StartsWith("-")) continue;
                bool hasValue = i + 1 < a.Length && !a[i + 1].StartsWith("-");
                d[a[i]] = hasValue ? a[i + 1] : "";
            }
            return d;
        }

        static string Need(Dictionary<string, string> a, string key) =>
            a.TryGetValue(key, out var v) && v.Length > 0
                ? v
                : throw new ArgumentException($"missing argument {key}");

        public static void Run()
        {
            int code = 0;
            var clock = Stopwatch.StartNew();
            try
            {
                var a = Args();
                string scene = a.TryGetValue("-scene", out var s) && s.Length > 0
                    ? s
                    : "Assets/Scenes/E8.unity";
                EditorSceneManager.OpenScene(scene, OpenSceneMode.Single);
                Physics.queriesHitBackfaces = true; // heightfield meshes are open surfaces
                Physics.SyncTransforms();

                var samples = TwinIO.ReadFacetSamples(Need(a, "-samples"));
                string traj = Need(a, "-trajectory"), outArg = Need(a, "-out");
                bool dirMode = Directory.Exists(traj);
                string outDir = dirMode ? outArg : Path.GetDirectoryName(Path.GetFullPath(outArg));
                Directory.CreateDirectory(outDir);

                var gc = GroundControlCheck.Run(TwinIO.ReadGroundControl(Need(a, "-gcp")));
                GroundControlCheck.Write(gc, Path.Combine(outDir, "ground_control_unity.csv"));
                foreach (var r in gc)
                    Debug.Log($"[TwinBatch] mark {r.mark.id}: unity {r.uUnity:F3} m, " +
                              $"expected {r.mark.uExpected:F3} m, delta {r.delta:+0.000;-0.000} m " +
                              (r.pass ? "ok" : "FAIL"));
                if (!GroundControlCheck.AllPass(gc))
                {
                    Debug.LogError("[TwinBatch] ground-control check failed: no run counts");
                    code = 2;
                    return;
                }

                var car = new GameObject("ProbeCar").transform; // no colliders on the car
                var files = dirMode
                    ? Directory.GetFiles(traj, "trajectory_*.csv").OrderBy(f => f, StringComparer.Ordinal).ToArray()
                    : new[] { traj };
                bool resume = a.ContainsKey("-resume");
                long records = 0;
                for (int k = 0; k < files.Length; k++)
                {
                    string f = files[k];
                    string outPath = dirMode
                        ? Path.Combine(outDir,
                            Path.GetFileNameWithoutExtension(f).Replace("trajectory_", "visibility_") + ".csv.gz")
                        : outArg;
                    if (resume && File.Exists(outPath)) continue;
                    var rows = TwinIO.ReadTrajectory(f);
                    WriteVisibility(rows, car, samples, outPath);
                    records += rows.Count;
                    Debug.Log($"[TwinBatch] {k + 1}/{files.Length} {Path.GetFileName(f)}: " +
                              $"{rows.Count} records, {clock.Elapsed.TotalSeconds:F0} s");
                }
                File.WriteAllText(Path.Combine(outDir, "unity_run.txt"),
                    $"unity {Application.unityVersion}\nfiles {files.Length}\nrecords {records}\n" +
                    $"samples {samples.Length}\nseconds {clock.Elapsed.TotalSeconds.ToString("F1", CultureInfo.InvariantCulture)}\n");
            }
            catch (Exception e)
            {
                Debug.LogException(e);
                code = 1;
            }
            finally
            {
                Debug.Log($"[TwinBatch] exit {code} after {clock.Elapsed.TotalSeconds:F0} s");
                EditorApplication.Exit(code);
            }
        }

        public static void WriteVisibility(List<TrajRow> rows, Transform car, FacetSample[] samples, string path)
        {
            string tmp = path + ".part";
            using (var fs = File.Create(tmp))
            {
                Stream s = path.EndsWith(".gz")
                    ? new GZipStream(fs, System.IO.Compression.CompressionLevel.Optimal)
                    : (Stream)fs;
                using var w = new StreamWriter(s, new UTF8Encoding(false), 1 << 20) { NewLine = "\n" };
                w.Write(VisibilityProbe.Header + "\n");
                foreach (var r in rows) VisibilityProbe.Probe(r, car, samples, w);
            }
            if (File.Exists(path)) File.Delete(path);
            File.Move(tmp, path);
        }
    }
}
