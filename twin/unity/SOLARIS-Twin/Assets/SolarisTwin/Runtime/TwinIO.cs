// SOLARIS-Twin: readers for the Python -> Unity exchange files (twin/exchange/README.md).
// Frames: Python ENU (x east, y north, z up) -> Unity (x east, y up, z north).
// Vehicle body frame (x forward, y left, z up) -> Unity local (x right, y up, z forward).
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using UnityEngine;

namespace SolarisTwin
{
    public struct TrajRow
    {
        public string tUtc;
        public float xE, yN, zU, headingDeg, speedMps, sunAzDeg, sunElDeg;
        public bool covered;
    }

    public struct FacetSample
    {
        public string facetId;
        public int sampleId;
        public Vector3 localPos;
        public Vector3 localNormal;
    }

    public struct GroundMark
    {
        public string id;
        public float xE, yN, uExpected;
    }

    public static class TwinIO
    {
        static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

        public static Vector3 EnuToUnity(float e, float n, float u) => new Vector3(e, u, n);

        public static Vector3 BodyToUnity(float x, float y, float z) => new Vector3(-y, z, x);

        static float F(string s) => float.Parse(s, NumberStyles.Float, Inv);

        static bool B(string s) =>
            s == "1" || s.Equals("true", StringComparison.OrdinalIgnoreCase);

        static Dictionary<string, int> Header(string line)
        {
            var h = new Dictionary<string, int>();
            var cols = line.Trim().Split(',');
            for (int i = 0; i < cols.Length; i++) h[cols[i].Trim()] = i;
            return h;
        }

        static IEnumerable<string[]> Rows(string path, out Dictionary<string, int> header)
        {
            var lines = File.ReadAllLines(path);
            header = Header(lines[0]);
            var rows = new List<string[]>(lines.Length - 1);
            for (int i = 1; i < lines.Length; i++)
                if (lines[i].Length > 0) rows.Add(lines[i].Split(','));
            return rows;
        }

        public static List<TrajRow> ReadTrajectory(string path)
        {
            var outRows = new List<TrajRow>();
            foreach (var c in Rows(path, out var h))
            {
                outRows.Add(new TrajRow
                {
                    tUtc = c[h["t_utc"]],
                    xE = F(c[h["x_e"]]),
                    yN = F(c[h["y_n"]]),
                    zU = F(c[h["z_u"]]),
                    headingDeg = F(c[h["heading_deg"]]),
                    speedMps = F(c[h["speed_mps"]]),
                    sunAzDeg = F(c[h["sun_az_deg"]]),
                    sunElDeg = F(c[h["sun_el_deg"]]),
                    covered = B(c[h["covered"]]),
                });
            }
            return outRows;
        }

        public static FacetSample[] ReadFacetSamples(string path)
        {
            var outRows = new List<FacetSample>();
            foreach (var c in Rows(path, out var h))
            {
                outRows.Add(new FacetSample
                {
                    facetId = c[h["facet_id"]],
                    sampleId = int.Parse(c[h["sample_id"]], Inv),
                    localPos = BodyToUnity(F(c[h["x_body"]]), F(c[h["y_body"]]), F(c[h["z_body"]])),
                    localNormal = BodyToUnity(F(c[h["nx"]]), F(c[h["ny"]]), F(c[h["nz"]])).normalized,
                });
            }
            return outRows.ToArray();
        }

        public static List<GroundMark> ReadGroundControl(string path)
        {
            var outRows = new List<GroundMark>();
            foreach (var c in Rows(path, out var h))
            {
                outRows.Add(new GroundMark
                {
                    id = c[h["id"]],
                    xE = F(c[h["x_e"]]),
                    yN = F(c[h["y_n"]]),
                    uExpected = F(c[h["u_lidar"]]),
                });
            }
            return outRows;
        }
    }
}
