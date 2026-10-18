"""SUMO job, run in the separate 'sumo' conda env (stdlib + sumolib only; no solaris imports).

    <sumo env python> sumo_job.py job.json

job.json keys: osm (OSM XML), workdir, routes {id: [[lon, lat], ...]} (forward direction),
departures_s (seconds after sim start), end_s, seeds {name: {seed, period_s}}, step_s.
Per demand seed: background trips (randomTrips), the ego vehicles (each route forward and
reverse at every departure, map-matched to the network), one SUMO run with 1 Hz FCD for
the egos only, written as fcd_<seed>.csv (veh, t, x, y, lon, lat, angle, speed, edge).
"""

import csv
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import sumolib
import sumolib.route

SUMO_HOME = Path(os.environ.get("SUMO_HOME") or Path(sumolib.__file__).parents[1] / "sumo")
BIN = Path(sys.executable).parent / "Scripts"
TOOLS = SUMO_HOME / "tools"


def exe(name):
    for d in (BIN, SUMO_HOME / "bin"):
        p = d / f"{name}.exe"
        if p.exists():
            return str(p)
    return name


def run(cmd, log):
    with open(log, "a", encoding="utf-8") as f:
        f.write("$ " + " ".join(map(str, cmd)) + "\n")
        r = subprocess.run(list(map(str, cmd)), stdout=f, stderr=subprocess.STDOUT)
    if r.returncode != 0:
        raise SystemExit(f"failed ({r.returncode}): {cmd[0]}; see {log}")


def build_net(osm, net, log):
    if net.exists():
        return
    run(
        [
            exe("netconvert"),
            "--osm-files",
            osm,
            "--output-file",
            net,
            "--geometry.remove",
            "--ramps.guess",
            "--junctions.join",
            "--tls.guess-signals",
            "--tls.discard-simple",
            "--tls.join",
            "--remove-edges.isolated",
            "--keep-edges.by-vclass",
            "passenger",
            "--osm.all-attributes",
            "false",
            "--no-warnings",
        ],
        log,
    )


def resample(xy, step):
    """Points every ``step`` m along a polyline, with the local travel bearing (deg)."""
    segs = [(a, b) for a, b in zip(xy[:-1], xy[1:], strict=True) if a != b]
    lens = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in segs]
    total = sum(lens)
    targets = [k * step for k in range(int(total // step) + 1)] + [total]
    out, start, i = [], 0.0, 0
    for t in targets:
        while i < len(segs) - 1 and start + lens[i] < t:
            start += lens[i]
            i += 1
        (x0, y0), (x1, y1) = segs[i]
        f = min(1.0, (t - start) / lens[i])
        out.append(
            (
                x0 + (x1 - x0) * f,
                y0 + (y1 - y0) * f,
                math.degrees(math.atan2(x1 - x0, y1 - y0)) % 360,
            )
        )
    return out


def edge_bearing(edge, x, y):
    """Bearing (deg) of the edge's shape segment nearest (x, y)."""
    shape = edge.getShape()
    best = None
    for (x0, y0), (x1, y1) in zip(shape[:-1], shape[1:], strict=True):
        d = sumolib.geomhelper.distancePointToLine((x, y), (x0, y0), (x1, y1))
        if best is None or d < best[0]:
            best = (d, math.degrees(math.atan2(x1 - x0, y1 - y0)) % 360)
    return best[1]


def snap(net, x, y, bearing, radius=40.0):
    """Nearest passenger edge running within 60 deg of the travel bearing."""
    cands = []
    for e, d in net.getNeighboringEdges(x, y, radius):
        if not e.allows("passenger"):
            continue
        diff = abs((edge_bearing(e, x, y) - bearing + 180) % 360 - 180)
        if diff <= 60:
            cands.append((d + diff / 6.0, e))
    return min(cands, key=lambda c: c[0])[1] if cands else None


def ego_routes(net, polylines, log_path, via_m=400.0):
    """Edges for every route, forward and reverse: via points every ``via_m`` along the
    frozen polyline, each snapped to the nearest edge running in the travel direction,
    chained with SUMO shortest paths (which follow real lane connections)."""
    out = {}
    with open(log_path, "a", encoding="utf-8") as log:
        for rid, ll in polylines.items():
            for d, pts in (("fwd", ll), ("rev", ll[::-1])):
                xy = [net.convertLonLat2XY(lon, lat) for lon, lat in pts]
                vias = [snap(net, x, y, b) for x, y, b in resample(xy, via_m)]
                vias = [
                    v for i, v in enumerate(vias) if v is not None and (i == 0 or v != vias[i - 1])
                ]
                ids = [vias[0].getID()]
                for a, b in zip(vias[:-1], vias[1:], strict=True):
                    path, _ = net.getShortestPath(a, b, vClass="passenger")
                    if path is None:
                        log.write(f"{rid} {d}: no path {a.getID()} -> {b.getID()}, via skipped\n")
                        continue
                    ids += [e.getID() for e in path[1:]]
                log.write(f"{rid} {d}: {len(vias)} vias, {len(ids)} edges\n")
                out[f"{rid}_{d}"] = ids
    return out


def write_egos(path, routes, departures_s):
    with open(path, "w", encoding="utf-8") as f:
        f.write('<routes>\n  <vType id="ego" vClass="passenger" length="5.0" width="2.0"/>\n')
        vehicles = []
        for rid, edges in routes.items():
            for dep in departures_s:
                vehicles.append((dep, f"{rid}_{int(dep)}", edges))
        for dep, vid, edges in sorted(vehicles):
            f.write(f'  <vehicle id="{vid}" type="ego" depart="{dep:.0f}" ')
            f.write('departLane="best" departSpeed="max">\n')
            f.write(f'    <route edges="{" ".join(edges)}"/>\n  </vehicle>\n')
        f.write("</routes>\n")
    return [v for _, v, _ in sorted(vehicles)]


def main(job_path):
    job = json.loads(Path(job_path).read_text(encoding="utf-8"))
    wd = Path(job["workdir"])
    wd.mkdir(parents=True, exist_ok=True)
    log = wd / "sumo.log"
    net_path = wd / "phoenix.net.xml.gz"
    build_net(job["osm"], net_path, log)
    net = sumolib.net.readNet(str(net_path))
    routes = ego_routes(net, job["routes"], log)
    (wd / "ego_edges.json").write_text(json.dumps(routes, indent=1), encoding="utf-8")
    egos = write_egos(wd / "ego.rou.xml", routes, job["departures_s"])
    for name, s in job["seeds"].items():
        bg = wd / f"bg_{name}.rou.xml"
        if not bg.exists():
            run(
                [
                    sys.executable,
                    TOOLS / "randomTrips.py",
                    "-n",
                    net_path,
                    "-o",
                    wd / f"bg_{name}.trips.xml",
                    "-r",
                    bg,
                    "-b",
                    0,
                    "-e",
                    job["end_s"],
                    "-p",
                    s["period_s"],
                    "--seed",
                    s["seed"],
                    "--fringe-factor",
                    5,
                    "--vehicle-class",
                    "passenger",
                    "--prefix",
                    f"bg{name}_",
                    "--min-distance",
                    1000,
                    "--validate",
                ],
                log,
            )
        fcd = wd / f"fcd_{name}.xml"
        run(
            [
                exe("sumo"),
                "-n",
                net_path,
                "-r",
                f"{bg},{wd / 'ego.rou.xml'}",
                "-b",
                0,
                "-e",
                job["end_s"],
                "--step-length",
                job["step_s"],
                "--seed",
                s["seed"],
                "--fcd-output",
                fcd,
                "--device.fcd.explicit",
                ",".join(egos),
                "--time-to-teleport",
                300,
                "--ignore-route-errors",
                "true",
                "--no-step-log",
                "true",
                "--tripinfo-output",
                wd / f"tripinfo_{name}.xml",
            ],
            log,
        )
        with open(wd / f"fcd_{name}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["veh", "t", "x", "y", "lon", "lat", "angle", "speed", "edge"])
            for ts in sumolib.xml.parse_fast_nested(
                str(fcd),
                "timestep",
                ["time"],
                "vehicle",
                ["id", "x", "y", "angle", "speed", "lane"],
            ):
                t, v = ts
                x, y = float(v.x), float(v.y)
                lon, lat = net.convertXY2LonLat(x, y)
                edge = v.lane.rsplit("_", 1)[0]
                w.writerow(
                    [
                        v.id,
                        t.time,
                        f"{x:.2f}",
                        f"{y:.2f}",
                        f"{lon:.7f}",
                        f"{lat:.7f}",
                        v.angle,
                        v.speed,
                        edge,
                    ]
                )
        fcd.unlink()
    print("ok")


if __name__ == "__main__":
    main(sys.argv[1])
