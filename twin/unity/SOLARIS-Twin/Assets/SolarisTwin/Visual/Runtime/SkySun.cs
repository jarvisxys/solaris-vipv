// SOLARIS-Twin visual: sky and visible sun disc for the Playback scene (display only).
// The sun's direction is NOT computed here: TrajectoryPlayer already turns the directional light
// to the pvlib azimuth/elevation of each trajectory record. This script only makes the sky
// follow that light: the procedural skybox draws its sun disc in the light's direction, the sky
// brightens and warms with the elevation, and the ambient light is refreshed from the sky.
using UnityEngine;

namespace SolarisTwin.Visual
{
    public class SkySun : MonoBehaviour
    {
        public TrajectoryPlayer player;
        [Tooltip("Procedural skybox (Skybox/Procedural)")]
        public Material sky;
        [Range(0.01f, 0.1f)] public float sunSize = 0.035f;

        Light _sun;
        float _baseIntensity = 1f, _lastEl = float.NaN, _nextGi;
        static readonly Color Noon = new Color(1f, 0.97f, 0.92f);
        static readonly Color Low = new Color(1f, 0.72f, 0.45f);

        void Start()
        {
            if (player != null) _sun = player.sun;
            if (_sun != null)
            {
                _baseIntensity = _sun.intensity;
                RenderSettings.sun = _sun; // the skybox draws its disc where this light points
            }
            if (sky != null)
            {
                RenderSettings.skybox = sky;
                sky.SetFloat("_SunDisk", 2f); // high quality disc
                sky.EnableKeyword("_SUNDISK_HIGH_QUALITY");
                sky.SetFloat("_SunSize", sunSize);
                sky.SetFloat("_SunSizeConvergence", 6f);
            }
            RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Skybox;
        }

        void Update()
        {
            if (player == null || sky == null) return;
            float el = player.SunElevation; // from the trajectory (pvlib), degrees
            float day = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(-6f, 12f, el));
            float warm = 1f - Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(2f, 25f, el));
            sky.SetFloat("_Exposure", Mathf.Lerp(0.12f, 1.25f, day));
            sky.SetFloat("_AtmosphereThickness", Mathf.Lerp(0.85f, 1.35f, warm));
            sky.SetFloat("_SunSize", sunSize);
            if (_sun != null)
            {
                _sun.color = Color.Lerp(Noon, Low, warm);
                _sun.intensity = _baseIntensity * Mathf.Lerp(0.35f, 1f, Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(0f, 10f, el)));
            }
            // ambient from the sky: refresh when the sun has moved a little
            if ((float.IsNaN(_lastEl) || Mathf.Abs(el - _lastEl) > 0.25f) && Time.unscaledTime > _nextGi)
            {
                DynamicGI.UpdateEnvironment();
                _lastEl = el;
                _nextGi = Time.unscaledTime + 1f;
            }
        }
    }
}
