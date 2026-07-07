"""Contract test: every queries.py function must return a DataFrame with
exactly the documented column set. This is what protects pages/*.py from
silently breaking when queries.py's internals change (mocks -> real CSV ->
eventually DB) -- the columns below must stay stable regardless of backend.
"""

import pandas as pd

import queries


def _assert_columns(df, expected):
    assert isinstance(df, pd.DataFrame)
    assert set(df.columns) == set(expected), (
        f"column mismatch: got {sorted(df.columns)}, want {sorted(expected)}"
    )


def test_get_summary():
    _assert_columns(
        queries.get_summary(),
        {"an_universitar", "nivel", "num_feedback", "proc_completare", "num_cursuri", "evaluare"},
    )
    for nivel in ("total", "licenta", "masterat"):
        _assert_columns(
            queries.get_summary(nivel=nivel),
            {"an_universitar", "nivel", "num_feedback", "proc_completare", "num_cursuri", "evaluare"},
        )


def test_get_course_coverage():
    _assert_columns(queries.get_course_coverage(), {"categorie", "num_cursuri", "pct"})


def test_get_period_breakdown():
    for ciclu in (None, "L", "M"):
        _assert_columns(
            queries.get_period_breakdown(ciclu=ciclu),
            {"bucket", "proc_completare", "evaluare"},
        )


def test_get_year_breakdown():
    for an in (1, 2, 3):
        _assert_columns(
            queries.get_year_breakdown(an),
            {"serie", "proc_completare", "evaluare"},
        )


def test_get_top_courses():
    for ciclu in (None, "L", "M"):
        for order_by in ("evaluare_curs", "proc_feedback"):
            _assert_columns(
                queries.get_top_courses(order_by=order_by, ciclu=ciclu),
                {"curs", "prof", "num_feedback", "proc_feedback", "num_utilizatori", "evaluare_curs"},
            )


def test_get_top_titulari():
    for order_by in ("evaluare_prof", "evaluare_curs", "proc_feedback"):
        _assert_columns(
            queries.get_top_titulari(order_by=order_by),
            {
                "persoana",
                "num_cursuri",
                "num_feedback",
                "proc_feedback",
                "num_utilizatori",
                "evaluare_curs",
                "evaluare_prof",
            },
        )


def test_get_top_asistenti():
    for order_by in ("evaluare_prof", "evaluare_curs"):
        _assert_columns(
            queries.get_top_asistenti(order_by=order_by),
            {"persoana", "num_feedback", "evaluare_curs", "evaluare_prof"},
        )


def test_get_score_distribution():
    for entitate in ("curs", "titular", "asistent"):
        _assert_columns(
            queries.get_score_distribution(entitate),
            {"banda", "num", "pct"},
        )
