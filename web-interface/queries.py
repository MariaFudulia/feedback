"""The data contract. This is the ONLY module pages/ and app.py may import from.

Right now every function delegates to mocks.py. Coleg A's job is to replace
each function body with a real SQL query against moodle_analytics.db (or the
local db/fixture.db before PR #3 merges) — keeping the exact signature and
returned-DataFrame columns documented in each docstring. Nothing outside this
file should need to change when that swap happens.

Selection thresholds (fixed by the coordinator's deck — do not make these
configurable in the UI):
    curs      >= 7%  proc_feedback  AND >= 3  feedback-uri
    titular   >= 7%  proc_feedback (mediu pe cursurile unde e titular) AND >= 15 feedback-uri
    asistent  >= 10  feedback-uri
"""

import mocks


def get_summary(nivel=None):
    """columns: an_universitar, nivel, num_feedback, proc_completare, num_cursuri, evaluare
    nivel in {None, "total", "licenta", "masterat"}; None returns all three per an.
    """
    return mocks.get_summary(nivel=nivel)


def get_course_coverage():
    """columns: categorie, num_cursuri, pct"""
    return mocks.get_course_coverage()


def get_period_breakdown(ciclu=None):
    """columns: bucket, proc_completare, evaluare
    ciclu in {None, "L", "M"}.
    """
    return mocks.get_period_breakdown(ciclu=ciclu)


def get_year_breakdown(an, ciclu="L"):
    """columns: serie, proc_completare, evaluare
    an in {1, 2, 3, 4} (an de studiu).
    """
    return mocks.get_year_breakdown(an, ciclu=ciclu)


def get_top_courses(order_by="evaluare_curs", ciclu=None, limit=10):
    """columns: curs, prof, num_feedback, proc_feedback, num_utilizatori, evaluare_curs
    order_by in {"evaluare_curs", "proc_feedback"}. ciclu in {None, "L", "M"}.
    """
    return mocks.get_top_courses(order_by=order_by, ciclu=ciclu, limit=limit)


def get_top_titulari(order_by="evaluare_prof", limit=10):
    """columns: persoana, num_cursuri, num_feedback, proc_feedback, num_utilizatori,
    evaluare_curs, evaluare_prof
    order_by in {"evaluare_prof", "evaluare_curs", "proc_feedback"}.
    """
    return mocks.get_top_titulari(order_by=order_by, limit=limit)


def get_top_asistenti(order_by="evaluare_prof", limit=10):
    """columns: persoana, num_feedback, evaluare_curs, evaluare_prof
    order_by in {"evaluare_prof", "evaluare_curs"}.
    """
    return mocks.get_top_asistenti(order_by=order_by, limit=limit)


def get_score_distribution(entitate):
    """columns: banda, num, pct
    entitate in {"curs", "titular", "asistent"}.
    """
    return mocks.get_score_distribution(entitate)
