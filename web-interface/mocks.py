"""Hand-written mock data matching the queries.py contract exactly.

Numbers are taken from the coordinator's reference deck (2025-2026 sem1,
CTI) wherever a slide was legible, so pages B/C build against these should
look visually right when compared to the deck. A few series are shape-only
placeholders (noted below) because the source slide couldn't be read
precisely — that's fine for UI development, just don't treat these numbers
as real for anything user-facing.

Coleg A: do not edit call sites in queries.py that reference this file —
just replace each function body in queries.py with a real SQL query
returning a DataFrame with the SAME columns, then queries.py stops
importing from here at all.
"""
import pandas as pd

_YEARS = ["2018-2019", "2019-2020", "2020-2021", "2021-2022", "2022-2023 sem1",
          "2022-2023", "2023-2024 sem1", "2024-2025 sem1", "2025-2026 sem1"]

_SUMMARY_RAW = {
    "total":    dict(num_feedback=[4239, 5866, 8119, 5386, 3040, 4880, 3649, 3429, 3195],
                      proc_completare=[21.87, 24.04, 25.42, 18.80, 22.82, 20.51, 21.88, 21.36, 20.53],
                      num_cursuri=[138, 173, 266, 215, 103, 176, 139, 129, 104],
                      evaluare=[3.74, 3.80, 3.92, 4.03, 4.02, 3.97, 4.07, 4.16, 4.13]),
    "licenta":  dict(num_feedback=[4087, 5541, 7412, 4936, 2829, 4577, 3290, 2991, 2865],
                      proc_completare=[22.27, 24.38, 26.54, 19.17, 23.41, 21.01, 22.07, 22.01, 20.86],
                      num_cursuri=[118, 137, 180, 165, 77, 136, 103, 91, 85],
                      evaluare=[3.75, 3.79, 3.90, 4.00, 3.99, 3.94, 4.05, 4.14, 4.11]),
    "masterat": dict(num_feedback=[152, 325, 707, 430, 211, 303, 359, 438, 330],
                      proc_completare=[14.73, 19.43, 17.58, 15.39, 17.04, 15.11, 20.29, 17.18, 16.48],
                      num_cursuri=[20, 36, 86, 50, 26, 40, 36, 38, 19],
                      evaluare=[3.49, 4.01, 4.11, 4.31, 4.47, 4.39, 4.26, 4.28, 4.32]),
}


def get_summary(nivel=None):
    """columns: an_universitar, nivel, num_feedback, proc_completare, num_cursuri, evaluare"""
    rows = []
    for lvl, d in _SUMMARY_RAW.items():
        if nivel is not None and lvl != nivel:
            continue
        for i, an in enumerate(_YEARS):
            rows.append({
                "an_universitar": an, "nivel": lvl,
                "num_feedback": d["num_feedback"][i],
                "proc_completare": d["proc_completare"][i],
                "num_cursuri": d["num_cursuri"][i],
                "evaluare": d["evaluare"][i],
            })
    return pd.DataFrame(rows)


def get_course_coverage():
    """columns: categorie, num_cursuri, pct  (slide 4 — 'Cursuri cu feedback > 7%')"""
    return pd.DataFrame([
        {"categorie": "cu procentaj > prag", "num_cursuri": 104, "pct": 43.9},
        {"categorie": "fara procentaj",       "num_cursuri": 78,  "pct": 32.9},
        {"categorie": "zero",                 "num_cursuri": 55,  "pct": 23.2},
    ])


_PERIOD_BUCKETS = ["all", "L", "L-A1", "L-A1-S1", "L-A2", "L-A2-S1", "L-A3", "L-A3-S1",
                   "L-A4", "L-A4-S1", "M", "M-A1", "M-A1-S1", "M-A2", "M-A2-S1"]
_PERIOD_PROC = [20.53, 20.86, 20.12, 20.12, 27.74, 27.74, 18.62, 18.62,
                15.01, 15.01, 16.48, 19.11, 19.11, 11.39, 11.39]
_PERIOD_EVAL = [4.13, 4.19, 4.20, 4.20, 4.10, 4.10, 4.01, 4.01,
                4.13, 4.13, 4.35, 4.43, 4.43, 4.10, 4.10]


def get_period_breakdown(ciclu=None):
    """columns: bucket, proc_completare, evaluare  (slides 5+6, same x-axis)"""
    df = pd.DataFrame({"bucket": _PERIOD_BUCKETS, "proc_completare": _PERIOD_PROC, "evaluare": _PERIOD_EVAL})
    if ciclu == "L":
        return df[df["bucket"].str.startswith(("all", "L"))].reset_index(drop=True)
    if ciclu == "M":
        return df[df["bucket"].str.startswith(("all", "M"))].reset_index(drop=True)
    return df


# An 2 / An 3 numbers are shape-only placeholders (slide images for these two
# weren't legible) — series names + column shape are confirmed, values are not.
_YEAR_BREAKDOWN = {
    1: dict(serie=["L-A1-S1-CA", "L-A1-S1-CB", "L-A1-S1-CC", "L-A1-S1-CD"],
            proc_completare=[28.75, 19.24, 22.32, 21.72], evaluare=[4.02, 3.89, 4.10, 4.36]),
    2: dict(serie=["L-A2-S1-CA", "L-A2-S1-CB", "L-A2-S1-CC", "L-A2-S1-CD"],  # placeholder values
            proc_completare=[24.10, 21.30, 19.80, 26.40], evaluare=[4.05, 3.95, 4.15, 4.20]),
    3: dict(serie=["L-A3-S1-CA", "L-A3-S1-CB", "L-A3-S1-CC", "L-A3-S1-CD"],  # placeholder values
            proc_completare=[17.20, 20.10, 18.90, 19.50], evaluare=[3.98, 4.05, 4.01, 4.12]),
}


def get_year_breakdown(an, ciclu="L"):
    """columns: serie, proc_completare, evaluare  (slides 7-9, 'An 1'/'An 2'/'An 3')"""
    d = _YEAR_BREAKDOWN[an]
    return pd.DataFrame(d)


_TOP_COURSES = pd.DataFrame([
    dict(curs="03-ACS-L-CTI-A1-S1-LS1E-CC", prof="Maria Liana CIUCEA", num_feedback=15, proc_feedback=11.36, num_utilizatori=132, evaluare_curs=5.00),
    dict(curs="03-ACS-M-CTI-A1-S1-BPDA-SCPD", prof="Costin CARABAS", num_feedback=6, proc_feedback=14.63, num_utilizatori=41, evaluare_curs=5.00),
    dict(curs="03-ACS-M-CTI-A1-S1-STS-G", prof="Emil Ioan SLUSANSCHI", num_feedback=14, proc_feedback=18.18, num_utilizatori=77, evaluare_curs=5.00),
    dict(curs="03-ACS-M-CTI-A2-S1-SAIOT-SSA", prof="Alexandru RADOVICI", num_feedback=7, proc_feedback=10.45, num_utilizatori=67, evaluare_curs=5.00),
    dict(curs="03-ACS-L-CTI-Calculatoare-A1-S1-IF", prof="Paula Pompilia TOMI", num_feedback=16, proc_feedback=19.75, num_utilizatori=81, evaluare_curs=4.94),
    dict(curs="03-ACS-L-CTI-A1-S1-LS1E-CA", prof="Daniela TANASE", num_feedback=13, proc_feedback=10.08, num_utilizatori=129, evaluare_curs=4.92),
    dict(curs="03-ACS-L-CTI-Calculatoare-A1-S1-TC", prof="Adriana Beatrice BALGIU", num_feedback=11, proc_feedback=7.53, num_utilizatori=146, evaluare_curs=4.91),
    dict(curs="03-ACS-M-CTI-A1-S1-PET-SRIC", prof="Razvan Victor RUGHINIS", num_feedback=10, proc_feedback=12.82, num_utilizatori=78, evaluare_curs=4.90),
    dict(curs="03-ACS-M-CTI-A1-S1-IPG-GMRV", prof="Andrei-Cristian LAMBRU", num_feedback=9, proc_feedback=14.29, num_utilizatori=63, evaluare_curs=4.89),
    dict(curs="03-ACS-L-CTI-A1-S1-LS1E-CD", prof="Daniela TANASE", num_feedback=23, proc_feedback=17.16, num_utilizatori=134, evaluare_curs=4.87),
])


def get_top_courses(order_by="evaluare_curs", ciclu=None, limit=10):
    """columns: curs, prof, num_feedback, proc_feedback, num_utilizatori, evaluare_curs
    Applies the deck's fixed selection threshold internally: curs >=7% & >=3 feedback-uri.
    """
    df = _TOP_COURSES.copy()
    df = df[(df["proc_feedback"] >= 7) & (df["num_feedback"] >= 3)]
    if ciclu == "L":
        df = df[df["curs"].str.contains("-L-")]
    elif ciclu == "M":
        df = df[df["curs"].str.contains("-M-")]
    return df.sort_values(order_by, ascending=False).head(limit).reset_index(drop=True)


_TOP_TITULARI = pd.DataFrame([
    dict(persoana="Daniela TANASE", num_cursuri=2, num_feedback=36, proc_feedback=13.69, num_utilizatori=263, evaluare_curs=4.89, evaluare_prof=5.00),
    dict(persoana="Maria Liana CIUCEA", num_cursuri=1, num_feedback=15, proc_feedback=11.36, num_utilizatori=132, evaluare_curs=5.00, evaluare_prof=5.00),
    dict(persoana="Paula Pompilia TOMI", num_cursuri=2, num_feedback=31, proc_feedback=14.90, num_utilizatori=208, evaluare_curs=4.81, evaluare_prof=4.99),
    dict(persoana="Victor Cristian PALEA", num_cursuri=1, num_feedback=17, proc_feedback=14.41, num_utilizatori=118, evaluare_curs=4.76, evaluare_prof=4.99),
    dict(persoana="Mihnea Cosmin MURARU", num_cursuri=2, num_feedback=25, proc_feedback=12.20, num_utilizatori=205, evaluare_curs=4.72, evaluare_prof=4.97),
    dict(persoana="Raluca Roxana PURNICHESCU-PURTAN", num_cursuri=1, num_feedback=48, proc_feedback=24.87, num_utilizatori=193, evaluare_curs=4.77, evaluare_prof=4.95),
    dict(persoana="Irina Georgiana MOCANU", num_cursuri=5, num_feedback=53, proc_feedback=10.27, num_utilizatori=516, evaluare_curs=4.64, evaluare_prof=4.89),
    dict(persoana="Emil Ioan SLUSANSCHI", num_cursuri=3, num_feedback=54, proc_feedback=17.03, num_utilizatori=317, evaluare_curs=4.61, evaluare_prof=4.88),
    dict(persoana="Radu Ioan CIOBANU", num_cursuri=2, num_feedback=35, proc_feedback=16.91, num_utilizatori=207, evaluare_curs=4.28, evaluare_prof=4.82),
    dict(persoana="Dumitru-Cristian TRANCA", num_cursuri=1, num_feedback=111, proc_feedback=81.62, num_utilizatori=136, evaluare_curs=4.58, evaluare_prof=4.82),
])


def get_top_titulari(order_by="evaluare_prof", limit=10):
    """columns: persoana, num_cursuri, num_feedback, proc_feedback, num_utilizatori, evaluare_curs, evaluare_prof
    Applies the deck's fixed selection threshold internally: titular avg >=7% & >=15 feedback-uri.
    """
    df = _TOP_TITULARI.copy()
    df = df[(df["proc_feedback"] >= 7) & (df["num_feedback"] >= 15)]
    return df.sort_values(order_by, ascending=False).head(limit).reset_index(drop=True)


_TOP_ASISTENTI = pd.DataFrame([
    dict(persoana="Teodora STROE", num_feedback=12, evaluare_curs=4.58, evaluare_prof=5.00),
    dict(persoana="Teodora-Daniela CHICIOREANU", num_feedback=30, evaluare_curs=4.80, evaluare_prof=4.98),
    dict(persoana="Catalin Marius DUTA", num_feedback=13, evaluare_curs=4.92, evaluare_prof=4.98),
    dict(persoana="Laura Cristina DRAGOMIR", num_feedback=11, evaluare_curs=3.91, evaluare_prof=4.98),
    dict(persoana="Bianca POPA", num_feedback=33, evaluare_curs=4.73, evaluare_prof=4.98),
    dict(persoana="Vlad Matei DRAGHICI", num_feedback=36, evaluare_curs=4.56, evaluare_prof=4.97),
    dict(persoana="Catalin-Mihail CHIRU", num_feedback=23, evaluare_curs=4.74, evaluare_prof=4.97),
    dict(persoana="Alexandra-Ana-Maria ION", num_feedback=37, evaluare_curs=4.11, evaluare_prof=4.96),
    dict(persoana="Giorgiana Violeta VLASCEANU", num_feedback=30, evaluare_curs=4.67, evaluare_prof=4.96),
    dict(persoana="Matei BELCIUG", num_feedback=17, evaluare_curs=4.71, evaluare_prof=4.96),
])


def get_top_asistenti(order_by="evaluare_prof", limit=10):
    """columns: persoana, num_feedback, evaluare_curs, evaluare_prof
    Applies the deck's fixed selection threshold internally: asistent >=10 feedback-uri.
    """
    df = _TOP_ASISTENTI.copy()
    df = df[df["num_feedback"] >= 10]
    return df.sort_values(order_by, ascending=False).head(limit).reset_index(drop=True)


# Asistenti score distribution is a shape-only placeholder (slide 19 image wasn't
# read) — band structure (4-5/3-4/2-3/1-2) is confirmed from slides 17-18.
_SCORE_DIST = {
    "curs":     [("4-5", 69, 65.1), ("3-4", 30, 28.3), ("2-3", 5, 4.7), ("1-2", 2, 1.9)],
    "titular":  [("4-5", 48, 80.0), ("3-4", 11, 18.3), ("2-3", 1, 1.7), ("1-2", 0, 0.0)],
    "asistent": [("4-5", 22, 73.3), ("3-4", 7, 23.3), ("2-3", 1, 3.3), ("1-2", 0, 0.0)],  # placeholder
}


def get_score_distribution(entitate):
    """columns: banda, num, pct  (slides 17-19, entitate in {'curs','titular','asistent'})"""
    rows = _SCORE_DIST[entitate]
    return pd.DataFrame(rows, columns=["banda", "num", "pct"])
