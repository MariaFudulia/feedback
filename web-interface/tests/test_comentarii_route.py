"""The /comentarii route: param validation, pagination, and the gate the export must not walk
around."""

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
