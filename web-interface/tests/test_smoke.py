"""Smoke test: every route must respond 200 without raising. Catches
template errors, broken url_for references, and queries.py mismatches
before merge.
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
]


@pytest.fixture
def client():
    app_module.app.config.update(TESTING=True)
    return app_module.app.test_client()


@pytest.mark.parametrize("route", ROUTES)
def test_route_responds(client, route):
    resp = client.get(route)
    assert resp.status_code == 200
