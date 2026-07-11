"""Content adapter (`taxonomy._load_content`) — fixture-based, no private data.

The real feedback_contents/ + users/ exports don't exist yet, so these tests run
against tests/fixtures/content/, built in the exact shape the pipeline produces
(feedback_contents/<id>.json = anonattempts→responses×25 positional; users/<id>.json
= array with roles). Functions are called directly, so they don't touch the
synthetic singleton (same approach as test_real_data.py).
"""

import json
import os

import config
import taxonomy

_FIX = os.path.join(os.path.dirname(__file__), "fixtures", "content")


def test_slot_map_has_25_positions():
    assert len(taxonomy._RESPONSE_SLOTS) == 25
    assert taxonomy._RESPONSE_SLOTS[1] == "prof"  # titular name
    assert taxonomy._RESPONSE_SLOTS[2] == "assist"  # asistent name
    assert taxonomy._RESPONSE_SLOTS[3] == "eval_overall"


def test_fixtures_are_well_formed():
    fb = json.load(open(os.path.join(_FIX, "feedback_contents", "9978.json"), encoding="utf-8"))
    assert len(fb["anonattempts"]) == 2
    assert all(len(a["responses"]) == 25 for a in fb["anonattempts"])
    assert all({"name", "printval", "rawval"} <= set(r) for a in fb["anonattempts"] for r in a["responses"])
    users = json.load(open(os.path.join(_FIX, "users", "2802.json"), encoding="utf-8"))
    assert isinstance(users, list) and len(users) == 5


def test_parse_feedback_file_decodes_positions_and_reverses_likert():
    attempts = taxonomy._parse_feedback_file(os.path.join(_FIX, "feedback_contents", "9978.json"))
    assert len(attempts) == 2
    a0 = attempts[0]
    # name slots come from printval, unchanged
    assert a0["prof"] == "Ion Popescu"
    assert a0["assist"] == "Maria Ionescu"
    # Likert: rawval "1" -> 6-1 = 5 (best); "2" -> 4; "3" -> 3
    assert a0["eval_overall"] == 5  # rawval "1"
    assert a0["prof_know"] == 5  # rawval "1"
    assert a0["prof_teach"] == 4  # rawval "2"
    assert a0["assist_interact"] == 3  # rawval "3"
    # numeric slot kept as-is (not reversed)
    assert a0["expected_grade"] == 8
    # second attempt differs
    assert attempts[1]["eval_overall"] == 4  # rawval "2"


def test_parse_users_file_classifies_roles():
    students, role_of = taxonomy._parse_users_file(os.path.join(_FIX, "users", "2802.json"))
    assert students == 3
    assert role_of["Ion Popescu"] == "titular"  # editingteacher
    assert role_of["Maria Ionescu"] == "asistent"


def test_load_content_none_without_export():
    # no feedback_contents/ + users/ dirs -> (None, 0): keeps synthetic scores + the badge
    content, skipped = taxonomy._load_content("/tmp/feedback-no-such-dir", [])
    assert content is None and skipped == 0


def test_load_content_skips_malformed_files_without_crashing(tmp_path):
    # a corrupt file must be skipped + counted, never crash the load (which runs at import)
    fc = tmp_path / "feedback_contents"
    fc.mkdir()
    us = tmp_path / "users"
    us.mkdir()
    (fc / "9978.json").write_text("{ truncated, not valid json", encoding="utf-8")
    (us / "2802.json").write_text("[]", encoding="utf-8")
    offerings = [{"course_id": 2802, "feedback_ids": [9978], "curs": "c"}]
    content, skipped = taxonomy._load_content(str(tmp_path), offerings)
    assert skipped == 1
    assert content is None  # the only course had no parseable attempts


def test_load_content_aggregates_per_course():
    offerings = [{"course_id": 2802, "feedback_ids": [9978], "curs": "test-curs"}]
    content, skipped = taxonomy._load_content(_FIX, offerings)
    assert content is not None and skipped == 0
    c = content[2802]
    assert c["responses"] == 2  # two attempts
    assert c["students"] == 3
    cadre = {row["nume"]: row for row in c["cadre"]}
    tit = cadre["Ion Popescu"]
    assert tit["tip"] == "titular" and tit["num_feedback"] == 2
    # titular: means over the two attempts (rawval reversed to 5-best)
    assert tit["eval_gen"] == 4.5 and tit["preg"] == 5.0 and tit["expl_clare"] == 4.5
    assert tit["comport"] == 5.0 and tit["indepl_ob"] == 3.5
    asi = cadre["Maria Ionescu"]
    assert asi["tip"] == "asistent" and asi["num_feedback"] == 2
    assert asi["preg"] == 4.0 and asi["expl_clare"] == 3.5 and asi["comport"] == 4.5
    assert asi["eval_gen"] == 4.5  # course-level, shared with the titular
    # cadre keys match the contract shape
    assert set(tit) == {"nume", "tip", "num_feedback", *taxonomy.QUESTION_KEYS}


def test_seam_flips_and_public_functions_read_real_content():
    # end-to-end: fixture content, installed, flows through the public API and flips the badge
    offerings = [{"course_id": 2802, "feedback_ids": [9978], "curs": "seam-curs", "serie": None}]
    content, _ = taxonomy._load_content(_FIX, offerings)
    saved = (
        taxonomy._OFFERINGS,
        taxonomy._BY_CURS,
        taxonomy._CONTENT,
        taxonomy._CONTENT_GENERATED,
    )
    taxonomy._OFFERINGS = offerings
    taxonomy._BY_CURS = {"seam-curs": offerings[0]}
    taxonomy._CONTENT = content
    taxonomy._CONTENT_GENERATED = False  # i.e. a real Moodle export, explicitly declared
    try:
        assert taxonomy.content_is_synthetic() is False  # badge clears app-wide
        assert taxonomy.course_responses("seam-curs") == 2
        assert taxonomy.course_students("seam-curs") == 3
        detail = {r["nume"]: r for r in taxonomy.course_detail("seam-curs")}
        assert detail["Ion Popescu"]["comport"] == 5.0  # real score, not synthetic
        assert set(taxonomy.faculty_average()) == set(taxonomy.QUESTION_KEYS)
    finally:
        (
            taxonomy._OFFERINGS,
            taxonomy._BY_CURS,
            taxonomy._CONTENT,
            taxonomy._CONTENT_GENERATED,
        ) = saved


def test_generated_content_keeps_the_demonstrative_badge_on():
    """Content being PRESENT is not content being REAL.

    generate-feedback produces a well-formed feedback_contents/ + users/ pair. Loading it
    must NOT clear the badge, or the public demo asserts that fabricated scores, teacher
    names and rankings are real. The check fails closed: only an export explicitly
    declared real (FEEDBACK_CONTENT_SYNTHETIC=0) clears it.
    """
    offerings = [{"course_id": 2802, "feedback_ids": [9978], "curs": "seam-curs", "serie": None}]
    content, _ = taxonomy._load_content(_FIX, offerings)
    saved = (taxonomy._CONTENT, taxonomy._CONTENT_GENERATED)
    taxonomy._CONTENT = content
    try:
        taxonomy._CONTENT_GENERATED = True  # a generated export, or provenance unknown
        assert taxonomy.content_is_synthetic() is True
    finally:
        taxonomy._CONTENT, taxonomy._CONTENT_GENERATED = saved


def test_content_provenance_fails_closed(tmp_path, monkeypatch):
    # no manifest, unreadable manifest, or a manifest marking the export synthetic ->
    # all count as synthetic. Only an explicit "synthetic": false says otherwise.
    monkeypatch.setattr(config, "CONTENT_SYNTHETIC", None)  # don't read the dev's shell

    assert taxonomy._content_is_generated(str(tmp_path)) is True  # no manifest at all

    (tmp_path / "manifest.json").write_text('{"synthetic": true}', encoding="utf-8")
    assert taxonomy._content_is_generated(str(tmp_path)) is True

    (tmp_path / "manifest.json").write_text("{ not json", encoding="utf-8")
    assert taxonomy._content_is_generated(str(tmp_path)) is True

    (tmp_path / "manifest.json").write_text('{"synthetic": false}', encoding="utf-8")
    assert taxonomy._content_is_generated(str(tmp_path)) is False


def test_synthetic_manifest_cannot_be_overridden_by_the_env_var(tmp_path, monkeypatch):
    """A stale FEEDBACK_CONTENT_SYNTHETIC=0 must not promote a generated export to real.

    The realistic accident: a deployment that once served a real Moodle export keeps the
    env var set, then gets pointed at generate-feedback output. If the env var won, the
    public dashboard would drop the 'date demonstrative' badge over fabricated scores and
    invented teacher names. An export that declares itself synthetic is un-promotable.
    """
    monkeypatch.setattr(config, "CONTENT_SYNTHETIC", "0")  # "this data is real"
    (tmp_path / "manifest.json").write_text('{"synthetic": true}', encoding="utf-8")
    assert taxonomy._content_is_generated(str(tmp_path)) is True  # the manifest wins

    # ...but the env var still works where the export makes no claim about itself.
    (tmp_path / "manifest.json").unlink()
    assert taxonomy._content_is_generated(str(tmp_path)) is False
