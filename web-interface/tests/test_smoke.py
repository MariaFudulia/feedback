"""Smoke test: every route must respond 200 without raising. Catches
template errors, broken url_for references, and queries.py mismatches
before merge. The synthetic taxonomy is forced globally by tests/conftest.py.
"""

import pytest

import app as app_module

ROUTES = [
    "/",
    "/completare-evaluare",
    "/pe-ani-de-studiu",
    "/top10-cursuri",
    "/top10-titulari",
    "/top10-asistenti",
    "/evaluare-pe-zone",
    "/curs-detaliu",
    "/comentarii",
    "/despre-date",  # was missing from this list
    "/taxonomie",
]


@pytest.fixture
def client():
    app_module.app.config.update(TESTING=True)
    return app_module.app.test_client()


@pytest.mark.parametrize("route", ROUTES)
def test_route_responds(client, route):
    resp = client.get(route)
    assert resp.status_code == 200


def test_set_filters_redirects_and_persists(client):
    """/set-filters isn't hit by the GET-only ROUTES loop above -- cover it
    directly: it must redirect back to `next`, and the choice must actually
    persist in the session (not just accept the POST and ignore it)."""
    resp = client.post(
        "/set-filters",
        data={"ciclu": "L", "an_universitar": "", "next": "/top10-cursuri"},
    )
    assert resp.status_code in (301, 302, 303, 307, 308)
    assert resp.headers["Location"].endswith("/top10-cursuri")

    resp2 = client.get("/top10-cursuri")
    assert resp2.status_code == 200
    assert b'<option value="L" selected>' in resp2.data


def test_set_filters_reset_to_toate(client):
    client.post("/set-filters", data={"ciclu": "L", "an_universitar": "", "next": "/"})
    client.post("/set-filters", data={"ciclu": "", "an_universitar": "", "next": "/"})
    resp = client.get("/")
    assert b'<option value="" selected>Toate</option>' in resp.data
