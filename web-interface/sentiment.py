"""Sentiment inference for the free-text answers. Estimation, never measurement.

A multinomial naive Bayes, pure standard library (the app depends on flask + pandas +
gunicorn and keeps it that way). The weights are TRAINED OFFLINE by tools/train_sentiment.py
and shipped as models/sentiment_ro.json -- the app can never train, because the labels live
in the generator's `groundtruth/` sidecar, which sits outside the directories the app reads
and will not exist at all for a real Moodle export.

Three things this module is deliberate about:

* ONE MODEL PER QUESTION. The same word means opposite things depending on which question
  it answers: in the "ce trebuie îmbunătățit" question the happiest answer is "Nu am ce să
  reproșez", while in the "aspecte pozitive" question the unhappiest is "Nimic". Pooling the
  questions lets the loud praise/complaint vocabulary of one drown the subtler hedging vs
  intensity signal of the other.

* NO SENTIMENT FOR `difficulty`. That question asks for a CAUSE ("dificultatea principală
  provine din:"), not an opinion, and the corpus carries no sentiment label for it. Running
  the classifier over it anyway would be inventing a number. `classify` returns None.

* A LOW-CONFIDENCE ANSWER IS "incert", NOT A GUESS. Naive Bayes posteriors are wildly
  overconfident, so we never render a probability; below a margin we decline to label.

The model is trained on the SYNTHETIC corpus the generator produces -- our own templates. Its
accuracy figure therefore describes performance on text like the training text. Real student
prose uses vocabulary it has never seen, and it will do worse; we cannot say how much worse,
because we have no labelled real data to measure against. Whatever renders these labels must
say so (see templates/_chips.html: model_badge).
"""

import json
import os
import re
import unicodedata

LABELS = ("pozitiv", "neutru", "negativ")

# The questions we label. `difficulty` is absent on purpose -- see the docstring.
FIELDS = ("positive", "negative", "other")

# The generator's 5 tiers folded onto the 3 labels the UI shows.
TIER_TO_LABEL = {
    "strong_neg": "negativ",
    "neg": "negativ",
    "neutral": "neutru",
    "pos": "pozitiv",
    "strong_pos": "pozitiv",
}

# Below this log-odds margin between the top two labels we return "incert" instead of a
# coin-flip. Pinned, not tunable from the UI.
MARGIN = 0.75

UNCERTAIN = "incert"

SCHEMA = 1

_HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.environ.get("FEEDBACK_SENTIMENT_MODEL", os.path.join(_HERE, "models", "sentiment_ro.json"))

_TOKEN = re.compile(r"[a-z0-9]+")


def normalize(text):
    """Lowercase, strip diacritics. Moodle prose mixes both spellings of ș/ț (the correct
    comma-below and the legacy cedilla) and half of it is typed without diacritics at all,
    so 'laboratorul' and 'labóratorul' must reach the model as the same token.

    NOT taxonomy._slug: that also drops every non-alphanumeric and truncates to 48 chars.
    Reusing it here would be train/serve skew waiting to happen -- the trainer imports THIS.
    """
    text = unicodedata.normalize("NFKD", text or "")
    return text.encode("ascii", "ignore").decode("ascii").lower()


def tokens(text):
    return _TOKEN.findall(normalize(text))


def load(path=None):
    """The shipped weights, or None when they are missing or unusable.

    Fails soft on purpose: a missing model must degrade to "comments render without labels",
    never to a broken page. Same discipline as taxonomy's content loader.
    """
    try:
        with open(path or MODEL_PATH, encoding="utf-8") as f:
            model = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(model, dict) or model.get("schema") != SCHEMA:
        return None
    if not isinstance(model.get("fields"), dict) or not model["fields"]:
        return None
    return model


def classify(model, field, text):
    """-> 'pozitiv' | 'neutru' | 'negativ' | 'incert', or None when we decline to label.

    None (rather than a label) when: there is no model, the question is not one we label
    (`difficulty`), or the text carries no token the model has ever seen. Callers render
    nothing at all in that case -- an absent chip is honest, a wrong one is not.
    """
    if not model or field not in model.get("fields", {}):
        return None
    text = (text or "").strip()
    if not text:
        return None

    params = model["fields"][field]
    logprior = params["logprior"]
    logp = params["logp"]

    # Every row of `logp` carries a smoothed weight for all three labels (the trainer emits
    # them from one Laplace-smoothed table), so there is no "token seen for label A but not
    # for label B" case to fall back on. An out-of-vocabulary token is simply SKIPPED -- and
    # the trainer scores its holdout through this same function, so the accuracy we publish is
    # the accuracy of exactly this behaviour.
    seen_any = False
    scores = {label: logprior.get(label, 0.0) for label in LABELS}
    for token in tokens(text):
        row = logp.get(token)
        if row is None:
            continue
        seen_any = True
        for label in LABELS:
            scores[label] += row[label]

    if not seen_any:
        return None

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    if ranked[0][1] - ranked[1][1] < MARGIN:
        return UNCERTAIN
    return ranked[0][0]


def info(model):
    """What the UI needs to be honest about the labels it is showing."""
    if not model:
        return {"available": False, "accuracy": None, "per_field": {}, "corpus": {}, "trained_at": None}
    holdout = model.get("holdout", {})
    return {
        "available": True,
        "accuracy": holdout.get("accuracy"),
        "per_field": holdout.get("per_field", {}),
        "attempt_tier_accuracy": holdout.get("attempt_tier_accuracy"),
        "corpus": model.get("corpus", {}),
        "trained_at": model.get("trained_at"),
        "labels": list(LABELS),
    }
