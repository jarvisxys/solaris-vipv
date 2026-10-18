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
            string pv = player.externalControl
                ? "n/a (drive mode)"
                : _pv.TryGetValue(r.tUtc, out float w) ? $"{w:F0} W" : "n/a";
            string state = player.TilesLoading
                ? $"loading tiles {player.TileProgress:F0} %"
                : player.Playing ? $"playing x{player.speed:0.###}" : "paused";
            string text =
                $"<b>PV power  {pv}</b>\n{r.tUtc}   sun el {r.sunElDeg:F1}°   {r.speedMps * 3.6f:F0} km/h" +
                (r.covered ? "   <b>covered</b>" : "") +
                $"\n{state}   {100f * player.Time01:F0} % of trip" +
                "\n<size=14>Space play/pause · ←/→ ∓10 s · [ ] speed · R restart · Tab drive · " +
                "M dots · right-drag orbit · scroll zoom · C reset view</size>";
            GUI.Box(new Rect(24, 24, 760, 3.8f * fontSize + 40), text, _style);
        }
    }
}
