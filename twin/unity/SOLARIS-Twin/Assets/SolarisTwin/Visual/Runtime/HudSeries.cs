// SOLARIS-Twin visual: per-second PV for the HUD, read from Python
// (twin/exchange/visual/hud_<trip>_<date>.csv, written by twin/visual/export_visual.py).
// Unity never computes energy; this only looks values up by record time.
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using UnityEngine;

namespace SolarisTwin.Visual
{
    public class HudSeries
    {
        public static readonly string[] Facets = { "roof", "hood", "tailgate", "side_left", "side_right" };

        readonly Dictionary<string, int> _row = new Dictionary<string, int>();
        public float[] PvW { get; private set; } = new float[0];
        public float[] TripWh { get; private set; } = new float[0];
        public Dictionary<string, float[]> FacetW { get; } = new Dictionary<string, float[]>();
        public string[] Street { get; private set; } = new string[0];
        public string Path { get; private set; }
        public bool Loaded => PvW.Length > 0;

        /// The HUD file that belongs to a trajectory file (same trip and date).
        public static string ForTrajectory(string trajectoryPath)
        {
            string name = System.IO.Path.GetFileNameWithoutExtension(trajectoryPath);
            string id = name.StartsWith("trajectory_") ? name.Substring("trajectory_".Length) : name;
            return TwinPaths.Resolve($"../../exchange/visual/hud_{id}.csv");
        }

        public static HudSeries Load(string path)
        {
            var s = new HudSeries { Path = path };
            if (!File.Exists(path))
            {
                Debug.LogWarning($"[HUD] no PV series at {path}; run python twin/visual/export_visual.py");
                return s;
            }
            var inv = CultureInfo.InvariantCulture;
            var lines = File.ReadAllLines(path);
            var head = lines[0].Split(',');
            int Col(string c) => System.Array.IndexOf(head, c);
            int iT = Col("t_utc"), iP = Col("pv_W"), iE = Col("trip_Wh"), iS = Col("street");
            var fi = new Dictionary<string, int>();
            foreach (var f in Facets) fi[f] = Col($"pv_{f}_W");
            int n = lines.Length - 1;
            s.PvW = new float[n];
            s.TripWh = new float[n];
            foreach (var f in Facets) s.FacetW[f] = new float[n];
            s.Street = new string[n];
            for (int k = 0; k < n; k++)
            {
                var c = lines[k + 1].Split(',');
                s._row[c[iT]] = k;
                s.Street[k] = iS >= 0 && iS < c.Length ? c[iS] : "";
                s.PvW[k] = float.Parse(c[iP], inv);
                s.TripWh[k] = float.Parse(c[iE], inv);
                foreach (var f in Facets)
                    if (fi[f] >= 0) s.FacetW[f][k] = float.Parse(c[fi[f]], inv);
            }
            return s;
        }

        /// Row of a record time (t_utc), or -1.
        public int RowOf(string tUtc) => _row.TryGetValue(tUtc, out int k) ? k : -1;
    }
}
