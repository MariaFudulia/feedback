"""Deck-view rollups computed from the taxonomy content substrate.

Each function recomputes a deck view (Top-10, zones, coverage, breakdowns) from
`taxonomy.offering_metrics()` -- real structure now, real scores when the export lands
(badged "date demonstrative" until then, via `content_is_synthetic()`). Returns pandas
DataFrames with the exact columns the deck templates expect, so this is a drop-in for the
former `mocks.py` path. Sumar (the 9-year history) stays on `mocks` -- it can't be recomputed
from a single year of structure.
"""

import pandas as pd

import taxonomy

# a cadru's overall teaching score = mean of these 4 keys (per the pipeline's prof_* mapping)
_TEACH_KEYS = ["preg", "expl_clare", "interes", "comport"]


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 2) if xs else 0.0


def _courses(year=None):
    """offering_metrics grouped into one row per logical curs (sum counts, mean scores)."""
    groups = {}
    for m in taxonomy.offering_metrics(year):
        groups.setdefault(m["curs"], []).append(m)
    out = []
    for curs, ms in groups.items():
        responses = sum(m["responses"] for m in ms)
        students = sum(m["students"] for m in ms)
        titular = next((c["nume"] for m in ms for c in m["cadre"] if c["tip"] == "titular"), "-")
        out.append(
            {
                "curs": ms[0]["denumire"],
                "cod": curs,
                "prof": titular,
                "ciclu": ms[0]["ciclu"],
                "domeniu": ms[0]["domeniu"],
                "sem": ms[0]["sem"],
                "num_feedback": responses,
                "num_utilizatori": students,
                "proc_feedback": round(100 * responses / students, 2) if students else 0.0,
                "evaluare_curs": _mean([m["evaluare_curs"] for m in ms]),
            }
        )
    return out


def get_top_courses(order_by="evaluare_curs", ciclu=None, track=None, semestru=None, limit=10):
    """columns: curs, prof, num_feedback, proc_feedback, num_utilizatori, evaluare_curs
    Deck threshold: curs kept only if proc_feedback >= 7% AND num_feedback >= 3."""
    cols = ["curs", "prof", "num_feedback", "proc_feedback", "num_utilizatori", "evaluare_curs"]
    rows = [
        r
        for r in _courses()
        if (not ciclu or r["ciclu"] == ciclu)
        and (not track or r["domeniu"] == track)
        and (not semestru or f"S{r['sem']}" == semestru)
        and r["proc_feedback"] >= 7
        and r["num_feedback"] >= 3
    ]
    df = pd.DataFrame(rows, columns=cols)
    if order_by in cols:
        df = df.sort_values(order_by, ascending=False)
    return df.head(limit).reset_index(drop=True)
