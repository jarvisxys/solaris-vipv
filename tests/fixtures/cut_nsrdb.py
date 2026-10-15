"""Cut whole local days out of an NSRDB CSV to make a test fixture.

    python tests/fixtures/cut_nsrdb.py SRC DST 01-01 03-12 11-05 12-31

Keeps the two metadata lines, the column header and every row whose local-standard-time
date (month-day) is listed. UTC-stamped files are shifted by their Local Time Zone first.
"""

import csv
import sys
from datetime import datetime, timedelta


def cut(src, dst, days):
    with open(src, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    meta = dict(zip(rows[0], rows[1], strict=False))
    shift = timedelta(hours=int(meta["Local Time Zone"]) - int(meta["Time Zone"]))
    head = rows[2]
    keep = []
    for r in rows[3:]:
        stamp = datetime(
            *(int(r[head.index(c)]) for c in ("Year", "Month", "Day", "Hour", "Minute"))
        )
        if (stamp + shift).strftime("%m-%d") in days:
            keep.append(r)
    with open(dst, "w", newline="", encoding="utf-8") as f:
        csv.writer(f, lineterminator="\n").writerows(rows[:3] + keep)
    return len(keep)


if __name__ == "__main__":
    print(cut(sys.argv[1], sys.argv[2], set(sys.argv[3:])), "rows")
