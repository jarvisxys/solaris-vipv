// SOLARIS-Twin visual: trip picker (key P). The 120 exported trajectories are R-DENSE
// {forward, reverse} x {08:00 ... 16:00} x {low, medium, high traffic} x 4 days; pick one of each
// and Load (or Enter). Every visual reloads itself when TrajectoryPlayer.trajectoryPath changes.
// Display only: it only chooses which exported file the player reads.
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.UIElements;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

namespace SolarisTwin.Visual
{
    [DefaultExecutionOrder(50)] // after MiniMap, which clears ChaseCamera.MouseBlocked each frame
    [RequireComponent(typeof(UIDocument))]
    public class TripPicker : MonoBehaviour
    {
        public TrajectoryPlayer player;
        public VehicleDriver driver;
        public bool show;

        const string Prefix = "../../exchange/trajectories/trajectory_";

        static readonly (string id, string label)[] Dirs = { ("fwd", "Forward"), ("rev", "Reverse") };
        static readonly (string id, string label)[] Deps =
        {
            ("1800", "08:00"), ("9000", "10:00"), ("16200", "12:00"), ("23400", "14:00"), ("30600", "16:00"),
        };
        static readonly (string id, string label)[] Demand = { ("low", "Low"), ("medium", "Medium"), ("high", "High") };
        static readonly (string id, string label)[] Days =
        {
            ("2023-03-21", "21 Mar · equinox"), ("2023-06-21", "21 Jun · summer solstice"),
            ("2023-09-21", "21 Sep · equinox"), ("2023-12-21", "21 Dec · winter solstice"),
        };

        readonly int[] _sel = new int[4];
        readonly List<Button>[] _chips = { new(), new(), new(), new() };
        VisualElement _panel;
        Label _info;
        Button _load;
        static readonly Color Amber = new Color(1f, 0.74f, 0.16f);
        static readonly Color Chip = new Color(1f, 1f, 1f, 0.08f);

        string Id => $"R-DENSE_{Dirs[_sel[0]].id}_{Deps[_sel[1]].id}_{Demand[_sel[2]].id}_{Days[_sel[3]].id}";
        string RelPath => Prefix + Id + ".csv";

        static Label Text(string s, float size, Color c, bool bold = false)
        {
            var l = new Label(s) { pickingMode = PickingMode.Ignore };
            l.style.fontSize = size;
            l.style.color = c;
            l.style.unityFontStyleAndWeight = bold ? FontStyle.Bold : FontStyle.Normal;
            l.style.marginLeft = l.style.marginRight = l.style.marginTop = l.style.marginBottom = 0;
            return l;
        }

        static void Round(VisualElement v, float r) =>
            v.style.borderTopLeftRadius = v.style.borderTopRightRadius =
                v.style.borderBottomLeftRadius = v.style.borderBottomRightRadius = r;

        void Start()
        {
            var root = GetComponent<UIDocument>().rootVisualElement;
            root.pickingMode = PickingMode.Ignore;
            var font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            if (font != null) root.style.unityFontDefinition = FontDefinition.FromFont(font);

            _panel = new VisualElement();
            _panel.style.position = Position.Absolute;
            _panel.style.left = Length.Percent(50);
            _panel.style.top = Length.Percent(50);
            _panel.style.translate = new Translate(Length.Percent(-50), Length.Percent(-50));
            _panel.style.width = 760;
            _panel.style.paddingLeft = _panel.style.paddingRight = 28;
            _panel.style.paddingTop = _panel.style.paddingBottom = 22;
            _panel.style.backgroundColor = new Color(0.035f, 0.05f, 0.075f, 0.95f);
            Round(_panel, 14);
            _panel.Add(Text("TRIP PICKER  ·  R-DENSE (Central Ave corridor)", 20, Color.white, true));
            var sub = Text("30 SUMO traces x 4 days = 120 trips  ·  P or Esc closes  ·  Enter loads", 12,
                new Color(1f, 1f, 1f, 0.55f));
            sub.style.marginTop = 4;
            _panel.Add(sub);

            AddRow(0, "DIRECTION", Dirs);
            AddRow(1, "DEPARTURE", Deps);
            AddRow(2, "TRAFFIC", Demand);
            AddRow(3, "DAY", Days);

            _info = Text("", 13, new Color(1f, 1f, 1f, 0.8f));
            _info.style.marginTop = 18;
            _info.style.whiteSpace = WhiteSpace.Normal;
            _panel.Add(_info);
            _load = new Button(Load) { text = "Load trip" };
            _load.style.marginTop = 14;
            _load.style.height = 38;
            _load.style.fontSize = 16;
            _load.style.unityFontStyleAndWeight = FontStyle.Bold;
            _load.style.backgroundColor = Amber;
            _load.style.color = Color.black;
            _load.style.borderTopWidth = _load.style.borderBottomWidth =
                _load.style.borderLeftWidth = _load.style.borderRightWidth = 0;
            Round(_load, 8);
            _panel.Add(_load);
            root.Add(_panel);
            SelectCurrent();
        }

        void AddRow(int r, string title, (string id, string label)[] opts)
        {
            var t = Text(title, 12, Amber, true);
            t.style.marginTop = 16;
            t.style.marginBottom = 6;
            _panel.Add(t);
            var row = new VisualElement();
            row.style.flexDirection = FlexDirection.Row;
            row.style.flexWrap = Wrap.Wrap;
            for (int i = 0; i < opts.Length; i++)
            {
                int idx = i;
                var b = new Button(() =>
                {
                    _sel[r] = idx;
                    Refresh();
                }) { text = opts[i].label };
                b.style.height = 32;
                b.style.paddingLeft = b.style.paddingRight = 14;
                b.style.marginRight = 8;
                b.style.marginBottom = 6;
                b.style.fontSize = 14;
                b.style.borderTopWidth = b.style.borderBottomWidth = b.style.borderLeftWidth = b.style.borderRightWidth = 0;
                Round(b, 6);
                _chips[r].Add(b);
                row.Add(b);
            }
            _panel.Add(row);
        }

        /// Pre-select the trip that is playing now.
        void SelectCurrent()
        {
            string name = player != null ? Path.GetFileNameWithoutExtension(player.trajectoryPath) : "";
            var parts = name.Replace("trajectory_", "").Split('_'); // R-DENSE, dir, dep, demand, day
            if (parts.Length == 5)
            {
                for (int i = 0; i < Deps.Length; i++) if (Deps[i].id == parts[2]) _sel[1] = i;
                for (int i = 0; i < Demand.Length; i++) if (Demand[i].id == parts[3]) _sel[2] = i;
                for (int i = 0; i < Days.Length; i++) if (Days[i].id == parts[4]) _sel[3] = i;
                for (int i = 0; i < Dirs.Length; i++) if (Dirs[i].id == parts[1]) _sel[0] = i;
            }
            Refresh();
        }

        void Refresh()
        {
            for (int r = 0; r < 4; r++)
                for (int i = 0; i < _chips[r].Count; i++)
                {
                    bool on = i == _sel[r];
                    _chips[r][i].style.backgroundColor = on ? Amber : Chip;
                    _chips[r][i].style.color = on ? Color.black : Color.white;
                }
            string abs = TwinPaths.Resolve(RelPath);
            bool exists = File.Exists(abs);
            bool playing = player != null && player.trajectoryPath == RelPath;
            string dur = "";
            if (exists)
            {
                int n = 0;
                foreach (var _ in File.ReadLines(abs)) n++;
                n = Mathf.Max(0, n - 2); // header, and seconds = records - 1
                dur = $"  ·  {n / 60}:{n % 60:00} min";
            }
            _info.text = exists
                ? $"{Id}{dur}{(playing ? "  ·  playing now" : "")}"
                : $"{Id}  ·  not exported (run the e8_export rule)";
            _load.SetEnabled(exists);
        }

        void Load()
        {
            if (player == null || !File.Exists(TwinPaths.Resolve(RelPath))) return;
            if (driver != null && driver.Driving) driver.Toggle(); // back on the trajectory first
            player.trajectoryPath = RelPath;
            player.Load();
            player.Play();
            show = false;
            KeyHelp.Toast($"Trip {Dirs[_sel[0]].label} {Deps[_sel[1]].label} · {Demand[_sel[2]].label} traffic · {Days[_sel[3]].label}");
        }

        void Update()
        {
#if ENABLE_INPUT_SYSTEM
            var k = Keyboard.current;
            if (k != null)
            {
                if (k.pKey.wasPressedThisFrame)
                {
                    show = !show;
                    if (show) SelectCurrent();
                }
                if (show && k.escapeKey.wasPressedThisFrame) show = false;
                if (show && (k.enterKey.wasPressedThisFrame || k.numpadEnterKey.wasPressedThisFrame)) Load();
            }
#endif
            if (_panel == null) return;
            _panel.style.display = show ? DisplayStyle.Flex : DisplayStyle.None;
            if (show) ChaseCamera.MouseBlocked = true; // the panel owns the mouse while open
        }
    }
}
