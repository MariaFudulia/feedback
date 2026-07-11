"""The sentiment model is a committed binary-ish artifact. These tests are what make it
reviewable: they pin what it must classify correctly, and they pin that it fails soft."""

import json

import pytest

import sentiment

MODEL = sentiment.load()


def test_normalize_folds_both_spellings_of_romanian_diacritics():
    # Moodle text carries both the correct comma-below (U+0219/U+021B) and the legacy
    # cedilla (U+015F/U+0163), and half of it has no diacritics at all. All must fold to the
    # same tokens, or the model sees three different words.
    assert sentiment.normalize("Șerban ȚARĂ") == sentiment.normalize("Şerban ŢARĂ")
    assert sentiment.normalize("laboratorul") == "laboratorul"
    assert sentiment.normalize("Cursul e util și clar") == "cursul e util si clar"
    assert sentiment.tokens("Slide-urile sunt incomplete.") == ["slide", "urile", "sunt", "incomplete"]


def test_model_ships_with_provenance_and_per_field_metrics():
    # A shipped accuracy number is meaningless without saying what it was measured against.
    assert MODEL is not None, "models/sentiment_ro.json is missing -- run tools/train_sentiment.py"
    holdout = MODEL["holdout"]
    assert 0.0 < holdout["accuracy"] <= 1.0
    assert set(holdout["per_field"]) == set(sentiment.FIELDS)
    assert holdout["attempt_tier_accuracy"] is not None
    assert MODEL["corpus"]["answers"] > 0
    assert "SYNTHETIC" in MODEL["corpus"]["source"]


def test_difficulty_is_never_labelled():
    # The question asks for a cause, not an opinion; the corpus has no label for it. A chip
    # there would be a fabricated number.
    assert "difficulty" not in sentiment.FIELDS
    assert sentiment.classify(MODEL, "difficulty", "volumul mare de teme") is None


@pytest.mark.parametrize(
    "field,text,expected",
    [
        ("positive", "Cursul e foarte util si bine structurat.", "pozitiv"),
        ("positive", "Cursul e foarte util și bine structurat.", "pozitiv"),  # same, with diacritics
        ("positive", "Niciun aspect pozitiv.", "negativ"),
        ("positive", "Nimic. Slide-urile sunt incomplete.", "negativ"),
        ("negative", "Nu am ce sa reprosez.", "pozitiv"),
        ("negative", "Aproape nimic.", "pozitiv"),
        ("negative", "Totul: ritmul e prea alert, nu se raspunde pe forum.", "negativ"),
        ("other", "Felicitari echipei.", "pozitiv"),
        ("other", "Cea mai slaba materie de pana acum.", "negativ"),
    ],
)
def test_golden_classifications(field, text, expected):
    assert sentiment.classify(MODEL, field, text) == expected


def test_the_same_word_means_opposite_things_in_different_questions():
    # This is why there is one model per question. In "ce trebuie îmbunătățit", having
    # nothing to say is GOOD news; in "aspecte pozitive" it is bad news.
    assert sentiment.classify(MODEL, "negative", "Aproape nimic.") == "pozitiv"
    assert sentiment.classify(MODEL, "positive", "Nimic. Slide-urile sunt incomplete.") == "negativ"


def test_declines_to_label_rather_than_guessing():
    assert sentiment.classify(MODEL, "positive", "") is None
    assert sentiment.classify(MODEL, "positive", "   ") is None
    assert sentiment.classify(MODEL, "positive", "zzzz qqqq") is None  # nothing in vocabulary
    assert sentiment.classify(None, "positive", "Cursul e util.") is None  # no model at all


def test_load_fails_soft_on_anything_unusable(tmp_path):
    # A missing or corrupt model must degrade to "comments render without labels", never to a
    # broken page.
    assert sentiment.load(str(tmp_path / "nope.json")) is None

    bad = tmp_path / "bad.json"
    bad.write_text("{ not json", encoding="utf-8")
    assert sentiment.load(str(bad)) is None

    wrong_schema = tmp_path / "old.json"
    wrong_schema.write_text(json.dumps({"schema": 99, "fields": {}}), encoding="utf-8")
    assert sentiment.load(str(wrong_schema)) is None

    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"schema": sentiment.SCHEMA, "fields": {}}), encoding="utf-8")
    assert sentiment.load(str(empty)) is None


def test_info_is_honest_when_there_is_no_model():
    assert sentiment.info(None) == {
        "available": False,
        "accuracy": None,
        "per_field": {},
        "corpus": {},
        "trained_at": None,
    }
    assert sentiment.info(MODEL)["available"] is True
