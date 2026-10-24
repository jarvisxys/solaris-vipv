// SOLARIS-Twin visual: headless smoke test of the Playback visuals (developer tool).
// Opens Playback.unity without saving it, seeks the trajectory, runs the TrafficPlayer once and
// renders a few views to PNG. Needs a graphics device (batchmode without -nographics).
//   Unity -batchmode -projectPath ... -executeMethod SolarisTwin.Visual.Editor.VisualSmoke.TrafficBatch
//         -k 941 -shots <dir>
using System;
using System.IO;
using System.Reflection;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using Object = UnityEngine.Object;

namespace SolarisTwin.Visual.Editor
{
    public static class VisualSmoke
    {
        static string Arg(string name, string fallback)
        {
            var a = Environment.GetCommandLineArgs();
            int i = Array.IndexOf(a, name);
            return i >= 0 && i + 1 < a.Length ? a[i + 1] : fallback;
        }

        static void Call(object o, string method) =>
            o.GetType().GetMethod(method, BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public)
                ?.Invoke(o, null);

        public static void TrafficBatch()
        {
            int code = 0;
            try
            {
                EditorSceneManager.OpenScene(VisualSetup.PlaybackScene, OpenSceneMode.Single);
                int k = int.Parse(Arg("-k", "941"));
                string dir = Arg("-shots", Path.GetTempPath());
                Directory.CreateDirectory(dir);
                var player = Object.FindFirstObjectByType<TrajectoryPlayer>();
                var traffic = Object.FindFirstObjectByType<TrafficPlayer>();
                player.Load();
                player.Seek(k);
                Call(traffic, "Start");
                Call(traffic, "Update");
                Debug.Log($"[Smoke] k={k} cars={TrafficPlayer.CarsEnu.Count} heads={TrafficPlayer.SignalsEnu.Count}");
                Vector3 car = player.car.position;
                Vector3 fwd = player.car.forward;
                Shot(dir, "chase", car - fwd * 22f + Vector3.up * 7f, car + fwd * 15f);
                Shot(dir, "top", car + Vector3.up * 90f + fwd * 1f, car + fwd * 2f);
                // nearest signal ahead of the car
                Transform best = null;
                float bd = float.MaxValue;
                foreach (Transform s in traffic.transform.Find("Visual_TrafficSignals"))
                {
                    Vector3 d = s.position - car;
                    if (Vector3.Dot(d, fwd) < 0f) continue;
                    if (d.magnitude < bd)
                    {
                        bd = d.magnitude;
                        best = s;
                    }
                }
                if (best != null)
                    Shot(dir, "signal", best.position - best.forward * 25f + Vector3.up * 3.5f,
                        best.position + Vector3.up * 4.5f);
            }
            catch (Exception e)
            {
                Debug.LogException(e);
                code = 1;
            }
            finally { EditorApplication.Exit(code); }
        }

        /// Renders the EV sound of the first `-seconds` of the Playback trajectory to smoke_sound.wav
        /// (mono 48 kHz, 16 bit) plus smoke_sound_speed.csv, for listening and a spectrogram.
        public static void SoundBatch()
        {
            int code = 0;
            try
            {
                EditorSceneManager.OpenScene(VisualSetup.PlaybackScene, OpenSceneMode.Single);
                var player = Object.FindFirstObjectByType<TrajectoryPlayer>();
                player.Load();
                int seconds = Mathf.Min(int.Parse(Arg("-seconds", "120")), player.Count - 1);
                string dir = Arg("-shots", Path.GetTempPath());
                const int rate = 48000, block = 480; // 10 ms blocks, like the audio thread
                var synth = new EvSound.Synth();
                var pcm = new short[seconds * rate];
                var buf = new float[block];
                var speeds = new System.Text.StringBuilder("t,speed_mps\n");
                float last = 0f;
                for (int s = 0; s < seconds; s++)
                {
                    player.Seek(s);
                    float v = player.Current.speedMps;
                    synth.accel = s > 0 ? Mathf.Clamp(v - last, -4f, 4f) : 0f;
                    synth.speed = v;
                    synth.gain = 0.6f;
                    last = v;
                    speeds.Append($"{s},{v:0.00}\n");
                    for (int b = 0; b < rate / block; b++)
                    {
                        synth.Fill(buf, 1, rate);
                        for (int i = 0; i < block; i++)
                            pcm[s * rate + b * block + i] = (short)Mathf.Clamp(buf[i] * 32767f, -32768f, 32767f);
                    }
                }
                string wav = Path.Combine(dir, "smoke_sound.wav");
                using (var w = new BinaryWriter(File.Create(wav)))
                {
                    w.Write(System.Text.Encoding.ASCII.GetBytes("RIFF"));
                    w.Write(36 + pcm.Length * 2);
                    w.Write(System.Text.Encoding.ASCII.GetBytes("WAVEfmt "));
                    w.Write(16);
                    w.Write((short)1);
                    w.Write((short)1);
                    w.Write(rate);
                    w.Write(rate * 2);
                    w.Write((short)2);
                    w.Write((short)16);
                    w.Write(System.Text.Encoding.ASCII.GetBytes("data"));
                    w.Write(pcm.Length * 2);
                    foreach (var x in pcm) w.Write(x);
                }
                File.WriteAllText(Path.Combine(dir, "smoke_sound_speed.csv"), speeds.ToString());
                Debug.Log($"[Smoke] {wav} ({seconds} s)");
            }
            catch (Exception e)
            {
                Debug.LogException(e);
                code = 1;
            }
            finally { EditorApplication.Exit(code); }
        }

        static void Shot(string dir, string name, Vector3 from, Vector3 at)
        {
            var go = new GameObject("smoke_cam");
            var cam = go.AddComponent<Camera>();
            cam.transform.position = from;
            cam.transform.LookAt(at);
            cam.fieldOfView = 50f;
            cam.nearClipPlane = 0.3f;
            cam.farClipPlane = 5000f;
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = new Color(0.55f, 0.7f, 0.85f);
            var rt = new RenderTexture(1600, 900, 24);
            cam.targetTexture = rt;
            cam.Render();
            RenderTexture.active = rt;
            var tex = new Texture2D(rt.width, rt.height, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0, 0, rt.width, rt.height), 0, 0);
            tex.Apply();
            RenderTexture.active = null;
            string p = Path.Combine(dir, $"smoke_{name}.png");
            File.WriteAllBytes(p, tex.EncodeToPNG());
            cam.targetTexture = null;
            Object.DestroyImmediate(rt);
            Object.DestroyImmediate(go);
            Debug.Log($"[Smoke] {p}");
        }
    }
}
