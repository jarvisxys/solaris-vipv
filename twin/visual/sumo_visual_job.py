"""Visual-only SUMO re-run for the Playback scene (P8-visual). Runs in the 'sumo' conda env.

Re-runs the frozen v2 simulation (src/solaris/trajectory/sumo_job.py) with the identical network,
background demand, ego routes, seed and options, adding only OUTPUT:
  * FCD of every vehicle on edges within `corridor_m` of R-DENSE (instead of the egos only), kept
    per R-DENSE ego when the vehicle is within `radius_m` of that ego;
  * traffic-light switches (SaveTLSSwitchStates) of the signals controlling those edges,
    and their geometry.
Output goes to the job's out_dir only; data/derived/sumo/v2 and results/p6 are never written.
The ego rows are written too, so the caller can prove the re-run equals the frozen traces.

    <sumo env python> twin/visual/sumo_visual_job.py <job.json>
"""

import csv
import json
import math
import subprocess
import sys
from pathlib import Path

import sumolib

SUMO_HOME = Path(sumolib.__file__).parents[1] / "sumo"
BIN = Path(sys.executable).parent / "Scripts"


def exe(name):
    for p in (BIN / f"{name}.exe", SUMO_HOME / "bin" / f"{name}.exe"):
        if p.exists():
            return str(p)
    return name


def corridor_edges(net, lonlat, corridor_m):
    """Edges with any shape point within corridor_m of the route polyline (net metres)."""
    pts = [net.convertLonLat2XY(lon, lat) for lon, lat in lonlat]
    dense = []
    for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:], strict=True):
        n = max(1, int(math.hypot(x1 - x0, y1 - y0) // 20))
        dense += [(x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n) for k in range(n)]
    cell = corridor_m
    grid = {}
    for x, y in dense:
        grid.setdefault((int(x // cell), int(y // cell)), []).append((x, y))

    def near(x, y):
        cx, cy = int(x // cell), int(y // cell)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for px, py in grid.get((cx + dx, cy + dy), ()):
                    if (px - x) ** 2 + (py - y) ** 2 <= corridor_m**2:
                        return True
        return False

    keep = []
    for e in net.getEdges(withInternal=True):  # junction-internal lanes too: no gaps
        if any(near(x, y) for x, y in e.getShape()):
            keep.append(e)
    return keep


def ego_edges(net, src, route):
    """Every edge the route's egos drive, with the junction-internal lanes between them (the
    SUMO route can leave the 400 m corridor near its ends)."""
    out = set()
    routes = json.loads((src / "ego_edges.json").read_text(encoding="utf-8"))
    for rid, ids in routes.items():
        if not rid.startswith(route + "_"):
            continue
        out.update(ids)
        for a, b in zip(ids[:-1], ids[1:], strict=True):
            for c in net.getEdge(a).getOutgoing().get(net.getEdge(b), []):
                via = c.getViaLaneID()
                while via:
                    lane = net.getLane(via)
                    out.add(lane.getEdge().getID())
                    nxt = [x.getViaLaneID() for x in lane.getOutgoing() if x.getViaLaneID()]
                    via = nxt[0] if nxt else ""
    return out


def tls_meta(net, edges):
    """Signals controlling the corridor edges and, per controlled link, its incoming lane
    (index 0 = rightmost), the stop-line point (lon/lat), the lane's grid bearing and the
    turn direction ('s' straight, 'l'/'r' turns, 't' U-turn), for the signal heads in Unity."""
    ids = {e.getID() for e in edges}
    out = []
    for tls in net.getTrafficLights():
        links = []
        for lane_in, lane_out, li in tls.getConnections():
            e = lane_in.getEdge()
            if e.getID() not in ids:
                continue
            conn = [c for c in lane_in.getOutgoing() if c.getTLLinkIndex() == li]
            shp = lane_in.getShape()
            (xa, ya), (xb, yb) = shp[-2], shp[-1]
            lon, lat = net.convertXY2LonLat(xb, yb)
            links.append(
                {
                    "link": li,
                    "edge": e.getID(),
                    "to": lane_out.getEdge().getID(),
                    "far": list(net.convertXY2LonLat(*lane_out.getShape()[0])),
                    "lane": lane_in.getIndex(),
                    "lanes": e.getLaneNumber(),
                    "width": lane_in.getWidth(),
                    "dir": conn[0].getDirection().lower() if conn else "s",
                    "lon": lon,
                    "lat": lat,
                    "bearing": math.degrees(math.atan2(xb - xa, yb - ya)) % 360,
                }
            )
        if links:
            out.append({"id": tls.getID(), "links": links})
    return out


def write_meta(job_path):
    """Only the corridor edges and signal geometry (no simulation)."""
    job = json.loads(Path(job_path).read_text(encoding="utf-8"))
    src, out = Path(job["src_dir"]), Path(job["out_dir"])
    net = sumolib.net.readNet(str(src / "phoenix.net.xml.gz"), withInternal=True)
    lonlat = json.loads((src / "job.json").read_text(encoding="utf-8"))["routes"][job["route"]]
    edges = corridor_edges(net, lonlat, job["corridor_m"])
    have = {e.getID() for e in edges}
    edges += [net.getEdge(e) for e in sorted(ego_edges(net, src, job["route"]) - have)]
    meta = tls_meta(net, [e for e in edges if not e.getID().startswith(":")])
    (out / "tls_meta.json").write_text(json.dumps(meta), encoding="utf-8")
    print(f"signals {len(meta)}")


HEAD = ["veh", "t", "x", "y", "lon", "lat", "angle", "speed", "edge"]


class Splitter:
    """FCD rows of one seed -> ego_<seed>.csv (every ego) and traffic_<ego>_<seed>.csv (the
    other vehicles within the radius of each R-DENSE ego), one SUMO time step at a time."""

    def __init__(self, net, out, name, ego_ids, dense_egos, radius_m):
        self.net, self.out, self.name = net, out, name
        self.ego_ids, self.dense_egos, self.r2 = ego_ids, dense_egos, radius_m**2
        self.files, self.writers = {}, {}
        self.ego_f = open(out / f"ego_{name}.csv", "w", newline="", encoding="utf-8")
        self.ego_w = csv.writer(self.ego_f, lineterminator="\n")
        self.ego_w.writerow(HEAD)

    def writer(self, eid):
        if eid not in self.writers:
            f = open(self.out / f"traffic_{eid}_{self.name}.csv", "w", newline="", encoding="utf-8")
            self.files[eid] = f
            self.writers[eid] = csv.writer(f, lineterminator="\n")
            self.writers[eid].writerow(HEAD)
        return self.writers[eid]

    def step(self, t, rows):
        egos_now = {v.id: (float(v.x), float(v.y)) for v in rows if v.id in self.dense_egos}
        for v in rows:
            x, y = float(v.x), float(v.y)
            lon, lat = self.net.convertXY2LonLat(x, y)
            edge = v.lane.rsplit("_", 1)[0]
            row = [
                v.id,
                t,
                f"{x:.2f}",
                f"{y:.2f}",
                f"{lon:.7f}",
                f"{lat:.7f}",
                v.angle,
                v.speed,
                edge,
            ]
            if v.id in self.ego_ids:
                self.ego_w.writerow(row)
                continue
            for eid, (ex_, ey_) in egos_now.items():
                if (x - ex_) ** 2 + (y - ey_) ** 2 <= self.r2:
                    self.writer(eid).writerow(row)

    def close(self):
        self.ego_f.close()
        for f in self.files.values():
            f.close()
        return len(self.files)


def main(job_path):
    job = json.loads(Path(job_path).read_text(encoding="utf-8"))
    src, out = Path(job["src_dir"]), Path(job["out_dir"])
    out.mkdir(parents=True, exist_ok=True)
    net_path = src / "phoenix.net.xml.gz"
    net = sumolib.net.readNet(str(net_path), withInternal=True)
    lonlat = json.loads((src / "job.json").read_text(encoding="utf-8"))["routes"][job["route"]]
    edges = corridor_edges(net, lonlat, job["corridor_m"])
    have = {e.getID() for e in edges}
    edges += [net.getEdge(e) for e in sorted(ego_edges(net, src, job["route"]) - have)]
    (out / "edges.txt").write_text("".join(f"edge:{e.getID()}\n" for e in edges), encoding="utf-8")
    meta = tls_meta(net, [e for e in edges if not e.getID().startswith(":")])
    (out / "tls_meta.json").write_text(json.dumps(meta), encoding="utf-8")
    print(f"corridor edges {len(edges)}, signals {len(meta)}", flush=True)
    ego_ids = set()
    for line in (src / "ego.rou.xml").read_text(encoding="utf-8").splitlines():
        if "<vehicle " in line:
            ego_ids.add(line.split('id="')[1].split('"')[0])
    dense_egos = {v for v in ego_ids if v.startswith(job["route"] + "_")}

    for name, s in job["seeds"].items():
        add = out / f"tls_{name}.add.xml"
        tls_out = out / f"tls_{name}.xml"
        add.write_text(
            "<additional>\n"
            + "".join(
                f'  <timedEvent type="SaveTLSSwitchStates" source="{t["id"]}" '
                f'dest="{tls_out.name}"/>\n'
                for t in meta
            )
            + "</additional>\n",
            encoding="utf-8",
        )
        fcd = out / f"fcd_{name}.xml"
        cmd = [
            exe("sumo"),
            "-n",
            str(net_path),
            "-r",
            f"{src / f'bg_{name}.rou.xml'},{src / 'ego.rou.xml'}",
            "-b",
            "0",
            "-e",
            str(job["end_s"]),
            "--step-length",
            str(job["step_s"]),
            "--seed",
            str(s["seed"]),
            "--time-to-teleport",
            "300",
            "--ignore-route-errors",
            "true",
            "--no-step-log",
            "true",
            # visual-only outputs (they do not change the simulation)
            "--fcd-output",
            str(fcd),
            "--fcd-output.filter-edges.input-file",
            str(out / "edges.txt"),
            "--additional-files",
            str(add),
        ]
        with open(out / "sumo.log", "a", encoding="utf-8") as log:
            log.write(" ".join(cmd) + "\n")
            r = subprocess.run(cmd, cwd=out, stdout=log, stderr=subprocess.STDOUT)
        if r.returncode:
            raise RuntimeError(f"sumo exited {r.returncode} for {name}")

        sp = Splitter(net, out, name, ego_ids, dense_egos, job["radius_m"])
        block_t, block = None, []
        for ts, v in sumolib.xml.parse_fast_nested(
            str(fcd), "timestep", ["time"], "vehicle", ["id", "x", "y", "angle", "speed", "lane"]
        ):
            if ts.time != block_t:
                if block:
                    sp.step(block_t, block)
                block_t, block = ts.time, []
            block.append(v)
        if block:
            sp.step(block_t, block)
        n_files = sp.close()
        fcd.unlink()
        print(f"{name}: traffic files for {n_files} R-DENSE egos", flush=True)
    print("ok")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[2] == "--meta":
        write_meta(sys.argv[1])
    else:
        main(sys.argv[1])
