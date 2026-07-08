"""Deck-sourced MOCK aggregates for the report pages -- read this before trusting a number.

WHAT THIS IS. Hand-transcribed aggregates from the coordinator's reference deck
(ACS, ~2025-2026 sem1, mostly CTI). It backs the six report pages -- Sumar's
year-over-year table, Completare, Pe ani, the three Top-10s, Evaluare pe zone --
through the get_* functions below. Every one of those pages carries a "date
demonstrative" badge in the UI (templates/_chips.html) *because* these numbers are
illustrative, not measured.

REAL NAMES, DECK NUMBERS. Some rows carry real professor names (they were legible
on the slides) next to deck/placeholder scores. Fine inside the project repo and
badged as demonstrative; sanitize only if this ever goes truly public. A few series
are shape-only placeholders where a slide wasn't legible -- shape is right, values
are not.

HOW IT GETS REPLACED (and how it does NOT). Separate from the taxonomy layer. The
real STRUCTURE (courses, cascade, offer counts) already comes from taxonomy.py;
per-course scores on the DETAIL page swap in via taxonomy._load_content once the
feedback_contents/ + users/ export arrives. These DECK AGGREGATES (summary / top-10
/ zone) are a different, later swap: they need the pipeline's already-processed CSVs
(processed/entire/, sep-processed/{cti,is}/average/, ...), NOT this file and NOT a
DB/SQL. When those land, replace each function BODY below with a read of those CSVs,
keeping the SAME columns -- queries.py signatures never change.

Only queries.py imports this -- never app.py or the templates.
"""

import pandas as pd

_YEARS = [
    "2018-2019",
    "2019-2020",
    "2020-2021",
    "2021-2022",
    "2022-2023 sem1",
    "2022-2023",
    "2023-2024 sem1",
    "2024-2025 sem1",
    "2025-2026 sem1",
]

_SUMMARY_RAW = {
    "total": dict(
        num_feedback=[4239, 5866, 8119, 5386, 3040, 4880, 3649, 3429, 3195],
        proc_completare=[21.87, 24.04, 25.42, 18.80, 22.82, 20.51, 21.88, 21.36, 20.53],
        num_cursuri=[138, 173, 266, 215, 103, 176, 139, 129, 104],
        evaluare=[3.74, 3.80, 3.92, 4.03, 4.02, 3.97, 4.07, 4.16, 4.13],
    ),
    "licenta": dict(
        num_feedback=[4087, 5541, 7412, 4936, 2829, 4577, 3290, 2991, 2865],
        proc_completare=[22.27, 24.38, 26.54, 19.17, 23.41, 21.01, 22.07, 22.01, 20.86],
        num_cursuri=[118, 137, 180, 165, 77, 136, 103, 91, 85],
        evaluare=[3.75, 3.79, 3.90, 4.00, 3.99, 3.94, 4.05, 4.14, 4.11],
    ),
    "masterat": dict(
        num_feedback=[152, 325, 707, 430, 211, 303, 359, 438, 330],
        proc_completare=[14.73, 19.43, 17.58, 15.39, 17.04, 15.11, 20.29, 17.18, 16.48],
        num_cursuri=[20, 36, 86, 50, 26, 40, 36, 38, 19],
        evaluare=[3.49, 4.01, 4.11, 4.31, 4.47, 4.39, 4.26, 4.28, 4.32],
    ),
}


# _SUMMARY_RAW is CTI-only (see module docstring -- deck was CTI, 2025-2026 sem1).
# IS split below is SYNTHETIC (no real IS numbers exist yet): a fixed 0.6 scale on
# volume metrics, same rates -- illustrative only, replace with real per-track
# numbers once the CSV pipeline actually breaks summary out by track.
_IS_SCALE = 0.6


def get_summary(nivel=None, track=None):
    """columns: an_universitar, nivel, num_feedback, proc_completare, num_cursuri, evaluare
    track in {None, "CTI", "IS"} -- None/"CTI" return the deck's real numbers;
    "IS" is a synthetic scaled placeholder (see _IS_SCALE above).
    """
    rows = []
    for lvl, d in _SUMMARY_RAW.items():
        if nivel is not None and lvl != nivel:
            continue
        for i, an in enumerate(_YEARS):
            num_feedback = d["num_feedback"][i]
            num_cursuri = d["num_cursuri"][i]
            if track == "IS":
                num_feedback = round(num_feedback * _IS_SCALE)
                num_cursuri = round(num_cursuri * _IS_SCALE)
            rows.append(
                {
                    "an_universitar": an,
                    "nivel": lvl,
                    "num_feedback": num_feedback,
                    "proc_completare": d["proc_completare"][i],
                    "num_cursuri": num_cursuri,
                    "evaluare": d["evaluare"][i],
                }
            )
    return pd.DataFrame(rows)


def get_course_coverage():
    """columns: categorie, num_cursuri, pct  (slide 4 — 'Cursuri cu feedback > 7%')"""
    return pd.DataFrame(
        [
            {"categorie": "cu procentaj > prag", "num_cursuri": 104, "pct": 43.9},
            {"categorie": "fara procentaj", "num_cursuri": 78, "pct": 32.9},
            {"categorie": "zero", "num_cursuri": 55, "pct": 23.2},
        ]
    )


_PERIOD_BUCKETS = [
    "all",
    "L",
    "L-A1",
    "L-A1-S1",
    "L-A2",
    "L-A2-S1",
    "L-A3",
    "L-A3-S1",
    "L-A4",
    "L-A4-S1",
    "M",
    "M-A1",
    "M-A1-S1",
    "M-A2",
    "M-A2-S1",
]
_PERIOD_PROC = [
    20.53,
    20.86,
    20.12,
    20.12,
    27.74,
    27.74,
    18.62,
    18.62,
    15.01,
    15.01,
    16.48,
    19.11,
    19.11,
    11.39,
    11.39,
]
_PERIOD_EVAL = [4.13, 4.19, 4.20, 4.20, 4.10, 4.10, 4.01, 4.01, 4.13, 4.13, 4.35, 4.43, 4.43, 4.10, 4.10]


def get_period_breakdown(ciclu=None, semestru=None):
    """columns: bucket, proc_completare, evaluare  (slides 5+6, same x-axis)
    semestru in {None, "S1", "S2"} -- KNOWN GAP: all current buckets are S1-only
    (or semester-agnostic aggregates like "L"/"all"); semestru="S2" returns an
    empty DataFrame until real per-semester-2 data exists. Don't treat the empty
    result as a bug -- it's an honest "we don't have this yet", same pattern as
    the an=4 gap in get_year_breakdown.
    """
    df = pd.DataFrame({"bucket": _PERIOD_BUCKETS, "proc_completare": _PERIOD_PROC, "evaluare": _PERIOD_EVAL})
    if ciclu == "L":
        df = df[df["bucket"].str.startswith(("all", "L"))]
    elif ciclu == "M":
        df = df[df["bucket"].str.startswith(("all", "M"))]
    if semestru == "S1":
        df = df[df["bucket"].str.endswith("-S1")]
    elif semestru == "S2":
        df = df[df["bucket"].str.endswith("-S2")]
    return df.reset_index(drop=True)


# An 2 / An 3 numbers are shape-only placeholders (slide images for these two
# weren't legible) — series names + column shape are confirmed, values are not.
_YEAR_BREAKDOWN = {
    1: dict(
        serie=["L-A1-S1-CA", "L-A1-S1-CB", "L-A1-S1-CC", "L-A1-S1-CD"],
        proc_completare=[28.75, 19.24, 22.32, 21.72],
        evaluare=[4.02, 3.89, 4.10, 4.36],
    ),
    2: dict(
        serie=["L-A2-S1-CA", "L-A2-S1-CB", "L-A2-S1-CC", "L-A2-S1-CD"],  # placeholder values
        proc_completare=[24.10, 21.30, 19.80, 26.40],
        evaluare=[4.05, 3.95, 4.15, 4.20],
    ),
    3: dict(
        serie=["L-A3-S1-CA", "L-A3-S1-CB", "L-A3-S1-CC", "L-A3-S1-CD"],  # placeholder values
        proc_completare=[17.20, 20.10, 18.90, 19.50],
        evaluare=[3.98, 4.05, 4.01, 4.12],
    ),
}


def get_year_breakdown(an, ciclu="L"):
    """columns: serie, proc_completare, evaluare  (slides 7-9, 'An 1'/'An 2'/'An 3')"""
    d = _YEAR_BREAKDOWN[an]
    return pd.DataFrame(d)


_TOP_COURSES = pd.DataFrame(
    [
        dict(
            curs="03-ACS-L-CTI-A1-S1-LS1E-CC",
            prof="Maria Liana CIUCEA",
            num_feedback=15,
            proc_feedback=11.36,
            num_utilizatori=132,
            evaluare_curs=5.00,
        ),
        dict(
            curs="03-ACS-M-CTI-A1-S1-BPDA-SCPD",
            prof="Costin CARABAS",
            num_feedback=6,
            proc_feedback=14.63,
            num_utilizatori=41,
            evaluare_curs=5.00,
        ),
        dict(
            curs="03-ACS-M-CTI-A1-S1-STS-G",
            prof="Emil Ioan SLUSANSCHI",
            num_feedback=14,
            proc_feedback=18.18,
            num_utilizatori=77,
            evaluare_curs=5.00,
        ),
        dict(
            curs="03-ACS-M-CTI-A2-S1-SAIOT-SSA",
            prof="Alexandru RADOVICI",
            num_feedback=7,
            proc_feedback=10.45,
            num_utilizatori=67,
            evaluare_curs=5.00,
        ),
        dict(
            curs="03-ACS-L-CTI-Calculatoare-A1-S1-IF",
            prof="Paula Pompilia TOMI",
            num_feedback=16,
            proc_feedback=19.75,
            num_utilizatori=81,
            evaluare_curs=4.94,
        ),
        dict(
            curs="03-ACS-L-CTI-A1-S1-LS1E-CA",
            prof="Daniela TANASE",
            num_feedback=13,
            proc_feedback=10.08,
            num_utilizatori=129,
            evaluare_curs=4.92,
        ),
        dict(
            curs="03-ACS-L-CTI-Calculatoare-A1-S1-TC",
            prof="Adriana Beatrice BALGIU",
            num_feedback=11,
            proc_feedback=7.53,
            num_utilizatori=146,
            evaluare_curs=4.91,
        ),
        dict(
            curs="03-ACS-M-CTI-A1-S1-PET-SRIC",
            prof="Razvan Victor RUGHINIS",
            num_feedback=10,
            proc_feedback=12.82,
            num_utilizatori=78,
            evaluare_curs=4.90,
        ),
        dict(
            curs="03-ACS-M-CTI-A1-S1-IPG-GMRV",
            prof="Andrei-Cristian LAMBRU",
            num_feedback=9,
            proc_feedback=14.29,
            num_utilizatori=63,
            evaluare_curs=4.89,
        ),
        dict(
            curs="03-ACS-L-CTI-A1-S1-LS1E-CD",
            prof="Daniela TANASE",
            num_feedback=23,
            proc_feedback=17.16,
            num_utilizatori=134,
            evaluare_curs=4.87,
        ),
        # IS/semestru-2 entries added for track/semestru filtering -- illustrative,
        # not from the deck (the deck's slides were CTI/sem1-only, see module docstring).
        dict(
            curs="03-ACS-L-IS-A1-S1-PSD-CA",
            prof="Bogdan Alexandru URSU",
            num_feedback=18,
            proc_feedback=13.85,
            num_utilizatori=130,
            evaluare_curs=4.80,
        ),
        dict(
            curs="03-ACS-M-IS-A1-S1-SDA-G",
            prof="Elena Simona LOHAN",
            num_feedback=8,
            proc_feedback=11.27,
            num_utilizatori=71,
            evaluare_curs=4.76,
        ),
        dict(
            curs="03-ACS-L-CTI-A1-S2-LS2E-CA",
            prof="Daniela TANASE",
            num_feedback=12,
            proc_feedback=9.60,
            num_utilizatori=125,
            evaluare_curs=4.70,
        ),
    ]
)


def _course_track(curs):
    if "-CTI-" in curs:
        return "CTI"
    if "-IS-" in curs:
        return "IS"
    return None


def _course_semestru(curs):
    if "-S1-" in curs or curs.endswith("-S1"):
        return "S1"
    if "-S2-" in curs or curs.endswith("-S2"):
        return "S2"
    return None


def get_top_courses(order_by="evaluare_curs", ciclu=None, track=None, semestru=None, limit=10):
    """columns: curs, prof, num_feedback, proc_feedback, num_utilizatori, evaluare_curs
    Applies the deck's fixed selection threshold internally: curs >=7% & >=3 feedback-uri.
    track in {None, "CTI", "IS"}; semestru in {None, "S1", "S2"} -- derived from the
    course shortname, same convention analysis/ and the CSV pipeline already use.
    """
    df = _TOP_COURSES.copy()
    df = df[(df["proc_feedback"] >= 7) & (df["num_feedback"] >= 3)]
    if ciclu == "L":
        df = df[df["curs"].str.contains("-L-")]
    elif ciclu == "M":
        df = df[df["curs"].str.contains("-M-")]
    if track:
        df = df[df["curs"].apply(_course_track) == track]
    if semestru:
        df = df[df["curs"].apply(_course_semestru) == semestru]
    return df.sort_values(order_by, ascending=False).head(limit).reset_index(drop=True)


_TOP_TITULARI = pd.DataFrame(
    [
        dict(
            persoana="Daniela TANASE",
            num_cursuri=2,
            num_feedback=36,
            proc_feedback=13.69,
            num_utilizatori=263,
            evaluare_curs=4.89,
            evaluare_prof=5.00,
        ),
        dict(
            persoana="Maria Liana CIUCEA",
            num_cursuri=1,
            num_feedback=15,
            proc_feedback=11.36,
            num_utilizatori=132,
            evaluare_curs=5.00,
            evaluare_prof=5.00,
        ),
        dict(
            persoana="Paula Pompilia TOMI",
            num_cursuri=2,
            num_feedback=31,
            proc_feedback=14.90,
            num_utilizatori=208,
            evaluare_curs=4.81,
            evaluare_prof=4.99,
        ),
        dict(
            persoana="Victor Cristian PALEA",
            num_cursuri=1,
            num_feedback=17,
            proc_feedback=14.41,
            num_utilizatori=118,
            evaluare_curs=4.76,
            evaluare_prof=4.99,
        ),
        dict(
            persoana="Mihnea Cosmin MURARU",
            num_cursuri=2,
            num_feedback=25,
            proc_feedback=12.20,
            num_utilizatori=205,
            evaluare_curs=4.72,
            evaluare_prof=4.97,
        ),
        dict(
            persoana="Raluca Roxana PURNICHESCU-PURTAN",
            num_cursuri=1,
            num_feedback=48,
            proc_feedback=24.87,
            num_utilizatori=193,
            evaluare_curs=4.77,
            evaluare_prof=4.95,
        ),
        dict(
            persoana="Irina Georgiana MOCANU",
            num_cursuri=5,
            num_feedback=53,
            proc_feedback=10.27,
            num_utilizatori=516,
            evaluare_curs=4.64,
            evaluare_prof=4.89,
        ),
        dict(
            persoana="Emil Ioan SLUSANSCHI",
            num_cursuri=3,
            num_feedback=54,
            proc_feedback=17.03,
            num_utilizatori=317,
            evaluare_curs=4.61,
            evaluare_prof=4.88,
        ),
        dict(
            persoana="Radu Ioan CIOBANU",
            num_cursuri=2,
            num_feedback=35,
            proc_feedback=16.91,
            num_utilizatori=207,
            evaluare_curs=4.28,
            evaluare_prof=4.82,
        ),
        dict(
            persoana="Dumitru-Cristian TRANCA",
            num_cursuri=1,
            num_feedback=111,
            proc_feedback=81.62,
            num_utilizatori=136,
            evaluare_curs=4.58,
            evaluare_prof=4.82,
        ),
    ]
)


def get_top_titulari(order_by="evaluare_prof", limit=10):
    """columns: persoana, num_cursuri, num_feedback, proc_feedback, num_utilizatori,
    evaluare_curs, evaluare_prof
    Applies the deck's fixed selection threshold internally: titular avg >=7% & >=15 feedback-uri.
    """
    df = _TOP_TITULARI.copy()
    df = df[(df["proc_feedback"] >= 7) & (df["num_feedback"] >= 15)]
    return df.sort_values(order_by, ascending=False).head(limit).reset_index(drop=True)


_TOP_ASISTENTI = pd.DataFrame(
    [
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
    ]
)


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
    "curs": [("4-5", 69, 65.1), ("3-4", 30, 28.3), ("2-3", 5, 4.7), ("1-2", 2, 1.9)],
    "titular": [("4-5", 48, 80.0), ("3-4", 11, 18.3), ("2-3", 1, 1.7), ("1-2", 0, 0.0)],
    "asistent": [("4-5", 22, 73.3), ("3-4", 7, 23.3), ("2-3", 1, 3.3), ("1-2", 0, 0.0)],  # placeholder
}


def get_score_distribution(entitate):
    """columns: banda, num, pct  (slides 17-19, entitate in {'curs','titular','asistent'})"""
    rows = _SCORE_DIST[entitate]
    return pd.DataFrame(rows, columns=["banda", "num", "pct"])


# Per-question breakdown (Eval gen / Preg. / Expl. clare / Interes / Comport. /
# Indepl. ob.) for a curated set of illustrative courses -- NOT from the deck,
# added later once we confirmed process_feedback.py already computes a
# per-question average (18 columns) per titular/asistent, per course, and just
# never exposed it. Faculty-wide average is a placeholder until real data
# lands (see get_faculty_average).
_COURSE_DETAIL = {
    "03-ACS-L-CTI-A1-S1-LS1E-CC": {
        "denumire": "Programarea Calculatoarelor",
        "num_studenti": 156,
        "serii": ["CA", "CB", "CC", "CD"],
        "cadre": [
            dict(
                nume="Popescu Ion",
                tip="titular",
                num_feedback=49,
                eval_gen=4.61,
                preg=4.95,
                expl_clare=4.59,
                interes=4.71,
                comport=4.98,
                indepl_ob=4.24,
            ),
            dict(
                nume="Ionescu Maria",
                tip="titular",
                num_feedback=22,
                eval_gen=4.50,
                preg=4.90,
                expl_clare=4.60,
                interes=4.75,
                comport=4.95,
                indepl_ob=4.25,
            ),
            dict(
                nume="Georgescu Andrei",
                tip="asistent",
                num_feedback=16,
                eval_gen=4.50,
                preg=4.85,
                expl_clare=4.63,
                interes=4.81,
                comport=4.90,
                indepl_ob=4.31,
            ),
            dict(
                nume="Dumitrescu Elena",
                tip="asistent",
                num_feedback=9,
                eval_gen=4.78,
                preg=4.92,
                expl_clare=4.78,
                interes=4.56,
                comport=4.95,
                indepl_ob=4.22,
            ),
            dict(
                nume="Vasilescu Radu",
                tip="asistent",
                num_feedback=6,
                eval_gen=4.67,
                preg=4.80,
                expl_clare=4.17,
                interes=4.50,
                comport=4.60,
                indepl_ob=3.83,
            ),
            dict(
                nume="Marin Cristina",
                tip="asistent",
                num_feedback=26,
                eval_gen=4.20,
                preg=4.70,
                expl_clare=4.40,
                interes=4.35,
                comport=4.75,
                indepl_ob=4.10,
            ),
        ],
    },
    "03-ACS-L-CTI-A1-S1-LS1E-CA": {
        "denumire": "Structuri de Date și Algoritmi",
        "num_studenti": 149,
        "serii": ["CA", "CB", "CC", "CD"],
        "cadre": [
            dict(
                nume="Daniela Tănase",
                tip="titular",
                num_feedback=41,
                eval_gen=4.72,
                preg=4.90,
                expl_clare=4.68,
                interes=4.66,
                comport=4.93,
                indepl_ob=4.40,
            ),
            dict(
                nume="Andrei-Cristian Lambru",
                tip="asistent",
                num_feedback=19,
                eval_gen=4.55,
                preg=4.80,
                expl_clare=4.52,
                interes=4.60,
                comport=4.88,
                indepl_ob=4.29,
            ),
            dict(
                nume="Bianca Popa",
                tip="asistent",
                num_feedback=23,
                eval_gen=4.38,
                preg=4.71,
                expl_clare=4.45,
                interes=4.30,
                comport=4.70,
                indepl_ob=4.12,
            ),
        ],
    },
}

_FACULTY_AVERAGE = dict(eval_gen=4.42, preg=4.83, expl_clare=4.53, interes=4.61, comport=4.86, indepl_ob=4.16)


def get_course_list():
    """columns: curs, denumire, num_studenti"""
    return pd.DataFrame(
        [
            {"curs": k, "denumire": v["denumire"], "num_studenti": v["num_studenti"]}
            for k, v in _COURSE_DETAIL.items()
        ]
    )


def get_course_series(curs):
    """list of serie codes for a course (e.g. ['CA','CB',...]); [] if unknown."""
    entry = _COURSE_DETAIL.get(curs)
    return list(entry["serii"]) if entry else []


def get_course_detail(curs):
    """columns: nume, tip, num_feedback, eval_gen, preg, expl_clare, interes, comport, indepl_ob"""
    entry = _COURSE_DETAIL.get(curs)
    columns = [
        "nume",
        "tip",
        "num_feedback",
        "eval_gen",
        "preg",
        "expl_clare",
        "interes",
        "comport",
        "indepl_ob",
    ]
    if entry is None:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(entry["cadre"])[columns]


def get_faculty_average():
    """dict: eval_gen, preg, expl_clare, interes, comport, indepl_ob"""
    return dict(_FACULTY_AVERAGE)
