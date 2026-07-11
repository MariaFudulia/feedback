"""Contract test: every queries.py function must return a DataFrame with
exactly the documented column set. This is what protects pages/*.py from
silently breaking when queries.py's internals change (mocks -> real CSV ->
eventually DB) -- the columns below must stay stable regardless of backend.

The synthetic taxonomy is forced globally by tests/conftest.py, so the cascade
tests never depend on the private pickle export.
"""

import pandas as pd

import queries
import taxonomy


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
        for track in (None, "CTI", "IS"):
            _assert_columns(
                queries.get_summary(nivel=nivel, track=track),
                {"an_universitar", "nivel", "num_feedback", "proc_completare", "num_cursuri", "evaluare"},
            )


def test_get_summary_track_is_scaled_not_identical():
    cti = queries.get_summary(nivel="total", track="CTI")
    is_ = queries.get_summary(nivel="total", track="IS")
    assert not cti["num_feedback"].equals(is_["num_feedback"]), (
        "IS track should differ from CTI (synthetic scale)"
    )


def test_get_course_coverage():
    _assert_columns(queries.get_course_coverage(), {"categorie", "num_cursuri", "pct"})


def test_get_period_breakdown():
    for ciclu in (None, "L", "M"):
        for semestru in (None, "S1", "S2"):
            _assert_columns(
                queries.get_period_breakdown(ciclu=ciclu, semestru=semestru),
                {"bucket", "proc_completare", "evaluare"},
            )


def test_get_period_breakdown_semestru_s2_is_computed():
    # S2 is now recomputed from the real category tree (no longer the S1-only deck's empty gap)
    df = queries.get_period_breakdown(semestru="S2")
    _assert_columns(df, {"bucket", "proc_completare", "evaluare"})
    assert all(b.endswith("-S2") for b in df["bucket"])


def test_get_year_breakdown():
    for an in (1, 2, 3):
        _assert_columns(
            queries.get_year_breakdown(an),
            {"serie", "proc_completare", "evaluare"},
        )


def test_get_top_courses():
    for ciclu in (None, "L", "M"):
        for track in (None, "CTI", "IS"):
            for semestru in (None, "S1", "S2"):
                for order_by in ("evaluare_curs", "proc_feedback"):
                    _assert_columns(
                        queries.get_top_courses(
                            order_by=order_by, ciclu=ciclu, track=track, semestru=semestru
                        ),
                        {"curs", "prof", "num_feedback", "proc_feedback", "num_utilizatori", "evaluare_curs"},
                    )


def test_get_top_courses_track_filters_correctly():
    cti_only = queries.get_top_courses(track="CTI", limit=100)
    is_only = queries.get_top_courses(track="IS", limit=100)
    assert not cti_only.empty and not is_only.empty
    assert all("-CTI-" in c for c in cti_only["curs"])
    assert all("-IS-" in c for c in is_only["curs"])


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


# ---- taxonomy / cascade layer (list-of-dicts, not DataFrames) ----

_DETAIL_KEYS = {
    "nume",
    "tip",
    "num_feedback",
    "eval_gen",
    "preg",
    "expl_clare",
    "interes",
    "comport",
    "indepl_ob",
}


def test_get_course_list():
    courses = queries.get_course_list()
    assert isinstance(courses, list) and courses
    assert set(courses[0].keys()) == {"curs", "denumire", "num_studenti"}


def test_get_course_series():
    curs = queries.get_course_list()[0]["curs"]
    series = queries.get_course_series(curs)
    assert isinstance(series, list) and all(isinstance(s, str) for s in series)
    assert queries.get_course_series("nu-exista") == []


def test_get_course_detail():
    curs = queries.get_course_list()[0]["curs"]
    rows = queries.get_course_detail(curs)
    assert isinstance(rows, list) and rows
    for r in rows:
        assert set(r.keys()) == _DETAIL_KEYS
    assert queries.get_course_detail("nu-exista") == []  # unknown course -> empty, not an error


def test_get_faculty_average():
    avg = queries.get_faculty_average()
    assert isinstance(avg, dict)
    assert set(avg.keys()) == {"eval_gen", "preg", "expl_clare", "interes", "comport", "indepl_ob"}


# ---- the coupled cascade: contradictions must be impossible to reach ----


def _values(opts):
    return {o["value"] for o in opts}


def test_using_synthetic_fallback():
    # tests must run against the deterministic fallback, not a dev's real pickles
    assert queries.get_data_source() == "synthetic"


def test_taxonomy_resolves_cleanly():
    # on the synthetic dataset every offering resolves; on real data this lists
    # only the handful of feedback courses that don't map to ciclu+domeniu+an.
    assert queries.get_taxonomy_issues() == []


def test_cascade_master_has_no_year_3_or_4():
    assert _values(queries.get_filter_options({"ciclu": "M"})["an"]) <= {"1", "2"}


def test_cascade_licenta_offers_year_4():
    assert "4" in _values(queries.get_filter_options({"ciclu": "L"})["an"])


def test_cascade_real_domains_under_licenta():
    # domeniu (not a fabricated "AIA"-as-domain): the real Licență domains are CTI + IS
    opts = queries.get_filter_options({"ciclu": "L"})
    assert {"CTI", "IS"} <= _values(opts["domeniu"])


def test_cascade_specializare_is_optional_per_branch():
    # a branch that has a specializare level exposes it; one that doesn't stays empty
    with_spec = queries.get_filter_options({"ciclu": "L", "domeniu": "IS"})["specializare"]
    without_spec = queries.get_filter_options({"ciclu": "L", "domeniu": "CTI"})["specializare"]
    assert len(with_spec) >= 1
    assert without_spec == []


def test_cascade_domeniu_mixes_specializare_and_direct():
    # real ACS shape: the SAME domeniu can carry both a specializare subtree and
    # courses attached directly to the year. Both must stay reachable -- choosing
    # the specializare narrows, but the direct-on-year courses exist outside it.
    base = {"ciclu": "L", "domeniu": "IS", "an": "1"}
    spec = queries.get_filter_options({"ciclu": "L", "domeniu": "IS"})["specializare"]
    assert spec
    all_courses = {c["curs"] for c in queries.get_scope_courses(base)}
    spec_courses = {c["curs"] for c in queries.get_scope_courses({**base, "specializare": spec[0]["value"]})}
    assert spec_courses and spec_courses < all_courses


def test_cascade_serie_restricts_courses():
    base = {"ciclu": "L", "domeniu": "CTI", "an": "1"}
    serie = queries.get_filter_options(base)["serie"][0]["value"]
    opts = queries.get_filter_options({**base, "serie": serie})
    assert opts["curs"]  # at least one course under that series
    for c in opts["curs"]:
        assert serie in queries.get_course_series(c["value"])


def test_scope_narrows_courses():
    everything = {c["curs"] for c in queries.get_scope_courses({})}
    master_only = {c["curs"] for c in queries.get_scope_courses({"ciclu": "M"})}
    assert master_only and master_only < everything


def test_offer_structure_counts_are_real_and_consistent():
    o = queries.get_offer_structure()
    assert set(o.keys()) >= {"an_universitar", "total_cursuri", "total_instante", "pe_ciclu", "pe_domeniu"}
    # per-ciclu counts must add up to the distinct-course total (no double count)
    assert sum(c["num_cursuri"] for c in o["pe_ciclu"]) == o["total_cursuri"]
    assert sum(d["num_cursuri"] for d in o["pe_domeniu"]) == o["total_cursuri"]
    # instances (with series) are at least as many as distinct courses
    assert o["total_instante"] >= o["total_cursuri"] > 0


def test_content_seam_routes_to_real_content_when_present():
    # The scoring seam: once _load_content returns data, the content functions read it
    # and content_is_synthetic() flips (clearing the "date demonstrative" badge app-wide).
    # Synthetic offerings carry course_id=None, so the fake payload is keyed by None.
    curs = taxonomy.all_offerings()[0]["curs"]
    probe = {
        "nume": "SeamProbe",
        "tip": "titular",
        "num_feedback": 7,
        **{k: 4.5 for k in taxonomy.QUESTION_KEYS},
    }
    saved_generated = taxonomy._CONTENT_GENERATED
    taxonomy._CONTENT = {None: {"responses": 42, "students": 100, "cadre": [probe]}}
    taxonomy._CONTENT_GENERATED = False  # a real export; a GENERATED one keeps the badge on
    try:
        assert taxonomy.content_is_synthetic() is False
        assert taxonomy.course_detail(curs)[0]["nume"] == "SeamProbe"
    finally:
        taxonomy._CONTENT = None
        taxonomy._CONTENT_GENERATED = saved_generated
    assert taxonomy.content_is_synthetic() is True


# ---- the free-text answers ------------------------------------------------

_COMMENT_KEYS = {"intrebare", "comentariu", "sentiment"}
_GATE_KEYS = {"gated", "responses", "min", "has_content"}
_COUNT_KEYS = {"total", "pozitiv", "neutru", "negativ", "incert"}


def test_comments_questions_are_the_four_moodle_open_questions():
    q = queries.get_comments_questions()
    assert list(q) == ["positive", "negative", "difficulty", "other"]
    assert all(isinstance(v, str) and v for v in q.values())


def test_comments_gate_shape():
    curs = taxonomy.all_offerings()[0]["curs"]
    assert set(queries.get_comments_gate(curs)) == _GATE_KEYS
    assert queries.get_comments_gate(curs)["min"] == taxonomy.COMMENTS_MIN_RESPONSES


def test_course_comments_shape_and_sentiment_key_is_always_present():
    curs = taxonomy.all_offerings()[0]["curs"]
    rows = queries.get_course_comments(curs)
    for r in rows:
        assert set(r) == _COMMENT_KEYS
        # present even when None -- the shape is a contract, whether a model happens to be on
        # disk is a value
        assert "sentiment" in r


def test_course_comments_carry_no_author_or_attempt_identifier():
    curs = taxonomy.all_offerings()[0]["curs"]
    for r in queries.get_course_comments(curs):
        assert not (set(r) - _COMMENT_KEYS), "a comment must never carry an id back to its author"


def test_the_response_gate_is_part_of_the_contract(monkeypatch):
    # Below the gate, the data layer returns nothing at all -- not "nothing in the view".
    curs = taxonomy.all_offerings()[0]["curs"]
    monkeypatch.setattr(taxonomy, "course_responses", lambda c, a="2025-2026": 2)
    assert queries.get_course_comments(curs) == []
    assert queries.get_comments_gate(curs)["gated"] is True

    monkeypatch.setattr(taxonomy, "course_responses", lambda c, a="2025-2026": 50)
    assert queries.get_comments_gate(curs)["gated"] is False


def test_comment_counts_shape():
    curs = taxonomy.all_offerings()[0]["curs"]
    counts = queries.get_comment_counts(curs)
    assert set(counts) == {"positive", "negative", "difficulty", "other"}
    for row in counts.values():
        assert set(row) == _COUNT_KEYS


def test_sentiment_model_info_shape():
    info = queries.get_sentiment_model_info()
    assert "available" in info
    if info["available"]:
        assert set(info["per_field"]) <= {"positive", "negative", "other"}
        assert "difficulty" not in info["per_field"]  # never labelled, never scored


def test_content_for_tolerates_a_payload_without_comments():
    # test_content_seam_routes_to_real_content_when_present hand-builds a 3-key payload. If
    # _content_for ever indexes p["comments"] directly, that test explodes -- and so would any
    # cached content written before this feature existed.
    curs = taxonomy.all_offerings()[0]["curs"]
    saved = taxonomy._CONTENT
    taxonomy._CONTENT = {None: {"responses": 42, "students": 100, "cadre": []}}
    try:
        assert taxonomy._content_for(curs)["comments"] == {
            "positive": [],
            "negative": [],
            "difficulty": [],
            "other": [],
        }
    finally:
        taxonomy._CONTENT = saved
