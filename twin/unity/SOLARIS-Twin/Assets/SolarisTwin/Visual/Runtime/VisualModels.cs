// SOLARIS-Twin visual: simple low-poly background cars and US mast-arm signal heads, built
// from Unity's built-in cube/cylinder/sphere meshes (no colliders, layer Visual).
// Every SUMO background vehicle is a 5 m passenger car, so all four car variants stay within
// 5.0 m x 2.0 m: they fit the SUMO gaps exactly. Swap in CC0/CC-BY prefabs via
// TrafficPlayer.carPrefabs (origin on the ground under the body centre, +z forward).
using System.Collections.Generic;
using UnityEngine;

namespace SolarisTwin.Visual
{
    public static class VisualModels
    {
        static Mesh _cube, _cyl, _sphere;
        static readonly Dictionary<string, Material> Mats = new Dictionary<string, Material>();

        public static readonly Color[] Paint =
        {
            new Color(0.92f, 0.92f, 0.93f), new Color(0.08f, 0.08f, 0.09f), new Color(0.55f, 0.57f, 0.60f),
            new Color(0.30f, 0.32f, 0.35f), new Color(0.62f, 0.08f, 0.08f), new Color(0.10f, 0.22f, 0.45f),
            new Color(0.80f, 0.78f, 0.72f), new Color(0.18f, 0.30f, 0.22f),
        };

        static Mesh Builtin(ref Mesh m, string name)
        {
            if (m == null) m = Resources.GetBuiltinResource<Mesh>(name);
            return m;
        }

        public static Material Mat(string key, Color c, float smooth = 0.5f, float metal = 0f, Color? emit = null)
        {
            if (Mats.TryGetValue(key, out var m) && m != null) return m;
            var sh = Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard");
            m = new Material(sh) { name = "Visual_" + key };
            m.SetColor("_BaseColor", c);
            m.SetColor("_Color", c);
            m.SetFloat("_Smoothness", smooth);
            m.SetFloat("_Glossiness", smooth);
            m.SetFloat("_Metallic", metal);
            if (emit.HasValue)
            {
                m.EnableKeyword("_EMISSION");
                m.SetColor("_EmissionColor", emit.Value);
                m.globalIlluminationFlags = MaterialGlobalIlluminationFlags.None;
            }
            Mats[key] = m;
            return m;
        }

        static GameObject Part(Transform parent, Mesh mesh, Material mat, Vector3 pos, Vector3 scale,
            Quaternion? rot = null)
        {
            var go = new GameObject("part");
            go.transform.SetParent(parent, false);
            go.transform.localPosition = pos;
            go.transform.localRotation = rot ?? Quaternion.identity;
            go.transform.localScale = scale;
            go.AddComponent<MeshFilter>().sharedMesh = mesh;
            var r = go.AddComponent<MeshRenderer>();
            r.sharedMaterial = mat;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.On;
            return go;
        }

        // L, W, H (m), lower-body height share, cabin length share, cabin offset (+ = forward), pickup bed
        static readonly (float L, float W, float H, float low, float cab, float cabZ, bool bed)[] Cars =
        {
            (4.80f, 1.84f, 1.45f, 0.52f, 0.48f, -0.10f, false), // sedan
            (4.85f, 1.95f, 1.75f, 0.50f, 0.60f, -0.25f, false), // SUV
            (5.00f, 2.00f, 1.85f, 0.52f, 0.30f, 0.55f, true),   // pickup
            (5.00f, 1.95f, 1.85f, 0.46f, 0.78f, -0.15f, false), // minivan / van
        };

        public static int CarModels => Cars.Length;

        public static GameObject Car(int model, int paint, int layer)
        {
            var spec = Cars[Mathf.Abs(model) % Cars.Length];
            var cube = Builtin(ref _cube, "Cube.fbx");
            var cyl = Builtin(ref _cyl, "Cylinder.fbx");
            var root = new GameObject($"car_{model}");
            var t = root.transform;
            Color pc = Paint[Mathf.Abs(paint) % Paint.Length];
            var body = Mat($"paint{Mathf.Abs(paint) % Paint.Length}", pc, 0.75f, 0.35f);
            var glass = Mat("glass", new Color(0.06f, 0.09f, 0.12f), 0.95f, 0.2f);
            var tyre = Mat("tyre", new Color(0.04f, 0.04f, 0.04f), 0.2f);
            var rim = Mat("rim", new Color(0.65f, 0.66f, 0.68f), 0.7f, 0.8f);
            var tail = Mat("tail", new Color(0.5f, 0.02f, 0.02f), 0.6f, 0f, new Color(0.9f, 0.05f, 0.05f));
            var head = Mat("head", new Color(0.95f, 0.95f, 0.9f), 0.9f, 0f, new Color(0.6f, 0.6f, 0.55f));

            const float clear = 0.22f, wheelR = 0.34f;
            float lowH = spec.H * spec.low, cabH = spec.H - clear - lowH;
            Part(t, cube, body, new Vector3(0f, clear + lowH / 2f, 0f), new Vector3(spec.W, lowH, spec.L));
            float cabL = spec.L * spec.cab;
            Part(t, cube, glass, new Vector3(0f, clear + lowH + cabH * 0.45f, spec.cabZ),
                new Vector3(spec.W * 0.88f, cabH * 0.9f, cabL));
            Part(t, cube, body, new Vector3(0f, spec.H - 0.04f, spec.cabZ),
                new Vector3(spec.W * 0.86f, 0.08f, cabL * 0.92f)); // roof
            if (spec.bed) // bed walls
            {
                float bedL = spec.L * 0.38f, bz = -spec.L / 2f + bedL / 2f + 0.05f;
                foreach (float s in new[] { -1f, 1f })
                    Part(t, cube, body, new Vector3(s * (spec.W / 2f - 0.05f), clear + lowH + 0.2f, bz),
                        new Vector3(0.08f, 0.4f, bedL));
                Part(t, cube, body, new Vector3(0f, clear + lowH + 0.2f, -spec.L / 2f + 0.06f),
                    new Vector3(spec.W, 0.4f, 0.08f));
            }
            float wx = spec.W / 2f - 0.12f, wz = spec.L / 2f - 0.85f;
            var side = Quaternion.Euler(0f, 0f, 90f);
            foreach (float sx in new[] { -1f, 1f })
            foreach (float sz in new[] { -1f, 1f })
            {
                var p = new Vector3(sx * wx, wheelR, sz * wz);
                Part(t, cyl, tyre, p, new Vector3(wheelR * 2f, 0.12f, wheelR * 2f), side);
                Part(t, cyl, rim, p + new Vector3(sx * 0.02f, 0f, 0f), new Vector3(wheelR * 1.2f, 0.121f, wheelR * 1.2f), side);
            }
            foreach (float sx in new[] { -1f, 1f })
            {
                Part(t, cube, tail, new Vector3(sx * (spec.W / 2f - 0.25f), clear + lowH * 0.75f, -spec.L / 2f - 0.01f),
                    new Vector3(0.35f, 0.12f, 0.04f));
                Part(t, cube, head, new Vector3(sx * (spec.W / 2f - 0.25f), clear + lowH * 0.7f, spec.L / 2f + 0.01f),
                    new Vector3(0.32f, 0.12f, 0.04f));
            }
            SetLayer(root, layer);
            return root;
        }

        public static readonly Color Red = new Color(1f, 0.08f, 0.05f);
        public static readonly Color Amber = new Color(1f, 0.6f, 0.02f);
        public static readonly Color Green = new Color(0.1f, 1f, 0.45f);

        /// Lamp material: lit (emissive) or dark.
        public static Material Lamp(char which, bool on)
        {
            Color c = which == 'R' ? Red : which == 'Y' ? Amber : Green;
            return on
                ? Mat($"lamp{which}1", c, 0.9f, 0f, c * 2.5f)
                : Mat($"lamp{which}0", c * 0.12f, 0.9f);
        }

        /// One head of a US mast-arm signal. Root at the stop line of the approach's rightmost
        /// lane (ground), +z = travel direction. The head hangs `over` lanes to the left of the
        /// rightmost lane centre, facing the approaching cars; with `mast` the pole (on the
        /// right curb) and the arm out to this head are built too. A left-turn head carries a
        /// small white arrow plate. Returns the three lamp renderers (red, amber, green).
        public static MeshRenderer[] Signal(Transform root, float over, float laneWidth, bool mast, bool leftTurn,
            int layer, float far = 0f)
        {
            var side = new GameObject("far_side").transform; // the far-side corner of the junction
            side.SetParent(root, false);
            side.localPosition = new Vector3(0f, 0f, far);
            root = side;
            var cube = Builtin(ref _cube, "Cube.fbx");
            var cyl = Builtin(ref _cyl, "Cylinder.fbx");
            var sphere = Builtin(ref _sphere, "Sphere.fbx");
            var steel = Mat("steel", new Color(0.36f, 0.37f, 0.36f), 0.35f, 0.6f);
            var housing = Mat("housing", new Color(0.12f, 0.11f, 0.06f), 0.3f);
            var plate = Mat("plate", new Color(0.92f, 0.92f, 0.92f), 0.4f);
            float right = laneWidth / 2f + 1.2f; // pole beyond the curb
            float x = -over * laneWidth;         // head across the approach
            const float poleH = 6.2f, armY = 5.9f;
            if (mast)
            {
                Part(root, cyl, steel, new Vector3(right, poleH / 2f, 0f), new Vector3(0.28f, poleH / 2f, 0.28f));
                float armL = right - x + 0.8f;
                Part(root, cyl, steel, new Vector3(right - armL / 2f, armY, 0f), new Vector3(0.14f, armL / 2f, 0.14f),
                    Quaternion.Euler(0f, 0f, 90f));
            }
            var head = new GameObject(leftTurn ? "head_left" : "head").transform;
            head.SetParent(root, false);
            head.localPosition = new Vector3(x, armY - 0.75f, 0f);
            Part(head, cube, housing, Vector3.zero, new Vector3(0.42f, 1.15f, 0.3f));
            Part(head, cube, housing, new Vector3(0f, 0f, 0.17f), new Vector3(0.7f, 1.35f, 0.04f)); // backplate
            if (leftTurn) // arrow plate under the head: shaft and head of a left arrow
            {
                Part(head, cube, housing, new Vector3(0f, -0.95f, 0.1f), new Vector3(0.6f, 0.4f, 0.03f));
                Part(head, cube, plate, new Vector3(0.05f, -0.95f, 0.08f), new Vector3(0.36f, 0.07f, 0.02f));
                // seen by the approaching driver (looking along +z), the tip points to their left (-x)
                Part(head, cube, plate, new Vector3(-0.08f, -0.91f, 0.08f), new Vector3(0.16f, 0.06f, 0.02f),
                    Quaternion.Euler(0f, 0f, 40f));
                Part(head, cube, plate, new Vector3(-0.08f, -0.99f, 0.08f), new Vector3(0.16f, 0.06f, 0.02f),
                    Quaternion.Euler(0f, 0f, -40f));
            }
            var lamps = new MeshRenderer[3];
            for (int i = 0; i < 3; i++)
            {
                var go = Part(head, sphere, Lamp("RYG"[i], false), new Vector3(0f, 0.36f - i * 0.36f, -0.15f),
                    new Vector3(0.28f, 0.28f, 0.1f));
                go.name = "lamp" + "RYG"[i];
                lamps[i] = go.GetComponent<MeshRenderer>();
                lamps[i].shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            }
            SetLayer(root.gameObject, layer);
            return lamps;
        }

        public static void SetLayer(GameObject go, int layer)
        {
            if (layer < 0) return;
            foreach (var t in go.GetComponentsInChildren<Transform>(true)) t.gameObject.layer = layer;
        }

        /// Prefabs may carry colliders; the visual layer must never be hit by any ray.
        public static void StripColliders(GameObject go)
        {
            foreach (var c in go.GetComponentsInChildren<Collider>(true)) Object.DestroyImmediate(c);
        }
    }
}
