// SOLARIS-Twin visual: synthesised EV sound for the Playback scene (no recorded clips, so no
// licences). Speed comes from the trajectory (speed_mps of the frozen SUMO trace) or, in drive
// mode, from the driver; Unity computes nothing physical. Display only. Key V mutes.
//   motor:  inverter/motor whine, pitch rising with speed, louder under acceleration
//   AVAS:   the pedestrian-warning hum EVs must make below 30 km/h (FMVSS 141), fading out
//   road:   tyre-road noise and wind, filtered noise growing with speed
// Silent while playback is paused or waiting for tiles.
using UnityEngine;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

namespace SolarisTwin.Visual
{
    [RequireComponent(typeof(AudioSource))]
    public class EvSound : MonoBehaviour
    {
        public TrajectoryPlayer player;
        public VehicleDriver driver;
        [Range(0f, 1f)] public float volume = 1f;
        public bool muted;

        /// Synthesiser state; Fill runs on the audio thread, Update only writes the targets.
        public class Synth
        {
            public float speed, accel, gain;            // targets (m/s, m/s^2, 0..1)
            float _v, _a, _g;                           // smoothed on the audio thread
            double _ph1, _ph2, _ph3, _ph4, _ph5;
            float _tyre, _tyre2, _wind;
            uint _rng = 22222u;

            float Noise()
            {
                _rng ^= _rng << 13;
                _rng ^= _rng >> 17;
                _rng ^= _rng << 5;
                return (_rng / 4294967295f) * 2f - 1f;
            }

            public void Fill(float[] data, int channels, int rate)
            {
                float k = 1f / rate;
                for (int i = 0; i < data.Length; i += channels)
                {
                    _v += (speed - _v) * 2f * k;
                    _a += (accel - _a) * 3f * k;
                    _g += (gain - _g) * 4f * k;
                    float v = Mathf.Max(0f, _v);

                    // motor whine: two orders of the motor's electrical frequency
                    float f = 95f + 42f * v;
                    _ph1 += f * k;
                    _ph2 += f * 2.02 * k;
                    _ph3 += 3400.0 * k; // faint inverter switching tone
                    float load = Mathf.Clamp01(0.35f + Mathf.Abs(_a) * 0.35f);
                    float motor = (Mathf.Sin((float)(_ph1 * 6.2831853)) * 0.6f
                                   + Mathf.Sin((float)(_ph2 * 6.2831853)) * 0.25f) * load
                                  * Mathf.Clamp01(v / 1.5f) * 0.11f
                                  + Mathf.Sin((float)(_ph3 * 6.2831853)) * 0.006f * Mathf.Clamp01(v / 2f);

                    // AVAS below 30 km/h (8.33 m/s), pitch rising a little with speed
                    float avasAmp = v < 8.33f ? (1f - v / 8.33f) * 0.05f : 0f;
                    _ph4 += (330f + 18f * v) * k;
                    _ph5 += (495f + 27f * v) * k;
                    float avas = (Mathf.Sin((float)(_ph4 * 6.2831853)) + 0.6f * Mathf.Sin((float)(_ph5 * 6.2831853)))
                                 * avasAmp * Mathf.Clamp01(v / 0.3f + 0.25f);

                    // tyre-road noise: low-passed noise, brighter and louder with speed
                    float n = Noise();
                    float cut = Mathf.Clamp01(0.02f + v * 0.006f);
                    _tyre += (n - _tyre) * cut;
                    _tyre2 += (_tyre - _tyre2) * cut;
                    float road = _tyre2 * Mathf.Pow(Mathf.Clamp01(v / 30f), 1.2f) * 0.9f;

                    // wind: very low-passed noise, quadratic in speed
                    _wind += (Noise() - _wind) * 0.004f;
                    float wind = _wind * (v / 30f) * (v / 30f) * 3.5f;

                    float s = (motor + avas + road + wind) * _g;
                    s = s / (1f + Mathf.Abs(s)); // soft limit
                    for (int c = 0; c < channels; c++) data[i + c] = s;
                }
                Wrap();
            }

            // phase wrap so doubles never lose precision over a long trip
            void Wrap()
            {
                _ph1 -= System.Math.Floor(_ph1);
                _ph2 -= System.Math.Floor(_ph2);
                _ph3 -= System.Math.Floor(_ph3);
                _ph4 -= System.Math.Floor(_ph4);
                _ph5 -= System.Math.Floor(_ph5);
            }
        }

        readonly Synth _synth = new Synth();
        int _rate;
        float _lastSpeed, _accel;
        int _lastRow = -1;

        public static bool Muted { get; private set; }

        void Start()
        {
            _rate = AudioSettings.outputSampleRate;
            var src = GetComponent<AudioSource>();
            src.clip = null;
            src.loop = true;
            src.spatialBlend = 0f; // heard in the cabin / chase camera alike
            src.playOnAwake = true;
            if (!src.isPlaying) src.Play();
        }

        void Update()
        {
#if ENABLE_INPUT_SYSTEM
            var kb = Keyboard.current;
            if (kb != null && kb.vKey.wasPressedThisFrame) muted = !muted;
#endif
            Muted = muted;
            float v = 0f;
            bool moving = false;
            if (driver != null && driver.Driving)
            {
                v = Mathf.Abs(driver.Speed);
                _accel = Mathf.Clamp((v - _lastSpeed) / Mathf.Max(Time.deltaTime, 1e-3f), -4f, 4f);
                _lastSpeed = v;
                moving = true;
            }
            else if (player != null && player.HasRow)
            {
                v = player.Current.speedMps;
                if (player.Index != _lastRow) // the trace is 1 Hz: acceleration per record step
                {
                    _accel = _lastRow >= 0 ? Mathf.Clamp(v - _lastSpeed, -4f, 4f) : 0f;
                    _lastRow = player.Index;
                    _lastSpeed = v;
                }
                moving = player.Playing && !player.TilesLoading;
            }
            _synth.accel = _accel;
            _synth.speed = moving ? v : 0f;
            _synth.gain = moving && !muted ? volume : 0f;
        }

        void OnAudioFilterRead(float[] data, int channels)
        {
            _synth.Fill(data, channels, _rate > 0 ? _rate : 48000);
        }
    }
}
