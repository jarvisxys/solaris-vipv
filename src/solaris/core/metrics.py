"""Five-tier operational sufficiency metric (conference Sec. VIII)."""

# (lower bound of f_ss, class), checked top-down
TIERS = (
    (1.00, "self-sufficient"),
    (0.90, "quasi-self-sufficient"),
    (0.80, "highly solar-assisted"),
    (0.50, "moderately solar-assisted"),
)
LOWEST = "grid-dependent"


def classify(fss: float) -> str:
    for bound, name in TIERS:
        if fss >= bound:
            return name
    return LOWEST
