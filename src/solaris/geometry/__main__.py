"""python -m solaris.geometry {fetch,rasterize,model,meshes} [--workers N] [--tiles ID ...]"""

import argparse

from .build import WORKERS, check_results, run_tiles

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("step", choices=sorted(WORKERS))
    ap.add_argument("--workers", type=int)
    ap.add_argument("--tiles", nargs="*", help="tile ids (default: all in tiles.csv)")
    a = ap.parse_args()
    check_results(a.step, run_tiles(a.step, a.workers, set(a.tiles) if a.tiles else None))
