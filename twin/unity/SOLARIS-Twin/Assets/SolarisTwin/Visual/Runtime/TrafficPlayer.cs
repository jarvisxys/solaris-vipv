// SOLARIS-Twin visual: SUMO background cars and traffic signals, synced to the playback clock.
// Data come from Python (twin/visual/export_visual.py --traffic, from a visual-only SUMO re-run
// that reproduces the frozen ego trace exactly): per trip traffic_<id>.csv and signals_<id>.csv,
// plus signals.json. Positions are ENU, placed with the same transform as the SUMO ego car.
// Display only: layer Visual, no colliders, nothing feeds a reported number. Key T toggles.
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using UnityEngine;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

namespace SolarisTwin.Visual
{
    public class TrafficPlayer : MonoBehaviour
    {
        public TrajectoryPlayer player;
        [Tooltip("Car models (origin ground/body centre, +z forward, <= 5 m long; CC-BY, twin/unity/CREDITS.md); empty = built-in low-poly cars")]
        public GameObject[] carPrefabs;

        [Header("Signal kit (Visual/Models/Signals; empty = built-in shapes)")]
        public GameObject signalHeadPrefab;
        public GameObject signalPolePrefab;
        [Tooltip("Mast arm, 1 m long along -x from its origin; scaled to each approach")]
        public GameObject signalArmPrefab;
        public GameObject leftTurnSignPrefab;

        const float ArmY = 6.4f; // mast-arm height on the pole (kit geometry)
        public bool showCars = true;
        public bool showSignals = true;

        struct Rec
        {
            public Vector3 p;
            public float h;
            public int model;
        }

        [System.Serializable]
        class Head
        {
            public string tls, edge, turn;
            public int link;
            public float x, y, z, heading, width, over, far;
            public bool mast;
        }

        [System.Serializable]
        class HeadsJson
        {
            public Head[] heads;
        }

        // per second k since the trace start: vehicle number -> record
        Dictionary<int, Rec>[] _frames = new Dictionary<int, Rec>[0];
        int[][] _sigK = new int[0][];   // per head: change seconds
        char[][] _sigS = new char[0][]; // per head: state at each change (G/Y/R)
        Head[] _heads = new Head[0];
        MeshRenderer[][] _lamps = new MeshRenderer[0][];
        char[] _shown = new char[0];

        readonly Dictionary<int, GameObject> _active = new Dictionary<int, GameObject>();
        readonly Dictionary<int, Stack<GameObject>> _pool = new Dictionary<int, Stack<GameObject>>();
        readonly HashSet<int> _seen = new HashSet<int>();
        readonly List<int> _drop = new List<int>();
        Transform _carRoot, _sigRoot;
        string _for;
        int _layer = -1;

        /// Car and signal positions in ENU (east, north) for the mini-map, refreshed every frame.
        public static readonly List<Vector2> CarsEnu = new List<Vector2>();
        public static readonly List<(Vector2 pos, char state)> SignalsEnu = new List<(Vector2, char)>();
        public static bool Visible { get; private set; }

        static string Id(string trajectoryPath)
        {
            string name = Path.GetFileNameWithoutExtension(trajectoryPath);
            return name.StartsWith("trajectory_") ? name.Substring("trajectory_".Length) : name;
        }

        /// trip id without the date: traffic depends on the SUMO trace, not on the replay day
        static string Trip(string id)
        {
            int u = id.LastIndexOf('_');
            return u > 0 && id.Length - u == 11 ? id.Substring(0, u) : id;
        }

        static string Dir => TwinPaths.Resolve("../../exchange/visual/traffic");

        void Start()
        {
            _layer = LayerMask.NameToLayer("Visual");
            _carRoot = new GameObject("Visual_TrafficCars").transform;
            _sigRoot = new GameObject("Visual_TrafficSignals").transform;
            _carRoot.SetParent(transform, false);
            _sigRoot.SetParent(transform, false);
            LoadHeads();
        }

        void LoadHeads()
        {
            string p = Path.Combine(Dir, "signals.json");
            if (!File.Exists(p))
            {
                Debug.LogWarning($"[Traffic] no {p}; run python twin/visual/export_visual.py --traffic");
                return;
            }
            _heads = JsonUtility.FromJson<HeadsJson>(File.ReadAllText(p)).heads ?? new Head[0];
            _lamps = new MeshRenderer[_heads.Length][];
            _shown = new char[_heads.Length];
            for (int i = 0; i < _heads.Length; i++)
            {
                var h = _heads[i];
                var go = new GameObject($"signal_{h.tls}_{h.edge}_{h.turn}");
                go.transform.SetParent(_sigRoot, false);
                go.transform.SetPositionAndRotation(TwinIO.EnuToUnity(h.x, h.y, h.z),
                    Quaternion.Euler(0f, h.heading, 0f));
                _lamps[i] = signalHeadPrefab != null
                    ? BuildKit(go.transform, h)
                    : VisualModels.Signal(go.transform, h.over, h.width, h.mast, h.turn == "l", _layer, h.far);
                _shown[i] = ' ';
            }
        }

        /// One head from the Blender kit. Root = stop line of the approach's rightmost lane, +z the
        /// travel direction. The pole stands on the far-side right corner (h.far metres past the
        /// stop line, where the outgoing lanes start) and the arm reaches over the lanes; the head
        /// hangs `over` lanes left of the rightmost lane centre, lenses towards approaching cars.
        MeshRenderer[] BuildKit(Transform root, Head h)
        {
            float right = h.width / 2f + 1.5f, x = -h.over * h.width, z = h.far;
            if (h.mast)
            {
                Place(signalPolePrefab, root, new Vector3(right, 0f, z), Vector3.one);
                Place(signalArmPrefab, root, new Vector3(right, ArmY, z), new Vector3(right - x + 0.9f, 1f, 1f));
            }
            var head = Place(signalHeadPrefab, root, new Vector3(x, ArmY, z), Vector3.one);
            if (h.turn == "l" && leftTurnSignPrefab != null)
                Place(leftTurnSignPrefab, root, new Vector3(x - 0.8f, ArmY - 0.12f, z), Vector3.one);
            var lamps = new MeshRenderer[3];
            foreach (var r in head.GetComponentsInChildren<MeshRenderer>(true))
            {
                int k = r.name == "LampR" ? 0 : r.name == "LampY" ? 1 : r.name == "LampG" ? 2 : -1;
                if (k < 0) continue;
                lamps[k] = r;
                r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            }
            return lamps;
        }

        GameObject Place(GameObject prefab, Transform parent, Vector3 local, Vector3 scale)
        {
            if (prefab == null) return new GameObject("missing");
            var go = Instantiate(prefab, parent, false);
            go.transform.localPosition = local;
            go.transform.localRotation = Quaternion.identity;
            go.transform.localScale = scale;
            VisualModels.StripColliders(go);
            VisualModels.SetLayer(go, _layer);
            return go;
        }

        void LoadTrip(string trajectoryPath)
        {
            _for = trajectoryPath;
            foreach (var kv in _active) Release(kv.Key, kv.Value);
            _active.Clear();
            string trip = Trip(Id(trajectoryPath));
            var inv = CultureInfo.InvariantCulture;

            string tp = Path.Combine(Dir, $"traffic_{trip}.csv");
            var frames = new List<Dictionary<int, Rec>>();
            if (File.Exists(tp))
            {
                var lines = File.ReadAllLines(tp);
                for (int r = 1; r < lines.Length; r++)
                {
                    var c = lines[r].Split(',');
                    if (c.Length < 7) continue;
                    int k = int.Parse(c[0], inv);
                    while (frames.Count <= k) frames.Add(new Dictionary<int, Rec>());
                    frames[k][int.Parse(c[1], inv)] = new Rec
                    {
                        p = TwinIO.EnuToUnity(float.Parse(c[2], inv), float.Parse(c[3], inv), float.Parse(c[4], inv)),
                        h = float.Parse(c[5], inv),
                        model = int.Parse(c[6], inv),
                    };
                }
            }
            else Debug.LogWarning($"[Traffic] no {tp}; run python twin/visual/export_visual.py --traffic");
            _frames = frames.ToArray();

            var ks = new List<int>[_heads.Length];
            var ss = new List<char>[_heads.Length];
            for (int i = 0; i < _heads.Length; i++)
            {
                ks[i] = new List<int>();
                ss[i] = new List<char>();
            }
            string sp = Path.Combine(Dir, $"signals_{trip}.csv");
            if (File.Exists(sp))
            {
                var lines = File.ReadAllLines(sp);
                for (int r = 1; r < lines.Length; r++)
                {
                    var c = lines[r].Split(',');
                    if (c.Length < 3) continue;
                    int head = int.Parse(c[1], inv);
                    if (head < 0 || head >= _heads.Length) continue;
                    ks[head].Add(int.Parse(c[0], inv));
                    ss[head].Add(c[2].Length > 0 ? c[2][0] : 'R');
                }
            }
            _sigK = new int[_heads.Length][];
            _sigS = new char[_heads.Length][];
            for (int i = 0; i < _heads.Length; i++)
            {
                _sigK[i] = ks[i].ToArray();
                _sigS[i] = ss[i].ToArray();
                _shown[i] = ' ';
            }
            Debug.Log($"[Traffic] {trip}: {_frames.Length} s of background traffic, {_heads.Length} signal heads");
        }

        void Update()
        {
#if ENABLE_INPUT_SYSTEM
            var kb = Keyboard.current;
            if (kb != null && kb.tKey.wasPressedThisFrame)
            {
                showCars = !showCars;
                showSignals = showCars;
            }
#endif
            if (_carRoot == null || player == null || !player.HasRow) return;
            if (_for != player.trajectoryPath) LoadTrip(player.trajectoryPath);
            _carRoot.gameObject.SetActive(showCars);
            _sigRoot.gameObject.SetActive(showSignals);
            Visible = showCars;

            float t = player.Time01 * (player.Count - 1);
            int k0 = Mathf.FloorToInt(t);
            float f = t - k0;
            UpdateCars(k0, f);
            UpdateSignals(k0);
        }

        void UpdateCars(int k0, float f)
        {
            CarsEnu.Clear();
            _seen.Clear();
            if (showCars && k0 >= 0 && k0 < _frames.Length)
            {
                var a = _frames[k0];
                var b = k0 + 1 < _frames.Length ? _frames[k0 + 1] : null;
                foreach (var kv in a)
                {
                    Rec ra = kv.Value;
                    Vector3 p = ra.p;
                    float h = ra.h;
                    if (b != null && b.TryGetValue(kv.Key, out Rec rb))
                    {
                        p = Vector3.Lerp(ra.p, rb.p, f);
                        h = Mathf.LerpAngle(ra.h, rb.h, f);
                    }
                    if (!_active.TryGetValue(kv.Key, out var go))
                    {
                        go = Acquire(ra.model, kv.Key);
                        _active[kv.Key] = go;
                    }
                    go.transform.SetPositionAndRotation(p, Quaternion.Euler(0f, h, 0f));
                    _seen.Add(kv.Key);
                    CarsEnu.Add(new Vector2(p.x, p.z)); // Unity x = east, z = north
                }
            }
            _drop.Clear();
            foreach (var kv in _active)
                if (!_seen.Contains(kv.Key)) _drop.Add(kv.Key);
            foreach (int v in _drop)
            {
                Release(v, _active[v]);
                _active.Remove(v);
            }
        }

        void UpdateSignals(int k)
        {
            SignalsEnu.Clear();
            for (int i = 0; i < _heads.Length; i++)
            {
                char s = StateAt(i, k);
                if (s != _shown[i])
                {
                    _shown[i] = s;
                    var l = _lamps[i];
                    if (l[0] != null) l[0].sharedMaterial = VisualModels.Lamp('R', s == 'R');
                    if (l[1] != null) l[1].sharedMaterial = VisualModels.Lamp('Y', s == 'Y');
                    if (l[2] != null) l[2].sharedMaterial = VisualModels.Lamp('G', s == 'G');
                }
                if (showSignals) SignalsEnu.Add((new Vector2(_heads[i].x, _heads[i].y), s));
            }
        }

        char StateAt(int head, int k)
        {
            var ks = _sigK.Length > head ? _sigK[head] : null;
            if (ks == null || ks.Length == 0) return 'R';
            int lo = 0, hi = ks.Length - 1, best = 0; // last change at or before k
            while (lo <= hi)
            {
                int mid = (lo + hi) / 2;
                if (ks[mid] <= k)
                {
                    best = mid;
                    lo = mid + 1;
                }
                else hi = mid - 1;
            }
            return _sigS[head][best];
        }

        GameObject Acquire(int model, int vehicle)
        {
            int key = model;
            if (_pool.TryGetValue(key, out var st) && st.Count > 0)
            {
                var g = st.Pop();
                g.SetActive(true);
                return g;
            }
            GameObject go;
            if (carPrefabs != null && carPrefabs.Length > 0 && carPrefabs[model % carPrefabs.Length] != null)
            {
                go = Instantiate(carPrefabs[model % carPrefabs.Length]);
                VisualModels.StripColliders(go);
                VisualModels.SetLayer(go, _layer);
            }
            else go = VisualModels.Car(model, vehicle * 7 + model, _layer);
            go.name = $"car_{model}";
            go.transform.SetParent(_carRoot, false);
            return go;
        }

        void Release(int vehicle, GameObject go)
        {
            if (go == null) return;
            go.SetActive(false);
            int key = 0;
            string n = go.name;
            if (n.StartsWith("car_")) int.TryParse(n.Substring(4), out key);
            if (!_pool.TryGetValue(key, out var st)) _pool[key] = st = new Stack<GameObject>();
            st.Push(go);
        }
    }
}
