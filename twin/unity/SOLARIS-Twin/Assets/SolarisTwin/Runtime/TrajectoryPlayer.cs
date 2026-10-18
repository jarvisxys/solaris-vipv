// SOLARIS-Twin: deterministic playback of a Python trajectory (workflow guide Sec. 6, step 8).
// Steps record by record (never by frame time): `recordsPerFrame` records per rendered frame,
// so a 1 Hz trajectory recorded at 30 fps plays 30x faster than real time, identically on
// every run. Car yaw = heading (Unity +Z north, rotation about +Y turns it east). The
// directional light follows the record's sun angles (visual only).
using System.Collections.Generic;
using UnityEngine;

namespace SolarisTwin
{
    public class TrajectoryPlayer : MonoBehaviour
    {
        [Tooltip("trajectory_<trip>_<date>.csv, absolute or relative to the Unity project folder")]
        public string trajectoryPath =
            "../../exchange/trajectories/trajectory_R-DENSE_fwd_1800_medium_2023-12-21.csv";

        public Transform car;
        public Light sun;
        public int recordsPerFrame = 1;
        public bool playOnStart = true;
        public bool loop;

        List<TrajRow> _rows;
        bool _playing;

        public int Index { get; private set; }
        public int Count => _rows?.Count ?? 0;
        public bool HasRow => _rows != null && _rows.Count > 0;
        public TrajRow Current => _rows[Index];

        void Start()
        {
            Load();
            _playing = playOnStart;
        }

        [ContextMenu("Load trajectory")]
        public void Load()
        {
            _rows = TwinIO.ReadTrajectory(TwinPaths.Resolve(trajectoryPath));
            Apply(0);
        }

        void Update()
        {
            if (!_playing || !HasRow) return;
            int next = Index + Mathf.Max(1, recordsPerFrame);
            if (next >= _rows.Count)
            {
                if (!loop)
                {
                    _playing = false;
                    return;
                }
                next = 0;
            }
            Apply(next);
        }

        public void Apply(int i)
        {
            if (!HasRow) return;
            Index = Mathf.Clamp(i, 0, _rows.Count - 1);
            var r = _rows[Index];
            if (car != null) VisibilityProbe.Place(car, r);
            if (sun != null)
            {
                var v = VisibilityProbe.SunVector(r.sunAzDeg, r.sunElDeg);
                sun.transform.rotation = Quaternion.LookRotation(-v);
                sun.enabled = r.sunElDeg > 0f;
            }
        }
    }
}
