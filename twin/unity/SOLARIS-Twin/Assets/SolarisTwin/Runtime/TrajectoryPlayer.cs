// SOLARIS-Twin: playback of a Python trajectory (workflow guide Sec. 6, step 8). Visual only:
// the E8 numbers come from TwinBatch, which never uses this component.
//
// Time runs in trajectory seconds and the pose is interpolated between the 1 Hz records.
//   fixedFps = 0   follow the wall clock: `speed` trajectory seconds per real second (viewing)
//   fixedFps > 0   advance exactly speed / fixedFps per rendered frame, independent of how
//                  fast frames render: deterministic, for Unity Recorder at that frame rate
// With waitForTiles, time stands still while Cesium tilesets in view are still loading, so
// roads and buildings are drawn before the car moves on.
// Car yaw = heading (Unity +Z north, rotation about +Y turns it east). The directional light
// follows the record's pvlib sun angles; Unity never computes them.
//
// Keys: Space pause/play, Left/Right -/+10 s, [ / ] half/double speed, R restart.
using System.Collections.Generic;
using UnityEngine;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

namespace SolarisTwin
{
    public class TrajectoryPlayer : MonoBehaviour
    {
        [Tooltip("trajectory_<trip>_<date>.csv, absolute or relative to the Unity project folder")]
        public string trajectoryPath =
            "../../exchange/trajectories/trajectory_R-DENSE_fwd_1800_medium_2023-12-21.csv";

        public Transform car;
        public Light sun;

        [Tooltip("Trajectory seconds per second of playback (1 = real time)")]
        public float speed = 1f;

        [Tooltip("0 = wall clock (interactive). >0 = fixed step per frame for Unity Recorder at this frame rate")]
        public int fixedFps;

        [Tooltip("Hold the clock while Cesium tiles in view are loading")]
        public bool waitForTiles = true;

        [Range(50f, 100f)] public float tilesReadyPercent = 95f;
        public bool playOnStart = true;
        public bool loop;

        /// Set by VehicleDriver: the player keeps the sun but no longer moves the car.
        [HideInInspector] public bool externalControl;

        List<TrajRow> _rows;
        bool _playing;
        float _t;
        CesiumForUnity.Cesium3DTileset[] _tilesets = new CesiumForUnity.Cesium3DTileset[0];

        public int Count => _rows?.Count ?? 0;
        public bool HasRow => Count > 0;
        public int Index => HasRow ? Mathf.Clamp(Mathf.FloorToInt(_t), 0, Count - 1) : 0;
        public TrajRow Current => _rows[Index];
        public float Time01 => Count > 1 ? _t / (Count - 1) : 0f;
        public bool Playing => _playing;
        public bool TilesLoading { get; private set; }
        public float TileProgress { get; private set; } = 100f;
        public Vector3 SunDirection { get; private set; } = Vector3.up;
        public float SunElevation { get; private set; }
        public bool Covered => HasRow && Current.covered;

        void Start()
        {
            Load();
            _tilesets = FindObjectsByType<CesiumForUnity.Cesium3DTileset>(FindObjectsSortMode.None);
            _playing = playOnStart;
        }

        [ContextMenu("Load trajectory")]
        public void Load()
        {
            _rows = TwinIO.ReadTrajectory(TwinPaths.Resolve(trajectoryPath));
            _t = 0f;
            ApplyTime(0f);
        }

        public void Pause() => _playing = false;
        public void Play() => _playing = true;

        public void Seek(float seconds)
        {
            if (!HasRow) return;
            _t = Mathf.Clamp(seconds, 0f, Count - 1);
            ApplyTime(_t);
        }

        void Update()
        {
            HandleKeys();
            if (!HasRow) return;
            TilesLoading = waitForTiles && TilesBusy();
            if (!_playing || TilesLoading) return;
            float dt = fixedFps > 0 ? 1f / fixedFps : Time.deltaTime;
            _t += dt * speed;
            if (_t >= Count - 1)
            {
                if (loop) _t = 0f;
                else
                {
                    _t = Count - 1;
                    _playing = false;
                }
            }
            ApplyTime(_t);
        }

        bool TilesBusy()
        {
            float worst = 100f;
            foreach (var ts in _tilesets)
                if (ts != null && ts.isActiveAndEnabled)
                    worst = Mathf.Min(worst, ts.ComputeLoadProgress());
            TileProgress = worst;
            return worst < tilesReadyPercent;
        }

        public void ApplyTime(float t)
        {
            if (!HasRow) return;
            int i = Mathf.Clamp(Mathf.FloorToInt(t), 0, Count - 1);
            int j = Mathf.Min(i + 1, Count - 1);
            float f = Mathf.Clamp01(t - i);
            TrajRow a = _rows[i], b = _rows[j];
            if (car != null && !externalControl)
            {
                var pa = TwinIO.EnuToUnity(a.xE, a.yN, a.zU);
                var pb = TwinIO.EnuToUnity(b.xE, b.yN, b.zU);
                car.SetPositionAndRotation(Vector3.Lerp(pa, pb, f),
                    Quaternion.Euler(0f, Mathf.LerpAngle(a.headingDeg, b.headingDeg, f), 0f));
            }
            SetSun(Mathf.LerpAngle(a.sunAzDeg, b.sunAzDeg, f), Mathf.Lerp(a.sunElDeg, b.sunElDeg, f));
        }

        void SetSun(float azDeg, float elDeg)
        {
            SunDirection = VisibilityProbe.SunVector(azDeg, elDeg);
            SunElevation = elDeg;
            if (sun == null) return;
            sun.transform.rotation = Quaternion.LookRotation(-SunDirection);
            sun.enabled = elDeg > 0f;
        }

        void HandleKeys()
        {
#if ENABLE_INPUT_SYSTEM
            var k = Keyboard.current;
            if (k == null) return;
            if (k.spaceKey.wasPressedThisFrame) _playing = !_playing;
            if (k.rKey.wasPressedThisFrame) Seek(0f);
            if (k.rightBracketKey.wasPressedThisFrame) speed = Mathf.Min(speed * 2f, 64f);
            if (k.leftBracketKey.wasPressedThisFrame) speed = Mathf.Max(speed / 2f, 0.125f);
            if (externalControl) return; // arrows steer the car in drive mode
            if (k.rightArrowKey.wasPressedThisFrame) Seek(_t + 10f);
            if (k.leftArrowKey.wasPressedThisFrame) Seek(_t - 10f);
#endif
        }
    }
}
