""""Shell + global filter cascade.
Forces the synthetic taxonomy so no private data is needed (same as test_smoke.py)."""

import os

os.environ["FEEDBACK_DATA_DIR"] = "/tmp/feedback-no-such-data-dir"

import pytest  # noqa: E402

import app as app_module  # noqa: E402


@pytest.fixture
def client():
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def _set(client, **filters):
    """POST the global filter form, exactly like the sidebar does."""
    data = {"an_universitar": "2024-2025", "next": "/", **filters}
    return client.post("/set-filters", data=data)


def test_upstream_change_clears_illegal_downstream(client):
    # Master has only years 1-2, so an=3 under Master is a contradiction and must be
    # dropped (to ""), never silently kept. This is the whole point of the cascade.
    _set(client, ciclu="M", an="3")
    with client.session_transaction() as sess:
        assert sess.get("ciclu") == "M"
        assert sess.get("an") == ""


def test_specializare_shows_only_after_a_domeniu_that_has_one(client):
    # specializare is optional; it appears only after you pick a domeniu that has one.
    # In the synthetic data, Licenta / IS carries the AIA specializare.
    _set(client, ciclu="L")  # no domeniu chosen yet
    page = client.get("/").get_data(as_text=True)
    assert 'name="specializare"' not in page
    
    # TODO 1: Setăm domeniul la "IS", reîncărcăm și verificăm apariția filtrului
    _set(client, ciclu="L", domeniu="IS")
    page_with_domeniu = client.get("/").get_data(as_text=True)
    assert 'name="specializare"' in page_with_domeniu


def test_reset_clears_all_filters(client):
    _set(client, ciclu="L", domeniu="CTI", an="2")
    client.get("/reset-filters?next=/")
    
    # TODO 2: Verificăm top-down că toate cheile din FILTER_KEYS sunt goale
    with client.session_transaction() as sess:
        for key in app_module.FILTER_KEYS:
            # Cheia nu trebuie să existe în sesiune sau valoarea ei trebuie să fie un string gol
            assert not sess.get(key)