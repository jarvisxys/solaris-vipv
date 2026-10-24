// SOLARIS-Twin visual: key K shows a panel with every key of the Playback scene; K again hides
// it. Also shows short notices at the top centre (camera mode, loaded trip). Display only.
using UnityEngine;
using UnityEngine.UIElements;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

namespace SolarisTwin.Visual
{
    [RequireComponent(typeof(UIDocument))]
    public class KeyHelp : MonoBehaviour
    {
        public bool show;

        static readonly (string group, (string key, string what)[] rows)[] Keys =
        {
            ("PLAYBACK", new[]
            {
                ("Space", "play / pause"),
                ("R", "back to the start of the trip"),
                ("← / →", "jump 10 s back / forward"),
                ("[ / ]", "half / double playback speed"),
                ("P", "trip picker (all 120 trips)"),
            }),
            ("CAMERA", new[]
            {
                ("C", "next camera: chase · driver's seat · overhead · cinematic"),
                ("Right-drag", "orbit (chase) / look around (driver's seat)"),
                ("Wheel", "zoom, height (overhead) or radius (cinematic)"),
            }),
            ("PANELS", new[]
            {
                ("H", "dashboard HUD on / off"),
                ("N", "full map (wheel zoom, left-drag pan)"),
                ("B", "full map: aerial photo / dark map"),
                ("M", "shade dots on the panels"),
                ("T", "background traffic and signals"),
                ("V", "sound on / off"),
                ("F12", "photo mode: hide panels and pause; Enter saves a PNG"),
                ("K", "this list"),
            }),
            ("DRIVE MODE", new[]
            {
                ("Tab", "drive yourself / back to the trajectory"),
                ("W / S", "throttle / brake and reverse"),
                ("A / D", "steer"),
            }),
        };

        VisualElement _panel;
        Label _toast;
        float _toastUntil;
        static KeyHelp _inst;

        /// A short notice at the top centre (about 2 s).
        public static void Toast(string text)
        {
            if (_inst == null || _inst._toast == null) return;
            _inst._toast.text = text;
            _inst._toast.style.display = DisplayStyle.Flex;
            _inst._toastUntil = Time.unscaledTime + 2f;
        }

        static Label Text(string s, float size, Color c, bool bold = false)
        {
            var l = new Label(s) { pickingMode = PickingMode.Ignore };
            l.style.fontSize = size;
            l.style.color = c;
            l.style.unityFontStyleAndWeight = bold ? FontStyle.Bold : FontStyle.Normal;
            l.style.marginLeft = l.style.marginRight = l.style.marginTop = l.style.marginBottom = 0;
            l.style.paddingLeft = l.style.paddingRight = l.style.paddingTop = l.style.paddingBottom = 0;
            return l;
        }

        void Start()
        {
            _inst = this;
            var root = GetComponent<UIDocument>().rootVisualElement;
            root.pickingMode = PickingMode.Ignore;
            var font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            if (font != null) root.style.unityFontDefinition = FontDefinition.FromFont(font);
            var amber = new Color(1f, 0.74f, 0.16f);

            _panel = new VisualElement { pickingMode = PickingMode.Ignore };
            _panel.style.position = Position.Absolute;
            _panel.style.left = Length.Percent(50);
            _panel.style.top = Length.Percent(50);
            _panel.style.translate = new Translate(Length.Percent(-50), Length.Percent(-50));
            _panel.style.width = 640;
            _panel.style.paddingLeft = _panel.style.paddingRight = 28;
            _panel.style.paddingTop = _panel.style.paddingBottom = 22;
            _panel.style.backgroundColor = new Color(0.035f, 0.05f, 0.075f, 0.93f);
            _panel.style.borderTopLeftRadius = _panel.style.borderTopRightRadius =
                _panel.style.borderBottomLeftRadius = _panel.style.borderBottomRightRadius = 14;
            _panel.Add(Text("KEYS", 20, Color.white, true));
            foreach (var (group, rows) in Keys)
            {
                var g = Text(group, 13, amber, true);
                g.style.marginTop = 14;
                g.style.marginBottom = 4;
                _panel.Add(g);
                foreach (var (key, what) in rows)
                {
                    var row = new VisualElement { pickingMode = PickingMode.Ignore };
                    row.style.flexDirection = FlexDirection.Row;
                    row.style.marginTop = 3;
                    var k = Text(key, 15, Color.white, true);
                    k.style.width = 130;
                    row.Add(k);
                    row.Add(Text(what, 15, new Color(1f, 1f, 1f, 0.82f)));
                    _panel.Add(row);
                }
            }
            var foot = Text("press K again to close", 12, new Color(1f, 1f, 1f, 0.5f));
            foot.style.marginTop = 16;
            _panel.Add(foot);
            root.Add(_panel);

            _toast = Text("", 18, Color.white, true);
            _toast.style.position = Position.Absolute;
            _toast.style.top = 70;
            _toast.style.left = Length.Percent(50);
            _toast.style.translate = new Translate(Length.Percent(-50), 0);
            _toast.style.paddingLeft = _toast.style.paddingRight = 16;
            _toast.style.paddingTop = _toast.style.paddingBottom = 7;
            _toast.style.backgroundColor = new Color(0f, 0f, 0f, 0.6f);
            _toast.style.borderTopLeftRadius = _toast.style.borderTopRightRadius =
                _toast.style.borderBottomLeftRadius = _toast.style.borderBottomRightRadius = 8;
            _toast.style.display = DisplayStyle.None;
            root.Add(_toast);
        }

        void Update()
        {
#if ENABLE_INPUT_SYSTEM
            var k = Keyboard.current;
            if (k != null && k.kKey.wasPressedThisFrame) show = !show;
#endif
            if (_panel != null) _panel.style.display = show ? DisplayStyle.Flex : DisplayStyle.None;
            if (_toast != null && _toast.style.display == DisplayStyle.Flex && Time.unscaledTime > _toastUntil)
                _toast.style.display = DisplayStyle.None;
        }
    }
}
