// SOLARIS-Twin visual: photo mode (key F12). Hides every panel except the credits (and Cesium's
// own), pauses playback; Enter saves a 2x PNG to twin/renders/photos; F12 again returns.
// The camera keys (C, right-drag, wheel) keep working, so the shot can be framed. Display only.
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.UIElements;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

namespace SolarisTwin.Visual
{
    public class PhotoMode : MonoBehaviour
    {
        public TrajectoryPlayer player;
        [Range(1, 4)] public int superSize = 2;

        public static bool Active { get; private set; }
        static PhotoMode _inst;

        readonly List<UIDocument> _hidden = new();
        bool _wasPlaying;

        static string Dir => Path.GetFullPath(Path.Combine(TwinPaths.Exchange, "..", "renders", "photos"));

        void Awake() => _inst = this;

        public static void Enter()
        {
            if (_inst != null && !Active) _inst.Toggle();
        }

        void Toggle()
        {
            Active = !Active;
            if (Active)
            {
                _hidden.Clear();
                foreach (var d in FindObjectsByType<UIDocument>(FindObjectsSortMode.None))
                {
                    string n = d.gameObject.name;
                    if (!n.StartsWith("Visual_") || n == "Visual_Credits" || n == "Visual_KeyHelp") continue;
                    if (d.rootVisualElement == null) continue;
                    d.rootVisualElement.style.display = DisplayStyle.None;
                    _hidden.Add(d);
                }
                foreach (var k in FindObjectsByType<KeyHelp>(FindObjectsSortMode.None)) k.show = false;
                foreach (var p in FindObjectsByType<TripPicker>(FindObjectsSortMode.None)) p.show = false;
                _wasPlaying = player != null && player.Playing;
                if (player != null) player.Pause();
            }
            else
            {
                foreach (var d in _hidden)
                    if (d != null && d.rootVisualElement != null) d.rootVisualElement.style.display = DisplayStyle.Flex;
                _hidden.Clear();
                if (player != null && _wasPlaying) player.Play();
                KeyHelp.Toast("Photo mode off");
            }
        }

        IEnumerator Capture()
        {
            Directory.CreateDirectory(Dir);
            string trip = player != null ? Path.GetFileNameWithoutExtension(player.trajectoryPath).Replace("trajectory_", "") : "view";
            string t = player != null && player.HasRow ? player.Current.tUtc.Replace(":", "").Replace("-", "") : "";
            string path = Path.Combine(Dir, $"{trip}_{t}_{System.DateTime.Now:HHmmss}.png");
            yield return new WaitForEndOfFrame();
            ScreenCapture.CaptureScreenshot(path, superSize);
            yield return null;
            yield return null; // the notice must not end up in the picture
            Debug.Log($"[PhotoMode] saved {path}");
            KeyHelp.Toast($"Saved {Path.GetFileName(path)}");
        }

        void Update()
        {
#if ENABLE_INPUT_SYSTEM
            var k = Keyboard.current;
            if (k == null) return;
            if (k.f12Key.wasPressedThisFrame) Toggle();
            if (Active && (k.enterKey.wasPressedThisFrame || k.numpadEnterKey.wasPressedThisFrame))
                StartCoroutine(Capture());
#endif
        }
    }
}
