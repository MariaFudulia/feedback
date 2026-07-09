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
_BANDS = ["4-5", "3-4", "2-3", "1-2"]  # score bands, high to low (1-5 Likert)


def _band(score):
    if score >= 4:
        return "4-5"
    if score >= 3:
        return "3-4"
    if score >= 2:
        return "2-3"
    return "1-2"


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
                "an": ms[0]["an"],
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


def _people(tip, year=None):
    """Aggregate cadre of a `tip` (titular/asistent) across every offering, per person.
    evaluare_prof is the num_feedback-weighted mean of each appearance's teaching-key mean;
    proc_feedback is the person's overall responses/students across their offerings."""
    acc = {}
    for m in taxonomy.offering_metrics(year):
        for c in m["cadre"]:
            if c["tip"] != tip:
                continue
            a = acc.setdefault(
                c["nume"], {"cursuri": set(), "nf": 0, "stud": 0, "resp": 0, "prof_w": 0.0, "curs_w": 0.0}
            )
            nf = c["num_feedback"]
            a["cursuri"].add(m["curs"])
            a["nf"] += nf
            a["stud"] += m["students"]
            a["resp"] += m["responses"]
            a["prof_w"] += nf * _mean([c[k] for k in _TEACH_KEYS])
            a["curs_w"] += nf * m["evaluare_curs"]
    out = []
    for nume, a in acc.items():
        nf = a["nf"] or 1
        out.append(
            {
                "persoana": nume,
                "num_cursuri": len(a["cursuri"]),
                "num_feedback": a["nf"],
                "num_utilizatori": a["stud"],
                "proc_feedback": round(100 * a["resp"] / a["stud"], 2) if a["stud"] else 0.0,
                "evaluare_curs": round(a["curs_w"] / nf, 2),
                "evaluare_prof": round(a["prof_w"] / nf, 2),
            }
        )
    return out


def get_top_titulari(order_by="evaluare_prof", limit=10):
    """columns: persoana, num_cursuri, num_feedback, proc_feedback, num_utilizatori,
    evaluare_curs, evaluare_prof. Deck threshold: proc_feedback >= 7% AND num_feedback >= 15."""
    cols = [
        "persoana",
        "num_cursuri",
        "num_feedback",
        "proc_feedback",
        "num_utilizatori",
        "evaluare_curs",
        "evaluare_prof",
    ]
    rows = [r for r in _people("titular") if r["proc_feedback"] >= 7 and r["num_feedback"] >= 15]
    df = pd.DataFrame(rows, columns=cols)
    if order_by in cols:
        df = df.sort_values(order_by, ascending=False)
    return df.head(limit).reset_index(drop=True)


def get_top_asistenti(order_by="evaluare_prof", limit=10):
    """columns: persoana, num_feedback, evaluare_curs, evaluare_prof.
    Deck threshold: num_feedback >= 10."""
    cols = ["persoana", "num_feedback", "evaluare_curs", "evaluare_prof"]
    rows = [r for r in _people("asistent") if r["num_feedback"] >= 10]
    df = pd.DataFrame(rows, columns=cols)
    if order_by in cols:
        df = df.sort_values(order_by, ascending=False)
    return df.head(limit).reset_index(drop=True)


def get_score_distribution(entitate):
    """columns: banda, num, pct  (entitate in {'curs', 'titular', 'asistent'})
    Histograms the per-entity evaluation into the deck's 4-5/3-4/2-3/1-2 bands."""
    if entitate == "curs":
        scores = [r["evaluare_curs"] for r in _courses()]
    else:
        scores = [r["evaluare_prof"] for r in _people(entitate)]
    total = len(scores) or 1
    counts = dict.fromkeys(_BANDS, 0)
    for s in scores:
        counts[_band(s)] += 1
    rows = [{"banda": b, "num": counts[b], "pct": round(100 * counts[b] / total, 1)} for b in _BANDS]
    return pd.DataFrame(rows, columns=["banda", "num", "pct"])


def _rollup(courses):
    """{proc_completare, evaluare} over a set of per-curs rows."""
    resp = sum(c["num_feedback"] for c in courses)
    stud = sum(c["num_utilizatori"] for c in courses)
    return (
        round(100 * resp / stud, 2) if stud else 0.0,
        _mean([c["evaluare_curs"] for c in courses]),
    )


def get_period_breakdown(ciclu=None, semestru=None):
    """columns: bucket, proc_completare, evaluare -- structural rollup of the current year
    (all / L / L-A1 / L-A1-S1 / ...). ciclu/semestru filter the bucket labels (as the deck did)."""
    courses = _courses()
    specs = [("all", lambda c: True)]
    for cic in sorted({c["ciclu"] for c in courses}):
        specs.append((cic, lambda c, cic=cic: c["ciclu"] == cic))
        for an in sorted({c["an"] for c in courses if c["ciclu"] == cic}):
            specs.append((f"{cic}-A{an}", lambda c, cic=cic, an=an: c["ciclu"] == cic and c["an"] == an))
            for sem in sorted(
                {c["sem"] for c in courses if c["ciclu"] == cic and c["an"] == an and c["sem"]}
            ):
                specs.append(
                    (
                        f"{cic}-A{an}-S{sem}",
                        lambda c, cic=cic, an=an, sem=sem: (
                            c["ciclu"] == cic and c["an"] == an and c["sem"] == sem
                        ),
                    )
                )
    rows = []
    for label, pred in specs:
        sel = [c for c in courses if pred(c)]
        if not sel:
            continue
        proc, evaluare = _rollup(sel)
        rows.append({"bucket": label, "proc_completare": proc, "evaluare": evaluare})
    df = pd.DataFrame(rows, columns=["bucket", "proc_completare", "evaluare"])
    if ciclu in ("L", "M"):
        df = df[df["bucket"].str.startswith(("all", ciclu))]
    if semestru == "S1":
        df = df[df["bucket"].str.endswith("-S1")]
    elif semestru == "S2":
        df = df[df["bucket"].str.endswith("-S2")]
    return df.reset_index(drop=True)


def get_year_breakdown(an, ciclu="L"):
    """columns: serie, proc_completare, evaluare -- per-serie within an an de studiu.
    Empty for years with no data (honest gap; the deck stopped at An 3)."""
    groups = {}
    for m in taxonomy.offering_metrics():
        if m["ciclu"] == ciclu and m["an"] == an and m["serie"]:
            groups.setdefault((m["sem"], m["serie"]), []).append(m)
    rows = []
    for (sem, serie), ms in sorted(groups.items()):
        resp = sum(m["responses"] for m in ms)
        stud = sum(m["students"] for m in ms)
        rows.append(
            {
                "serie": f"{ciclu}-A{an}-S{sem}-{serie}",
                "proc_completare": round(100 * resp / stud, 2) if stud else 0.0,
                "evaluare": _mean([m["evaluare_curs"] for m in ms]),
            }
        )
    return pd.DataFrame(rows, columns=["serie", "proc_completare", "evaluare"])
