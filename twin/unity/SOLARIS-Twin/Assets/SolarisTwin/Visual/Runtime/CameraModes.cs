// SOLARIS-Twin visual: camera modes for the Playback scene (display only). Key C cycles
//   Chase      the ChaseCamera (right-drag orbit, wheel zoom)
//   Driver     driver's eye in the SOLARIS SUV (left seat), right-drag looks around
//   Overhead   straight down, heading-up, wheel changes the height
//   Cinematic  slow orbit around the car, wheel changes the radius
// Sits on the camera next to ChaseCamera and runs after it; in the other modes ChaseCamera is
// switched off so only one script moves the camera.
using UnityEngine;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

namespace SolarisTwin.Visual
{
    [DefaultExecutionOrder(100)]
    [RequireComponent(typeof(Camera))]
    public class CameraModes : MonoBehaviour
    {
        public enum Mode { Chase, Driver, Overhead, Cinematic }

        public TrajectoryPlayer player;
        public Mode mode = Mode.Chase;

        // driver's eye in the body frame (x forward, y left, z up), m: left seat, above the cowl
        static readonly Vector3 DriverEyeBody = new Vector3(0.20f, 0.37f, 1.42f);
        public float overheadHeight = 70f;
        public float orbitRadius = 16f, orbitHeight = 5f, orbitDegPerSec = 9f;

        public static Mode Current { get; private set; }
        public static string Label(Mode m) => m switch
        {
            Mode.Chase => "Chase",
            Mode.Driver => "Driver's seat",
            Mode.Overhead => "Overhead",
            _ => "Cinematic orbit",
        };

        ChaseCamera _chase;
        Camera _cam;
        // driver's seat: the car's tinted glass is swapped for a see-through one (display only)
        readonly System.Collections.Generic.List<(Renderer r, Material[] mats)> _glass = new();
        Material _clearGlass;
        float _near, _lookYaw, _lookPitch, _orbit;

        void Start()
        {
            _chase = GetComponent<ChaseCamera>();
            _cam = GetComponent<Camera>();
            _near = _cam.nearClipPlane;
            Apply(mode, false);
        }

        void Apply(Mode m, bool announce = true)
        {
            mode = Current = m;
            if (_chase != null) _chase.enabled = m == Mode.Chase;
            _cam.nearClipPlane = m == Mode.Driver ? 0.05f : _near;
            SeeThroughGlass(m == Mode.Driver);
            _lookYaw = _lookPitch = 0f;
            if (m == Mode.Cinematic && player != null && player.car != null)
                _orbit = player.car.eulerAngles.y + 200f;
            if (announce) KeyHelp.Toast($"Camera: {Label(m)}");
        }

        void SeeThroughGlass(bool on)
        {
            foreach (var (r, mats) in _glass)
                if (r != null) r.sharedMaterials = mats;
            _glass.Clear();
            if (!on || player == null || player.car == null) return;
            if (_clearGlass == null)
            {
                var sh = Shader.Find("Universal Render Pipeline/Unlit");
                _clearGlass = new Material(sh) { name = "Visual_ClearGlass" };
                _clearGlass.SetFloat("_Surface", 1f); // transparent
                _clearGlass.SetFloat("_Blend", 0f);
                _clearGlass.SetFloat("_ZWrite", 0f);
                _clearGlass.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.SrcAlpha);
                _clearGlass.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
                _clearGlass.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
                _clearGlass.renderQueue = (int)UnityEngine.Rendering.RenderQueue.Transparent;
                _clearGlass.SetColor("_BaseColor", new Color(0.05f, 0.08f, 0.1f, 0.12f));
            }
            foreach (var r in player.car.GetComponentsInChildren<Renderer>())
            {
                var mats = r.sharedMaterials;
                bool any = false;
                var swapped = (Material[])mats.Clone();
                for (int i = 0; i < mats.Length; i++)
                    if (mats[i] != null && mats[i].name.Contains("Glass"))
                    {
                        swapped[i] = _clearGlass;
                        any = true;
                    }
                if (!any) continue;
                _glass.Add((r, mats));
                r.sharedMaterials = swapped;
            }
        }

        void OnDisable() => SeeThroughGlass(false);

        void LateUpdate()
        {
            if (player == null || player.car == null) return;
            var car = player.car;
#if ENABLE_INPUT_SYSTEM
            var k = Keyboard.current;
            if (k != null && k.cKey.wasPressedThisFrame) Apply((Mode)(((int)mode + 1) % 4));
            var m = Mouse.current;
            float wheel = 0f;
            Vector2 drag = Vector2.zero;
            if (m != null && !ChaseCamera.MouseBlocked)
            {
                wheel = m.scroll.ReadValue().y;
                if (m.rightButton.isPressed) drag = m.delta.ReadValue();
            }
#else
            float wheel = 0f;
            Vector2 drag = Vector2.zero;
#endif
            float z = Mathf.Abs(wheel) > 0.01f ? (wheel > 0 ? 0.9f : 1.1f) : 1f;
            switch (mode)
            {
                case Mode.Driver:
                {
                    _lookYaw = Mathf.Clamp(_lookYaw + drag.x * 0.2f, -150f, 150f);
                    _lookPitch = Mathf.Clamp(_lookPitch - drag.y * 0.2f, -35f, 35f);
                    var b = DriverEyeBody; // body (x fwd, y left, z up) -> Unity local (-y, z, x)
                    transform.position = car.TransformPoint(new Vector3(-b.y, b.z, b.x));
                    transform.rotation = car.rotation * Quaternion.Euler(_lookPitch + 1.5f, _lookYaw, 0f);
                    break;
                }
                case Mode.Overhead:
                {
                    overheadHeight = Mathf.Clamp(overheadHeight * z, 15f, 600f);
                    Vector3 want = car.position + Vector3.up * overheadHeight;
                    transform.position = Vector3.Lerp(transform.position, want, 0.2f);
                    transform.rotation = Quaternion.Euler(90f, car.eulerAngles.y, 0f);
                    break;
                }
                case Mode.Cinematic:
                {
                    orbitRadius = Mathf.Clamp(orbitRadius * z, 6f, 120f);
                    _orbit += orbitDegPerSec * Time.deltaTime;
                    Vector3 off = Quaternion.Euler(0f, _orbit, 0f) * Vector3.back * orbitRadius;
                    Vector3 want = car.position + off + Vector3.up * orbitHeight;
                    transform.position = Vector3.Lerp(transform.position, want, 0.1f);
                    transform.LookAt(car.position + Vector3.up * 1.2f);
                    break;
                }
            }
        }
    }
}
