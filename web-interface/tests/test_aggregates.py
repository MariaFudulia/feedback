"""Aggregation engine (aggregates.py) + its taxonomy substrate (offering_metrics).

Synthetic path runs on the fallback dataset (conftest forces it); the real path reuses
tests/fixtures/content/ by installing it directly (same approach as test_content_adapter).
"""

import os
from collections import defaultdict

import aggregates
import taxonomy

_FIX = os.path.join(os.path.dirname(__file__), "fixtures", "content")


def test_offering_metrics_shape():
    rows = taxonomy.offering_metrics()
    assert len(rows) == len(taxonomy.all_offerings())
    r = rows[0]
    assert {
        "course_id",
        "curs",
        "denumire",
        "ciclu",
        "domeniu",
        "an",
        "sem",
        "serie",
        "responses",
        "students",
        "evaluare_curs",
        "cadre",
    } <= set(r)
    assert 1.0 <= r["evaluare_curs"] <= 5.0
    assert r["responses"] >= 1 and r["students"] >= 1


def test_offering_metrics_synthetic_split_is_sum_preserving_per_curs():
    # grouping offerings back by curs must reproduce the per-curs functions (no page-to-page
    # contradiction). Synthetic rounding allows a small tolerance bounded by #offerings.
    rows = taxonomy.offering_metrics()
    stu, resp, n_off = defaultdict(int), defaultdict(int), defaultdict(int)
    for row in rows:
        stu[row["curs"]] += row["students"]
        resp[row["curs"]] += row["responses"]
        n_off[row["curs"]] += 1
    for curs in list(stu)[:20]:  # sample
        assert abs(stu[curs] - taxonomy.course_students(curs)) <= n_off[curs]
        assert abs(resp[curs] - taxonomy.course_responses(curs)) <= n_off[curs]


def test_offering_metrics_reads_real_content_via_fixture():
    offerings = [
        {
            "course_id": 2802,
            "feedback_ids": [9978],
            "curs": "c",
            "denumire": "C",
            "ciclu": "L",
            "domeniu": "CTI",
            "specializare": None,
            "an": 2,
            "sem": 1,
            "serie": "CA",
        }
    ]
    content, _ = taxonomy._load_content(_FIX, offerings)
    saved = (taxonomy._OFFERINGS, taxonomy._CONTENT)
    taxonomy._OFFERINGS, taxonomy._CONTENT = offerings, content
    try:
        rows = taxonomy.offering_metrics()
        assert len(rows) == 1
        assert rows[0]["responses"] == 2 and rows[0]["students"] == 3
        assert rows[0]["evaluare_curs"] == 4.5  # course-level eval_gen from the fixture
        assert rows[0]["serie"] == "CA"
    finally:
        taxonomy._OFFERINGS, taxonomy._CONTENT = saved


def test_top_courses_shape_threshold_sort_cap():
    df = aggregates.get_top_courses(limit=10)
    assert list(df.columns) == [
        "curs",
        "prof",
        "num_feedback",
        "proc_feedback",
        "num_utilizatori",
        "evaluare_curs",
    ]
    assert len(df) <= 10
    assert (df["proc_feedback"] >= 7).all()  # deck threshold
    assert (df["num_feedback"] >= 3).all()
    assert list(df["evaluare_curs"]) == sorted(df["evaluare_curs"], reverse=True)  # default sort


def test_top_courses_order_by_and_ciclu_filter():
    df = aggregates.get_top_courses(order_by="proc_feedback")
    assert list(df["proc_feedback"]) == sorted(df["proc_feedback"], reverse=True)
    # ciclu filter yields a valid (possibly smaller) board, still capped + thresholded
    dfm = aggregates.get_top_courses(ciclu="M")
    assert len(dfm) <= 10 and (dfm["num_feedback"] >= 3).all()


def test_top_titulari_shape_threshold_sort():
    df = aggregates.get_top_titulari()
    assert list(df.columns) == [
        "persoana",
        "num_cursuri",
        "num_feedback",
        "proc_feedback",
        "num_utilizatori",
        "evaluare_curs",
        "evaluare_prof",
    ]
    assert len(df) <= 10
    assert (df["num_feedback"] >= 15).all() and (df["proc_feedback"] >= 7).all()
    assert list(df["evaluare_prof"]) == sorted(df["evaluare_prof"], reverse=True)


def test_top_asistenti_shape_threshold():
    df = aggregates.get_top_asistenti()
    assert list(df.columns) == ["persoana", "num_feedback", "evaluare_curs", "evaluare_prof"]
    assert len(df) <= 10
    assert (df["num_feedback"] >= 10).all()
