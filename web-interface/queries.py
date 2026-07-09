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

import aggregates
import mocks
import taxonomy


def get_summary(nivel=None, track=None):
    """columns: an_universitar, nivel, num_feedback, proc_completare, num_cursuri, evaluare
    nivel in {None, "total", "licenta", "masterat"}; None returns all three per an.
    track in {None, "CTI", "IS"} -- None/"CTI" are the deck's real numbers; "IS"
    is a synthetic scaled placeholder (see mocks._IS_SCALE) until real per-track
    data lands.
    Stays on the deck mock: a 9-year year-over-year history, not recomputable from
    the single year of structure the taxonomy holds (the other deck views moved to
    aggregates.py).
    """
    return mocks.get_summary(nivel=nivel, track=track)


def get_course_coverage():
    """columns: categorie, num_cursuri, pct
    Stays on the deck mock: it counts courses with NO feedback, which the
    feedback-scoped taxonomy structurally excludes -- not recomputable here.
    """
    return mocks.get_course_coverage()


def get_period_breakdown(ciclu=None, semestru=None):
    """columns: bucket, proc_completare, evaluare
    ciclu in {None, "L", "M"}. semestru in {None, "S1", "S2"} -- computed from the
    real category tree, so S2 now returns data where S2 courses exist (it was an
    empty gap only while this came from the S1-only deck).
    """
    return aggregates.get_period_breakdown(ciclu=ciclu, semestru=semestru)


def get_year_breakdown(an, ciclu="L"):
    """columns: serie, proc_completare, evaluare
    an in {1, 2, 3, 4} (an de studiu); years with no data return an empty frame.
    """
    return aggregates.get_year_breakdown(an, ciclu=ciclu)


def get_top_courses(order_by="evaluare_curs", ciclu=None, track=None, semestru=None, limit=10):
    """columns: curs, prof, num_feedback, proc_feedback, num_utilizatori, evaluare_curs
    order_by in {"evaluare_curs", "proc_feedback"}. ciclu in {None, "L", "M"}.
    track in {None, "CTI", "IS"}; semestru in {None, "S1", "S2"} -- read from the
    taxonomy dims (domeniu / sem), no shortname parsing.
    """
    return aggregates.get_top_courses(
        order_by=order_by, ciclu=ciclu, track=track, semestru=semestru, limit=limit
    )


def get_top_titulari(order_by="evaluare_prof", limit=10):
    """columns: persoana, num_cursuri, num_feedback, proc_feedback, num_utilizatori,
    evaluare_curs, evaluare_prof
    order_by in {"evaluare_prof", "evaluare_curs", "proc_feedback"}.
    """
    return aggregates.get_top_titulari(order_by=order_by, limit=limit)


def get_top_asistenti(order_by="evaluare_prof", limit=10):
    """columns: persoana, num_feedback, evaluare_curs, evaluare_prof
    order_by in {"evaluare_prof", "evaluare_curs"}.
    """
    return aggregates.get_top_asistenti(order_by=order_by, limit=limit)


def get_score_distribution(entitate):
    """columns: banda, num, pct
    entitate in {"curs", "titular", "asistent"}.
    """
    return aggregates.get_score_distribution(entitate)


# ---------------------------------------------------------------------------
# Taxonomy / cascade layer (the coupled filter model). Everything below derives
# from taxonomy.py -- the real Moodle category tree -- so the UI can never build
# a contradictory scope. Structural filter order:
#   ciclu -> domeniu -> specializare (optional) -> an -> sem -> serie -> curs.
# See taxonomy.py.
# ---------------------------------------------------------------------------


def get_academic_years():
    """list of academic-year labels (temporal axis), e.g. ["2021-2022", ...]."""
    return taxonomy.academic_years()


def get_filter_options(selection):
    """ordered dict: structural dim -> [{value, label}], each restricted to what
    is reachable given the upstream selections (contradiction-proof cascade)."""
    return taxonomy.get_filter_options(selection)


def get_struct_order():
    """the structural cascade order:
    ['ciclu','domeniu','specializare','an','sem','serie','curs']."""
    return taxonomy.struct_order()


def get_scope_courses(selection):
    """columns-as-dicts: curs, denumire, num_studenti -- courses in the current
    scope (offerings matching the structural selection)."""
    return taxonomy.scope_courses(selection)


def get_course_list():
    """columns: curs, denumire, num_studenti -- every course in the taxonomy
    (unscoped). Kept for callers that want the full list."""
    return taxonomy.scope_courses({})


def get_course_series(curs):
    """list of serie codes for a course (e.g. ["CA","CB",...]); [] if unknown."""
    return taxonomy.course_series(curs)


def get_course_detail(curs, an_universitar="2025-2026"):
    """columns: nume, tip, num_feedback, eval_gen, preg, expl_clare, interes,
    comport, indepl_ob -- per-cadru per-question rows for one course in one
    academic year. These per-question averages are exactly what
    process_feedback.py already computes per cadru, per course (18 questions);
    we surface a curated 6 of them."""
    return taxonomy.course_detail(curs, an_universitar)


def get_course_students(curs, an_universitar="2025-2026"):
    """number of enrolled students for a course in a year (denominator for
    completion %)."""
    return taxonomy.course_students(curs, an_universitar)


def get_course_responses(curs, an_universitar="2025-2026"):
    """unique student submissions for a course that year (<= enrolled) -- the
    correct numerator for completion %, not the sum of per-teacher counts."""
    return taxonomy.course_responses(curs, an_universitar)


def get_faculty_average(an_universitar="2025-2026"):
    """dict: eval_gen, preg, expl_clare, interes, comport, indepl_ob -- mean
    per-question score across every cadru of every course that year. Reference
    for 'cadru selectat vs. media facultății'."""
    return taxonomy.faculty_average(an_universitar)


def get_taxonomy_issues():
    """list of real-data sanity issues (feedback courses that don't resolve to
    ciclu+domeniu+an, or lack a semester). Empty == everything scoped resolved."""
    return taxonomy.consistency_issues()


def get_taxonomy_tree():
    """the full valid space as a nested tree, for eyeballing every interaction:
    ciclu -> domeniu -> specializare -> an -> sem -> [courses]."""
    return taxonomy.tree()


def get_data_source():
    """'real' (pickle export present) or 'synthetic' (fallback)."""
    return taxonomy.data_source()


def get_content_is_synthetic():
    """True while scores/teacher names are placeholder (no content export yet)."""
    return taxonomy.content_is_synthetic()


def get_offer_structure():
    """real course counts (no scores) for the loaded year -- see taxonomy.offer_structure."""
    return taxonomy.offer_structure()
