"""Content adapter (`taxonomy._load_content`) — fixture-based, no private data.

The real feedback_contents/ + users/ exports don't exist yet, so these tests run
against tests/fixtures/content/, built in the exact shape the pipeline produces
(feedback_contents/<id>.json = anonattempts→responses×25 positional; users/<id>.json
= array with roles). Functions are called directly, so they don't touch the
synthetic singleton (same approach as test_real_data.py).
"""

import json
import os

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
