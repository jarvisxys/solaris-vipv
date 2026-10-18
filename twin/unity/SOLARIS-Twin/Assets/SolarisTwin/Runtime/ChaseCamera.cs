// SOLARIS-Twin: chase camera for the render (workflow guide Sec. 6, step 11). Visual only.
using UnityEngine;

namespace SolarisTwin
{
    public class ChaseCamera : MonoBehaviour
    {
        public Transform target;
        public Vector3 offset = new Vector3(0f, 4.5f, -11f); // behind and above, car frame
        public float lookAhead = 6f;
        [Range(0f, 1f)] public float smoothing = 0.15f;

        void LateUpdate()
        {
            if (target == null) return;
            Vector3 want = target.TransformPoint(offset);
            transform.position = Vector3.Lerp(transform.position, want, 1f - smoothing);
            transform.LookAt(target.position + target.forward * lookAhead + Vector3.up * 1f);
        }
    }
}
