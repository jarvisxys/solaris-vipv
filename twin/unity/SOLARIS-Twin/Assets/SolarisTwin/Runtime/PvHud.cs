// SOLARIS-Twin: heads-up overlay of PV power read from Python's output (workflow guide
// Sec. 6, step 11). Display only: Unity never computes energy.
// File: twin/exchange/render/pv_<trip>_<date>.csv with columns t_utc, pv_W.
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using UnityEngine;

namespace SolarisTwin
{
    public class PvHud : MonoBehaviour
    {
        public TrajectoryPlayer player;

        [Tooltip("pv_<trip>_<date>.csv, absolute or relative to the Unity project folder")]
        public string pvPath = "../../exchange/render/pv_R-DENSE_fwd_1800_medium_2023-12-21.csv";

        public int fontSize = 28;

        readonly Dictionary<string, float> _pv = new Dictionary<string, float>();
        GUIStyle _style;

        void Start()
        {
            var inv = CultureInfo.InvariantCulture;
            var lines = File.ReadAllLines(TwinPaths.Resolve(pvPath));
            for (int i = 1; i < lines.Length; i++)
            {
                var c = lines[i].Split(',');
                if (c.Length >= 2) _pv[c[0]] = float.Parse(c[1], NumberStyles.Float, inv);
            }
        }

        void OnGUI()
        {
            if (player == null || !player.HasRow) return;
            _style ??= new GUIStyle(GUI.skin.box)
            {
                fontSize = fontSize, alignment = TextAnchor.UpperLeft, richText = true,
            };
            var r = player.Current;
            string pv = _pv.TryGetValue(r.tUtc, out float w) ? $"{w:F0} W" : "n/a";
            string text =
                $"<b>PV power  {pv}</b>\n{r.tUtc}   sun el {r.sunElDeg:F1}°   {r.speedMps * 3.6f:F0} km/h" +
                (r.covered ? "   <b>covered</b>" : "");
            GUI.Box(new Rect(24, 24, 700, 2.6f * fontSize + 24), text, _style);
        }
    }
}
