"""Unity -> Python import and E8 agreement metrics (workflow guide E8).

Beam state per facet sample and record: building (blocked by terrain, buildings, bridges or
covered), tree (blocked by trees only), lit, or invalid (sun below the horizon or behind
the facet). Trees count once per crossing in every engine, so states compare like with like.

Gates: per-sample state agreement >= 97 % over sample-records valid in both engines; each
trip's lit (beam-visible) fraction within 2 percentage points.
"""

import gzip

import numpy as np
import pandas as pd

INVALID, LIT, TREE, BUILDING = -1, 0, 1, 2
NAMES = {LIT: "lit", TREE: "tree", BUILDING: "building"}
GATE_AGREEMENT = 0.97
GATE_LIT_PP = 2.0


def unity_state(bld, tree):
    bld, tree = np.asarray(bld), np.asarray(tree)
    return np.where(bld < 0, INVALID, np.where(bld == 1, BUILDING, np.where(tree == 1, TREE, LIT)))


def engine_state(bld, tree, valid):
    return np.where(~np.asarray(valid), INVALID, np.where(bld, BUILDING, np.where(tree, TREE, LIT)))


def read_visibility(path, n_samples):
    """Unity visibility file -> (t_utc per record, building hit, tree hit), (records, samples)."""
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as fh:
        df = pd.read_csv(fh, dtype={"t_utc": str, "facet_id": str})
    if len(df) % n_samples:
        raise ValueError(f"{path}: {len(df)} rows is not a multiple of {n_samples} samples")
    n = len(df) // n_samples
    bld = df["beam_building_hit"].to_numpy().reshape(n, n_samples)
    tree = df["beam_tree_hit"].to_numpy().reshape(n, n_samples)
    t = df["t_utc"].to_numpy()[::n_samples]
    return (
        t,
        bld,
        tree,
        df["sample_id"].to_numpy()[:n_samples],
        df["facet_id"].to_numpy()[:n_samples],
    )


def sun_enu(az_deg, el_deg):
    az, el = np.radians(np.asarray(az_deg, float)), np.radians(np.asarray(el_deg, float))
    return np.stack([np.cos(el) * np.sin(az), np.cos(el) * np.cos(az), np.sin(el)], axis=-1)


def body_to_enu(vec_body, heading_deg):
    """Body vectors (samples, 3: x fwd, y left, z up) at headings (records) -> ENU (records,
    samples, 3)."""
    h = np.radians(np.asarray(heading_deg, float))[:, None]
    b = np.asarray(vec_body, float)[None, :, :]
    fx, fy = np.sin(h), np.cos(h)  # forward
    lx, ly = -np.cos(h), np.sin(h)  # left
    e = b[..., 0] * fx + b[..., 1] * lx
    n = b[..., 0] * fy + b[..., 1] * ly
    return np.stack([e, n, np.broadcast_to(b[..., 2], e.shape)], axis=-1)


def valid_mask(traj, normals_body):
    """Sun above the horizon and in front of the facet, the probe's test (records, samples)."""
    n = body_to_enu(normals_body, traj["heading_deg"].to_numpy())
    s = sun_enu(traj["sun_az_deg"], traj["sun_el_deg"])
    facing = np.einsum("rsk,rk->rs", n, s) > 0
    return facing & (traj["sun_el_deg"].to_numpy() > 0)[:, None]


def compare(a, b):
    """Agreement of two state arrays over cells valid in both."""
    both = (a != INVALID) & (b != INVALID)
    n = int(both.sum())
    av, bv = a[both], b[both]
    conf = np.zeros((3, 3), np.int64)
    for i in (LIT, TREE, BUILDING):
        for j in (LIT, TREE, BUILDING):
            conf[i, j] = int(((av == i) & (bv == j)).sum())
    lit_a = float((av == LIT).mean()) if n else np.nan
    lit_b = float((bv == LIT).mean()) if n else np.nan
    return {
        "valid_both": n,
        "valid_only_one": int(((a != INVALID) ^ (b != INVALID)).sum()),
        "agreement": float((av == bv).mean()) if n else np.nan,
        "agreement_buildings": float(((av == BUILDING) == (bv == BUILDING)).mean())
        if n
        else np.nan,
        "lit_a": lit_a,
        "lit_b": lit_b,
        "lit_diff_pp": 100 * (lit_b - lit_a),
        "confusion": conf,
    }


def summarize(per_trip, a_name, b_name):
    """Pooled agreement and gate verdicts from per-trip compare() results."""
    conf = sum(r["confusion"] for r in per_trip)
    n = conf.sum()
    agree = np.trace(conf) / n if n else np.nan
    worst = max(abs(r["lit_diff_pp"]) for r in per_trip)
    within = sum(abs(r["lit_diff_pp"]) <= GATE_LIT_PP for r in per_trip)
    return {
        "pair": f"{a_name} vs {b_name}",
        "trips": len(per_trip),
        "sample_records": int(n),
        "agreement": round(float(agree), 5),
        "agreement_buildings": round(
            float((conf[BUILDING, BUILDING] + conf[:2, :2].sum()) / n) if n else np.nan, 5
        ),
        "confusion_rows_a_cols_b": {
            NAMES[i]: {NAMES[j]: int(conf[i, j]) for j in (LIT, TREE, BUILDING)}
            for i in (LIT, TREE, BUILDING)
        },
        "lit_diff_pp_max_abs": round(float(worst), 3),
        "lit_diff_pp_mean": round(float(np.mean([r["lit_diff_pp"] for r in per_trip])), 3),
        "trips_within_2pp": int(within),
        "pass_agreement": bool(agree >= GATE_AGREEMENT),
        "pass_lit_fraction": bool(within == len(per_trip)),
    }


def clusters(x, y, kind, el, cell_m=5.0, top=25):
    """Disagreements binned on a ``cell_m`` grid: count, dominant kind, median sun elevation."""
    df = pd.DataFrame(
        {
            "gx": np.floor(np.asarray(x) / cell_m),
            "gy": np.floor(np.asarray(y) / cell_m),
            "kind": kind,
            "el": el,
        }
    )
    g = df.groupby(["gx", "gy"])
    out = g.agg(n=("kind", "size"), sun_el_median=("el", "median")).reset_index()
    dom = g["kind"].agg(lambda k: k.value_counts().index[0]).reset_index(name="dominant")
    out = out.merge(dom, on=["gx", "gy"]).sort_values("n", ascending=False).head(top)
    out["x_utm"] = (out["gx"] + 0.5) * cell_m
    out["y_utm"] = (out["gy"] + 0.5) * cell_m
    out["share"] = out["n"] / len(df) if len(df) else np.nan
    return out.drop(columns=["gx", "gy"]).reset_index(drop=True)


def disagreement_kind(a, b):
    """Label each disagreeing cell: which states the two engines gave (a -> b)."""
    lab = np.array(["lit", "tree", "building"], dtype=object)
    return np.char.add(np.char.add(lab[a].astype(str), "->"), lab[b].astype(str))


class MeshProbe:
    """The Unity probe re-implemented on the same .glb meshes with Embree: rays from the
    sample offset 0.02 m along its normal toward the sun, buildings layer and trees layer
    queried separately, back faces hit. Used as a control (same geometry, other code)."""

    def __init__(self, surface_meshes, tree_meshes):
        import trimesh
        from trimesh.ray.ray_pyembree import RayMeshIntersector

        self.bld = RayMeshIntersector(trimesh.util.concatenate(list(surface_meshes)))
        trees = list(tree_meshes)
        self.tree = RayMeshIntersector(trimesh.util.concatenate(trees)) if trees else None

    def states(self, traj, pos_body, normals_body, offset=0.02):
        valid = valid_mask(traj, normals_body)
        cov = traj["covered"].to_numpy().astype(bool)
        p = body_to_enu(pos_body, traj["heading_deg"].to_numpy())
        p = p + traj[["x_e", "y_n", "z_u"]].to_numpy()[:, None, :]
        nrm = body_to_enu(normals_body, traj["heading_deg"].to_numpy())
        s = np.broadcast_to(sun_enu(traj["sun_az_deg"], traj["sun_el_deg"])[:, None, :], p.shape)
        cast = valid & ~cov[:, None]
        o = (p + offset * nrm)[cast]
        d = s[cast]
        bld = np.zeros(valid.shape, bool)
        tree = np.zeros(valid.shape, bool)
        if len(o):
            bld[cast] = self.bld.intersects_any(o, d)
            if self.tree is not None:
                tree[cast] = self.tree.intersects_any(o, d)
        bld[cov] = True
        tree[cov] = False
        return engine_state(bld, tree, valid)
