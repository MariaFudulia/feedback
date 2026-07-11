""" "Shell + global filter cascade.
Forces the synthetic taxonomy so no private data is needed (same as test_smoke.py)."""

import os
import re

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


# ---- the domeniu->track bridge (_coarse_scope) ------------------------------
# The report pages read scope through this translation onto the deck aggregates'
# coarser params. It duplicates knowledge (CTI/IS map, "S"+sem) by design, so it
# gets its own tests -- a silent mismatch here shows up as silently unfiltered
# pages, not as an error (that is exactly how the completare-evaluare sem bug hid).


def _scope_after(client, **filters):
    """Set filters through the real form, then read _coarse_scope under a request."""
    _set(client, **filters)
    with client.session_transaction() as sess:
        stored = {k: sess.get(k, "") for k in app_module.FILTER_KEYS}
    with app_module.app.test_request_context("/"):
        from flask import session

        session.update(stored)
        return app_module._coarse_scope()


def test_coarse_scope_empty_filters_map_to_all_none(client):
    assert _scope_after(client) == (None, None, None, None)


def test_coarse_scope_maps_known_domenii_to_track(client):
    assert _scope_after(client, ciclu="L", domeniu="CTI")[1] == "CTI"
    client.get("/reset-filters?next=/")
    assert _scope_after(client, ciclu="L", domeniu="IS")[1] == "IS"


def test_coarse_scope_unknown_domeniu_widens_to_no_track(client):
    # IM exists in the taxonomy but has no deck track -- must become None, not crash
    assert _scope_after(client, ciclu="M", domeniu="IM")[1] is None


def test_coarse_scope_semester_gets_deck_prefix(client):
    # the aggregates expect "S1"/"S2"; the cascade stores "1"/"2"
    ciclu, _track, semestru, an = _scope_after(client, ciclu="L", domeniu="CTI", an="2", sem="1")
    assert ciclu == "L"
    assert semestru == "S1"
    assert an == 2  # int, not the session's string


# ---- shareable scope URLs ----------------------------------------------------
# A GET carrying structural params applies them like a sidebar submission, so a
# pasted link reproduces the exact view. Same revalidation -> still contradiction-proof.


def test_url_scope_applies_to_session(client):
    client.get("/top10-cursuri?ciclu=L&domeniu=CTI&an=2")
    with client.session_transaction() as sess:
        assert sess.get("ciclu") == "L"
        assert sess.get("domeniu") == "CTI"
        assert sess.get("an") == "2"


def test_url_scope_is_revalidated_not_trusted(client):
    # Master has no year 3: the illegal an must be dropped, not stored
    client.get("/?ciclu=M&an=3")
    with client.session_transaction() as sess:
        assert sess.get("ciclu") == "M"
        assert sess.get("an") == ""


def test_url_scope_is_the_whole_scope(client):
    # a link's params REPLACE the scope; a dim absent from the link means 'Toate'
    _set(client, ciclu="L", domeniu="CTI", an="2")
    client.get("/?ciclu=M")
    with client.session_transaction() as sess:
        assert sess.get("ciclu") == "M"
        assert sess.get("domeniu") == ""
        assert sess.get("an") == ""


def test_share_link_offered_only_when_scoped(client):
    client.get("/reset-filters?next=/")
    assert "share-link" not in client.get("/").get_data(as_text=True)
    _set(client, ciclu="L")
    page = client.get("/").get_data(as_text=True)
    assert "share-link" in page and "ciclu=L" in page


# ---- theme -------------------------------------------------------------------
# The theme is carried entirely by which radio the server renders as :checked --
# the stylesheet keys off it (body:has(#tema-dark:checked)) and there is no JS to
# fall back on. So "the right radio is checked" IS the feature, and these tests
# guard it: lose the `checked` and every page silently renders in the wrong theme.


def _checked_theme(client, path="/"):
    page = client.get(path).get_data(as_text=True)
    found = re.findall(r'id="tema-(\w+)"([^>]*)', page)
    return [t for t, attrs in found if "checked" in attrs]


def test_theme_defaults_to_auto(client):
    # no choice made yet -> defer to the OS (prefers-color-scheme), never a guess
    assert _checked_theme(client) == ["auto"]


def test_theme_choice_persists_across_pages(client):
    client.post("/tema", data={"tema": "dark"})
    for path in ("/", "/top10-cursuri", "/despre-date"):
        assert _checked_theme(client, path) == ["dark"], f"theme lost on {path}"


def test_theme_post_swaps_nothing(client):
    # the CSS already flipped client-side; the POST only makes it stick, so it must
    # stay a 204 -- returning a body here would make htmx swap the page away
    r = client.post("/tema", data={"tema": "dark"})
    assert r.status_code == 204
    assert r.get_data() == b""


def test_unknown_theme_falls_back_to_auto(client):
    # the value lands in an HTML attribute, so it is never trusted
    client.post("/tema", data={"tema": '"><script>alert(1)</script>'})
    with client.session_transaction() as sess:
        assert sess.get("tema") == "auto"
    assert "<script>alert(1)</script>" not in client.get("/").get_data(as_text=True)


def test_reset_filters_keeps_the_theme(client):
    # theme is a display preference, not part of the data scope -- resetting the
    # filters must not throw the user back into light mode
    client.post("/tema", data={"tema": "dark"})
    _set(client, ciclu="L")
    client.get("/reset-filters?next=/")
    assert _checked_theme(client) == ["dark"]
