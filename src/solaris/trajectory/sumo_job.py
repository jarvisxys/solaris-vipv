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


def ego_routes(net, polylines, log_path):
    """Edges for every route, forward and reverse, by map matching the polyline."""
    out = {}
    with open(log_path, "a", encoding="utf-8") as log:
        for rid, ll in polylines.items():
            for d, pts in (("fwd", ll), ("rev", ll[::-1])):
                trace = [net.convertLonLat2XY(lon, lat) for lon, lat in pts]
                edges = sumolib.route.mapTrace(
                    trace, net, delta=25.0, fillGaps=3000.0, direction=True, vClass="passenger"
                )
                ids = [e.getID() for e in edges]
                log.write(f"{rid} {d}: {len(ids)} edges\n")
                if not ids:
                    raise SystemExit(f"map matching failed for {rid} {d}")
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
