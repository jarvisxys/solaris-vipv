// SOLARIS-Twin visual: sets up Figure 3 of the paper, "Unity render of R-DENSE with shadows on
// the skin". Off by default; menu SOLARIS Visual -> Figure 3 switches it on. On Play it loads the
// trip, holds the chosen second, frames the car from a fixed camera and enters photo mode.
// Default moment (from the frozen E8 visibility file, read only): R-DENSE forward 08:00, medium
// traffic, 21 Dec, record 232 = 08:03:52 MST; building shadow on 42 % of the roof, 69 % of the
// right side and 30 % of the tailgate; sun 5.7 deg high in the ESE. Display only.
using UnityEngine;

namespace SolarisTwin.Visual
{
    [DefaultExecutionOrder(300)] // after the player, ChaseCamera and CameraModes
    public class Figure3Director : MonoBehaviour
    {
        public TrajectoryPlayer player;
        public string trip = "R-DENSE_fwd_1800_medium_2023-12-21";
        [Tooltip("Record index (seconds since the trip start)")]
        public int second = 232;
        [Tooltip("Camera position in the car's frame (x right, y up, z forward), m")]
        public Vector3 cameraOffset = new Vector3(5.5f, 7.5f, -11f);
        public Vector3 lookAtOffset = new Vector3(0f, 0.9f, 0.6f);
        public float fieldOfView = 42f;
        public bool photoMode = true;

        bool _set;
        Camera _cam;

        void Update()
        {
            if (_set || player == null || !player.HasRow) return;
            string path = $"../../exchange/trajectories/trajectory_{trip}.csv";
            if (player.trajectoryPath != path)
            {
                player.trajectoryPath = path;
                player.Load();
            }
            player.Seek(second);
            player.Pause();
            var chase = FindFirstObjectByType<ChaseCamera>();
            if (chase != null)
            {
                _cam = chase.GetComponent<Camera>();
                chase.enabled = false;
            }
            if (_cam == null) _cam = Camera.main;
            if (_cam != null) _cam.fieldOfView = fieldOfView;
            if (photoMode) PhotoMode.Enter();
            _set = true;
        }

        void LateUpdate()
        {
            if (!_set || _cam == null || player.car == null || CameraModes.Current != CameraModes.Mode.Chase) return;
            var car = player.car;
            _cam.transform.position = car.TransformPoint(cameraOffset);
            _cam.transform.LookAt(car.TransformPoint(lookAtOffset));
        }
    }
}
