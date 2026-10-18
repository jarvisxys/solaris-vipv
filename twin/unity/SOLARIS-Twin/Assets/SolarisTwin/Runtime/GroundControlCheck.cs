// SOLARIS-Twin: ground-control check (workflow guide Sec. 6, step 6). Every surveyed mark
// must land within the tolerance (0.5 m) of its lidar surface height in Unity before any
// run counts. A ray is cast straight down onto the Buildings layer (terrain, buildings,
// bridges) at each mark's ENU position.
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using UnityEngine;

namespace SolarisTwin
{
    public static class GroundControlCheck
    {
        public const float Tolerance = 0.5f;

        public struct Result
        {
            public GroundMark mark;
            public bool hit;
            public float uUnity, delta;
            public bool pass;
        }

        public static List<Result> Run(List<GroundMark> marks, float tol = Tolerance)
        {
            int layer = LayerMask.GetMask("Buildings");
            var outRows = new List<Result>();
            Physics.SyncTransforms();
            foreach (var m in marks)
            {
                var o = new Vector3(m.xE, m.uExpected + 300f, m.yN);
                bool hit = Physics.Raycast(o, Vector3.down, out RaycastHit h, 2000f, layer);
                float u = hit ? h.point.y : float.NaN;
                float d = u - m.uExpected;
                outRows.Add(new Result
                {
                    mark = m, hit = hit, uUnity = u, delta = d,
                    pass = hit && Mathf.Abs(d) <= tol,
                });
            }
            return outRows;
        }

        public static bool AllPass(List<Result> results)
        {
            if (results.Count == 0) return false;
            foreach (var r in results)
                if (!r.pass) return false;
            return true;
        }

        public static void Write(List<Result> results, string path)
        {
            var inv = CultureInfo.InvariantCulture;
            using var w = new StreamWriter(path);
            w.Write("id,x_e,y_n,u_expected,u_unity,delta_m,pass\n");
            foreach (var r in results)
                w.Write(string.Join(",", r.mark.id, r.mark.xE.ToString("F3", inv),
                    r.mark.yN.ToString("F3", inv), r.mark.uExpected.ToString("F3", inv),
                    r.uUnity.ToString("F3", inv), r.delta.ToString("F3", inv),
                    r.pass ? "1" : "0") + "\n");
        }
    }
}
