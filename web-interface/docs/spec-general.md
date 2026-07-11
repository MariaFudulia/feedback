
> Project-level spec, maintained by Claudiu (coordination); covers the whole team's work.
>
> This document is what to read **first**: what the interface is, its architecture, the stack
> and the decisions behind it, and who owns what. The deep dive on the **data layer** — how the
> course taxonomy was derived and why — is a companion document,
> [`data-layer-decisions.md`](data-layer-decisions.md), linked from here rather than repeated.
> Borrowed facts carry a source: repo-checkable (`[file]`, `[PR #N]`, `git`) or attributed
> (`[Slack]`, `[deck]`, `[empiric]`).

> **Note (HackMD):** cross-links use repo-relative paths; when both docs live on HackMD, replace
> them with the companion note's HackMD URL — relative links don't resolve across HackMD notes.

---

## 1. Overview & objectives

We build a **web dashboard over the UPB Automatică și Calculatoare (ACS) course-feedback data** —
data already produced by the `cs-pub-ro/feedback` pipeline. The interface only *reads*; it
changes nothing in `retrieve-feedback/`, `process-feedback/`, or the database work
[`docs/index.html`].

The target is fixed: the coordinator's processing **deck**
([Google Slides](https://docs.google.com/presentation/d/1yeyFpKXQoP89euGxUTp3GAwK161xP9yXMiBl95k8MtI/edit?usp=sharing))
is the specification — *"Ideal, așa ceva am obține în urma interfeței web"* [Slack: Răzvan
Deaconescu]. The pages mirror it: a comparative **Sumar**, **Top-10** rankings (cursuri /
titulari / asistenți), completion/evaluation breakdowns, and score-band distributions.

The audience today is a single **admin** role that sees all data and can filter it. The team:
**Claudiu** (data layer + coordination), **Maria** (shell + filters + Sumar), **Vlad**
(rankings + zones) — see §6.

---

## 2. ★ Architecture

### 2.1 One rule: the UI never touches the data source

The whole design rests on a single seam. Every page reads through **`web-interface/queries.py`**
and nothing else — no template or route imports a data source directly. The frontend does not
know, and cannot depend on, where the data actually comes from.

```
┌─────────────┐   ┌───────────────┐   ┌────────────────────────────┐
│ Flask route │──▶│  queries.py   │──▶│  taxonomy.py  (real dumps) │
│  + Jinja    │   │ (the CONTRACT │   │  mocks.py     (deck aggreg)│
└─────────────┘   │   — frozen)   │   └────────────────────────────┘
      ▲           └───────────────┘               │
      │ renders HTML                              ▼
   the browser                     future: SQLite DB (PR #3) swaps
                                    in behind queries.py — no page change
```

Because the contract is frozen (signatures + returned columns), the backend behind it can change
completely — mock → real dumps → eventually the SQLite DB — without touching a single page. This
is exactly what let the data layer be rebuilt entirely (companion §5) with zero changes to
Maria's or Vlad's templates.

> **Note:** The rule is mechanical, not aspirational. `queries.py` never imports Flask, and a
> contract test asserts each function still returns exactly its documented columns
> [`tests/test_contract.py`] — a drift breaks CI immediately.

### 2.2 Request flow

A render is **route → `queries.py` → (`taxonomy.py` for structure / `mocks.py` for deck
aggregates) → Jinja template**. Routes hold only request/session logic; all data logic sits below
the contract. There are **11 view pages** plus three state routes (`/set-filters`,
`/reset-filters`, `/tema`) [`app.py`].

### 2.3 The global filter cascade (the cross-cutting piece)

Every page renders inside a shared shell (`base.html`) whose sidebar is a **session-based,
contradiction-proof filter cascade**: `ciclu → domeniu → specializare → an → sem → serie → curs`
[`app.py` `STRUCT`; `base.html`]. It is the one stateful thing spanning the whole app:

- Filter state lives in `flask.session`; `current_filters()` reads it and a context processor
  injects it into every template [`app.py`].
- `get_filter_options(selection)` returns, for each dimension, only the values reachable given
  the choices already made — the UI can never offer an impossible combination (companion §5.4).
- `set_filters()` re-validates top-down and clears anything a change upstream made illegal;
  `_dim_visible()` reveals a filter only once it has meaning (e.g. specializare appears only for
  a domeniu that has one) [`app.py`].

### 2.4 Honesty as an architectural rule

All of the *content* is placeholder (companion §6), so the UI is **required** to say so.
`templates/_chips.html` provides three badges, answering three independent questions:

| Badge | Question |
|---|---|
| **date reale** | is the *structure* real? (the Moodle category tree) |
| **date demonstrative** | are the *numbers* real? |
| **sentiment estimat** | is this *label* reported, or inferred by a model? |

Two consequences that are load-bearing rather than cosmetic:

**The demo badge fails closed.** It used to mean "no content export is present", and flipped
off the moment any well-formed `feedback_contents/` + `users/` pair appeared. Once we had our
own generator (§4), that became a hole: the generator produces a perfectly valid export of
entirely fabricated numbers and invented staff names, and its mere presence would have cleared
the badge — the app asserting that fake data is real. Content now counts as real only when
someone says so explicitly (`FEEDBACK_CONTENT_SYNTHETIC=0`), and an export that declares
itself synthetic (`manifest.json`) can never be promoted, not even by that variable. No
manifest, or an unreadable one, means synthetic: we do not vouch for data whose provenance
nobody recorded [`taxonomy.py: _content_is_generated`].

**The model badge is not gated on the other two.** It renders unconditionally on
`/comentarii`. When a real export finally lands, the demo badge switches off — and the
sentiment chips would otherwise sit beside real comments with no caveat, at exactly the moment
the caveat matters most.

### 2.5 Who owns which files

| Owner | Files |
|---|---|
| Claudiu (A) | `queries.py`, `taxonomy.py`, `mocks.py`, `config.py`, `db/`, `tests/` |
| Maria (B) | `app.py` (routes + cascade), `base.html`, `sumar.html`, `completare_evaluare.html` |
| Vlad (C) | `pe_ani_de_studiu.html`, `top10_{cursuri,titulari,asistenti}.html`, `evaluare_pe_zone.html` |
| Shared | `_chips.html`, `curs_detaliu.html`, `taxonomie.html`, `static/style.css` |

---

## 3. ★ Stack & rationale

| Choice | Why (constraint, not taste) |
|---|---|
| **Flask + Jinja** | Real per-route auth. Admin-only now, but the long-term plan is public/student access to a *subset* of data without an account; Flask serves public routes and `@login_required` admin routes over the *same* data layer [`docs/index.html`; git `2024e3e`]. Streamlit (the first prototype) has no such notion. |
| **Plain HTML forms** | Filters submit as normal forms (`onchange="this.form.requestSubmit()"`) — zero hand-written JS, nothing to debug on the client [`base.html`]. Sufficient for an admin tool. |
| **htmx (boost)** | Wired: a vendored `htmx.min.js` + `hx-boost` on `<body>` sends those same form/link round-trips over AJAX and swaps the page in place — no reload flash, same server templates, still no JS front-end [`base.html`]. Fragment-level swaps (`hx-target`) remain the approved next step *when needed*; rationale in companion §2.3. |
| **pandas** | Data layer only (`queries.py`/`mocks.py`) — the report functions return DataFrames. |
| **CSS `light-dark()` tokens** | One token table declares every colour's light and dark value side by side, so the two can never drift. The theme picker is a server-rendered radio; the stylesheet keys off `:checked` via `body:has()`, so the switch is instant and there is still **zero hand-written JS** — the strongest example of this table's own thesis [`static/style.css`, `app.py: /tema`]. |
| **naive Bayes (stdlib)** | The sentiment labels on `/comentarii`. No scikit-learn, no numpy: the app's dependencies stay flask + pandas + gunicorn. Trained **offline** (`tools/train_sentiment.py`) and shipped as weights, because the labels live in the generator's `groundtruth/` sidecar — outside what the app reads, and non-existent for a real export. One model **per question**: the same word flips sign between them ("nimic" is good news under *ce trebuie îmbunătățit*, bad news under *aspecte pozitive*), and that split is what exposed the number a pooled model hides — `negative` scores 0.855 where the others reach 0.97. |
| **ruff + pytest** | Lint/format + tests, on every commit (pre-commit) and PR (CI) — §9. |

> **Note:** The Streamlit prototype was deleted once we moved to Flask (nobody had built on it);
> the visual mockup (§7) survives from it as the design target [`docs/index.html`].

---

## 4. ★ Key decisions

| Decision | Rationale | More |
|---|---|---|
| Streamlit → **Flask** | Per-route auth for eventual public access | §3 |
| **Contract-first** (`queries.py` frozen) | Parallel work today + a future DB swap with no page changes | §2.1, §5 |
| **Mock-first** | Build pages against deck-shaped mock data; don't block on real data | §5.1 |
| **Taxonomy from the category tree** | The pipeline's shortname/CSV taxonomy was inconsistent and incomplete; Moodle's category tree is authoritative | companion §4–5 |
| **Real-vs-mock badges** | Never let a reviewer mistake placeholder for measured | §2.4, companion §6 |
| **Own test-data generator** | The existing generator→migrate chain was empirically broken | §8, companion §4.2 |

---

## 5. Data source & contract

### 5.1 What the interface reads *now*

> **Note:** This corrects the earlier plan [`docs/index.html`], which described reading
> `process-feedback/` CSVs. That is no longer accurate.

Two sources sit behind the contract today:

1. **Real course structure**, derived from the raw Moodle **category-tree dumps**
   (`categories.p`, `courses.p`, …) — not from parsing shortnames or reading processed CSVs. This
   is the taxonomy layer; the full story is the companion doc (§4–5). It powers the cascade, the
   course list, series, and the Sumar offer-structure panel.
2. **Deck-sourced aggregates** for the report pages (Sumar evolution, Top-10, zones) — numbers
   transcribed from the coordinator's deck [`mocks.py`], clearly badged demonstrative until the
   real per-course content arrives (companion §6).

### 5.2 The future database (PR #3) — what the contract points at

The intended long-term backend is a SQLite database with a JSON parser for the Moodle feedback
[PR #3, @lakalex, open]. Its schema is the shape the contract anticipates:

```
categories(category_id PK, name, parent_id, path, depth, sortorder)
courses(course_id PK, shortname UNIQUE, fullname, startdate, enddate, category_id)
feedback_instances(instance_id PK, course_id, name, anonymous)
feedback_responses(response_id PK, attempt_id UNIQUE, instance_id,
  prof_name, assist_name, eval_overall, expected_grade, load, equipment,
  part_percent, prof_know, prof_teach, prof_interact, prof_behave, lecture_doc,
  assist_know, assist_teach, assist_interact, assist_behave, lab_doc,
  assign_time, assign_diff, assign_useful,
  positive_text, negative_text, difficulty_text, other_text)
```

When it lands (carrying the data we need), adopting it is an internal change to `queries.py`, not
a UI rewrite (§2.1).

### 5.3 The contract

Every function returns a documented shape; the fixed selection thresholds live *in* these
functions, not the UI: **curs ≥7% & ≥3 feedback-uri · titular ≥7% mediu & ≥15 · asistent ≥10**
[`docs/index.html`; mirrors the pipeline's `analysis/select_*`].

- **Deck aggregates (DataFrames):** `get_summary(nivel=None, track=None)`,
  `get_course_coverage()`, `get_period_breakdown(ciclu=None, semestru=None)`,
  `get_year_breakdown(an, ciclu="L")`,
  `get_top_courses(order_by, ciclu=None, track=None, semestru=None, limit=10)`,
  `get_top_titulari(order_by, limit=10)`, `get_top_asistenti(order_by, limit=10)`,
  `get_score_distribution(entitate)`.
- **Taxonomy / cascade:** `get_academic_years`, `get_struct_order`, `get_filter_options`,
  `get_scope_courses`, `get_course_list`, `get_course_series`, `get_course_detail`,
  `get_course_students`, `get_course_responses`, `get_faculty_average`, `get_taxonomy_issues`,
  `get_taxonomy_tree`.
- **Provenance (the real/synthetic discipline):** `get_offer_structure` (real offer counts),
  `get_data_source` (`"real"`/`"synthetic"` structure), `get_content_is_synthetic` (drives the
  badge — see §2.4 for why it fails closed).
- **Free text + sentiment:** `get_comments_questions`, `get_comments_gate`,
  `get_course_comments`, `get_comment_counts`, `get_sentiment_model_info`.

  Two shape rules here are contract, not implementation detail. Every comment carries a
  `sentiment` key that is **always present and sometimes `None`** — if it vanished when the
  model file is absent, the contract test's assertions would depend on whether an artifact
  happens to be on disk. And `get_course_comments` returns `[]` for a course below the response
  gate: **the gate is enforced in the data layer, not the view**, because `_export_url`
  re-emits every query argument by design and a gate the CSV export can walk around is not a
  gate.

[all in `queries.py`]

---

## 6. ★ The work split

Three areas, one contract between them.

### 6.1 Coleg A — Claudiu (data layer + coordination)

Owns `queries.py`, `taxonomy.py`, `mocks.py`, `config.py`, `db/`, `tests/`. Derives the taxonomy
and implements the contract; keeps repo/branch/CI in order. Full account: the companion doc.

### 6.2 Coleg B — Maria (shell, global filters, Sumar)

Owns the **shell every page renders in** and the **global filter state** — architecturally the
most cross-cutting frontend area, since it touches every page.

- **`base.html`** — the common layout (nav + cascade sidebar). It renders the cascade
  *generically* from `cascade_rows` injected by the context processor, so it needs no per-filter
  code — add a dimension in the data layer and the sidebar picks it up.
- **`app.py` cascade machinery** — `current_filters()` (read session), `build_cascade()` (which
  filters to show, progressively revealed), `_dim_visible()` (reveal rules), `set_filters()`
  (top-down re-validation), `reset_filters()`, and `_coarse_scope()` (bridges the cascade onto
  the deck aggregates' coarser params). This is genuine logic with edge cases — she has a
  dedicated test target (`tests/test_shell.py`, scaffolded).
- **`sumar.html`** — the landing page: a **real** offer-structure panel (`get_offer_structure`,
  badged "date reale") above the deck's year-over-year evolution (badged "date demonstrative").
- **`completare_evaluare.html`** — completion/evaluation per an/semestru.

> **Note:** The cascade shell is scaffolded and working on `develop`; Maria consumes and extends
> it, she does not rebuild it. Her boundary: she never edits `queries.py` — if she needs a new
> parameter, she asks for it.

### 6.3 Coleg C — Vlad (rankings & score zones)

Owns the five ranking/zone pages: `pe_ani_de_studiu.html`, the three `top10_*.html`, and
`evaluare_pe_zone.html`. Architecturally simpler than Maria's area — largely *rendering* a
DataFrame from the contract:

- **Top-10** (cursuri / titulari / asistenți) — sortable by evaluation and by feedback
  percentage; the fixed thresholds (§5.3) are applied in `queries.py` and shown as captions.
- **Evaluare pe zone** — score-band distributions (4–5 / 3–4 / 2–3 / 1–2).
- These pages run on **deck-mock data**, so all carry the "date demonstrative" badge. His routes
  live in Maria's `app.py` and read scope via `_coarse_scope()`; he coordinates with her on that
  one shared file and does not touch `queries.py`.
- Test target: `tests/test_rankings.py` (scaffolded) — locks the thresholds and the sort
  behaviour.

---

## 7. Visual mockup

The pages follow the deck's structure — comparative summary, Top-10 rankings, score-zone
distributions [deck]. The original mockup came from the (deleted) Streamlit prototype and remains
the **visual target**; the real implementation is Flask + Jinja + CSS [`docs/index.html`].

---

## 8. The assignment (Tema): generator + pipeline run

The coordinator's assigned exercise was to generate feedback (Cătălina's `generate-feedback`) and
run the `process-feedback/` scripts (branch `upb`) over it, reporting what we hit. We did, and the
findings are why the data layer took the direction it did.

- The generated forms have **12 questions in English placeholder text**; the processing scripts
  assume **~25 Romanian** questions. `json2csv-file` has `head -25` hardcoded, so with 12
  questions its 25-line window bleeds into the next attempt and rows come out mixed — the same
  over all **9654** generated files [empiric].
- `process_feedback.py` then crashes (`IndexError`/`ValueError`) on the mixed rows.
- We checked whether a fix already existed — **PR #17, #18**. #18 does fix the count (25
  questions), but a **column shift** remains: it adds an extra "evaluare generală" question, so
  the field `process_feedback.py` reads as `eval_overall` is actually the expected grade
  [empiric].
### 8.1 What we did about it — and it shipped

The original plan was to sidestep the broken generator with a small one of our own, emitting
rows directly in the 26-column format `process_feedback.py` reads [`docs/index.html`]. **That
is not what we built,** and the change of direction matters.

When we asked the coordinator for real data he refused, and pointed us back at the same
generator: *"Soluția bună este să actualizați scripturile de generare"* [Slack]. So we fixed it
instead of routing around it, and opened a PR upstream. `generate-feedback/` is now in this
repo.

The root cause of the 12-vs-25 failure turned out to be simpler and worse than a count
mismatch: the generator emitted **12 responses per attempt where both consumers require exactly
25 and skip anything else** — so every file it produced was discarded whole, not partially
used. Four more bugs sat underneath it, each individually silent:

- courses were looked up by `category`, but the Moodle dumps key on `categoryid` — the lookup
  always returned `None`;
- the `Subject` slot carried `fullname (category)` where the real export carries the course
  **shortname**, which is what every join in `analysis/` and `mappings/` uses;
- **every teacher of every course was the string `"Prenume NUME"`** — the whole faculty
  collapsed onto one person, which is what made the Top-10 pages meaningless;
- `courses4categories.p` came back from JSON with **string** keys (JSON has no integer keys),
  so `processor.courses4category(7)` — which swallows the `KeyError` — reported **zero courses
  for every category**.

It also emits Moodle-shaped JSON (`feedback_contents/<id>.json`, 25 slots read by position;
`users/<course_id>.json`), not 26-column CSV, because that is what the *web interface*
consumes and what a real export actually looks like. `slots.py` is the single source of truth
for that contract, and `validate.py` checks an export against both consumers' acceptance rules.

The numbers are no longer uniform noise either: each course, titular and asistent carries a
hidden quality, so the rankings and the selection thresholds (7%/3, 7%/15, 10) actually
discriminate instead of filtering nothing. Details: [`generate-feedback/README.md`].

---

## 9. Git workflow & automation

- Work in the team fork **`MariaFudulia/feedback`**, on **`develop`** (the active UPB branch;
  `master` is behind, from 2021) — not the central `cs-pub-ro/feedback`, not `master`
  [`docs/index.html`].
- Branch per person (`maria-b/…`, `vlad-c/…`, `busuyoc-a/…`); **draft PR early → `develop`**;
  merge when your own page runs on mock without errors — don't wait on the others.
- **pre-commit** runs ruff (check `--fix` + format), scoped to `web-interface/`
  [`.pre-commit-config.yaml`].
- **CI** (`.github/workflows/web-interface-ci.yml`) triggers only on `web-interface/**` changes;
  two jobs — **lint** (`ruff check` + `ruff format --check`) and **test** (`pytest tests/`).
- Branch protection on `develop` (require PR + passing checks, no force-push) is an ask to Maria —
  the team has `Write`, not `Admin`, on the repo [`docs/index.html`].

---

## 10. Current status & roadmap

On `develop`: the taxonomy + cascade + curs-detaliu + offer-structure + badge system
[PR #4, merged], an order-independent test suite [PR #5, merged], the aggregates layer
(rankings, distributions, CSV export, charts, shareable scope), a light/dark/auto theme, the
`/despre-date` page, the `/comentarii` page with an estimated-sentiment model, and — merged in
from our own PR to the generator repo — `generate-feedback/` itself.

**The content export is no longer the blocking dependency.** That was the story for most of
this project's life, and it stopped being true when we fixed the generator (§8): it now emits
exactly the `feedback_contents/` + `users/` pair the app consumes, so realistic content is a
`python3 main.py` away and does not require the coordinator to hand over student data.

What that does **not** mean is that the numbers became real. They are fabricated, and the app
says so — see §2.4 on why importing an export deliberately does *not* clear the badge.

Still open:

- **Real feedback responses.** Refused by the coordinator, and that is the settled answer, not
  a pending one [Slack]. Everything downstream is built to work without them.
- **The noise-filter policy** (~39 non-teaching "courses") — a question to the coordinator.
- **The comments page is new surface the spec never scoped.** The ≥5 response gate and the
  staff-name redaction were choices we made in the absence of any privacy policy in this
  project. If the "part of the data becomes public for students" plan ever happens, raw
  comments are exactly the artifact that decision has to cover.
- Full data-layer status: companion doc §8.

---

## 11. Reproduce it

Every claim here is checkable — grouped by what data it needs.

### Needs nothing (self-contained)

The shortname parser reads the wrong field (companion §4.1) — run it:

```bash
python3 -c "import re; print(re.split('-', '03-ACS-L-CTI-Calculatoare-A2-S1-DEEA-CA')[4])"
# → Calculatoare      (the script treats index [4] as the series; the series is 'CA', at [8])
```

### Needs only a clone — no private data

The interface runs on a **synthetic** dataset whenever the real Moodle export is absent — and
the export is gitignored, so it is never in a clone. This shows the real behaviour with zero
private data:

```bash
cd web-interface
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
flask --app app run --debug        # → http://localhost:5000
```

In the UI:
- Pick **Ciclu = Master** → **An** collapses to 1–2. The cascade cannot offer an impossible
  scope (companion §5.4).
- Open **`/taxonomie`** → the full valid tree, with a data-source banner ("sintetică" here).
- Open **`/comentarii`** → the free-text answers, one question at a time. Most courses here sit
  under the ≥5-response gate and say so; pick a large first-year course to see a populated
  list. **Dificultăți** deliberately carries no sentiment chip — it asks for a *cause*, not an
  opinion, and there is no ground truth for it.
- Open **`/despre-date`** → the three badges, the gate, and the model's per-question accuracy,
  including the weak one.
- Flip the **theme** picker in the sidebar. No page reload, no hand-written JS.

Tests are synthetic too (no private data):

```bash
pytest tests/ -q                       # 141 passing (conftest forces the synthetic dataset)
ruff check . && ruff format --check .
```

### Needs the private export (the coordinator's dumps)

Drop the four pickle files into `web-interface/data/` and the same app loads the **real** ACS
taxonomy. The live counts the companion doc cites are then reproducible:

```bash
python3 -c "import taxonomy as t; print(t.consistency_issues()); \
print('instances:', len(t.all_offerings()), 'distinct:', t.offer_structure()['total_cursuri'])"
# → 887 instances / 627 distinct; 13 excluded, 1 unresolved  (companion §5.3)
```

### Needs the generator + pipeline (the Tema, §8)

The generator→pipeline failure is reproducible in the `generate-feedback` and `process-feedback/`
(branch `upb`) repos: run the generator, then `json2csv-file` + `process_feedback.py`, and
observe the row-mixing / crash described in §8.
