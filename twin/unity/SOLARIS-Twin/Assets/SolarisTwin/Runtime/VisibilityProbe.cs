// SOLARIS-Twin: beam visibility per facet sample (workflow guide Sec. 6, "Core of
// VisibilityProbe.cs"). One CSV row per record and sample:
//   t_utc, facet_id, sample_id, beam_building_hit, beam_tree_hit
// 1 = blocked, 0 = clear, -1 = sun below the horizon or behind the facet.
// Covered records (tunnels, under bridges) are written as building 1, tree 0.
// Unity never computes sun angles or energy: angles come from Python (pvlib SPA).
using System.Globalization;
using System.IO;
using UnityEngine;

namespace SolarisTwin
{
    public static class VisibilityProbe
    {
        public const string Header = "t_utc,facet_id,sample_id,beam_building_hit,beam_tree_hit";
        public const float MaxDistance = 5000f;
        public const float SkinOffset = 0.02f; // m, off the skin along the normal

        static readonly CultureInfo Inv = CultureInfo.InvariantCulture;
        static int _bld = -1, _tree = -1;

        static int Bld => _bld >= 0 ? _bld : (_bld = LayerMask.GetMask("Buildings"));
        static int Tree => _tree >= 0 ? _tree : (_tree = LayerMask.GetMask("Trees"));

        public static Vector3 SunVector(float azDeg, float elDeg)
        {
            float az = azDeg * Mathf.Deg2Rad, el = elDeg * Mathf.Deg2Rad;
            return new Vector3(
                Mathf.Cos(el) * Mathf.Sin(az), // East
                Mathf.Sin(el), //                 Up
                Mathf.Cos(el) * Mathf.Cos(az)); // North
        }

        public static void Place(Transform car, TrajRow r)
        {
            car.SetPositionAndRotation(
                TwinIO.EnuToUnity(r.xE, r.yN, r.zU), Quaternion.Euler(0f, r.headingDeg, 0f));
        }

        /// r: one trajectory row; car: vehicle root (no colliders); samples: body-frame points.
        public static void Probe(TrajRow r, Transform car, FacetSample[] samples, TextWriter w)
        {
            Place(car, r);
            Physics.SyncTransforms();
            Vector3 sun = SunVector(r.sunAzDeg, r.sunElDeg);
            foreach (var s in samples)
            {
                Vector3 p = car.TransformPoint(s.localPos);
                Vector3 n = car.TransformDirection(s.localNormal);
                int bld = -1, tree = -1;
                if (r.sunElDeg > 0f && Vector3.Dot(n, sun) > 0f && !r.covered)
                {
                    Vector3 o = p + n * SkinOffset;
                    bld = Physics.Raycast(o, sun, MaxDistance, Bld) ? 1 : 0;
                    tree = Physics.Raycast(o, sun, MaxDistance, Tree) ? 1 : 0;
                }
                else if (r.covered)
                {
                    bld = 1;
                    tree = 0;
                }
                w.Write(r.tUtc);
                w.Write(',');
                w.Write(s.facetId);
                w.Write(',');
                w.Write(s.sampleId.ToString(Inv));
                w.Write(',');
                w.Write(bld.ToString(Inv));
                w.Write(',');
                w.Write(tree.ToString(Inv));
                w.Write('\n');
            }
        }
    }
}
