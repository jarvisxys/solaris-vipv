"""A parked vehicle's sky from the E4 horizon masks (data/derived/e4/masks_<site>_<hdg>.npz):
per-sample beam visibility at any sun position and per-facet sky and horizon-band views,
with trees passing ``tau`` (the same arithmetic as experiments/e4_parking)."""

import numpy as np

from solaris.vehicle import facets, normal_enu, samples

from .city import D
from .horizon import facet_sky_weights

EL_STEP = 0.5
N_EL = int(90 / EL_STEP)


def load_masks(site, heading_deg, root=D):
    """(blocked by buildings or a canopy, blocked by anything) per sample, azimuth, elevation."""
    z = np.load(root / "e4" / f"masks_{site}_{int(heading_deg):03d}.npz")
    mb = np.unpackbits(z["buildings"], axis=-1)[..., :N_EL].astype(bool)
    ma = np.unpackbits(z["all"], axis=-1)[..., :N_EL].astype(bool)
    return mb, ma


def facet_views(mb, ma, vcfg, heading_deg, tau, band_deg):
    """Per facet: sample indices, mean sky view and mean horizon-band view (trees pass tau)."""
    s = samples(facets(vcfg), vcfg["sample_spacing_m"])
    band = int(round(band_deg / EL_STEP))
    out = {}
    for f in facets(vcfg):
        idx = np.nonzero(s["facet_id"].to_numpy() == f.id)[0]
        W = facet_sky_weights(normal_enu(f, heading_deg), mb.shape[1], EL_STEP)
        open_c, tree_c = ~ma[idx], ma[idx] & ~mb[idx]
        svf = ((open_c * W).sum((1, 2)) + tau * (tree_c * W).sum((1, 2))) / W.sum()
        wb = W[:, :band].sum()
        vhz = (
            (
                (open_c[:, :, :band] * W[:, :band]).sum((1, 2))
                + tau * (tree_c[:, :, :band] * W[:, :band]).sum((1, 2))
            )
            / wb
            if wb > 0
            else np.ones(len(idx))
        )
        out[f.id] = {"facet": f, "idx": idx, "svf": float(svf.mean()), "vhz": float(vhz.mean())}
    return out


def sample_vb(mb, ma, idx, sun_az, sun_el, tau):
    """Beam visibility (steps, samples): 0 behind buildings or the canopy, tau behind trees."""
    az_i = np.rint(np.asarray(sun_az)).astype(int) % mb.shape[1]
    el_i = np.clip((np.asarray(sun_el) / EL_STEP).astype(int), 0, mb.shape[2] - 1)
    bb = mb[idx][:, az_i, el_i]
    ba = ma[idx][:, az_i, el_i]
    return np.where(bb, 0.0, np.where(ba, tau, 1.0)).T
