// SOLARIS-Twin: live beam state of every facet sample, drawn as small dots on the skin
// (visual only). Same test as VisibilityProbe: sun above the horizon and in front of the
// facet, one ray on layer Buildings and one on layer Trees, 2 cm off the skin.
//   yellow lit · green behind trees · blue behind buildings (or covered) · grey sun behind facet
// Key M shows/hides the dots. The box at the bottom right gives the lit share per facet.
using System.Collections.Generic;
using UnityEngine;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

namespace SolarisTwin
{
    public class ShadeMarkers : MonoBehaviour
    {
        public TrajectoryPlayer player;
        public float dotSize = 0.09f;
        public bool show = true;

        static readonly Color Lit = new Color(1f, 0.82f, 0.1f);
        static readonly Color TreeShade = new Color(0.1f, 0.65f, 0.3f);
        static readonly Color BldShade = new Color(0.15f, 0.35f, 0.95f);
        static readonly Color Off = new Color(0.35f, 0.35f, 0.35f);

        readonly List<(Transform sample, Renderer dot, string facet)> _dots = new();
        readonly Dictionary<string, (int lit, int valid)> _share = new();
        MaterialPropertyBlock _mpb;
        int _bld, _tree;

        void Start()
        {
            _bld = LayerMask.GetMask("Buildings");
            _tree = LayerMask.GetMask("Trees");
            _mpb = new MaterialPropertyBlock();
            var root = transform.Find("Samples");
            if (root == null) return;
            foreach (Transform s in root)
            {
                var d = GameObject.CreatePrimitive(PrimitiveType.Sphere);
                Destroy(d.GetComponent<Collider>()); // rays must never hit the car
                d.name = "dot";
                d.transform.SetParent(s, false);
                d.transform.localScale = Vector3.one * dotSize;
                d.transform.localPosition = new Vector3(0f, 0f, 0.03f);
                var r = d.GetComponent<Renderer>();
                r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                string facet = s.name.Substring(0, s.name.LastIndexOf('_'));
                _dots.Add((s, r, facet));
            }
        }

        void Update()
        {
#if ENABLE_INPUT_SYSTEM
            var k = Keyboard.current;
            if (k != null && k.mKey.wasPressedThisFrame) show = !show;
#endif
            if (player == null) return;
            Physics.SyncTransforms();
            Vector3 sun = player.SunDirection;
            float el = player.SunElevation;
            bool covered = player.Covered && !player.externalControl; // drive mode: not on the trace
            _share.Clear();
            foreach (var (s, dot, facet) in _dots)
            {
                dot.enabled = show;
                Vector3 n = s.forward, p = s.position;
                Color c;
                bool valid = el > 0f && Vector3.Dot(n, sun) > 0f;
                if (!valid) c = Off;
                else if (covered || Physics.Raycast(p + n * VisibilityProbe.SkinOffset, sun,
                             VisibilityProbe.MaxDistance, _bld)) c = BldShade;
                else if (Physics.Raycast(p + n * VisibilityProbe.SkinOffset, sun,
                             VisibilityProbe.MaxDistance, _tree)) c = TreeShade;
                else c = Lit;
                _share.TryGetValue(facet, out var sh);
                _share[facet] = (sh.lit + (c == Lit ? 1 : 0), sh.valid + (valid ? 1 : 0));
                if (!show) continue;
                _mpb.SetColor("_BaseColor", c); // URP Lit
                _mpb.SetColor("_Color", c); //     built-in fallback
                dot.SetPropertyBlock(_mpb);
            }
        }

        void OnGUI()
        {
            if (_share.Count == 0) return;
            var lines = "Beam on the skin (lit share)";
            foreach (var kv in _share)
                lines += $"\n{kv.Key,-11} " + (kv.Value.valid > 0
                    ? $"{100f * kv.Value.lit / kv.Value.valid:F0} %"
                    : "sun behind");
            GUI.Box(new Rect(Screen.width - 260, Screen.height - 150, 236, 126), lines);
        }
    }
}
