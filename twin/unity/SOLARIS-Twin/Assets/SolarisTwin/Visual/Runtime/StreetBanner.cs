// SOLARIS-Twin visual: current street name at the bottom centre, fading in when it changes.
// Names come from Python (street column of the HUD file: the trace's OSM way ids). Display only.
using UnityEngine;
using UnityEngine.UIElements;

namespace SolarisTwin.Visual
{
    [RequireComponent(typeof(UIDocument))]
    public class StreetBanner : MonoBehaviour
    {
        public TrajectoryPlayer player;
        public float fadeSeconds = 0.6f;

        HudSeries _series = new HudSeries();
        string _seriesFor, _shown;
        Label _name;
        VisualElement _box;
        float _fade = 1f;

        void Start()
        {
            var root = GetComponent<UIDocument>().rootVisualElement;
            root.pickingMode = PickingMode.Ignore;
            var font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            if (font != null) root.style.unityFontDefinition = FontDefinition.FromFont(font);
            _box = new VisualElement { pickingMode = PickingMode.Ignore };
            _box.style.position = Position.Absolute;
            _box.style.bottom = 56;
            _box.style.left = Length.Percent(50);
            _box.style.translate = new Translate(Length.Percent(-50), 0);
            _box.style.alignItems = Align.Center;
            _name = new Label("") { pickingMode = PickingMode.Ignore };
            _name.style.fontSize = 30;
            _name.style.color = Color.white;
            _name.style.unityFontStyleAndWeight = FontStyle.Bold;
            _name.style.unityTextOutlineWidth = 0.2f;
            _name.style.unityTextOutlineColor = new Color(0f, 0f, 0f, 0.85f);
            var line = new VisualElement { pickingMode = PickingMode.Ignore };
            line.style.height = 3;
            line.style.width = 160;
            line.style.marginTop = 4;
            line.style.backgroundColor = new Color(1f, 0.74f, 0.16f);
            _box.Add(_name);
            _box.Add(line);
            root.Add(_box);
        }

        void Update()
        {
            if (_box == null || player == null || !player.HasRow) return;
            if (_seriesFor != player.trajectoryPath)
            {
                _seriesFor = player.trajectoryPath;
                _series = HudSeries.Load(HudSeries.ForTrajectory(player.trajectoryPath));
            }
            int row = player.externalControl ? -1 : _series.RowOf(player.Current.tUtc);
            string street = row >= 0 && row < _series.Street.Length ? _series.Street[row] : "";
            if (street != _shown)
            {
                _shown = street;
                _name.text = street;
                _fade = 0f;
            }
            _fade = Mathf.Min(1f, _fade + Time.unscaledDeltaTime / Mathf.Max(0.01f, fadeSeconds));
            _box.style.opacity = string.IsNullOrEmpty(street) ? 0f : _fade;
        }
    }
}
