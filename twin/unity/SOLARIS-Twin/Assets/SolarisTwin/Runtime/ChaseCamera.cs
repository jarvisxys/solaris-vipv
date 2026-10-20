// SOLARIS-Twin: chase camera for viewing and the render (workflow guide Sec. 6, step 11).
// Visual only. Hold the right mouse button and drag to orbit around the car; scroll to zoom;
// key C resets the view behind the car.
using UnityEngine;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

namespace SolarisTwin
{
    public class ChaseCamera : MonoBehaviour
    {
        public Transform target;
        public float distance = 12f;
        public float pitchDeg = 20f;
        public float yawDeg; // relative to the car's heading; 0 = behind
        public float lookHeight = 1.2f;
        [Range(0f, 1f)] public float smoothing = 0.15f;
        public float minDistance = 4f, maxDistance = 400f;

        /// Set each frame by UI that owns the mouse (the full map under the cursor): no orbit/zoom.
        public static bool MouseBlocked;

        void LateUpdate()
        {
            if (target == null) return;
#if ENABLE_INPUT_SYSTEM
            var m = Mouse.current;
            if (m != null && !MouseBlocked)
            {
                if (m.rightButton.isPressed)
                {
                    Vector2 d = m.delta.ReadValue();
                    yawDeg += d.x * 0.25f;
                    pitchDeg = Mathf.Clamp(pitchDeg - d.y * 0.25f, -5f, 85f);
                }
                float s = m.scroll.ReadValue().y;
                if (Mathf.Abs(s) > 0f)
                    distance = Mathf.Clamp(distance * (s > 0 ? 0.9f : 1.1f), minDistance, maxDistance);
            }
            var k = Keyboard.current;
            if (k != null && k.cKey.wasPressedThisFrame)
            {
                yawDeg = 0f;
                pitchDeg = 20f;
                distance = 12f;
            }
#endif
            var rot = Quaternion.Euler(pitchDeg, target.eulerAngles.y + yawDeg, 0f);
            Vector3 focus = target.position + Vector3.up * lookHeight;
            Vector3 want = focus - rot * Vector3.forward * distance;
            transform.position = Vector3.Lerp(transform.position, want, 1f - smoothing);
            transform.LookAt(focus);
        }
    }
}
