#!/usr/bin/env python3

"""Train the sentiment model from a generator export. Offline; the app never imports this.

    python3 tools/train_sentiment.py --out-dir ../generate-feedback/out

Reads the generator's `groundtruth/sentiment.jsonl` (the labels) and joins it back to
`feedback_contents/<feedback_id>.json` (the text), then fits one multinomial naive Bayes per
question and writes models/sentiment_ro.json. Also emits models/demo_comments.json, a small
labelled corpus the web app falls back to when no content export is present -- without it the
public demo shows an empty comments page and nobody can see the feature.

WHICH LABEL WE TRAIN ON. Each answer carries two:

  * the DRAWN tier -- `fields[<field>].tier`, the bank the words actually came from
  * the attempt's own tier -- the student's underlying opinion

They differ ~10% of the time, because the generator deliberately draws from an adjacent tier
sometimes (real people leave nitpicks in glowing reviews). We train on the DRAWN tier: a
classifier reads text, and the text expresses the bank it was drawn from -- that is the most
it could ever recover. We then report accuracy against BOTH, because they answer different
questions ("can it recover the bank" vs "can it recover the opinion", the latter capped near
90% by that noise). A single accuracy number without saying which one it is means nothing.

`difficulty` is skipped entirely: it asks for a cause, not an opinion, and carries no tier.
"""

import argparse
import collections
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sentiment  # noqa: E402  -- the tokenizer MUST be the one the app uses, never a copy

SMOOTHING = 1.0
DEMO_CORPUS_SIZE = 400


def load_corpus(out_dir):
    """-> [{"field", "text", "label", "attempt_label"}] for the three labelled questions."""
    truth_path = os.path.join(out_dir, "groundtruth", "sentiment.jsonl")
    contents_dir = os.path.join(out_dir, "feedback_contents")
    if not os.path.exists(truth_path):
        raise SystemExit(
            f"no labels at {truth_path}\n"
            f"Run the generator first (it writes groundtruth/ unless --no-truth was passed)."
        )

    slot_index = {"positive": 21, "negative": 22, "other": 24}
    rows, seen, files = [], set(), {}
    for line in open(truth_path, encoding="utf-8"):
        rec = json.loads(line)
        key = (rec["feedback_id"], rec["attempt"])
        if key in seen:
            # main.py dedupes feedback ids (feedbacks.p lists a few twice); if that ever
            # regresses, the same answer would be trained on twice. Catch it here.
            raise SystemExit(f"duplicate label for {key} -- the generator emitted an attempt twice")
        seen.add(key)

        fid = rec["feedback_id"]
        if fid not in files:
            path = os.path.join(contents_dir, f"{fid}.json")
            files[fid] = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else None
        doc = files[fid]
        if not doc:
            continue
        try:
            responses = doc["anonattempts"][rec["attempt"]]["responses"]
        except IndexError:
            continue

        attempt_label = sentiment.TIER_TO_LABEL[rec["tier"]]
        for field, idx in slot_index.items():
            meta = rec["fields"].get(field)
            if not meta or "tier" not in meta:  # difficulty carries {"cause": ...}, no tier
                continue
            text = (responses[idx].get("printval") or "").strip()
            if not text:
                continue
            rows.append(
                {
                    "field": field,
                    "text": text,
                    "label": sentiment.TIER_TO_LABEL[meta["tier"]],  # the DRAWN tier
                    "attempt_label": attempt_label,
                }
            )
    return rows


def fit(rows):
    """Multinomial naive Bayes with Laplace smoothing, for one question."""
    counts = {label: collections.Counter() for label in sentiment.LABELS}
    docs = collections.Counter()
    for r in rows:
        docs[r["label"]] += 1
        counts[r["label"]].update(sentiment.tokens(r["text"]))

    vocab = sorted({t for c in counts.values() for t in c})
    total = sum(docs.values())

    logprior = {label: math.log(docs[label] / total) if docs[label] else -30.0 for label in sentiment.LABELS}
    denom = {label: sum(counts[label].values()) + SMOOTHING * len(vocab) for label in sentiment.LABELS}
    logp_unseen = {
        label: math.log(SMOOTHING / denom[label]) if denom[label] else -30.0 for label in sentiment.LABELS
    }
    logp = {}
    for token in vocab:
        logp[token] = {
            label: round(math.log((counts[label][token] + SMOOTHING) / denom[label]), 4)
            for label in sentiment.LABELS
        }
    return {
        "logprior": {k: round(v, 4) for k, v in logprior.items()},
        "logp_unseen": {k: round(v, 4) for k, v in logp_unseen.items()},
        "logp": logp,
    }


def score(model, rows, key="label"):
    """Accuracy, counting a declined label ('incert'/None) as wrong -- the UI shows no chip
    there, so it is a miss from the reader's point of view. No free lunch."""
    if not rows:
        return None
    hits = sum(1 for r in rows if sentiment.classify(model, r["field"], r["text"]) == r[key])
    return round(hits / len(rows), 3)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out-dir", default="../generate-feedback/out", help="a generator output dir")
    p.add_argument("--model", default="models/sentiment_ro.json")
    p.add_argument("--demo-corpus", default="models/demo_comments.json")
    p.add_argument("--seed", type=int, default=1234)
    p.add_argument("--holdout", type=float, default=0.2)
    args = p.parse_args()

    rows = load_corpus(args.out_dir)
    if not rows:
        raise SystemExit("no labelled answers found")
    rng = random.Random(args.seed)
    rng.shuffle(rows)

    by_field = collections.defaultdict(list)
    for r in rows:
        by_field[r["field"]].append(r)

    fields, per_field, per_field_attempt = {}, {}, {}
    train_all, test_all = [], []
    for field in sentiment.FIELDS:
        frows = by_field.get(field, [])
        if not frows:
            continue
        cut = int(len(frows) * (1 - args.holdout))
        train, test = frows[:cut], frows[cut:]
        fields[field] = fit(train)
        train_all += train
        test_all += test

    model = {
        "schema": sentiment.SCHEMA,
        "trained_by": "tools/train_sentiment.py",
        "corpus": {
            "source": "generate-feedback groundtruth/sentiment.jsonl (SYNTHETIC)",
            "answers": len(rows),
            "per_field": {f: len(by_field[f]) for f in sorted(by_field)},
            "label": "drawn tier (the phrase bank the words came from)",
        },
        "labels": list(sentiment.LABELS),
        "fields": fields,
    }

    for field in fields:
        test = [r for r in test_all if r["field"] == field]
        per_field[field] = score(model, test)
        per_field_attempt[field] = score(model, test, key="attempt_label")

    model["holdout"] = {
        "split": args.holdout,
        "seed": args.seed,
        "n": len(test_all),
        "accuracy": score(model, test_all),
        "per_field": per_field,
        # against the student's underlying opinion rather than the bank -- structurally
        # capped near 0.90 by the generator's deliberate 10% adjacent-tier noise
        "attempt_tier_accuracy": score(model, test_all, key="attempt_label"),
        "attempt_tier_per_field": per_field_attempt,
        "note": (
            "Synthetic holdout. Measures performance on text like the training text. Real "
            "student prose is out of distribution and will score worse; we have no labelled "
            "real data to say by how much."
        ),
    }

    os.makedirs(os.path.dirname(args.model), exist_ok=True)
    with open(args.model, "w", encoding="utf-8", newline="\n") as f:
        json.dump(model, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")

    # The demo corpus: what the app shows when there is no content export at all. Quota per
    # question, so every section of /comentarii has something in it -- a plain shuffle-and-cut
    # starves `difficulty`, whose phrase bank is much smaller than the others'.
    pool = collections.defaultdict(list)
    for r in rows:
        pool[r["field"]].append({"field": r["field"], "text": r["text"], "label": r["label"]})
    for text in _difficulty_texts(args.out_dir):
        pool["difficulty"].append({"field": "difficulty", "text": text, "label": None})

    quota = DEMO_CORPUS_SIZE // 4
    demo = []
    for field in ("positive", "negative", "difficulty", "other"):
        items = pool[field]
        rng.shuffle(items)
        demo += items[:quota]
    rng.shuffle(demo)
    with open(args.demo_corpus, "w", encoding="utf-8", newline="\n") as f:
        json.dump(
            {
                "synthetic": True,
                "note": "Fabricated comments from generate-feedback. Not written by students.",
                "comments": demo,
            },
            f,
            ensure_ascii=False,
            indent=1,
        )
        f.write("\n")

    holdout = model["holdout"]
    print(f"corpus: {len(rows)} answers  {model['corpus']['per_field']}")
    print(f"holdout accuracy (drawn tier)   : {holdout['accuracy']}   {per_field}")
    print(f"holdout accuracy (student tier) : {holdout['attempt_tier_accuracy']}   {per_field_attempt}")
    print(f"wrote {args.model} and {args.demo_corpus} ({len(demo)} demo comments)")
    return 0


def _difficulty_texts(out_dir):
    """difficulty answers -- they belong in the demo corpus but never in training: the question
    asks for a cause, not an opinion, and the corpus carries no sentiment label for it."""
    contents_dir = os.path.join(out_dir, "feedback_contents")
    out = []
    for name in sorted(os.listdir(contents_dir))[:200]:
        doc = json.load(open(os.path.join(contents_dir, name), encoding="utf-8"))
        for att in doc["anonattempts"]:
            text = (att["responses"][23].get("printval") or "").strip()
            if text:
                out.append(text)
    return out


if __name__ == "__main__":
    sys.exit(main())
