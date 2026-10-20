// SOLARIS-Twin: drive the SUV yourself (visual only; never part of a reported number).
// Tab switches between trajectory replay and manual driving. While driving, the sun stays
// at the trajectory instant where you took over (Unity never computes sun angles), and the
// car follows the analysis surface (layer Buildings) under its wheels.
//
// Keys (drive mode): W/S or Up/Down throttle and brake/reverse, A/D or Left/Right steer,
// Tab back to replay (the car returns to the trajectory).
using UnityEngine;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

namespace SolarisTwin
{
    public class VehicleDriver : MonoBehaviour
    {
        public TrajectoryPlayer player;
        public Transform car;

        [Header("Vehicle (kinematic bicycle model)")]
        public float maxSpeed = 22f; // m/s (~80 km/h)
        public float maxReverse = 5f;
        public float acceleration = 3.5f; // m/s^2
        public float braking = 8f;
        public float coastDecel = 0.6f;
        public float maxSteerDeg = 32f;
        public float wheelBase = 2.95f;

        [Header("Ground following")]
        public float probeUp = 2.5f; // m above the wheels; lower so bridge decks are not climbed
        public float probeDown = 6f;

        [Tooltip("Draw the drive-mode box (off when the visual dashboard shows drive mode)")]
        public bool showGui = true;

        public bool Driving { get; private set; }
        public float Speed { get; private set; }

        int _ground = -1;

        void Update()
        {
#if ENABLE_INPUT_SYSTEM
            var k = Keyboard.current;
            if (k == null || car == null) return;
            if (k.tabKey.wasPressedThisFrame) Toggle();
            if (!Driving) return;

            float throttle = (k.wKey.isPressed || k.upArrowKey.isPressed ? 1f : 0f)
                             - (k.sKey.isPressed || k.downArrowKey.isPressed ? 1f : 0f);
            float steer = (k.dKey.isPressed || k.rightArrowKey.isPressed ? 1f : 0f)
                          - (k.aKey.isPressed || k.leftArrowKey.isPressed ? 1f : 0f);
            float dt = Time.deltaTime;
            float v = Speed;
            if (throttle > 0f) v += (v < 0f ? braking : acceleration) * dt;
            else if (throttle < 0f) v -= (v > 0f ? braking : acceleration) * dt;
            else v = Mathf.MoveTowards(v, 0f, coastDecel * dt);
            Speed = v = Mathf.Clamp(v, -maxReverse, maxSpeed);

            float yawRate = v / wheelBase * Mathf.Tan(steer * maxSteerDeg * Mathf.Deg2Rad);
            car.Rotate(0f, yawRate * Mathf.Rad2Deg * dt, 0f, Space.World);
            Vector3 p = car.position + car.forward * (v * dt);
            if (_ground < 0) _ground = LayerMask.GetMask("Buildings");
            if (Physics.Raycast(p + Vector3.up * probeUp, Vector3.down, out RaycastHit hit,
                    probeUp + probeDown, _ground))
                p.y = hit.point.y;
            car.position = p;
#endif
        }

        public void Toggle()
        {
            Driving = !Driving;
            Speed = 0f;
            if (player == null) return;
            player.externalControl = Driving;
            if (Driving) player.Pause();
            else player.ApplyTime(player.Index); // back on the trajectory
        }

        void OnGUI()
        {
            if (!Driving || !showGui) return;
            var r = new Rect(Screen.width - 380, 24, 356, 74);
            GUI.Box(r, $"DRIVE MODE   {Speed * 3.6f:F0} km/h\n" +
                       "W/S throttle, A/D steer, Tab back to replay\n" +
                       $"sun fixed at {(player != null && player.HasRow ? player.Current.tUtc : "-")}");
        }
    }
}
