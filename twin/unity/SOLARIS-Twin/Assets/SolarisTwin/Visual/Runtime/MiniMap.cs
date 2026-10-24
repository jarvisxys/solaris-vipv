// SOLARIS-Twin visual: heading-up mini-map with the sun (top right; the map turns so the car
// always points up, N marks north on the rim) and a north-up full map of the study area (key N). Display only. Data from Python (twin/exchange/visual): map.json (routes, parking
// sites, Overture footprints, OpenStreetMap landmarks, ENU) and map_naip.jpg (USDA NAIP aerial,
// north-up ENU square). The trip path comes from the exported trajectory; the sun direction from
// the trajectory's pvlib angles (TrajectoryPlayer). Unity computes nothing physical here.
//   N   full map          B   aerial / dark background
//   full map: mouse wheel zooms at the cursor, left-drag pans, it opens centred on the car.
using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.UIElements;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

namespace SolarisTwin.Visual
{
    [Serializable]
    public class MapRoute
    {
        public string id, label;
        public float[] xy;
    }

    [Serializable]
    public class MapPoint
    {
        public string id, label;
        public float x, y;
    }

    [Serializable]
    public class MapBuilding
    {
        public float h;
        public float[] xy;
    }

    [Serializable]
    public class MapJson
    {
        public MapRoute[] routes;
        public MapPoint[] points;
        public MapBuilding[] buildings;
        public MapPoint[] landmarks;
    }

    [Serializable]
    public class MapImageMeta
    {
        public float x0, y0, x1, y1;
        public int px;
    }

    [RequireComponent(typeof(UIDocument))]
    public class MiniMap : MonoBehaviour
    {
        public TrajectoryPlayer player;
        public float viewRadius = 450f; // m from the centre to the edge of the mini-map
        public float tallM = 20f;
        public bool showFull, aerial = true;

        public const float MiniSize = 260f;
        const float MiniDraw = MiniSize * 1.45f; // rotating layer: covers the panel at any angle
        const float FullSize = 940f;
        static readonly Color Bg = new Color(0.035f, 0.05f, 0.075f, 0.90f);
        static readonly Color Bldg = new Color(0.30f, 0.33f, 0.38f, 0.95f);
        static readonly Color BldgTall = new Color(0.50f, 0.54f, 0.60f, 0.95f);
        static readonly Color Road = new Color(1f, 1f, 1f, 0.55f);
        static readonly Color Path = new Color(1f, 0.74f, 0.16f);
        static readonly Color Ink = new Color(0.97f, 0.97f, 0.98f);
        static readonly Color Landmark = new Color(0.62f, 0.85f, 1f);
        static readonly Color Grid = new Color(1f, 1f, 1f, 0.22f);

        struct Shape
        {
            public Vector2[] pts;
            public Vector2 centre;
            public float radius;
            public bool tall;
        }

        class Tag
        {
            public Label label;
            public MapPoint point;
            public int priority;
        }

        MapJson _map;
        MapImageMeta _imgMeta;
        Texture2D _imgTex;
        readonly List<Shape> _bldg = new();
        readonly List<List<Vector2>> _routes = new();
        readonly List<Vector2> _path = new();
        string _pathFor;
        Vector2 _car, _sunDir;
        float _heading, _sunEl, _sunAz;
        Rect _world;
        float _fullBase, _zoom = 2f;
        Vector2 _fullCentre;
        bool _dragging;
        Vector2 _lastPointer;

        VisualElement _mini, _miniRot, _miniImg, _miniCanvas, _full, _fullImg, _fullCanvas;
        Label _sunText, _bgHint, _scaleText, _north;
        readonly List<Tag> _miniTags = new(), _fullTags = new();
        readonly List<Label> _gridCols = new(), _gridRows = new();

        // ------------------------------------------------------------------ setup
        void Start()
        {
            string dir = TwinPaths.Resolve("../../exchange/visual");
            string mj = System.IO.Path.Combine(dir, "map.json"),
                ij = System.IO.Path.Combine(dir, "map_naip.json"),
                jpg = System.IO.Path.Combine(dir, "map_naip.jpg");
            if (File.Exists(mj)) _map = JsonUtility.FromJson<MapJson>(File.ReadAllText(mj));
            else Debug.LogWarning($"[MiniMap] {mj} missing; run python twin/visual/export_visual.py --map");
            if (File.Exists(ij) && File.Exists(jpg))
            {
                _imgMeta = JsonUtility.FromJson<MapImageMeta>(File.ReadAllText(ij));
                _imgTex = new Texture2D(2, 2, TextureFormat.RGB24, true);
                _imgTex.LoadImage(File.ReadAllBytes(jpg));
                _imgTex.wrapMode = TextureWrapMode.Clamp;
                _imgTex.filterMode = FilterMode.Trilinear;
                _imgTex.anisoLevel = 4;
                _imgTex.Compress(true);
            }
            Prepare();

            var root = GetComponent<UIDocument>().rootVisualElement;
            root.pickingMode = PickingMode.Ignore;
            var font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            if (font != null) root.style.unityFontDefinition = FontDefinition.FromFont(font);

            // mini-map, top right, with the sun
            _mini = Panel(MiniSize, MiniSize + 26);
            _mini.style.right = 24;
            _mini.style.top = 24;
            // map layer, larger than the panel, turned about the panel centre (heading-up)
            _miniRot = new VisualElement { pickingMode = PickingMode.Ignore };
            _miniRot.style.position = Position.Absolute;
            _miniRot.style.width = _miniRot.style.height = MiniDraw;
            _miniRot.style.left = _miniRot.style.top = (MiniSize - MiniDraw) / 2f;
            _miniRot.style.overflow = Overflow.Hidden;
            _miniRot.style.transformOrigin = new TransformOrigin(Length.Percent(50), Length.Percent(50));
            _miniImg = Image();
            _miniRot.Add(_miniImg);
            _miniCanvas = Canvas(MiniDraw, MiniDraw, mgc => DrawMap(mgc, MiniDraw, MiniDraw, _car, MiniScale, true));
            _miniRot.Add(_miniCanvas);
            _mini.Add(_miniRot);
            _north = Text("N", 14, Ink, true);
            _north.style.position = Position.Absolute;
            _mini.Add(_north);
            _sunText = Text("", 13, Ink);
            _sunText.style.position = Position.Absolute;
            _sunText.style.left = 10;
            _sunText.style.top = MiniSize + 4;
            _mini.Add(_sunText);
            root.Add(_mini);

            // full map
            _full = Panel(FullSize, FullSize);
            _full.style.left = Length.Percent(50);
            _full.style.top = Length.Percent(50);
            _full.style.translate = new Translate(Length.Percent(-50), Length.Percent(-50));
            _fullImg = Image();
            _full.Add(_fullImg);
            _fullCanvas = Canvas(FullSize, FullSize, mgc => DrawMap(mgc, FullSize, FullSize, _fullCentre, FullScale, false));
            _full.Add(_fullCanvas);
            for (int i = 0; i < 24; i++)
            {
                _gridCols.Add(AddLabel(_full, 13, new Color(1, 1, 1, 0.8f)));
                _gridRows.Add(AddLabel(_full, 13, new Color(1, 1, 1, 0.8f)));
            }
            var title = Bar("STUDY AREA  ·  wheel zoom · drag pan · B background · N close", true);
            title.style.top = 0;
            _full.Add(title);
            var credit = Bar("Map data © OpenStreetMap contributors (ODbL) · buildings © Overture Maps Foundation · " +
                             "imagery USDA NAIP", false);
            credit.style.bottom = 0;
            _full.Add(credit);
            _scaleText = Text("", 12, Ink, true);
            _scaleText.style.position = Position.Absolute;
            _scaleText.style.left = 18;
            _scaleText.style.bottom = 38;
            _full.Add(_scaleText);
            _bgHint = Text("", 12, Ink);
            _bgHint.style.position = Position.Absolute;
            _bgHint.style.right = 16;
            _bgHint.style.bottom = 38;
            _full.Add(_bgHint);
            _full.style.display = DisplayStyle.None;
            root.Add(_full);

            int pr = 0;
            foreach (var (pt, col) in AllPoints())
            {
                _miniTags.Add(new Tag { label = AddLabel(_mini, 11, col), point = pt, priority = pr });
                _fullTags.Add(new Tag { label = AddLabel(_full, 13, col), point = pt, priority = pr });
                pr++;
            }
            // labels above the drawing, in priority order
            foreach (var t in _miniTags) t.label.BringToFront();
            foreach (var t in _fullTags) t.label.BringToFront();
            title.BringToFront();
            credit.BringToFront();
        }

        float MiniScale => MiniSize / 2f / viewRadius;
        float FullScale => _fullBase * _zoom;

        IEnumerable<(MapPoint, Color)> AllPoints()
        {
            if (_map?.points != null) foreach (var p in _map.points) yield return (p, Ink);
            if (_map?.landmarks != null) foreach (var p in _map.landmarks) yield return (p, Landmark);
        }

        void Prepare()
        {
            if (_imgMeta != null) _world = Rect.MinMaxRect(_imgMeta.x0, _imgMeta.y0, _imgMeta.x1, _imgMeta.y1);
            else _world = new Rect(-6000, -6000, 12000, 12000);
            _fullBase = FullSize / Mathf.Max(_world.width, _world.height);
            if (_map?.routes != null)
                foreach (var r in _map.routes)
                {
                    var pts = new List<Vector2>(r.xy.Length / 2);
                    for (int i = 0; i + 1 < r.xy.Length; i += 2) pts.Add(new Vector2(r.xy[i], r.xy[i + 1]));
                    _routes.Add(pts);
                }
            if (_map?.buildings != null)
                foreach (var b in _map.buildings)
                {
                    var pts = new Vector2[b.xy.Length / 2];
                    Vector2 c = Vector2.zero;
                    for (int i = 0; i < pts.Length; i++)
                    {
                        pts[i] = new Vector2(b.xy[2 * i], b.xy[2 * i + 1]);
                        c += pts[i];
                    }
                    c /= Mathf.Max(1, pts.Length);
                    float r = 0f;
                    foreach (var q in pts) r = Mathf.Max(r, (q - c).magnitude);
                    _bldg.Add(new Shape { pts = pts, centre = c, radius = r, tall = b.h >= tallM });
                }
        }

        static Label Text(string s, float size, Color c, bool bold = false)
        {
            var l = new Label(s) { pickingMode = PickingMode.Ignore };
            l.style.fontSize = size;
            l.style.color = c;
            l.style.unityFontStyleAndWeight = bold ? FontStyle.Bold : FontStyle.Normal;
            l.style.unityTextOutlineWidth = 0.18f;
            l.style.unityTextOutlineColor = Color.black;
            l.style.paddingLeft = l.style.paddingRight = l.style.paddingTop = l.style.paddingBottom = 0;
            l.style.marginLeft = l.style.marginRight = l.style.marginTop = l.style.marginBottom = 0;
            return l;
        }

        static Label AddLabel(VisualElement parent, float size, Color c)
        {
            var l = Text("", size, c);
            l.style.position = Position.Absolute;
            parent.Add(l);
            return l;
        }

        static VisualElement Bar(string text, bool bold)
        {
            var v = new VisualElement { pickingMode = PickingMode.Ignore };
            v.style.position = Position.Absolute;
            v.style.left = 0;
            v.style.right = 0;
            v.style.height = 30;
            v.style.backgroundColor = new Color(0f, 0f, 0f, 0.55f);
            v.style.justifyContent = Justify.Center;
            v.style.paddingLeft = 16;
            v.Add(Text(text, bold ? 14 : 11, new Color(1, 1, 1, bold ? 0.95f : 0.7f), bold));
            return v;
        }

        static VisualElement Panel(float w, float h)
        {
            var v = new VisualElement { pickingMode = PickingMode.Ignore };
            v.style.position = Position.Absolute;
            v.style.width = w;
            v.style.height = h;
            v.style.backgroundColor = Bg;
            v.style.overflow = Overflow.Hidden; // clip the map to the panel
            v.style.borderTopLeftRadius = v.style.borderTopRightRadius =
                v.style.borderBottomLeftRadius = v.style.borderBottomRightRadius = 12;
            v.style.borderTopWidth = v.style.borderBottomWidth = v.style.borderLeftWidth = v.style.borderRightWidth = 1;
            v.style.borderTopColor = v.style.borderBottomColor =
                v.style.borderLeftColor = v.style.borderRightColor = new Color(1, 1, 1, 0.12f);
            return v;
        }

        VisualElement Image()
        {
            var v = new VisualElement { pickingMode = PickingMode.Ignore };
            v.style.position = Position.Absolute;
            if (_imgTex != null) v.style.backgroundImage = Background.FromTexture2D(_imgTex);
            return v;
        }

        static VisualElement Canvas(float w, float h, Action<MeshGenerationContext> draw)
        {
            var v = new VisualElement { pickingMode = PickingMode.Ignore };
            v.style.position = Position.Absolute;
            v.style.width = w;
            v.style.height = h;
            v.generateVisualContent += draw;
            return v;
        }

        // ------------------------------------------------------------------ per frame
        void Update()
        {
            if (_mini == null || player == null || player.car == null) return;
            ChaseCamera.MouseBlocked = false;
#if ENABLE_INPUT_SYSTEM
            var k = Keyboard.current;
            if (k != null && k.nKey.wasPressedThisFrame)
            {
                showFull = !showFull;
                if (showFull)
                {
                    _fullCentre = _car;
                    _zoom = 2f;
                }
            }
            if (k != null && k.bKey.wasPressedThisFrame) aerial = !aerial;
            ChaseCamera.MouseBlocked = false;
            if (showFull) HandleMouse();
#endif
            if (_pathFor != player.trajectoryPath)
            {
                _pathFor = player.trajectoryPath;
                _path.Clear();
                foreach (var r in TwinIO.ReadTrajectory(TwinPaths.Resolve(player.trajectoryPath)))
                    _path.Add(new Vector2(r.xE, r.yN));
            }
            var pos = player.car.position;
            _car = new Vector2(pos.x, pos.z); // Unity x = east, z = north
            _heading = player.car.eulerAngles.y;
            var d = player.SunDirection; //     from the trajectory's pvlib angles
            _sunDir = new Vector2(d.x, d.z).normalized;
            _sunAz = (Mathf.Atan2(d.x, d.z) * Mathf.Rad2Deg + 360f) % 360f;
            _sunEl = player.SunElevation;
            _sunText.text = _sunEl > 0f
                ? $"SUN  elevation {_sunEl:0.0}°  ·  azimuth {_sunAz:0}°"
                : $"SUN  below the horizon ({_sunEl:0.0}°)";

            // heading-up: turn the map layer by -heading; labels and N stay upright
            _miniRot.style.rotate = new Rotate(Angle.Degrees(-_heading));
            PlaceImage(_miniImg, MiniDraw, MiniDraw, _car, MiniScale);
            PlaceTags(_miniTags, MiniSize, MiniSize, _car, MiniScale, 11, -_heading);
            var nd = Turn(new Vector2(0f, -1f), -_heading) * (MiniSize / 2f - 13f);
            _north.style.left = MiniSize / 2f + nd.x - 5f;
            _north.style.top = MiniSize / 2f + nd.y - 8f;
            _miniCanvas.MarkDirtyRepaint();

            _full.style.display = showFull ? DisplayStyle.Flex : DisplayStyle.None;
            if (showFull)
            {
                PlaceImage(_fullImg, FullSize, FullSize, _fullCentre, FullScale);
                PlaceTags(_fullTags, FullSize, FullSize, _fullCentre, FullScale, 13);
                PlaceGrid();
                PlaceScaleText(FullScale);
                _bgHint.text = aerial ? "B: aerial photo (USDA NAIP)" : "B: dark map";
                _fullCanvas.MarkDirtyRepaint();
            }
        }

#if ENABLE_INPUT_SYSTEM
        void HandleMouse()
        {
            var m = Mouse.current;
            if (m == null || _full.panel == null) return;
            Vector2 sp = m.position.ReadValue();
            sp.y = UnityEngine.Screen.height - sp.y;
            Vector2 local = RuntimePanelUtils.ScreenToPanel(_full.panel, sp) - _full.worldBound.position;
            bool inside = local.x >= 0 && local.y >= 0 && local.x <= FullSize && local.y <= FullSize;
            ChaseCamera.MouseBlocked = inside || _dragging; // the map owns the mouse under it
            float wheel = m.scroll.ReadValue().y;
            if (inside && Mathf.Abs(wheel) > 0.01f)
            {
                Vector2 before = FromScreen(local, FullSize, FullSize, _fullCentre, FullScale);
                _zoom = Mathf.Clamp(_zoom * (wheel > 0 ? 1.25f : 0.8f), 1f, 12f);
                _fullCentre += before - FromScreen(local, FullSize, FullSize, _fullCentre, FullScale);
            }
            if (m.leftButton.wasPressedThisFrame && inside)
            {
                _dragging = true;
                _lastPointer = local;
            }
            if (!m.leftButton.isPressed) _dragging = false;
            if (_dragging)
            {
                Vector2 dpx = local - _lastPointer;
                _fullCentre += new Vector2(-dpx.x, dpx.y) / FullScale;
                _lastPointer = local;
            }
            var half = new Vector2(_world.width, _world.height) / 2f;
            _fullCentre = new Vector2(
                Mathf.Clamp(_fullCentre.x, _world.center.x - half.x, _world.center.x + half.x),
                Mathf.Clamp(_fullCentre.y, _world.center.y - half.y, _world.center.y + half.y));
        }
#endif

        static Vector2 ToScreen(Vector2 w, float sw, float sh, Vector2 centre, float scale) =>
            new Vector2(sw / 2f + (w.x - centre.x) * scale, sh / 2f - (w.y - centre.y) * scale);

        static Vector2 FromScreen(Vector2 s, float sw, float sh, Vector2 centre, float scale) =>
            new Vector2(centre.x + (s.x - sw / 2f) / scale, centre.y - (s.y - sh / 2f) / scale);

        void PlaceImage(VisualElement img, float sw, float sh, Vector2 centre, float scale)
        {
            bool on = aerial && _imgTex != null;
            img.style.display = on ? DisplayStyle.Flex : DisplayStyle.None;
            if (!on) return;
            var tl = ToScreen(new Vector2(_world.xMin, _world.yMax), sw, sh, centre, scale);
            img.style.left = tl.x;
            img.style.top = tl.y;
            img.style.width = _world.width * scale;
            img.style.height = _world.height * scale;
        }

        /// Screen vector turned by deg (positive = clockwise on screen, whose y points down).
        static Vector2 Turn(Vector2 v, float deg)
        {
            float a = deg * Mathf.Deg2Rad, c = Mathf.Cos(a), s = Mathf.Sin(a);
            return new Vector2(v.x * c - v.y * s, v.x * s + v.y * c);
        }

        /// Labels in priority order (parking sites, then landmarks largest first); one that would
        /// overlap a label already placed is hidden, so zooming in reveals more names. `turnDeg`
        /// turns the anchor points about the panel centre (the heading-up mini-map).
        static void PlaceTags(List<Tag> tags, float sw, float sh, Vector2 centre, float scale, float font,
            float turnDeg = 0f)
        {
            var placed = new List<Rect>();
            var mid = new Vector2(sw / 2f, sh / 2f);
            foreach (var t in tags)
            {
                var s = mid + Turn(ToScreen(new Vector2(t.point.x, t.point.y), sw, sh, centre, scale) - mid, turnDeg);
                var r = new Rect(s.x + 7, s.y - font * 0.6f, t.point.label.Length * font * 0.52f + 4, font + 4);
                bool ok = r.xMin > 2 && r.xMax < sw - 2 && r.yMin > 32 && r.yMax < sh - 34;
                if (ok)
                    foreach (var q in placed)
                        if (q.Overlaps(r)) { ok = false; break; }
                if (ok) placed.Add(r);
                t.label.text = t.point.label;
                t.label.style.display = ok ? DisplayStyle.Flex : DisplayStyle.None;
                t.label.style.left = r.x;
                t.label.style.top = r.y;
            }
        }

        /// 1 km grid cells lettered A, B, C... west to east and numbered 1, 2, 3... north to south.
        void PlaceGrid()
        {
            float cell = 1000f, scale = FullScale;
            int i = 0;
            for (float x = Mathf.Floor(_world.xMin / cell) * cell; x < _world.xMax && i < _gridCols.Count; x += cell)
            {
                var s = ToScreen(new Vector2(x + cell / 2f, 0), FullSize, FullSize, _fullCentre, scale);
                int col = Mathf.RoundToInt((x - Mathf.Floor(_world.xMin / cell) * cell) / cell);
                var l = _gridCols[i++];
                bool vis = s.x > 20 && s.x < FullSize - 20 && cell * scale > 26;
                l.style.display = vis ? DisplayStyle.Flex : DisplayStyle.None;
                l.text = ((char)('A' + col)).ToString();
                l.style.left = s.x - 4;
                l.style.top = 36;
            }
            for (; i < _gridCols.Count; i++) _gridCols[i].style.display = DisplayStyle.None;
            int j = 0;
            for (float y = Mathf.Ceil(_world.yMax / cell) * cell; y > _world.yMin && j < _gridRows.Count; y -= cell)
            {
                var s = ToScreen(new Vector2(0, y - cell / 2f), FullSize, FullSize, _fullCentre, scale);
                int row = Mathf.RoundToInt((Mathf.Ceil(_world.yMax / cell) * cell - y) / cell) + 1;
                var l = _gridRows[j++];
                bool vis = s.y > 50 && s.y < FullSize - 50 && cell * scale > 26;
                l.style.display = vis ? DisplayStyle.Flex : DisplayStyle.None;
                l.text = row.ToString();
                l.style.left = 8;
                l.style.top = s.y - 7;
            }
            for (; j < _gridRows.Count; j++) _gridRows[j].style.display = DisplayStyle.None;
        }

        // ------------------------------------------------------------------ drawing
        void DrawMap(MeshGenerationContext mgc, float sw, float sh, Vector2 centre, float scale, bool mini)
        {
            var p = mgc.painter2D;
            float reach = Mathf.Max(sw, sh) / 2f / scale * 1.5f;
            if (!aerial || _imgTex == null)
                foreach (var b in _bldg) // dark map: footprints (on the photo they are already visible)
                {
                    if ((b.centre - centre).magnitude > reach + b.radius) continue;
                    if (!mini && !b.tall && scale < 0.35f) continue;
                    p.fillColor = b.tall ? BldgTall : Bldg;
                    p.BeginPath();
                    p.MoveTo(ToScreen(b.pts[0], sw, sh, centre, scale));
                    for (int i = 1; i < b.pts.Length; i++) p.LineTo(ToScreen(b.pts[i], sw, sh, centre, scale));
                    p.ClosePath();
                    p.Fill();
                }
            if (!mini) DrawGridLines(p, sw, sh, centre, scale);
            p.lineJoin = LineJoin.Round;
            p.lineCap = LineCap.Round;
            foreach (var r in _routes) Poly(p, r, Road, mini ? 3f : 2.5f, sw, sh, centre, scale);
            Poly(p, _path, Path, mini ? 4f : 4f, sw, sh, centre, scale);
            foreach (var (pt, col) in AllPoints())
            {
                var s = ToScreen(new Vector2(pt.x, pt.y), sw, sh, centre, scale);
                p.fillColor = Color.black;
                p.BeginPath();
                p.Arc(s, mini ? 5f : 6f, Angle.Degrees(0), Angle.Degrees(360));
                p.Fill();
                p.fillColor = col;
                p.BeginPath();
                p.Arc(s, mini ? 3.5f : 4.5f, Angle.Degrees(0), Angle.Degrees(360));
                p.Fill();
            }
            DrawTraffic(p, sw, sh, centre, scale, reach, mini);
            var car = ToScreen(_car, sw, sh, centre, scale);
            if (mini) DrawSun(p, car, sw, MiniSize / 2f - 16f);
            else DrawScaleBar(p, sh, scale);
            DrawCar(p, car, mini ? 1f : 1.3f);
        }

        /// SUMO background cars (white dots) and signal heads (state colour), from TrafficPlayer.
        void DrawTraffic(Painter2D p, float sw, float sh, Vector2 centre, float scale, float reach, bool mini)
        {
            if (!TrafficPlayer.Visible) return;
            if (mini || scale >= 0.5f)
                foreach (var (pos, state) in TrafficPlayer.SignalsEnu)
                {
                    if ((pos - centre).magnitude > reach) continue;
                    var s = ToScreen(pos, sw, sh, centre, scale);
                    float r = mini ? 2.5f : 3f;
                    p.fillColor = Color.black;
                    p.BeginPath();
                    p.MoveTo(s + new Vector2(-r - 1, -r - 1));
                    p.LineTo(s + new Vector2(r + 1, -r - 1));
                    p.LineTo(s + new Vector2(r + 1, r + 1));
                    p.LineTo(s + new Vector2(-r - 1, r + 1));
                    p.ClosePath();
                    p.Fill();
                    p.fillColor = state == 'G' ? VisualModels.Green : state == 'Y' ? VisualModels.Amber : VisualModels.Red;
                    p.BeginPath();
                    p.MoveTo(s + new Vector2(-r, -r));
                    p.LineTo(s + new Vector2(r, -r));
                    p.LineTo(s + new Vector2(r, r));
                    p.LineTo(s + new Vector2(-r, r));
                    p.ClosePath();
                    p.Fill();
                }
            p.fillColor = new Color(1f, 1f, 1f, 0.9f);
            foreach (var c in TrafficPlayer.CarsEnu)
            {
                if ((c - centre).magnitude > reach) continue;
                p.BeginPath();
                p.Arc(ToScreen(c, sw, sh, centre, scale), mini ? 2.2f : 2.6f, Angle.Degrees(0), Angle.Degrees(360));
                p.Fill();
            }
        }

        void DrawGridLines(Painter2D p, float sw, float sh, Vector2 centre, float scale)
        {
            float cell = 1000f;
            p.strokeColor = Grid;
            p.lineWidth = 1f;
            for (float x = Mathf.Floor(_world.xMin / cell) * cell; x <= _world.xMax; x += cell)
            {
                float s = ToScreen(new Vector2(x, 0), sw, sh, centre, scale).x;
                p.BeginPath();
                p.MoveTo(new Vector2(s, 0));
                p.LineTo(new Vector2(s, sh));
                p.Stroke();
            }
            for (float y = Mathf.Floor(_world.yMin / cell) * cell; y <= _world.yMax; y += cell)
            {
                float s = ToScreen(new Vector2(0, y), sw, sh, centre, scale).y;
                p.BeginPath();
                p.MoveTo(new Vector2(0, s));
                p.LineTo(new Vector2(sw, s));
                p.Stroke();
            }
        }

        static float ScaleBarMetres(float scale)
        {
            float[] nice = { 50, 100, 200, 500, 1000, 2000, 5000 };
            float m = nice[0];
            foreach (var v in nice)
                if (v * scale <= 140f) m = v;
            return m;
        }

        /// Painting only: no element may change while generateVisualContent runs.
        static void DrawScaleBar(Painter2D p, float sh, float scale)
        {
            float len = ScaleBarMetres(scale) * scale, x0 = 18, y = sh - 46;
            p.strokeColor = Color.white;
            p.lineWidth = 3f;
            p.BeginPath();
            p.MoveTo(new Vector2(x0, y));
            p.LineTo(new Vector2(x0 + len, y));
            p.Stroke();
        }

        /// The scale bar's label, set from Update (never during drawing).
        void PlaceScaleText(float scale)
        {
            float m = ScaleBarMetres(scale);
            _scaleText.text = m >= 1000 ? $"{m / 1000:0} km" : $"{m:0} m";
            _scaleText.style.left = 18 + m * scale + 8;
            _scaleText.style.bottom = 39;
        }

        void DrawSun(Painter2D p, Vector2 car, float size, float radius)
        {
            // sun on the visible rim at its compass azimuth (drawn north-up; the layer turns with
            // the map), ray from the car toward it
            Vector2 c = new Vector2(size / 2f, size / 2f);
            Vector2 dir = new Vector2(_sunDir.x, -_sunDir.y); // screen y points down
            Vector2 rim = c + dir * radius;
            bool up = _sunEl > 0f;
            Color amber = new Color(1f, 0.78f, 0.15f);
            if (up)
            {
                p.strokeColor = new Color(1f, 0.78f, 0.15f, 0.55f);
                p.lineWidth = 2.5f;
                p.BeginPath();
                p.MoveTo(car);
                p.LineTo(rim);
                p.Stroke();
            }
            p.fillColor = up ? new Color(1f, 0.78f, 0.15f, 0.3f) : new Color(0.5f, 0.5f, 0.5f, 0.3f);
            p.BeginPath();
            p.Arc(rim, 13f, Angle.Degrees(0), Angle.Degrees(360));
            p.Fill();
            p.fillColor = up ? amber : new Color(0.6f, 0.6f, 0.6f);
            p.BeginPath();
            p.Arc(rim, 7f, Angle.Degrees(0), Angle.Degrees(360));
            p.Fill();
        }

        static void Poly(Painter2D p, List<Vector2> pts, Color c, float w, float sw, float sh, Vector2 centre, float scale)
        {
            if (pts.Count < 2) return;
            p.strokeColor = c;
            p.lineWidth = w;
            p.BeginPath();
            p.MoveTo(ToScreen(pts[0], sw, sh, centre, scale));
            for (int i = 1; i < pts.Count; i++) p.LineTo(ToScreen(pts[i], sw, sh, centre, scale));
            p.Stroke();
        }

        void DrawCar(Painter2D p, Vector2 c, float k)
        {
            float h = _heading * Mathf.Deg2Rad;
            Vector2 R(float x, float y) =>
                c + k * new Vector2(x * Mathf.Cos(h) - y * Mathf.Sin(h), x * Mathf.Sin(h) + y * Mathf.Cos(h));
            p.fillColor = Color.white;
            p.strokeColor = Color.black;
            p.lineWidth = 1.5f;
            p.BeginPath();
            p.MoveTo(R(0, -11));
            p.LineTo(R(8, 9));
            p.LineTo(R(0, 4));
            p.LineTo(R(-8, 9));
            p.ClosePath();
            p.Fill();
            p.Stroke();
        }
    }
}
