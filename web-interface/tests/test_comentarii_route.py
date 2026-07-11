"""The /comentarii route: param validation, pagination, and the gate the export must not walk
around."""

import os

import pytest

import app as app_module
import taxonomy


@pytest.fixture
def client():
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


def test_page_renders(client):
    assert client.get("/comentarii").status_code == 200


@pytest.mark.parametrize(
    "qs",
    [
        "intrebare=bogus",
        "sentiment=bogus",
        "page=abc",
        "page=0",
        "page=-1",
    ],
)
def test_unknown_parameters_are_rejected_not_silently_defaulted(client, qs):
    # Same discipline as _order_by: a value we don't recognise is a 400, never a quiet
    # fallback that shows the user something other than what they asked for.
    assert client.get(f"/comentarii?{qs}").status_code == 400


def test_every_real_question_is_accepted(client):
    for slot in ("positive", "negative", "difficulty", "other"):
        assert client.get(f"/comentarii?intrebare={slot}").status_code == 200


def test_page_beyond_the_end_is_clamped_not_an_error(client):
    assert client.get("/comentarii?page=99999").status_code == 200


def test_a_gated_course_leaks_nothing_through_the_csv_export(client, monkeypatch):
    """The classic leak: the gate lives in the template, and ?export=csv renders past it.

    _export_url re-emits every query argument by design, so this has to be enforced in the
    data layer. Prove it: force a below-the-gate course and demand an empty export.
    """
    monkeypatch.setattr(
        taxonomy,
        "comments_gate",
        lambda curs, an="2025-2026": {"gated": True, "responses": 2, "min": 5, "has_content": True},
    )
    r = client.get("/comentarii?export=csv")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    # header row only -- no comment text of any kind
    assert body.strip().splitlines()[0].startswith("intrebare")
    assert len(body.strip().splitlines()) == 1


def test_csv_carries_no_per_comment_identifier(client):
    """No attempt id, no index, no row number. taxonomy destroyed the link between a comment
    and its author; a stable identifier here would hand it straight back."""
    body = client.get("/comentarii?export=csv").get_data(as_text=True)
    header = body.strip().splitlines()[0]
    assert header.replace("\r", "") == "intrebare,sentiment,comentariu"


def test_difficulty_ignores_a_stale_sentiment_filter(client):
    # `difficulty` is never labelled, so filtering it by sentiment would silently empty the
    # list. The route forces "toate" rather than 400-ing on a link the user didn't type.
    assert client.get("/comentarii?intrebare=difficulty&sentiment=pozitiv").status_code == 200


def test_missing_comment_data_is_not_blamed_on_the_students(client, monkeypatch):
    """The three "there is nothing here" cases mean different things and must not be conflated.

    `has_content` used to be `bool(curs)` -- i.e. "is a course selected" -- which made this
    branch unreachable, so a deployment with no comment data at all rendered "nimeni nu a
    răspuns la această întrebare": blaming students for a missing file.
    """
    monkeypatch.setattr(taxonomy, "_CONTENT", None)
    monkeypatch.setattr(taxonomy, "_DEMO_CORPUS", {})

    html = client.get("/comentarii").get_data(as_text=True)
    assert "Nu există comentarii în această instanță" in html
    assert "Nimeni nu a răspuns" not in html


def test_a_course_where_nobody_wrote_anything_says_so(client, monkeypatch):
    # Above the gate, comment data exists in the instance, but this question is empty.
    monkeypatch.setattr(
        taxonomy,
        "comments_gate",
        lambda curs, an="2025-2026": {"gated": False, "responses": 40, "min": 5, "has_content": True},
    )
    monkeypatch.setattr(
        taxonomy,
        "course_comments",
        lambda curs, an="2025-2026": {"positive": [], "negative": [], "difficulty": [], "other": []},
    )
    html = client.get("/comentarii").get_data(as_text=True)
    assert "Nimeni nu a răspuns" in html
    assert "Nu există comentarii în această instanță" not in html


def test_the_gate_threshold_is_never_restated_as_a_literal():
    # app.py used to hand-roll {"min": 5} for the no-course case -- a pinned safety threshold
    # copied into a second place, free to drift from the constant it mirrors.
    import queries

    assert queries.get_comments_gate(None)["min"] == taxonomy.COMMENTS_MIN_RESPONSES

    # resolved from THIS file, not the cwd: CI happens to run pytest from web-interface/, but a
    # test that only passes from one directory is a trap for whoever runs it from the repo root
    app_py = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")
    with open(app_py, encoding="utf-8") as f:
        assert '"min": 5' not in f.read()
