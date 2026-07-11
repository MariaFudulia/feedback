"""The free-text answers: extraction, redaction, and severing them from their author.

Slots 21-24 of every attempt are prose a student typed. `taxonomy._parse_feedback_file`
already decodes them; this module is what turns them into something safe to display, and it
runs at exactly the moment the attempt row is discarded -- so nothing downstream ever holds
the link between a comment and the person who wrote it.

Two protections, both of which have to happen HERE and nowhere else:

1. THE LINKAGE MUST DIE. Moodle's anonymity is per-attempt: it removes the author, not the
   content. Publishing the four answers side by side lets a reader assemble one student's
   whole opinion, and four fragments identify a person far more sharply than one does. So we
   split them into four independent lists.

   Splitting is NOT enough on its own. In attempt order, item #3 of `positive` and item #3 of
   `negative` are still the same student -- the join survives as a position, and it is worse
   than a row because it is invisible. Each list is therefore re-ordered by a hash of its own
   text: deterministic (so pagination is stable across restarts), independent of attempt
   order, and it destroys the positional join.

2. NAMES COME OUT. A comment can name a cadru, and slots 1-2 of the very same attempt carry
   the titular and asistent in plaintext. We strip known FULL names.

   Full names only -- never bare surnames. The synthetic staff pool contains "State", "Marin"
   and "Ursu"; `state` is an ordinary Romanian word and `Marin` is also a given name. A
   surname rule would quietly rewrite student prose, and a false positive here does not look
   like a bug, it looks like evidence. Redaction is defence in depth, not a guarantee:
   misspellings, nicknames and bare surnames survive it, and /despre-date says so.

This module knows nothing about Flask, and nothing about the sentiment model beyond calling
it.
"""

import hashlib
import re
import unicodedata

import sentiment

# The four open questions, in Moodle's own wording (process-feedback/processor.py).
INTREBARI = {
    "positive": "Care sunt aspectele pozitive ale acestei discipline?",
    "negative": "Ce considerați că trebuie îmbunătățit la această disciplină?",
    "difficulty": (
        "După părerea dumneavoastră, dificultatea principală în urmărirea acestei discipline provine din:"
    ),
    "other": (
        "Alte comentarii personale sau sugestii referitoare la activitățile desfășurate "
        "la această disciplină:"
    ),
}
SLOTS = tuple(INTREBARI)

REDACTED = "[cadru didactic]"


def _fold(text):
    """Case- and diacritic-insensitive form, for matching only -- never for display."""
    return unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii").lower()


def _name_patterns(names):
    """Full-name matchers, in both orderings ('Ion Popescu' and 'Popescu Ion').

    Built over the FOLDED text, so 'ION POPESCU' and 'Ioan Popescu'-with-diacritics both hit.
    A name of fewer than two parts is ignored: a single token is a surname, and matching bare
    surnames corrupts prose (see the module docstring).
    """
    patterns = []
    for name in names:
        parts = [p for p in _fold(name).split() if p]
        if len(parts) < 2:
            continue
        for ordering in (parts, list(reversed(parts))):
            patterns.append(re.compile(r"\b" + r"\s+".join(re.escape(p) for p in ordering) + r"\b"))
    return patterns


def redact(text, patterns):
    """Replace full staff names with a placeholder.

    Matching happens on the folded text, but the ORIGINAL is what gets edited: we map the
    match's span back, so diacritics and capitalisation survive everywhere we did not touch.
    Folding is 1:1 on character count for the Romanian letters we care about (NFKD drops
    combining marks, so 'ș' -> 's'), which keeps the spans aligned.
    """
    if not patterns or not text:
        return text
    folded = _fold(text)
    if len(folded) != len(text):
        # A character folded to a different length (rare -- e.g. a ligature). Spans would be
        # off, and a misaligned redaction is worse than none, so fall back to matching on the
        # folded text and returning it. Display loses diacritics; it never loses a name.
        for pattern in patterns:
            folded = pattern.sub(REDACTED, folded)
        return folded

    spans = []
    for pattern in patterns:
        spans += [m.span() for m in pattern.finditer(folded)]
    if not spans:
        return text
    out, last = [], 0
    for start, end in sorted(spans):
        if start < last:  # overlapping matches
            continue
        out.append(text[last:start])
        out.append(REDACTED)
        last = end
    out.append(text[last:])
    return "".join(out)


def _order_key(text):
    """Sort key that depends only on the comment's own text -- see the module docstring."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def build(attempts, role_of=None, model=None):
    """attempts -> {slot: [{"text", "sentiment"}, ...]}, with the author link destroyed.

    `role_of` is the per-course staff roster from users/<course_id>.json; it can be absent
    (the users file is optional), so the titular/asistent names carried in the attempts
    themselves are folded in too -- those are always present.
    """
    names = set(role_of or ())
    for a in attempts:
        for slot in ("prof", "assist"):
            if a.get(slot):
                names.add(a[slot])
    patterns = _name_patterns(names)

    out = {slot: [] for slot in SLOTS}
    for a in attempts:
        for slot in SLOTS:
            text = (a.get(slot) or "").strip()
            if not text:
                continue  # unanswered: both "" and None occur
            text = redact(text, patterns)
            out[slot].append({"text": text, "sentiment": sentiment.classify(model, slot, text)})

    for slot in SLOTS:
        out[slot].sort(key=lambda c: _order_key(c["text"]))
    return out


def merge(parts):
    """Concatenate the comment blocks of a logical course's series, keeping the hash order so
    the merged list does not depend on which offering came first."""
    out = {slot: [] for slot in SLOTS}
    for part in parts:
        for slot in SLOTS:
            out[slot] += part.get(slot, [])
    for slot in SLOTS:
        out[slot].sort(key=lambda c: _order_key(c["text"]))
    return out


def counts(comments):
    """{slot: {total, pozitiv, neutru, negativ, incert}} -- the distribution the page charts."""
    out = {}
    for slot in SLOTS:
        items = comments.get(slot, [])
        row = {"total": len(items)}
        for label in (*sentiment.LABELS, sentiment.UNCERTAIN):
            row[label] = sum(1 for c in items if c["sentiment"] == label)
        out[slot] = row
    return out
