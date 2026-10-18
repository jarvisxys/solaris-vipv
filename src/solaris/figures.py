"""Shared matplotlib style for result figures (light, print): reference data-viz palette,
fixed categorical order, hairline grid, recessive axes, system sans."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"


def style():
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Segoe UI", "DejaVu Sans", "Arial"],
            "font.size": 9,
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "axes.edgecolor": AXIS,
            "axes.labelcolor": INK2,
            "axes.titlecolor": INK,
            "axes.titlesize": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": GRID,
            "grid.linewidth": 0.6,
            "axes.axisbelow": True,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "xtick.labelcolor": INK2,
            "ytick.labelcolor": INK2,
            "lines.linewidth": 1.5,
            "legend.frameon": False,
            "svg.hashsalt": "solaris",
            "pdf.compression": 6,
        }
    )
    return plt


def save(fig, stem):
    """PNG (300 dpi) and PDF with fixed metadata so reruns are byte-stable where possible."""
    fig.savefig(f"{stem}.png", dpi=300, bbox_inches="tight", metadata={"Software": None})
    fig.savefig(
        f"{stem}.pdf", bbox_inches="tight", metadata={"CreationDate": None, "Producer": None}
    )
