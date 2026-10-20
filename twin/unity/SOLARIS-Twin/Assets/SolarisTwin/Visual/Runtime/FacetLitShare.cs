// SOLARIS-Twin visual: live beam state of every facet sample (dots on the skin, key M) and
// the lit share per facet for the HUD car diagram. Same test as VisibilityProbe: sun above the
// horizon and in front of the facet, one ray on layer Buildings, one on layer Trees, 2 cm off
// the skin. Read-only physics queries; the dots sit on layer Visual and have no colliders.
//   yellow lit · green behind trees · blue behind buildings (or covered) · grey sun behind
using System.Collections.Generic;
using UnityEngine;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

namespace SolarisTwin.Visual
{
    public class FacetLitShare : MonoBehaviour
    {
        public TrajectoryPlayer player;
        public float dotSize = 0.09f;
        public bool showDots = true;

        public static readonly Color Lit = new Color(1f, 0.82f, 0.1f);
        public static readonly Color TreeShade = new Color(0.1f, 0.65f, 0.3f);
        public static readonly Color BldShade = new Color(0.15f, 0.35f, 0.95f);
        public static readonly Color Off = new Color(0.35f, 0.35f, 0.35f);

        public struct Share
        {
            public int lit, tree, building, valid, total;
            public float LitFraction => valid > 0 ? (float)lit / valid : float.NaN;
        }

        readonly List<(Transform sample, Renderer dot, string facet)> _dots = new();
        public Dictionary<string, Share> Shares { get; } = new();
        MaterialPropertyBlock _mpb;
        int _bld, _tree;

        void Start()
        {
            _bld = LayerMask.GetMask("Buildings");
            _tree = LayerMask.GetMask("Trees");
            int visual = LayerMask.NameToLayer("Visual");
            _mpb = new MaterialPropertyBlock();
            var root = transform.Find("Samples");
            if (root == null) return;
            foreach (Transform s in root)
            {
                var d = GameObject.CreatePrimitive(PrimitiveType.Sphere);
                Destroy(d.GetComponent<Collider>()); // nothing new may be hit by any ray
                d.name = "dot";
                if (visual >= 0) d.layer = visual;
                d.transform.SetParent(s, false);
                d.transform.localScale = Vector3.one * dotSize;
                d.transform.localPosition = new Vector3(0f, 0f, 0.03f);
                var r = d.GetComponent<Renderer>();
                r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                _dots.Add((s, r, s.name.Substring(0, s.name.LastIndexOf('_'))));
            }
        }

        void Update()
        {
#if ENABLE_INPUT_SYSTEM
            var k = Keyboard.current;
            if (k != null && k.mKey.wasPressedThisFrame) showDots = !showDots;
#endif
            if (player == null || !player.HasRow) return;
            Physics.SyncTransforms();
            Vector3 sun = player.SunDirection;
            float el = player.SunElevation;
            bool covered = player.Covered && !player.externalControl;
            Shares.Clear();
            foreach (var (s, dot, facet) in _dots)
            {
                dot.enabled = showDots;
                Vector3 n = s.forward, o = s.position + n * VisibilityProbe.SkinOffset;
                Shares.TryGetValue(facet, out var sh);
                sh.total++;
                Color c;
                if (!(el > 0f && Vector3.Dot(n, sun) > 0f)) c = Off;
                else
                {
                    sh.valid++;
                    if (covered || Physics.Raycast(o, sun, VisibilityProbe.MaxDistance, _bld))
                    {
                        c = BldShade;
                        sh.building++;
                    }
                    else if (Physics.Raycast(o, sun, VisibilityProbe.MaxDistance, _tree))
                    {
                        c = TreeShade;
                        sh.tree++;
                    }
                    else
                    {
                        c = Lit;
                        sh.lit++;
                    }
                }
                Shares[facet] = sh;
                if (!showDots) continue;
                _mpb.SetColor("_BaseColor", c);
                _mpb.SetColor("_Color", c);
                dot.SetPropertyBlock(_mpb);
            }
        }
    }
}
