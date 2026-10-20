// SOLARIS-Twin visual: dashboard HUD for the Playback scene (replaces the PvHud box).
// Display only. PV power and trip energy come from Python (HudSeries); sun angles from the
// trajectory's pvlib values (TrajectoryPlayer); lit shares from FacetLitShare's rays.
//   top left   clock (MST), date, trip, speed, progress, play state
//   top centre covered/tunnel badge
//   top right  sun compass, car-relative (car points up)
//   right      car diagram: lit share per facet + Python W per facet
//   bottom     PV gauge, trip Wh, 60 s sparkline
// Key H shows/hides the HUD.
using System;
using System.Collections.Generic;
using System.Globalization;
using UnityEngine;
using UnityEngine.UIElements;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

namespace SolarisTwin.Visual
{
    [RequireComponent(typeof(UIDocument))]
    public class DashboardHud : MonoBehaviour
    {
        public TrajectoryPlayer player;
        public FacetLitShare litShare;
        public VehicleDriver driver;
        public float gaugeMaxW = 2000f;
        public bool show = true;

        static readonly Color Panel = new Color(0.035f, 0.05f, 0.075f, 0.74f);
        static readonly Color Edge = new Color(1f, 1f, 1f, 0.08f);
        static readonly Color Ink = new Color(0.94f, 0.95f, 0.97f);
        static readonly Color Ink2 = new Color(0.66f, 0.70f, 0.76f);
        static readonly Color Muted = new Color(0.42f, 0.46f, 0.52f);
        static readonly Color Amber = new Color(1f, 0.74f, 0.16f);
        static readonly Color Track = new Color(1f, 1f, 1f, 0.10f);
        static readonly Color Badge = new Color(0.95f, 0.45f, 0.10f, 0.92f);

        static readonly Dictionary<string, string> Pretty = new()
        {
            ["roof"] = "Roof", ["hood"] = "Hood", ["tailgate"] = "Tailgate",
            ["side_left"] = "Left side", ["side_right"] = "Right side",
        };

        HudSeries _series = new HudSeries();
        string _seriesFor;
        VisualElement _root, _gauge, _spark, _compass, _car, _tunnel, _progressFill, _northTag;
        Label _pv, _pvUnit, _tripWh, _avg, _clock, _date, _trip, _speed, _state, _sun;
        readonly Dictionary<string, (VisualElement swatch, Label text)> _rows = new();
        float _pvNow = float.NaN, _sunAz, _sunEl, _heading;
        readonly float[] _sparkBuf = new float[60];
        int _sparkN;

        // ------------------------------------------------------------------ setup
        void Start()
        {
            var doc = GetComponent<UIDocument>();
            if (doc.panelSettings == null)
            {
                var ps = ScriptableObject.CreateInstance<PanelSettings>();
                ps.scaleMode = PanelScaleMode.ScaleWithScreenSize;
                ps.referenceResolution = new Vector2Int(1920, 1080);
                doc.panelSettings = ps;
            }
            Build(doc.rootVisualElement);
        }

        static Label Text(string s, float size, Color c, bool bold = false)
        {
            var l = new Label(s);
            l.style.fontSize = size;
            l.style.color = c;
            l.style.unityFontStyleAndWeight = bold ? FontStyle.Bold : FontStyle.Normal;
            l.style.marginLeft = l.style.marginRight = l.style.marginTop = l.style.marginBottom = 0;
            l.style.paddingLeft = l.style.paddingRight = l.style.paddingTop = l.style.paddingBottom = 0;
            l.pickingMode = PickingMode.Ignore;
            return l;
        }

        static VisualElement Box(float left, float top, float right, float bottom, float w, float h)
        {
            var v = new VisualElement { pickingMode = PickingMode.Ignore };
            v.style.position = Position.Absolute;
            if (left >= 0) v.style.left = left;
            if (top >= 0) v.style.top = top;
            if (right >= 0) v.style.right = right;
            if (bottom >= 0) v.style.bottom = bottom;
            if (w > 0) v.style.width = w;
            if (h > 0) v.style.height = h;
            v.style.backgroundColor = Panel;
            foreach (var r in new Action<StyleLength>[] { x => v.style.borderTopLeftRadius = x,
                         x => v.style.borderTopRightRadius = x, x => v.style.borderBottomLeftRadius = x,
                         x => v.style.borderBottomRightRadius = x })
                r(14);
            v.style.borderTopWidth = v.style.borderBottomWidth = v.style.borderLeftWidth = v.style.borderRightWidth = 1;
            v.style.borderTopColor = v.style.borderBottomColor = v.style.borderLeftColor = v.style.borderRightColor = Edge;
            v.style.paddingLeft = v.style.paddingRight = 16;
            v.style.paddingTop = v.style.paddingBottom = 12;
            return v;
        }

        static VisualElement Canvas(float w, float h, Action<MeshGenerationContext> draw)
        {
            var v = new VisualElement { pickingMode = PickingMode.Ignore };
            v.style.width = w;
            v.style.height = h;
            v.generateVisualContent += draw;
            return v;
        }

        void Build(VisualElement root)
        {
            _root = root;
            root.Clear();
            root.pickingMode = PickingMode.Ignore;
            root.style.flexGrow = 1;
            var font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            if (font != null) root.style.unityFontDefinition = FontDefinition.FromFont(font);

            // top left: clock, date, trip, speed, progress
            var tl = Box(24, 24, -1, -1, 360, 0);
            _clock = Text("--:--:--", 34, Ink, true);
            _date = Text("", 15, Ink2);
            _trip = Text("", 13, Muted);
            var speedRow = new VisualElement { pickingMode = PickingMode.Ignore };
            speedRow.style.flexDirection = FlexDirection.Row;
            speedRow.style.alignItems = Align.FlexEnd;
            speedRow.style.marginTop = 6;
            _speed = Text("0", 40, Ink, true);
            var kmh = Text(" km/h", 15, Ink2);
            kmh.style.marginBottom = 7;
            speedRow.Add(_speed);
            speedRow.Add(kmh);
            var bar = new VisualElement { pickingMode = PickingMode.Ignore };
            bar.style.height = 5;
            bar.style.marginTop = 8;
            bar.style.backgroundColor = Track;
            bar.style.borderTopLeftRadius = bar.style.borderTopRightRadius =
                bar.style.borderBottomLeftRadius = bar.style.borderBottomRightRadius = 3;
            _progressFill = new VisualElement { pickingMode = PickingMode.Ignore };
            _progressFill.style.height = 5;
            _progressFill.style.width = Length.Percent(0);
            _progressFill.style.backgroundColor = Amber;
            _progressFill.style.borderTopLeftRadius = _progressFill.style.borderBottomLeftRadius = 3;
            bar.Add(_progressFill);
            _state = Text("", 13, Ink2);
            _state.style.marginTop = 6;
            foreach (var e in new VisualElement[] { _clock, _date, _trip, speedRow, bar, _state }) tl.Add(e);
            root.Add(tl);

            // top centre: covered badge
            _tunnel = new VisualElement { pickingMode = PickingMode.Ignore };
            _tunnel.style.position = Position.Absolute;
            _tunnel.style.top = 24;
            _tunnel.style.left = Length.Percent(50);
            _tunnel.style.translate = new Translate(Length.Percent(-50), 0);
            _tunnel.style.backgroundColor = Badge;
            _tunnel.style.paddingLeft = _tunnel.style.paddingRight = 18;
            _tunnel.style.paddingTop = _tunnel.style.paddingBottom = 8;
            _tunnel.style.borderTopLeftRadius = _tunnel.style.borderTopRightRadius =
                _tunnel.style.borderBottomLeftRadius = _tunnel.style.borderBottomRightRadius = 10;
            _tunnel.Add(Text("COVERED · tunnel / under bridge · no sun on the skin", 16, Color.white, true));
            _tunnel.style.display = DisplayStyle.None;
            root.Add(_tunnel);

            // top right: sun compass
            var tr = Box(-1, 24, 24, -1, 236, 0);
            tr.Add(Text("SUN, car-relative", 12, Muted, true));
            var compassWrap = new VisualElement { pickingMode = PickingMode.Ignore };
            compassWrap.style.width = 200;
            compassWrap.style.height = 200;
            compassWrap.style.marginTop = 6;
            _compass = Canvas(200, 200, DrawCompass);
            _compass.style.position = Position.Absolute;
            compassWrap.Add(_compass);
            _northTag = Text("N", 13, Ink2, true);
            _northTag.style.position = Position.Absolute;
            compassWrap.Add(_northTag);
            tr.Add(compassWrap);
            _sun = Text("", 14, Ink);
            _sun.style.marginTop = 6;
            tr.Add(_sun);
            root.Add(tr);

            // right: car diagram with per-facet rows
            var cr = Box(-1, 330, 24, -1, 236, 0);
            cr.Add(Text("PANELS · direct sun · PV power", 12, Muted, true));
            var carWrap = new VisualElement { pickingMode = PickingMode.Ignore };
            carWrap.style.alignItems = Align.Center;
            carWrap.style.marginTop = 6;
            _car = Canvas(120, 220, DrawCar);
            carWrap.Add(_car);
            cr.Add(carWrap);
            foreach (var f in HudSeries.Facets)
            {
                var row = new VisualElement { pickingMode = PickingMode.Ignore };
                row.style.flexDirection = FlexDirection.Row;
                row.style.alignItems = Align.Center;
                row.style.marginTop = 4;
                var sw = new VisualElement { pickingMode = PickingMode.Ignore };
                sw.style.width = 12;
                sw.style.height = 12;
                sw.style.marginRight = 8;
                sw.style.borderTopLeftRadius = sw.style.borderTopRightRadius =
                    sw.style.borderBottomLeftRadius = sw.style.borderBottomRightRadius = 3;
                var tx = Text("", 13, Ink);
                row.Add(sw);
                row.Add(tx);
                cr.Add(row);
                _rows[f] = (sw, tx);
            }
            var note = Text("PV includes diffuse sky light,\nso it stays above 0 W in shade.", 11, Muted);
            note.style.marginTop = 8;
            note.style.whiteSpace = WhiteSpace.Normal;
            cr.Add(note);
            root.Add(cr);

            // bottom left: PV gauge, trip energy, sparkline
            var bl = Box(24, -1, -1, 24, 600, 250);
            bl.style.flexDirection = FlexDirection.Row;
            var gaugeWrap = new VisualElement { pickingMode = PickingMode.Ignore };
            gaugeWrap.style.width = 220;
            gaugeWrap.style.height = 220;
            _gauge = Canvas(220, 220, DrawGauge);
            _gauge.style.position = Position.Absolute;
            gaugeWrap.Add(_gauge);
            var centre = new VisualElement { pickingMode = PickingMode.Ignore };
            centre.style.position = Position.Absolute;
            centre.style.left = 0;
            centre.style.right = 0;
            centre.style.top = 78;
            centre.style.alignItems = Align.Center;
            _pv = Text("--", 44, Ink, true);
            _pvUnit = Text("W  PV now", 14, Ink2);
            centre.Add(_pv);
            centre.Add(_pvUnit);
            gaugeWrap.Add(centre);
            bl.Add(gaugeWrap);
            var right = new VisualElement { pickingMode = PickingMode.Ignore };
            right.style.marginLeft = 20;
            right.style.flexGrow = 1;
            right.Add(Text("TRIP ENERGY", 12, Muted, true));
            _tripWh = Text("-- Wh", 34, Amber, true);
            right.Add(_tripWh);
            var lbl = Text("LAST 60 s", 12, Muted, true);
            lbl.style.marginTop = 10;
            right.Add(lbl);
            _spark = Canvas(320, 96, DrawSpark);
            _spark.style.marginTop = 4;
            right.Add(_spark);
            _avg = Text("", 13, Ink2);
            _avg.style.marginTop = 4;
            right.Add(_avg);
            bl.Add(right);
            root.Add(bl);

            var keys = Text("H HUD · M dots · Space pause · ←/→ 10 s · [ ] speed · Tab drive · C view",
                12, new Color(1, 1, 1, 0.55f));
            keys.style.position = Position.Absolute;
            keys.style.right = 24;
            keys.style.bottom = 16;
            root.Add(keys);
        }

        // ------------------------------------------------------------------ per frame
        void Update()
        {
#if ENABLE_INPUT_SYSTEM
            var k = Keyboard.current;
            if (k != null && k.hKey.wasPressedThisFrame) show = !show;
#endif
            if (_root == null) return;
            _root.style.display = show ? DisplayStyle.Flex : DisplayStyle.None;
            if (player == null || !player.HasRow) return;
            if (_seriesFor != player.trajectoryPath)
            {
                _seriesFor = player.trajectoryPath;
                _series = HudSeries.Load(HudSeries.ForTrajectory(player.trajectoryPath));
            }
            var r = player.Current;
            bool driving = player.externalControl;

            // clock and trip (MST = UTC-7, Arizona has no DST)
            if (DateTime.TryParse(r.tUtc, CultureInfo.InvariantCulture,
                    DateTimeStyles.AdjustToUniversal | DateTimeStyles.AssumeUniversal, out var utc))
            {
                var mst = utc.AddHours(-7);
                _clock.text = mst.ToString("HH:mm:ss", CultureInfo.InvariantCulture) + " MST";
                _date.text = mst.ToString("dddd d MMMM yyyy", CultureInfo.InvariantCulture);
            }
            _trip.text = TripLabel(player.trajectoryPath);
            float kmh = (driving && driver != null ? driver.Speed : r.speedMps) * 3.6f;
            _speed.text = Mathf.Abs(kmh).ToString("0", CultureInfo.InvariantCulture);
            _progressFill.style.width = Length.Percent(100f * player.Time01);
            _state.text = driving ? "DRIVE MODE · sun held at this record"
                : player.TilesLoading ? $"loading tiles {player.TileProgress:0} %"
                : player.Playing ? $"playing ×{player.speed:0.###}" : "paused";
            _tunnel.style.display = player.Covered && !driving ? DisplayStyle.Flex : DisplayStyle.None;

            // sun (from the trajectory's pvlib angles) relative to the car
            var d = player.SunDirection;
            _sunAz = (Mathf.Atan2(d.x, d.z) * Mathf.Rad2Deg + 360f) % 360f;
            _sunEl = player.SunElevation;
            _heading = player.car != null ? player.car.eulerAngles.y : 0f;
            _sun.text = _sunEl > 0f
                ? $"elevation {_sunEl:0.0}°   azimuth {_sunAz:0}°"
                : $"sun below the horizon ({_sunEl:0.0}°)";
            float nAng = (-_heading - 90f) * Mathf.Deg2Rad; // dial: up = car forward
            _northTag.style.left = 100 + 88 * Mathf.Cos(nAng) - 5;
            _northTag.style.top = 100 + 88 * Mathf.Sin(nAng) - 8;

            // PV and trip energy from Python
            int row = driving ? -1 : _series.RowOf(r.tUtc);
            if (row >= 0)
            {
                _pvNow = _series.PvW[row];
                _pv.text = _pvNow.ToString("0", CultureInfo.InvariantCulture);
                _pvUnit.text = "W  PV now";
                _tripWh.text = _series.TripWh[row].ToString("0.0", CultureInfo.InvariantCulture) + " Wh";
                _sparkN = Mathf.Min(60, row + 1);
                float sum = 0f;
                for (int i = 0; i < _sparkN; i++)
                {
                    _sparkBuf[i] = _series.PvW[row - _sparkN + 1 + i];
                    sum += _sparkBuf[i];
                }
                _avg.text = $"mean {sum / _sparkN:0} W   peak {Max(_sparkBuf, _sparkN):0} W";
            }
            else
            {
                _pvNow = float.NaN;
                _pv.text = "--";
                _pvUnit.text = driving ? "W  n/a in drive mode" : "W  no Python series";
                _tripWh.text = "-- Wh";
                _sparkN = 0;
                _avg.text = "";
            }

            // per-facet rows: live lit share (Unity rays) + Python W
            foreach (var f in HudSeries.Facets)
            {
                var (sw, tx) = _rows[f];
                float share = Lit(f);
                sw.style.backgroundColor = ShareColor(share);
                string w = row >= 0 && _series.FacetW.TryGetValue(f, out var fw) ? $"{fw[row]:0} W" : "";
                string s = float.IsNaN(share) ? "sun behind" : $"sun {100f * share:0} %";
                tx.text = $"{Pretty[f],-11} {s}   {w}";
            }

            _gauge.MarkDirtyRepaint();
            _spark.MarkDirtyRepaint();
            _compass.MarkDirtyRepaint();
            _car.MarkDirtyRepaint();
        }

        static float Max(float[] a, int n)
        {
            float m = 0f;
            for (int i = 0; i < n; i++) m = Mathf.Max(m, a[i]);
            return m;
        }

        float Lit(string facet) =>
            litShare != null && litShare.Shares.TryGetValue(facet, out var s) ? s.LitFraction : float.NaN;

        static Color ShareColor(float share) =>
            float.IsNaN(share) ? FacetLitShare.Off : Color.Lerp(FacetLitShare.BldShade, FacetLitShare.Lit, share);

        static string TripLabel(string path)
        {
            string n = System.IO.Path.GetFileNameWithoutExtension(path).Replace("trajectory_", "");
            var p = n.Split('_'); // R-DENSE fwd 1800 medium 2023-12-21
            if (p.Length < 4 || !int.TryParse(p[2], out int secs)) return n;
            var dep = new TimeSpan(7, 30, 0).Add(TimeSpan.FromSeconds(secs));
            string dir = p[1] == "fwd" ? "forward" : "reverse";
            return $"{p[0]} {dir} · departs {dep:hh\\:mm} · {p[3]} traffic";
        }

        // ------------------------------------------------------------------ drawing
        void DrawGauge(MeshGenerationContext mgc)
        {
            var p = mgc.painter2D;
            var c = new Vector2(110, 116);
            const float R = 92f, a0 = 135f, sweep = 270f;
            p.lineCap = LineCap.Round;
            p.lineWidth = 14;
            p.strokeColor = Track;
            p.BeginPath();
            p.Arc(c, R, Angle.Degrees(a0), Angle.Degrees(a0 + sweep));
            p.Stroke();
            if (!float.IsNaN(_pvNow) && _pvNow > 0.5f)
            {
                float f = Mathf.Clamp01(_pvNow / gaugeMaxW);
                p.strokeColor = Amber;
                p.BeginPath();
                p.Arc(c, R, Angle.Degrees(a0), Angle.Degrees(a0 + sweep * f));
                p.Stroke();
            }
            p.lineCap = LineCap.Butt;
            p.lineWidth = 2;
            p.strokeColor = Muted;
            for (int w = 0; w <= (int)gaugeMaxW; w += 500)
            {
                float ang = (a0 + sweep * w / gaugeMaxW) * Mathf.Deg2Rad;
                var dir = new Vector2(Mathf.Cos(ang), Mathf.Sin(ang));
                p.BeginPath();
                p.MoveTo(c + dir * (R - 16));
                p.LineTo(c + dir * (R - 24));
                p.Stroke();
            }
        }

        void DrawSpark(MeshGenerationContext mgc)
        {
            var p = mgc.painter2D;
            float w = 320, h = 96;
            p.lineWidth = 1;
            p.strokeColor = Track;
            p.BeginPath();
            p.MoveTo(new Vector2(0, h - 1));
            p.LineTo(new Vector2(w, h - 1));
            p.Stroke();
            if (_sparkN < 2) return;
            float top = Mathf.Max(100f, Max(_sparkBuf, _sparkN) * 1.15f);
            Vector2 P(int i) => new Vector2(w * (60 - _sparkN + i) / 59f, h - 2 - (h - 6) * _sparkBuf[i] / top);
            p.fillColor = new Color(Amber.r, Amber.g, Amber.b, 0.18f);
            p.BeginPath();
            p.MoveTo(new Vector2(P(0).x, h - 1));
            for (int i = 0; i < _sparkN; i++) p.LineTo(P(i));
            p.LineTo(new Vector2(P(_sparkN - 1).x, h - 1));
            p.ClosePath();
            p.Fill();
            p.lineWidth = 2;
            p.lineJoin = LineJoin.Round;
            p.strokeColor = Amber;
            p.BeginPath();
            p.MoveTo(P(0));
            for (int i = 1; i < _sparkN; i++) p.LineTo(P(i));
            p.Stroke();
        }

        void DrawCompass(MeshGenerationContext mgc)
        {
            var p = mgc.painter2D;
            var c = new Vector2(100, 100);
            const float R = 78f;
            p.lineWidth = 2;
            p.strokeColor = Track;
            p.BeginPath();
            p.Arc(c, R, Angle.Degrees(0), Angle.Degrees(360));
            p.Stroke();
            p.BeginPath();
            p.Arc(c, R * 2f / 3f, Angle.Degrees(0), Angle.Degrees(360)); // 30 deg elevation ring
            p.Stroke();
            p.BeginPath();
            p.Arc(c, R / 3f, Angle.Degrees(0), Angle.Degrees(360)); //      60 deg
            p.Stroke();
            // car in the middle, pointing up
            p.fillColor = Ink2;
            p.BeginPath();
            p.MoveTo(c + new Vector2(0, -12));
            p.LineTo(c + new Vector2(8, 10));
            p.LineTo(c + new Vector2(0, 5));
            p.LineTo(c + new Vector2(-8, 10));
            p.ClosePath();
            p.Fill();
            // sun: angle relative to the heading, radius from elevation (zenith in the centre)
            float rel = (_sunAz - _heading - 90f) * Mathf.Deg2Rad;
            float rr = _sunEl > 0f ? R * (1f - _sunEl / 90f) : R;
            var s = c + new Vector2(Mathf.Cos(rel), Mathf.Sin(rel)) * rr;
            if (_sunEl > 0f)
            {
                p.fillColor = new Color(Amber.r, Amber.g, Amber.b, 0.25f);
                p.BeginPath();
                p.Arc(s, 15, Angle.Degrees(0), Angle.Degrees(360));
                p.Fill();
                p.fillColor = Amber;
                p.BeginPath();
                p.Arc(s, 8, Angle.Degrees(0), Angle.Degrees(360));
                p.Fill();
            }
            else
            {
                p.strokeColor = Muted;
                p.BeginPath();
                p.Arc(s, 7, Angle.Degrees(0), Angle.Degrees(360));
                p.Stroke();
            }
        }

        void DrawCar(MeshGenerationContext mgc)
        {
            var p = mgc.painter2D;
            // top view, front at the top: body 120 x 220 px ~ 2.0 x 5.0 m
            void Rect(float x, float y, float w, float h, Color fill)
            {
                p.fillColor = fill;
                p.BeginPath();
                p.MoveTo(new Vector2(x, y));
                p.LineTo(new Vector2(x + w, y));
                p.LineTo(new Vector2(x + w, y + h));
                p.LineTo(new Vector2(x, y + h));
                p.ClosePath();
                p.Fill();
            }
            p.lineWidth = 2;
            p.strokeColor = Ink2;
            p.fillColor = new Color(1, 1, 1, 0.05f);
            p.BeginPath();
            p.MoveTo(new Vector2(30, 2));
            p.LineTo(new Vector2(90, 2));
            p.QuadraticCurveTo(new Vector2(118, 4), new Vector2(118, 30));
            p.LineTo(new Vector2(118, 200));
            p.QuadraticCurveTo(new Vector2(118, 218), new Vector2(96, 218));
            p.LineTo(new Vector2(24, 218));
            p.QuadraticCurveTo(new Vector2(2, 218), new Vector2(2, 200));
            p.LineTo(new Vector2(2, 30));
            p.QuadraticCurveTo(new Vector2(2, 4), new Vector2(30, 2));
            p.ClosePath();
            p.Fill();
            p.Stroke();
            // facet footprints (yaml placeholder layout, to scale)
            Rect(28, 12, 64, 40, ShareColor(Lit("hood"))); //            x 1.26..2.24 m
            Rect(28, 68, 64, 112, ShareColor(Lit("roof"))); //           x -1.48..1.28 m
            Rect(36, 196, 48, 12, ShareColor(Lit("tailgate"))); //       x -2.48..-2.23 m
            Rect(4, 30, 9, 160, ShareColor(Lit("side_left"))); //        x -2..2 m, left
            Rect(107, 30, 9, 160, ShareColor(Lit("side_right"))); //     right
        }
    }
}
