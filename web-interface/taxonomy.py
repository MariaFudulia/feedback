"""Course taxonomy, derived from the real Moodle category tree.

Reads the retrieve-feedback pickle export (categories.p, courses.p,
courses4categories.p, feedbacks.p) from ``config.FEEDBACK_DATA_DIR`` when
present, and builds the cascade

    ciclu -> domeniu -> specializare -> an -> sem -> serie -> curs

by classifying category-tree nodes *by name* (robust to Moodle's varying
depth), scoped to the ACS faculty (``config.FACULTY_CATEGORY_ID``) and to
courses that actually have feedback. When the export is absent it falls back to
a small synthetic dataset faithful to the real shape, so tests / CI / teammates
run without the private data.

STRUCTURE (cascade, course list, series) is REAL. Per-question SCORES, teacher
(titular/asistent) names, and enrolment counts are deterministic-synthetic while the
response contents (feedback_contents/) and enrolled-users (users/) exports are absent.
The seam for real scores is already in place: each offering carries `feedback_ids` (the
join key to feedback_contents/<id>.json), and `_load_content` is the single adapter to
implement -- once it returns data, course_detail / course_students / course_responses /
faculty_average read from it and `content_is_synthetic()` flips, clearing the
'date demonstrative' badge app-wide. Until then everything falls back to the `_hashf`
generators below.
"""

import hashlib
import json
import os
import pickle
import re

import config

CICLU_LABEL = {"L": "Licență", "M": "Master", "P": "Postuniversitar"}

QUESTION_KEYS = ["eval_gen", "preg", "expl_clare", "interes", "comport", "indepl_ob"]
_STRUCT_ORDER = ["ciclu", "domeniu", "specializare", "an", "sem", "serie", "curs"]

# populated at load (from real category names, or the synthetic fallback)
_DOMENIU_LABEL = {}
_SPEC_LABEL = {}

# ---- classification of category-tree node names ---------------------------

_RE_CICLU = [
    (re.compile(r"^Licen[țţ]"), "L"),
    (re.compile(r"^Master"), "M"),
    (re.compile(r"^Postuniversitar"), "P"),
]
_RE_DOMENIU = re.compile(r"^Domeniul\s+(.*?)\s*\(([^)]+)\)\s*$")
_RE_SPEC = re.compile(r"^Specializarea\s+(.*?)\s*\(([^)]+)\)\s*$")
_RE_AN = re.compile(r"^Anul\s+(\d)")
_RE_SEM = re.compile(r"^Semestrul\s+(\d)")
_RE_SERIE = re.compile(r"\(Seria\s+([^)\-]+?)(?:\s*-\s*\d{4})?\)\s*$")
_RE_YEAR = re.compile(r"-\s*(\d{4})\s*\)")
_RE_YEAR_SUFFIX = re.compile(r"\s*\(20\d\d\)\s*$")  # bare trailing year on no-series courses
# Master research/dissertation/specialization-admin codes the real pipeline drops
# (process-feedback/upb/remove_extra; analysis/select_feedback_course_mapping.py).
# Mirrored here so our scope matches the pipeline on the part that IS defined.
_RE_RESEARCH_DENY = re.compile(r"-M-.*-(CSP|CSPED|Cercet[^-]*|ELD|ET|AR)(-|$)")


def _slug(s):
    s = s.lower()
    for a, b in (("ăâ", "a"), ("î", "i"), ("șş", "s"), ("țţ", "t")):
        s = re.sub(f"[{a}]", b, s)
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:48] or "curs"


def _curs_id(ciclu, domeniu, spec, an, sem, denumire):
    """Stable logical-course id: slot + readable slug + a hash of the FULL name.
    The hash guarantees two different names can't collide when the slug is
    truncated (e.g. 'PCLP 2' vs 'PCLP 3'), while identical names in the same
    slot still map to the same id (unifying inconsistent shortnames)."""
    slot = f"{ciclu}-{domeniu}-{spec or '_'}-A{an}-S{sem or '_'}"
    tag = hashlib.md5(denumire.strip().lower().encode("utf-8")).hexdigest()[:6]
    return f"{slot}-{_slug(denumire)}-{tag}"


def _parse_fullname(fullname):
    """'03-ACS-L-A2-S1: Programare orientată pe obiecte (Seria AA - 2024)'
    -> ('Programare orientată pe obiecte', 'AA')."""
    body = fullname.split(":", 1)[1].strip() if ":" in fullname else fullname.strip()
    serie = None
    m = _RE_SERIE.search(body)
    if m:
        serie = m.group(1).strip()
        body = body[: m.start()].strip()
    body = _RE_YEAR_SUFFIX.sub("", body).strip()  # drop a leftover "(2024)" year tag
    return body, serie


def _classify(cat_id, by_cat, dom_labels, spec_labels):
    """Walk a course's category up to the faculty root, reading each node's name.
    Nearest ancestor wins for each dimension."""
    d = {}
    cur, guard = by_cat.get(cat_id), 0
    while cur and guard < 20:
        guard += 1
        n = cur["name"]
        for rx, val in _RE_CICLU:
            if rx.match(n):
                d.setdefault("ciclu", val)
        m = _RE_DOMENIU.match(n)
        if m and "domeniu" not in d:
            d["domeniu"] = m.group(2)
            dom_labels.setdefault(m.group(2), n.replace("Domeniul ", "").strip())
        m = _RE_SPEC.match(n)
        if m and "specializare" not in d:
            d["specializare"] = m.group(2)
            spec_labels.setdefault(m.group(2), n.replace("Specializarea ", "").strip())
        m = _RE_AN.match(n)
        if m:
            d.setdefault("an", int(m.group(1)))
        m = _RE_SEM.match(n)
        if m:
            d.setdefault("sem", int(m.group(1)))
        cur = by_cat.get(cur.get("parent")) if cur.get("parent") else None
    return d


# ---- real loader ----------------------------------------------------------


def _pickles_present(data_dir):
    return all(
        os.path.exists(os.path.join(data_dir, f"{n}.p")) for n in ("categories", "courses", "feedbacks")
    )


def _load_real(data_dir, faculty_id):
    cats = pickle.load(open(os.path.join(data_dir, "categories.p"), "rb"))
    courses = pickle.load(open(os.path.join(data_dir, "courses.p"), "rb"))
    feedbacks = pickle.load(open(os.path.join(data_dir, "feedbacks.p"), "rb"))

    by_cat = {c["id"]: c for c in cats if "id" in c}
    fb_by_course = {}  # course_id -> [feedback_id] (join key to feedback_contents/<id>.json)
    for f in feedbacks:
        if "course" in f and "id" in f:
            fb_by_course.setdefault(f["course"], []).append(f["id"])
    fb_ids = set(fb_by_course)
    fac_prefix = f"/{faculty_id}/"
    dom_labels, spec_labels = {}, {}

    offerings, unresolved, excluded, malformed, years = [], 0, 0, 0, set()
    for c in courses:
        if not ({"id", "shortname", "fullname"} <= c.keys()):  # a bad record must not crash import
            malformed += 1
            continue
        if c["id"] not in fb_ids:
            continue
        cat = by_cat.get(c.get("categoryid"))
        if not cat:
            continue
        path = cat.get("path", "")
        if not (path.startswith(fac_prefix) or path == f"/{faculty_id}"):
            continue
        if _RE_RESEARCH_DENY.search(c["shortname"]):  # master research codes, per pipeline
            excluded += 1
            continue
        d = _classify(c["categoryid"], by_cat, dom_labels, spec_labels)
        if not ({"ciclu", "domeniu", "an"} <= set(d)):
            unresolved += 1
            continue
        denumire, serie = _parse_fullname(c["fullname"])
        ym = _RE_YEAR.search(c["fullname"])
        if ym:
            years.add(int(ym.group(1)))
        spec, an, sem = d.get("specializare"), d["an"], d.get("sem")
        curs = _curs_id(d["ciclu"], d["domeniu"], spec, an, sem, denumire)
        offerings.append(
            {
                "ciclu": d["ciclu"],
                "domeniu": d["domeniu"],
                "specializare": spec,
                "an": an,
                "sem": sem,
                "serie": serie,
                "curs": curs,
                "denumire": denumire,
                "cod": c["shortname"],
                "course_id": c["id"],
                "feedback_ids": fb_by_course.get(c["id"], []),
            }
        )
    year_labels = sorted(f"{y}-{y + 1}" for y in years) or ["2024-2025"]
    stats = {"unresolved": unresolved, "excluded_research": excluded, "malformed": malformed}
    return offerings, dom_labels, spec_labels, year_labels, stats


# ---- synthetic fallback (faithful to the real shape) ----------------------

_SYNTH_DOM_LABELS = {
    "CTI": "Calculatoare şi tehnologia informaţiei (CTI)",
    "IS": "Ingineria sistemelor (IS)",
    "IM": "Inginerie şi management (IM)",
}
_SYNTH_SPEC_LABELS = {
    "AIA": "Automatică şi informatică aplicată (AIA)",
    "AII": "Automatică şi informatică industrială (AII)",
    "IMSA": "Ingineria şi managementul sistemelor de afaceri (IMSA)",
}
_SYNTH_COURSES = [
    "Programarea Calculatoarelor",
    "Analiză Matematică",
    "Structuri de Date",
    "Baze de Date",
    "Sisteme de Operare",
    "Rețele Locale",
    "Proiectarea Algoritmilor",
    "Teoria Sistemelor",
    "Ingineria Reglării Automate",
    "Securitate Aplicată",
]


def _synthetic():
    """Small dataset with the real shape: 3 cicluri, domenii with/without a
    specializare level, years, both semesters, series -> exercises the whole
    cascade without any private data."""
    # (ciclu, domeniu, specializare-or-None, years, series)
    branches = [
        ("L", "CTI", None, [1, 2, 3, 4], ["CA", "CB", "CC"]),
        ("L", "IS", "AIA", [1, 2, 3, 4], ["AA", "AB"]),
        ("L", "IS", None, [1, 2], ["AA", "AB"]),  # IS also has courses directly on the year
        ("M", "CTI", None, [1, 2], ["G"]),
        ("M", "IS", "AII", [1, 2], ["G"]),
        ("M", "IM", "IMSA", [1, 2], ["G"]),
        ("P", "CTI", None, [1], ["G"]),
    ]
    offerings = []
    for ciclu, domeniu, spec, years, series in branches:
        for an in years:
            for sem in (1, 2):
                idx = (an + sem) % len(_SYNTH_COURSES)
                for j in range(2):  # two courses per slot
                    denumire = _SYNTH_COURSES[(idx + j) % len(_SYNTH_COURSES)]
                    for serie in series:
                        curs = _curs_id(ciclu, domeniu, spec, an, sem, denumire)
                        offerings.append(
                            {
                                "ciclu": ciclu,
                                "domeniu": domeniu,
                                "specializare": spec,
                                "an": an,
                                "sem": sem,
                                "serie": serie,
                                "curs": curs,
                                "denumire": denumire,
                                "cod": curs,
                                "course_id": None,
                                "feedback_ids": [],
                            }
                        )
    stats = {"unresolved": 0, "excluded_research": 0}
    return offerings, dict(_SYNTH_DOM_LABELS), dict(_SYNTH_SPEC_LABELS), ["2024-2025"], stats


# ---- content adapter: the seam where real scores plug in ------------------

# A feedback submission ("attempt") is 25 responses read BY POSITION -- the
# processing pipeline maps them by index, never by question text, because the
# titular and asistent blocks reuse identical wording
# [process-feedback/processor.py:208-234]. Slot layout:
_RESPONSE_SLOTS = [
    "course",
    "prof",
    "assist",  # 0-2: discipline + titular name + asistent name
    "eval_overall",
    "expected_grade",
    "load",
    "equipment",
    "part",  # 3-7 course-level
    "prof_know",
    "prof_teach",
    "prof_interact",
    "prof_behave",
    "lecture_doc",  # 8-12 titular
    "assist_know",
    "assist_teach",
    "assist_interact",
    "assist_behave",
    "lab_doc",  # 13-17 asistent
    "assign_time",
    "assign_diff",
    "assign_useful",  # 18-20 course-level
    "positive",
    "negative",
    "difficulty",
    "other",  # 21-24 free text
]
# Likert slots are stored as a raw Moodle option index (1 = top option); the
# pipeline reverses to a 5-is-best scale via `6 - x` [processor.py:355-376].
_LIKERT_SLOTS = {
    "eval_overall",
    "load",
    "equipment",
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
    "assign_diff",
    "assign_useful",
}
# Bridge the real 18-question form onto our 6 QUESTION_KEYS. eval_gen / indepl_ob
# are course-level (no per-teacher split), so every cadru of a course shares them.
_KEY_SLOTS_TITULAR = {
    "eval_gen": "eval_overall",
    "preg": "prof_know",
    "expl_clare": "prof_teach",
    "interes": "prof_interact",
    "comport": "prof_behave",
    "indepl_ob": "assign_useful",
}
_KEY_SLOTS_ASISTENT = {
    "eval_gen": "eval_overall",
    "preg": "assist_know",
    "expl_clare": "assist_teach",  # VERIFY: slot 14 = "activitatea individuală", loose fit for clarity
    "interes": "assist_interact",
    "comport": "assist_behave",
    "indepl_ob": "assign_useful",  # VERIFY: no literal "objectives" question; assign_useful is the closest
}

_NUMERIC_SLOTS = {"expected_grade", "part", "assign_time"}  # kept as-is (not reversed)

# _load_content runs at import; a single malformed/unreadable file must never crash
# startup and defeat the synthetic fallback -- it is skipped and counted instead.
_PARSE_ERRORS = (ValueError, OSError, KeyError, TypeError, AttributeError)


def _likert(raw):
    """Moodle raw option index (1 = top option) -> 5-is-best score, or None if not an int."""
    try:
        return 6 - int(raw)
    except (TypeError, ValueError):
        return None


def _int_or_none(raw):
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _parse_feedback_file(path):
    """Decode one feedback_contents/<id>.json into a list of attempts, each a dict keyed
    by _RESPONSE_SLOTS: Likert slots -> reversed score (6 - rawval), numeric slots -> int,
    name/text slots -> printval. Attempts without exactly 25 responses are skipped -- the
    pipeline's own validity rule [process-feedback/processor.py:615]."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    attempts = []
    for att in data.get("anonattempts", []):
        responses = att.get("responses", [])
        if len(responses) != 25:
            continue
        row = {}
        for i, slot in enumerate(_RESPONSE_SLOTS):
            r = responses[i]
            if slot in _LIKERT_SLOTS:
                row[slot] = _likert(r.get("rawval"))
            elif slot in _NUMERIC_SLOTS:
                row[slot] = _int_or_none(r.get("rawval"))
            else:  # names + free text
                row[slot] = r.get("printval")
        attempts.append(row)
    return attempts


def _parse_users_file(path):
    """Read users/<course_id>.json -> (num_students, {fullname: role}) where role is
    'titular' (Moodle `editingteacher`) or 'asistent' (Moodle `asistent`). Students are
    counted separately (the completion-% denominator) [process-feedback/processor.py:668,684,692]."""
    with open(path, encoding="utf-8") as f:
        users = json.load(f)
    role_of, students = {}, 0
    for u in users:
        shortnames = {r.get("shortname") for r in u.get("roles", [])}
        if "editingteacher" in shortnames:
            role_of[u.get("fullname")] = "titular"
        elif "asistent" in shortnames:
            role_of[u.get("fullname")] = "asistent"
        if "student" in shortnames:
            students += 1
    return students, role_of


def _cadru(nume, tip_default, rows, key_slots, role_of):
    """One cadru row: the mean of each mapped slot over `rows`, plus num_feedback.
    `tip` prefers the users-file role, falling back to which name-slot grouped it."""
    scores = {}
    for key, slot in key_slots.items():
        vals = [r[slot] for r in rows if r.get(slot) is not None]
        scores[key] = round(sum(vals) / len(vals), 2) if vals else 0.0
    return {"nume": nume, "tip": role_of.get(nume, tip_default), "num_feedback": len(rows), **scores}


def _aggregate_course(attempts, students, role_of):
    """Decoded attempts -> {responses, students, cadre}. Cadre are grouped by the titular
    (slot `prof`) and asistent (slot `assist`) names; each gets the mean of its role-specific
    slots plus the course-level eval_gen / indepl_ob (shared by all cadre of the course)."""
    by_titular, by_asistent = {}, {}
    for a in attempts:
        if a.get("prof"):
            by_titular.setdefault(a["prof"], []).append(a)
        if a.get("assist"):
            by_asistent.setdefault(a["assist"], []).append(a)
    cadre = [_cadru(n, "titular", rows, _KEY_SLOTS_TITULAR, role_of) for n, rows in by_titular.items()]
    cadre += [_cadru(n, "asistent", rows, _KEY_SLOTS_ASISTENT, role_of) for n, rows in by_asistent.items()]
    return {"responses": len(attempts), "students": students, "cadre": cadre}


def _load_content(data_dir, offerings):
    """Real per-course feedback content, or None while the export is absent -- the single
    adapter that turns the demonstrative scores real. Reads feedback_contents/<fid>.json
    (responses, via `_parse_feedback_file`) and users/<course_id>.json (roles/enrolment, via
    `_parse_users_file`) for every offering with a course_id, and aggregates to:

        {course_id: {"responses": int, "students": int,
                     "cadre": [{nume, tip, num_feedback, **QUESTION_KEYS}, ...]}}

    Returns `(content, skipped)` where `content` is the dict above or None while the two
    export dirs aren't both present (keeping the synthetic scores and the 'date demonstrative'
    badge on), and `skipped` counts files that couldn't be parsed. Once `content` is non-None,
    `content_is_synthetic()` flips and `course_detail`/`course_students`/`course_responses`/
    `faculty_average` read it (a logical `curs` is summed across its series' course_ids by
    `_content_for`)."""
    contents_dir = os.path.join(data_dir, "feedback_contents")
    users_dir = os.path.join(data_dir, "users")
    if not (os.path.isdir(contents_dir) and os.path.isdir(users_dir)):
        return None, 0
    out, skipped = {}, 0
    for o in offerings:
        cid = o.get("course_id")
        if cid is None:
            continue
        attempts = []
        for fid in o.get("feedback_ids", []):  # merge valid attempts across the course's forms
            fpath = os.path.join(contents_dir, f"{fid}.json")
            if not os.path.exists(fpath):
                continue
            try:
                attempts.extend(_parse_feedback_file(fpath))
            except _PARSE_ERRORS:  # one bad file is a skip, not a startup crash
                skipped += 1
        if not attempts:
            continue
        students, role_of = 0, {}
        upath = os.path.join(users_dir, f"{cid}.json")
        if os.path.exists(upath):
            try:
                students, role_of = _parse_users_file(upath)
            except _PARSE_ERRORS:
                skipped += 1
        out[cid] = _aggregate_course(attempts, students, role_of)
    return (out or None), skipped


def _content_is_generated(data_dir):
    """True when the loaded content export is itself synthetic.

    Content being PRESENT is not the same as content being REAL. The feedback generator
    (generate-feedback/) produces a perfectly well-formed feedback_contents/ + users/
    pair, and without this check loading it would clear the 'date demonstrative' badge
    app-wide -- i.e. the public demo would assert that fabricated scores, teacher names
    and rankings are real. That is the one thing this app must never do.

    FAILS CLOSED. The two mistakes are not symmetric: showing the badge over real data is
    a harmless understatement, while hiding it over fabricated data is the app lying about
    its own numbers. So content counts as real only when something says so, and an export
    that declares ITSELF synthetic can never be promoted -- not even by the env var. That
    ordering matters: a deployment that once served real data keeps FEEDBACK_CONTENT_
    SYNTHETIC=0 set, and the day someone points it at generator output, a manifest that
    could not veto would clear the badge over fabricated scores and invented staff names.

    Precedence:
      manifest says "synthetic": true  -> synthetic. Nothing overrides this.
      FEEDBACK_CONTENT_SYNTHETIC set   -> whatever it says ("0" = real).
      manifest says "synthetic": false -> real.
      no manifest / unreadable one     -> synthetic (provenance unknown).
    """
    declared = _manifest_synthetic(data_dir)
    if declared is True:
        return True
    if config.CONTENT_SYNTHETIC is not None:
        return config.CONTENT_SYNTHETIC != "0"
    if declared is False:
        return False
    return True


def _manifest_synthetic(data_dir):
    """The export's own claim about itself: True, False, or None when it doesn't say.
    An unreadable manifest counts as a claim of 'synthetic' -- we cannot trust what we
    cannot read."""
    try:
        with open(os.path.join(data_dir, "manifest.json"), encoding="utf-8") as f:
            return bool(json.load(f).get("synthetic", True))
    except FileNotFoundError:
        return None
    except _PARSE_ERRORS:
        return True


def _content_for(curs):
    """Merged real content for a logical curs (summed across its series' course_ids),
    or None while no content is loaded -- the single point real scores flow through."""
    if _CONTENT is None:
        return None
    parts = [_CONTENT[o["course_id"]] for o in _OFFERINGS if o["curs"] == curs and o["course_id"] in _CONTENT]
    if not parts:
        return None
    return {
        "responses": sum(p["responses"] for p in parts),
        "students": sum(p["students"] for p in parts),
        "cadre": [row for p in parts for row in p["cadre"]],
    }


# ---- init (once, at import) -----------------------------------------------


def _init():
    global \
        _OFFERINGS, \
        _BY_CURS, \
        _DOMENIU_LABEL, \
        _SPEC_LABEL, \
        _YEARS, \
        _UNRESOLVED, \
        _EXCLUDED, \
        _SOURCE, \
        _CONTENT, \
        _CONTENT_SKIPPED, \
        _CONTENT_GENERATED, \
        _MALFORMED
    data_dir = config.FEEDBACK_DATA_DIR
    if _pickles_present(data_dir):
        _OFFERINGS, _DOMENIU_LABEL, _SPEC_LABEL, _YEARS, stats = _load_real(
            data_dir, config.FACULTY_CATEGORY_ID
        )
        _SOURCE = "real"
    else:
        _OFFERINGS, _DOMENIU_LABEL, _SPEC_LABEL, _YEARS, stats = _synthetic()
        _SOURCE = "synthetic"
    _UNRESOLVED = stats["unresolved"]
    _EXCLUDED = stats["excluded_research"]
    _MALFORMED = stats.get("malformed", 0)
    # None until feedback_contents/ + users/ arrive; skip-count surfaced in consistency_issues
    _CONTENT, _CONTENT_SKIPPED = _load_content(data_dir, _OFFERINGS)
    _CONTENT_GENERATED = _content_is_generated(data_dir)
    _BY_CURS = {}
    for r in _OFFERINGS:
        _BY_CURS.setdefault(r["curs"], r)


# ---- deterministic (synthetic) scores / volumes / staff -------------------

_CADRE_POOL = [
    "Ion Popescu",
    "Maria Ionescu",
    "Andrei Georgescu",
    "Elena Dumitrescu",
    "Radu Vasilescu",
    "Cristina Marin",
    "Mihai Olteanu",
    "Diana State",
    "Bogdan Ursu",
    "Paula Tomi",
    "Giorgiana Vlăsceanu",
    "Matei Belciug",
]


def _h(seed, n):
    return int(hashlib.md5(seed.encode("utf-8")).hexdigest(), 16) % n


def _hashf(seed, lo, hi):
    return lo + (_h(seed, 10_000) / 10_000) * (hi - lo)


def _cadre_for(curs):
    start = _h(curs + "|cadre", len(_CADRE_POOL))
    names = [_CADRE_POOL[(start + i * 5) % len(_CADRE_POOL)] for i in range(2 + _h(curs + "|nc", 4))]
    return [(nm, "titular" if i == 0 else "asistent") for i, nm in enumerate(names)]


def _cadru_scores(year, curs, nume):
    base = _hashf(f"{year}|{curs}|{nume}|base", 3.8, 4.9)
    s = {
        k: round(min(5.0, max(1.0, base + _hashf(f"{year}|{curs}|{nume}|{k}", -0.25, 0.35))), 2)
        for k in QUESTION_KEYS
    }
    s["eval_gen"] = round(base, 2)
    return s


def _course_students(year, curs):
    return int(_hashf(f"{year}|{curs}|studenti", 90, 180))


def _course_responses(year, curs):
    return max(1, round(_course_students(year, curs) * _hashf(f"{year}|{curs}|rate", 0.15, 0.35)))


def _cadru_feedback(year, curs, nume):
    return max(1, round(_course_responses(year, curs) * _hashf(f"{year}|{curs}|{nume}|nf", 0.55, 1.0)))


# ---- cascade engine (reused shape) ----------------------------------------


def _val(rec, dim):
    if dim == "curs":
        return [rec["curs"]]
    v = rec.get(dim)
    return [] if v is None else [v]  # None (no specializare / no serie) is not an option


def _matches(rec, dim, value):
    if value in (None, ""):
        return True
    if dim == "curs":
        return rec["curs"] == value
    return rec.get(dim) is not None and str(rec.get(dim)) == str(value)


def _label(dim, value):
    if dim == "ciclu":
        return CICLU_LABEL.get(value, value)
    if dim == "domeniu":
        return _DOMENIU_LABEL.get(value, value)
    if dim == "specializare":
        return _SPEC_LABEL.get(value, value)
    if dim == "an":
        return f"Anul {value}"
    if dim == "sem":
        return f"Semestrul {value}"
    if dim == "serie":
        return f"Seria {value}"
    if dim == "curs":
        rec = _BY_CURS.get(value)
        return rec["denumire"] if rec else value
    return str(value)


def get_filter_options(selection):
    selection = selection or {}
    out = {}
    for i, dim in enumerate(_STRUCT_ORDER):
        upstream = _STRUCT_ORDER[:i]
        recs = [r for r in _OFFERINGS if all(_matches(r, u, selection.get(u)) for u in upstream)]
        values = []
        for r in recs:
            values.extend(_val(r, dim))
        uniq = sorted(set(values), key=str)
        out[dim] = [{"value": str(v), "label": _label(dim, v)} for v in uniq]
    return out


# ---- public API -----------------------------------------------------------


def data_source():
    """'real' or 'synthetic' -- which structure dataset is loaded."""
    return _SOURCE


def content_is_synthetic():
    """True while scores/teacher names/enrolment are not real -- which is what drives the
    'date demonstrative' badge across the app. Two ways to be synthetic:

      * no content export at all -> the _hashf placeholder generators are in use
      * a content export that is itself GENERATED (generate-feedback), which is
        well-formed but fabricated

    Only a real Moodle export clears the badge. Independent of whether the STRUCTURE is
    real or synthetic."""
    return _CONTENT is None or _CONTENT_GENERATED


def academic_years():
    return list(_YEARS)


def struct_order():
    return list(_STRUCT_ORDER)


def scope_courses(selection):
    selection = selection or {}
    recs = [r for r in _OFFERINGS if all(_matches(r, d, selection.get(d)) for d in _STRUCT_ORDER)]
    year = _YEARS[-1] if _YEARS else "2024-2025"
    seen, out = set(), []
    for r in recs:
        if r["curs"] in seen:
            continue
        seen.add(r["curs"])
        out.append(
            {"curs": r["curs"], "denumire": r["denumire"], "num_studenti": _course_students(year, r["curs"])}
        )
    return out


def course_offering(curs):
    return _BY_CURS.get(curs)


def course_series(curs):
    return sorted({r["serie"] for r in _OFFERINGS if r["curs"] == curs and r["serie"]})


def course_detail(curs, an_universitar="2024-2025"):
    if curs not in _BY_CURS:
        return []
    hit = _content_for(curs)  # real content when loaded, else deterministic synthetic
    if hit is not None:
        return hit["cadre"]
    rows = []
    for nume, tip in _cadre_for(curs):
        rows.append(
            {
                "nume": nume,
                "tip": tip,
                "num_feedback": _cadru_feedback(an_universitar, curs, nume),
                **_cadru_scores(an_universitar, curs, nume),
            }
        )
    return rows


def course_students(curs, an_universitar="2024-2025"):
    hit = _content_for(curs)
    if hit is not None:
        return hit["students"]
    return _course_students(an_universitar, curs)


def course_responses(curs, an_universitar="2024-2025"):
    hit = _content_for(curs)
    if hit is not None:
        return hit["responses"]
    return _course_responses(an_universitar, curs)


def faculty_average(an_universitar="2024-2025"):
    if _CONTENT is not None:
        rows = [row for p in _CONTENT.values() for row in p["cadre"]]
        if rows:
            return {k: round(sum(r[k] for r in rows) / len(rows), 2) for k in QUESTION_KEYS}
    totals, n = dict.fromkeys(QUESTION_KEYS, 0.0), 0
    for curs in _BY_CURS:
        for nume, _ in _cadre_for(curs):
            s = _cadru_scores(an_universitar, curs, nume)
            for k in QUESTION_KEYS:
                totals[k] += s[k]
            n += 1
    return {k: round(totals[k] / n, 2) for k in QUESTION_KEYS} if n else dict.fromkeys(QUESTION_KEYS, 0)


def offer_structure():
    """Real structural counts (NO scores) for the loaded academic year: distinct
    courses in scope, split by ciclu and by domeniu. This is derivable purely
    from the category tree, so it's real even while scores stay demonstrative."""
    year = _YEARS[-1] if _YEARS else "2024-2025"
    seen, per_ciclu, per_domeniu = set(), {}, {}
    for r in _OFFERINGS:
        if r["curs"] in seen:
            continue
        seen.add(r["curs"])
        per_ciclu[r["ciclu"]] = per_ciclu.get(r["ciclu"], 0) + 1
        per_domeniu[(r["ciclu"], r["domeniu"])] = per_domeniu.get((r["ciclu"], r["domeniu"]), 0) + 1
    return {
        "an_universitar": year,
        "source": _SOURCE,
        "total_cursuri": len(seen),
        "total_instante": len(_OFFERINGS),
        "pe_ciclu": [
            {"ciclu": c, "label": CICLU_LABEL.get(c, c), "num_cursuri": n}
            for c, n in sorted(per_ciclu.items())
        ],
        "pe_domeniu": [
            {"ciclu": c, "domeniu": d, "label": _DOMENIU_LABEL.get(d, d), "num_cursuri": n}
            for (c, d), n in sorted(per_domeniu.items())
        ],
    }


def all_offerings():
    return list(_OFFERINGS)


def offering_metrics(an_universitar=None):
    """Per-offering fact rows -- the substrate the deck-view rollups (aggregates.py) group
    over. One row per offering (course_id): the structural dims + content metrics, real from
    `_CONTENT[course_id]` when the export is loaded, else deterministic-synthetic.

    The synthetic per-offering split is sum-preserving per logical curs: a curs's synthetic
    total (`_course_students`/`_course_responses`) is divided across its series-offerings by a
    stable weight, so grouping the rows back by `curs` reproduces the per-curs functions -- no
    contradiction between a Top-10 row and the course-detail page. Real content is already
    per-course_id, so both paths agree.

    row: {course_id, curs, denumire, ciclu, domeniu, specializare, an, sem, serie,
          responses, students, evaluare_curs, cadre:[{nume,tip,num_feedback,**QUESTION_KEYS}]}
    """
    year = an_universitar or (_YEARS[-1] if _YEARS else "2024-2025")
    sibs_of = {}  # curs -> [offering, ...] (its series-offerings; course_id may be None in synthetic)
    for o in _OFFERINGS:
        sibs_of.setdefault(o["curs"], []).append(o)
    rows = []
    for curs, sibs in sibs_of.items():
        # split each per-curs synthetic total across its offerings, seeded by position so it
        # works even when course_id is None (synthetic); real content is per-course_id already.
        weights = [_hashf(f"{curs}|{i}|w", 0.6, 1.4) for i in range(len(sibs))]
        wsum = sum(weights)
        tot_stu, tot_resp = _course_students(year, curs), _course_responses(year, curs)
        for i, o in enumerate(sibs):
            cid = o["course_id"]
            if _CONTENT is not None and cid in _CONTENT:
                c = _CONTENT[cid]
                responses, students, cadre = c["responses"], c["students"], c["cadre"]
            else:
                frac = weights[i] / wsum
                students = max(1, round(tot_stu * frac))
                responses = max(1, round(tot_resp * frac))
                cadre = [
                    {
                        "nume": nm,
                        "tip": tip,
                        "num_feedback": max(1, round(_cadru_feedback(year, curs, nm) * frac)),
                        **_cadru_scores(year, curs, nm),
                    }
                    for nm, tip in _cadre_for(curs)
                ]
            evaluare_curs = round(sum(cd["eval_gen"] for cd in cadre) / len(cadre), 2) if cadre else 0.0
            rows.append(
                {
                    "course_id": cid,
                    "curs": curs,
                    "cod": o["cod"],
                    "denumire": o["denumire"],
                    "ciclu": o["ciclu"],
                    "domeniu": o["domeniu"],
                    "specializare": o["specializare"],
                    "an": o["an"],
                    "sem": o["sem"],
                    "serie": o["serie"],
                    "responses": responses,
                    "students": students,
                    "evaluare_curs": evaluare_curs,
                    "cadre": cadre,
                }
            )
    return rows


def tree():
    """Full valid space as a nested dict for the debug view:
    ciclu -> domeniu -> specializare ('—' if none) -> an -> sem -> [course names]."""
    t = {}
    for r in _OFFERINGS:
        ciclu = CICLU_LABEL.get(r["ciclu"], r["ciclu"])
        domeniu = _DOMENIU_LABEL.get(r["domeniu"], r["domeniu"])
        spec = _SPEC_LABEL.get(r["specializare"], r["specializare"]) if r["specializare"] else "—"
        an = f"Anul {r['an']}"
        sem = f"Sem. {r['sem']}" if r["sem"] else "—"
        node = (
            t.setdefault(ciclu, {})
            .setdefault(domeniu, {})
            .setdefault(spec, {})
            .setdefault(an, {})
            .setdefault(sem, [])
        )
        if r["denumire"] not in node:
            node.append(r["denumire"])
    return t


def consistency_issues():
    """Real-data sanity, not synthetic-completeness. Empty == everything scoped
    resolved cleanly."""
    issues = []
    if _UNRESOLVED:
        issues.append(f"{_UNRESOLVED} feedback courses could not be resolved to ciclu+domeniu+an")
    if _EXCLUDED:
        issues.append(
            f"{_EXCLUDED} master research/dissertation courses excluded "
            "(CSP/CSPED/Cercetare/ELD/ET/AR — mirrors the real pipeline)"
        )
    no_sem = sorted({r["curs"] for r in _OFFERINGS if r["sem"] is None})
    if no_sem:
        issues.append(f"{len(no_sem)} courses have no semester in the category tree")
    if _CONTENT_SKIPPED:
        issues.append(f"{_CONTENT_SKIPPED} feedback/users content files could not be parsed and were skipped")
    if _MALFORMED:
        issues.append(f"{_MALFORMED} course records were missing required fields and were skipped")
    return issues


_init()
