// SOLARIS-Twin visual: one credit line (bottom right) for the third-party data and models this
// scene shows. Cesium ion and Google already show their own credits (bottom left), so they are
// not repeated. Stays visible in photo mode and recordings (attribution). Display only.
using UnityEngine;
using UnityEngine.UIElements;

namespace SolarisTwin.Visual
{
    [RequireComponent(typeof(UIDocument))]
    public class CreditStrip : MonoBehaviour
    {
        public const string Text =
            "Street names © OpenStreetMap contributors (ODbL)  ·  buildings © Overture Maps  ·  " +
            "aerial USDA NAIP  ·  car models © comrade1280, CC BY 4.0";

        void Start()
        {
            var root = GetComponent<UIDocument>().rootVisualElement;
            root.pickingMode = PickingMode.Ignore;
            var font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            if (font != null) root.style.unityFontDefinition = FontDefinition.FromFont(font);
            var l = new Label(Text) { pickingMode = PickingMode.Ignore };
            l.style.position = Position.Absolute;
            l.style.right = 12;
            l.style.bottom = 6;
            l.style.fontSize = 11;
            l.style.color = new Color(1f, 1f, 1f, 0.78f);
            l.style.paddingLeft = l.style.paddingRight = 8;
            l.style.paddingTop = l.style.paddingBottom = 2;
            l.style.backgroundColor = new Color(0f, 0f, 0f, 0.35f);
            l.style.borderTopLeftRadius = l.style.borderTopRightRadius =
                l.style.borderBottomLeftRadius = l.style.borderBottomRightRadius = 4;
            root.Add(l);
        }
    }
}
