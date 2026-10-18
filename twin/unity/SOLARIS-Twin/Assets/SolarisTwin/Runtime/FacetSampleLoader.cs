// SOLARIS-Twin: one child per facet sample under the vehicle (workflow guide Sec. 6, step 7).
// Reads twin/exchange/facet_samples.csv (rule facet_samples). Body frame x forward, y left,
// z up -> Unity local x right, y up, z forward; each child's +Z is the facet normal.
using System.IO;
using UnityEngine;

namespace SolarisTwin
{
    public static class TwinPaths
    {
        /// Project root (twin/unity/SOLARIS-Twin).
        public static string ProjectRoot => Path.GetFullPath(Path.Combine(Application.dataPath, ".."));

        /// twin/exchange, next to the Unity project.
        public static string Exchange =>
            Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "..", "exchange"));

        /// Absolute path, or a path relative to the project root.
        public static string Resolve(string p) =>
            Path.IsPathRooted(p) ? p : Path.GetFullPath(Path.Combine(ProjectRoot, p));
    }

    public class FacetSampleLoader : MonoBehaviour
    {
        [Tooltip("facet_samples.csv, absolute or relative to the Unity project folder")]
        public string csvPath = "../../exchange/facet_samples.csv";

        public float gizmoSize = 0.04f;

        [ContextMenu("Load facet samples")]
        public void Load() => Build(transform, TwinIO.ReadFacetSamples(TwinPaths.Resolve(csvPath)));

        public static Transform Build(Transform car, FacetSample[] samples)
        {
            var old = car.Find("Samples");
            if (old != null) DestroyImmediate(old.gameObject);
            var root = new GameObject("Samples").transform;
            root.SetParent(car, false);
            foreach (var s in samples)
            {
                var go = new GameObject($"{s.facetId}_{s.sampleId}").transform;
                go.SetParent(root, false);
                go.localPosition = s.localPos;
                go.localRotation = Quaternion.LookRotation(s.localNormal);
            }
            return root;
        }

        void OnDrawGizmosSelected()
        {
            var root = transform.Find("Samples");
            if (root == null) return;
            Gizmos.color = Color.yellow;
            foreach (Transform c in root)
            {
                Gizmos.DrawSphere(c.position, gizmoSize);
                Gizmos.DrawLine(c.position, c.position + c.forward * 0.3f);
            }
        }
    }
}
