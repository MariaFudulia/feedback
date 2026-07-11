"""The two protections that make it safe to display student prose. Both are invisible when
they fail -- a surviving linkage looks like nothing at all -- so they are tested directly."""

import json
import os

import comments
import sentiment

_FIX = os.path.join(os.path.dirname(__file__), "fixtures", "content")
_SLOTS = [
    "course",
    "prof",
    "assist",
    "eval_overall",
    "expected_grade",
    "load",
    "equipment",
    "part",
    "prof_know",
    "prof_teach",
    "prof_interact",
    "prof_behave",
    "lecture_doc",
    "assist_know",
    "assist_teach",
    "assist_interact",
    "assist_behave",
    "lab_doc",
    "assign_time",
    "assign_diff",
    "assign_useful",
    "positive",
    "negative",
    "difficulty",
    "other",
]
ROLE_OF = {"Ion Popescu": "titular", "Maria Ionescu": "asistent"}


def _attempts(feedback_id=9979):
    with open(os.path.join(_FIX, "feedback_contents", f"{feedback_id}.json"), encoding="utf-8") as f:
        doc = json.load(f)
    return [{s: r["printval"] for s, r in zip(_SLOTS, a["responses"])} for a in doc["anonattempts"]]


def test_blank_and_missing_answers_are_dropped():
    # The fixture has one "" and one null in `positive`, out of 6 attempts.
    built = comments.build(_attempts(), ROLE_OF, None)
    assert len(built["positive"]) == 4
    assert all(c["text"].strip() for slot in comments.SLOTS for c in built[slot])


def test_full_staff_names_are_redacted_in_both_orderings():
    built = comments.build(_attempts(), ROLE_OF, None)
    texts = [c["text"] for c in built["positive"]]
    assert any(comments.REDACTED in t for t in texts)
    # "Ion Popescu" and "Popescu Ion" both appear in the fixture; neither may survive.
    joined = " ".join(c["text"] for slot in comments.SLOTS for c in built[slot])
    assert "Popescu" not in joined
    assert "Ionescu" not in joined


def test_redaction_leaves_the_rest_of_the_sentence_alone():
    built = comments.build(_attempts(), ROLE_OF, None)
    texts = [c["text"] for c in built["positive"]]
    assert f"{comments.REDACTED} explică foarte clar." in texts  # diacritics survive
    assert f"{comments.REDACTED} e mereu disponibil." in texts


def test_bare_surnames_are_never_matched():
    # The staff pool contains "State", "Marin", "Ursu". `state` is an ordinary word: matching
    # bare surnames would silently rewrite student prose, which is worse than the leak it
    # prevents. The fixture has a comment containing "state machines".
    built = comments.build(_attempts(), {"Andrei State": "titular"}, None)
    joined = " ".join(c["text"] for c in built["negative"])
    assert "state machines" in joined
    assert comments.REDACTED not in joined


def test_a_single_token_name_is_ignored():
    assert comments.redact("cursul de state", comments._name_patterns({"State"})) == "cursul de state"


def test_the_positional_join_between_sections_is_destroyed():
    """Splitting the answers per question is NOT enough on its own.

    In attempt order, item #3 of `positive` and item #3 of `negative` are the same student --
    the link survives as an index, and an index is worse than a row because nobody can see it.
    The lists are hash-ordered, so zipping two sections must not reconstruct any real pair.
    """
    attempts = _attempts()
    built = comments.build(attempts, ROLE_OF, None)
    patterns = comments._name_patterns(set(ROLE_OF))

    real_pairs = {
        (comments.redact(a["positive"].strip(), patterns), comments.redact(a["negative"].strip(), patterns))
        for a in attempts
        if (a.get("positive") or "").strip() and (a.get("negative") or "").strip()
    }
    zipped = set(
        zip(
            [c["text"] for c in built["positive"]],
            [c["text"] for c in built["negative"]],
        )
    )
    assert not (zipped & real_pairs), "a student's positive+negative answers are still zippable"


def test_order_is_stable_across_runs_but_not_attempt_order():
    attempts = _attempts()
    first = [c["text"] for c in comments.build(attempts, ROLE_OF, None)["negative"]]
    second = [c["text"] for c in comments.build(attempts, ROLE_OF, None)["negative"]]
    assert first == second  # deterministic: pagination must not shuffle between requests

    in_attempt_order = [a["negative"].strip() for a in attempts if (a.get("negative") or "").strip()]
    assert first != in_attempt_order


def test_merge_keeps_hash_order_regardless_of_which_series_came_first():
    a = {"positive": [{"text": "aaa", "sentiment": None}], "negative": [], "difficulty": [], "other": []}
    b = {"positive": [{"text": "bbb", "sentiment": None}], "negative": [], "difficulty": [], "other": []}
    assert comments.merge([a, b])["positive"] == comments.merge([b, a])["positive"]


def test_difficulty_never_carries_a_sentiment():
    built = comments.build(_attempts(), ROLE_OF, sentiment.load())
    assert built["difficulty"]
    assert all(c["sentiment"] is None for c in built["difficulty"])


def test_names_are_taken_from_the_attempts_when_the_users_file_is_absent():
    # users/<id>.json is optional; the prof/assist slots of the attempt always exist.
    built = comments.build(_attempts(), None, None)
    joined = " ".join(c["text"] for c in built["positive"])
    assert "Popescu" not in joined


def test_counts_cover_every_label_and_the_declined_one():
    built = comments.build(_attempts(), ROLE_OF, sentiment.load())
    counts = comments.counts(built)

    row = counts["negative"]
    assert set(row) == {"total", *sentiment.LABELS, sentiment.UNCERTAIN}
    assert row["total"] == len(built["negative"])
    # a comment the model declined to label (sentiment=None) lands in no bucket, so the
    # buckets sum to AT MOST the total -- never more
    assert sum(row[k] for k in (*sentiment.LABELS, sentiment.UNCERTAIN)) <= row["total"]

    # difficulty is never labelled, so every one of its comments is unbucketed
    diff = counts["difficulty"]
    assert diff["total"] > 0
    assert sum(diff[k] for k in (*sentiment.LABELS, sentiment.UNCERTAIN)) == 0
