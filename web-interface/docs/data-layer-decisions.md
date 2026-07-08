 # Feedback Web Interface — Data Layer: Decisions, Investigation & Sources

> Author: Claudiu Busuioc (Coleg A — data layer).
>
> This document records **why** the data layer is built the way it is: the mandate, the
> options weighed, the evidence behind each decision, and the source for every borrowed fact.
> It is written to be checked — repository and PR references can be verified directly against
> the codebase. Source tags are either *repo-checkable* (`[file]`, `[PR #N]`,
> `[oficial: …]`) or *provenance-attributed* (`[Slack]`, `[deck]`, `[empiric: …]`).
>
> Runnable reproductions of the key claims are collected in the companion general spec
> ([`spec-general.md`](spec-general.md), §11 "Reproduce it").

---

## 1. Context & mandate

### 1.1 The project we joined

The `cs-pub-ro/feedback` repository automates the **retrieval, processing, and presentation of
student feedback** collected through the UPB Moodle instance of the **Automatică și
Calculatoare** faculty — abbreviated **ACS** in the data (the `acs.curs.pub.ro` host, the
`03-ACS-` shortname prefix, and the `03. Automatică şi Calculatoare` category root)
[`README.md`; `categories.p`]. It is not a single program but a pipeline of stages, each in its
own top-level directory [repo structure]:

- `retrieve-feedback/` — pulls raw data from Moodle via its web-service API (courses,
  categories, feedback forms, enrolled users).
- `process-feedback/` — turns raw feedback into per-course / per-teacher statistics.
- `analysis/`, `mappings/`, `statistics/`, `summarize/` — selection thresholds, enrolment
  maps, and aggregate reports built on top of the processed data.

The pipeline's existing "presentation" step is a batch export: it fans the processed data out
into a large tree of static Excel files. There was no interactive way to explore the results.

### 1.2 The mandate given to our sub-team

Our task, set by the coordinator (Răzvan Deaconescu), was to design a **web interface** over
this feedback data [Slack: #cdl-project-feedback]. The target was made explicit: the
coordinator's processing **deck** ([Google Slides](https://docs.google.com/presentation/d/1yeyFpKXQoP89euGxUTp3GAwK161xP9yXMiBl95k8MtI/edit?usp=sharing))
— the slide presentation of aggregated feedback — is the specification. In his words,
*"Ideal, așa ceva am obține în urma interfeței web pe care voi o veți proiecta"*
[Slack: #cdl-project-feedback, Răzvan Deaconescu]. So the deck's tables and charts — summary by
year, top-10 courses / teachers, score distributions, completion rates — are the pages we owe.

There are **two documents** by design. The team's **general spec** — a companion document
([`spec-general.md`](spec-general.md)) — frames the overall project: objectives, architecture,
stack, the data contract, the visual mockup, and the split of work across the three of us.
**This document is the deep dive on the data layer**, which grew enough to warrant its own
writeup (§1.4). Where the two overlap, they cross-reference rather than repeat. The general
spec also records a forward-looking objective — eventual **public, per-student access** to the
interface — discussed here in §2.2.

### 1.3 The starting position

Two facts about the starting position shaped everything after.

1. **The interface was greenfield, but the data was not ours.** The pages we had to build all
   consume *processed feedback* — scores, counts, taxonomy — which is the output of a pipeline
   maintained by a separate effort. Our layer sits downstream of code we did not own.
2. **Nothing forced us to wait.** We deliberately started against **mock data** shaped to the
   deck, behind a frozen contract (`queries.py`), so the three of us could build pages in
   parallel without blocking on the real database [`web-interface/README.md`]. The governing
   rule — *Flask routes import only from `queries.py`, never from `mocks.py` directly* — is
   what later let the data layer's internals change completely without touching anyone else's
   pages.

### 1.4 Why this became more than a UI

On paper, the remaining work was layout and filters. In practice, making the filters *correct*
required a reliable model of ACS's course taxonomy — and establishing that model turned out to
be the substance of the data-layer work, because the handed-over pipeline did not expose one
cleanly. Sections 3–5 document that investigation and the decisions it forced.

> **Note:** This is the point where the data layer stopped being a thin adapter and became its
> own piece of engineering. That growth was a response to evidence (§4), not scope creep — a
> distinction §7 returns to when discussing overlap with the refactoring team.

---

## 2. Technology stack & rationale

The stack was not chosen up front and kept; it moved as the constraints became clear. The
sequence — Streamlit → Flask + Jinja, with HTMX reserved for later — is itself a record of
those constraints.

### 2.1 Streamlit first, for speed

We began on **Streamlit** [git: `5ca611a` "add Streamlit scaffold"]. For an early prototype it
is the fastest way to put charts and filters on screen: no routing, no templates, no front-end
code. It let us stand up something shaped like the deck and validate the page inventory
quickly.

### 2.2 The move to Flask, forced by a real requirement

Streamlit was dropped for **Flask + Jinja** [git: `2024e3e` "replace Streamlit scaffold with
Flask"]. The deciding constraint was **role-based access control**. The intended model is
asymmetric: the **admin** view — the only role today — sees *everything* (all courses, all
cadre, all scores); the **planned public/student** access sees only a *subset* of the data, and
without an account. This split is the coordinator's long-term intent, recorded in the general
spec. Streamlit has no real notion of per-route authentication; Flask does — public routes
without auth, admin routes behind `@login_required`, both over the *same* data layer, so the
role split never forces a rewrite of `queries.py` [general spec §3].

> **Note:** This is also why the data layer is a plain Python module with no web-framework
> imports (`queries.py`): public and admin routes both call the same functions, so the auth
> split never reaches the data. The stack decision and the contract decision (§1.3) are the
> same decision seen from two sides.

### 2.3 Jinja + plain forms now, HTMX reserved for later

The current UI is **server-rendered Jinja templates with plain HTML forms** — filters submit
with a full page reload (`onchange="this.form.submit()"`) [`web-interface/templates/base.html:19,29`].
This is deliberate: no hand-written JavaScript, nothing to debug on the client, and it is
entirely sufficient for an admin tool today.

**HTMX** is recorded as the approved path for *later* interactivity, not a dependency taken on
now. The reasoning:

- **It fits the model we already have.** HTMX adds interactivity by letting the *server* return
  HTML fragments in response to element-level events, driven by HTML attributes (`hx-get`,
  `hx-target`) — no client-side state, no JSON API, no separate front-end build. Our pages are
  already server-rendered HTML behind `queries.py`; HTMX layers onto that without inverting it.
- **It respects the "no hand-written JS" constraint.** The alternative interactive path — a JS
  front-end calling a JSON API — would force us to build and maintain that API and duplicate the
  rendering logic on the client. HTMX avoids both.
- **Concrete example of where it slots in.** The sidebar cascade currently reloads the whole
  page every time you pick a `ciclu` or `domeniu`. With HTMX, that same `<select>` would
  `hx-post` to `/set-filters` and swap only the filter panel and the results region back in —
  the exact same server code and templates, just returning a fragment instead of a full page.

> **Note:** HTMX is intentionally *not* wired yet — `base.html` has no `hx-*` attributes.
> Adopting it is a scoped, later change, chosen precisely so that when interactivity matters we
> do not have to re-architect toward a JS front-end.

---

## 3. Why an independent data layer was required

### 3.1 The filters are the product, and correct filters need a taxonomy

The feature the laboranți and Răzvan reacted to in the mockup is the **filtering**: narrowing
feedback by ciclu → domeniu → specializare → an → semestru → serie → curs → cadru didactic. For
those filters to be trustworthy they must be **contradiction-proof** — the UI must never offer
a combination that cannot exist. You should not be able to select *Master, anul 4* when a
master programme has two years, or a *direcție* in a year where none branch.

Guaranteeing that requires a model of ACS's actual offering structure: which cicluri exist,
which domenii sit under each, where specializări branch, how many years each has. That model is
the taxonomy. Without it, filters are either wrong (they offer impossible scopes) or hard-coded
(and stale the moment the offering changes).

### 3.2 So the question became: where does the taxonomy live?

The taxonomy is not in the feedback responses — a submitted feedback row carries scores and
free text, not "this is a year-3 CTI course." It has to come from the *course metadata* the
pipeline retrieves. So before writing a single filter, the real task was to find where, in the
handed-over code and data, that structure is reliably encoded, and to confirm it could be
consumed cleanly. Section 4 is what that search found.

### 3.3 Designed with the future database in mind

The independence of the data layer is also a deliberate bet on a **future database
integration**, not just a reaction to the present. A separate open PR proposes exactly that
backend — a SQLite database plus a JSON parser for the Moodle feedback [PR #3, "SQLite database
+ JSON parser", @lakalex, open]. That is why the layer sits behind a single frozen contract
(`queries.py`, §1.3): whichever backend ends up filling it — today's derived model, tomorrow's
SQLite DB, or the pipeline's processed output — only the *internals* of `queries.py` change, and
no page is touched. Modelling the data this way means adopting the real database later (once it
carries the data we need — §4.2) is an internal swap, not a UI rewrite. The shape of the layer
is chosen for that integration.

---

## 4. Options evaluated and rejected

Three plausible sources of ground truth were available. Each was evaluated and set aside on
evidence — and the evidence is what pointed to the fourth option (§5).

### 4.1 Parsing the course shortname — rejected: internally inconsistent

The processing scripts encode taxonomy in the course *shortname*
(e.g. `03-ACS-L-CTI-Calculatoare-A2-S1-DEEA-CA`). Reading how they actually parse it surfaced
two problems:

- **Domain (CTI vs IS) is not parsed — it is guessed from a hard-coded list.** `separate_acs`
  decides a course's domain by testing its series code against a fixed list of ~20 codes
  [`process-feedback/separate_acs:34`]. That list is replicated in other scripts
  [`process-feedback/make_per_series`, `statistics/num_courses_per_group`], and the copies are
  not identical — so "what domain is this course" can have different answers depending on which
  script you ask.
- **The series is read by fixed position, on a layout the documented one contradicts.**
  `select_courses_series.py` takes the series as the 5th dash-separated segment — `re.split("-",
  c)[4]` [`analysis/select_courses_series.py:16`]. That is correct only for a *flat* 5-segment
  shortname with no domain and no course-name segment.

  Concretely, splitting the documented shortname on `-` gives:

  ```
  03-ACS-L-CTI-Calculatoare-A2-S1-DEEA-CA
   0   1  2   3       4       5  6   7    8
  ```

  so `[4]` is `"Calculatoare"` (the course-name segment) — not `"CA"`, the series at `[8]`. The
  parser reads the wrong field for any shortname that carries a domain and/or name segment,
  which the documented format does.

  > **→ Try this** (needs nothing): `python3 -c "import re; print(re.split('-',
  > '03-ACS-L-CTI-Calculatoare-A2-S1-DEEA-CA')[4])"` → prints `Calculatoare`, not the series.

> **Note:** A dimension the interface needs — the *direcție* (the year-3/4 branch within a
> domain) — is not captured anywhere in the pipeline at all. There was no field to read even if
> the parsing had been clean.

Building contradiction-proof filters on a source that disagrees with itself, and omits a
dimension outright, was not viable.

### 4.2 The fixture pipeline (generate → migrate → DB) — rejected: empirically broken

The plan-of-record for real data was to generate synthetic feedback with an existing generator
and load it into a SQLite database via an open PR's migration script [PR #3, "SQLite database +
JSON parser", open]. I evaluated this by running it end to end rather than reasoning about it.

- The generator emits feedback forms with roughly **12 questions in English placeholder text**;
  the processing/migration code matches on the **~25 Romanian** question strings it expects. The
  formats do not line up.
- Run through the migration, the result was **878 rows migrated with zero numeric scores set** —
  the fields the interface needs (evaluare etc.) were never populated [empiric: ran the
  generator output through the migration].
- The two open PRs on the generator at the time [PR #17, PR #18, both open, both
  "generate feedback"] were still in flux and did not close the format gap this path depended on.

Dropping this chain was therefore backed by an end-to-end run, not a guess. (This is the
`migrate.py` → SQLite path specifically; the *same* generator was also run through the classic
`process_feedback.py` path — the coordinator's assigned Tema — and broke identically on the same
12-vs-25 mismatch, over all 9654 generated files. That parallel run is documented in the general
spec §8.)

### 4.3 Verifying against the live Moodle — rejected: not reachable

The remaining way to establish ground truth was to look at the live system directly. The
repository's own connection template points at `https://acs.curs.pub.ro/2019`
[`retrieve-feedback/moodle.template.conf:2`]. That URL did not respond on repeated attempts
[empiric], so it could not be used to verify a single shortname or category. The recorded
endpoint was simply not reachable, which took this option off the table.

### 4.4 What the evidence pointed to

The scripts' taxonomy was internally inconsistent and missing a dimension; the "just load the
DB" path was empirically broken; and there was no live system to check against. The common
thread: all three tried to *derive* taxonomy from lossy or unreachable sources. The evidence
pointed toward obtaining the **raw, authoritative source** and deriving the model directly — §5.

---

## 5. The adopted solution: the Moodle category tree

### 5.1 Getting the authoritative source

The unlock was requesting the **raw Moodle dumps** the retrieval scripts produce, rather than
any downstream artifact. Răzvan provided a recent export — the pickled outputs of
`retrieve-feedback/` (`categories.p`, `courses.p`, `courses4categories.p`, `feedbacks.p`)
[Slack: #cdl-project-feedback]. These are the direct API dumps, upstream of all the lossy
processing in §4.

### 5.2 The insight: the category tree is clean where the shortname is not

Inspecting `categories.p` showed that Moodle already stores the taxonomy as a **category tree**
with self-describing node names:

```
03. Automatică şi Calculatoare
 └─ Licenţă
     └─ Domeniul Calculatoare şi tehnologia informaţiei (CTI)
         └─ Specializarea …
             └─ Anul 2
                 └─ Semestrul 1
                     └─ <courses>
```

Every level names itself — `Domeniul … (CTI)`, `Specializarea … (AIA)`, `Anul 2`,
`Semestrul 1`. This is the structure the shortname only encodes indirectly (and
inconsistently, §4.1). Reading it directly removes the guessing: domain is a labelled node, not
a whitelist lookup.

### 5.3 The method: classify nodes by name, walk to the root

For each course that has a feedback form, walk from its category up to the faculty root and read
each ancestor's name against a small set of patterns — `Licenţă/Master/Postuniversitar` →
ciclu, `Domeniul … (X)` → domeniu, `Specializarea … (X)` → specializare, `Anul N` → an,
`Semestrul N` → sem [`web-interface/taxonomy.py`, `_classify`]. Course name and series come from
the course `fullname`, not the shortname.

For example, the course `03-ACS-L-CTI-A4-S1-Bdd-C3` (`categoryid` 1032) resolves by walking its
category chain to the faculty root [`categories.p`; reproducible over the export]:

```
1032  Seria C3
1029  Semestrul 1
1028  Anul 4
 977  Domeniul Calculatoare şi tehnologia informaţiei (CTI)
  22  Licenţă
   7  03. Automatică şi Calculatoare
```

Read as labelled nodes, that is **Licență · CTI · Anul 4 · Semestrul 1** — every structural
dimension named, nothing guessed. The course name and series come from the `fullname`
(`Baze de date distribuite (Seria C3 …)`), so the model does not depend on the shortname at all.

- **Result (reproducible over the export):** of the ACS courses that have feedback, all but
  **one** classify cleanly to ciclu + domeniu + an — the single exception is a genuine Moodle
  mis-filing (§8.2), surfaced rather than hidden. After the deliberate policy exclusion of **13**
  master-research courses (§7.3), the loaded model holds **887 course-instances (627 distinct
  courses)** [`taxonomy.consistency_issues()`; `taxonomy.offer_structure()`].
- **Bonus:** because the category tree is authoritative, this *repairs* the shortname
  inconsistencies the old parsers suffered — e.g. `L-IS-A4-S1-SCR` and `L-IS-AIA-A4-S1-SCR` (the
  same course written two ways) unify correctly under one category node.

### 5.4 The model, and why it is safe to build on

The derived structure is `ciclu → domeniu → specializare → an → sem → serie → curs`, with
specializare optional (some domenii branch into named programmes, some attach years directly).
The cascade computes each filter's options from the real combination space, so a contradictory
scope is unreachable by construction [`web-interface/taxonomy.py`, `get_filter_options`].

> **Note:** To keep the interface runnable by teammates and CI *without* the private export, an
> equivalent **synthetic dataset** faithful to this shape is generated when the real dumps are
> absent [`web-interface/taxonomy.py`, `_synthetic`; `web-interface/tests/conftest.py` forces it
> under test]. Same code paths, no private data required.

---

## 6. Data provenance: real vs. synthetic

A reader — and a reviewer — should know exactly which numbers are measured and which are
placeholders. The split is deliberate and made visible in the UI.

### 6.1 What is real

The **structure** is real, from the category tree (§5): the cascade, the course list, the
series, and the offer counts on the summary page — all derived from the provided export.

### 6.2 What is synthetic, and why

The **content** — per-question scores, cadru names (titular/asistent), enrolment counts — is
**not** in the export we have. The zip is explicitly structure-only (`no-feedback-contents`): it
lacks `feedback_contents/` (the responses) and `users/` (roles/enrolment). Until those arrive,
those numbers are generated **deterministically** from the real course id
[`web-interface/taxonomy.py`, the `_hashf` generators] — stable and plausible, but placeholders.

Two distinct sources of placeholder data exist, and they are different things:

1. **Deck-sourced aggregates.** The report pages (summary, top-10, zones) render numbers
   hand-transcribed from the coordinator's reference **deck** [`web-interface/mocks.py` module
   docstring; deck de referință] — deck-accurate where a slide was legible.
2. **Deterministic synthetic scores.** The per-course detail page's scores/cadre are generated
   from the course id, as above.

### 6.3 The seam where real scores plug in

The swap to real scores is a **single, documented adaptor**, not a rewrite. Each course already
carries its `feedback_ids` (the join key to `feedback_contents/<id>.json`), and `_load_content`
is the one function to implement when the content export arrives; once it returns data, the four
content functions read it and the "date demonstrative" badge clears automatically
[`web-interface/taxonomy.py`, `_load_content` / `content_is_synthetic`]. A test exercises this
routing with an injected payload [`web-interface/tests/test_contract.py`].

### 6.4 Honesty made visible: the badge discipline

Every page that shows placeholder numbers carries a **"date demonstrative"** badge; the one
panel that is real structure carries **"date reale"** [`web-interface/templates/_chips.html`].
This is a rule, not decoration: a reviewer opening "Top-10 titulari" sees at a glance that the
ranking is illustrative and cannot mistake a placeholder for a measurement.

---

## 7. Coordination with the refactoring team

A separate effort is refactoring the processing pipeline. Because our data layer grew (§3–5), it
is worth being precise about where the two touch — and where they do not.

### 7.1 Why the layer grew, restated as a decision

We did not stop at "consume the pipeline and render it" because, on the evidence of §4, there was
nothing clean to consume: the taxonomy in the scripts was inconsistent and incomplete, and the DB
path was empirically broken. Deriving the taxonomy from the raw dumps was the option the evidence
left standing. The growth is a consequence of that evidence, not appetite.

### 7.2 Why we did not simply adopt the other teams' work

- **The SQLite DB (PR #3).** Attractive on paper — a real schema to query. But the chain that
  fills it is the one that produced 878 rows with no scores (§4.2), and the PR is still open
  [PR #3, open]. Adopting it would have coupled us to a schema that did not yet carry the data we
  need. We read the raw dumps directly instead — already produced, and stable.
- **The `analysis/` refactor (PRs #22, #23).** We checked these against our dependencies rather
  than assuming. PR #23 refactors all of `analysis/` and states it changes no behaviour; we
  verified that on the parts we mirror — the selection thresholds and the master-research denylist
  are equivalent (the diff is `re.match("x", c)` → `re.match(r"x", course)`), and it does not
  touch `retrieve-feedback/`, which is what we actually read [PR #23]. PR #22 adds a README and
  asserts no competing taxonomy model [PR #22]. Neither interferes with us.

### 7.3 The real coupling points

Two, and only two, genuine coupling points exist:

1. **A duplicated rule.** Our loader mirrors the pipeline's master-research course exclusion
   (`CSP`/`CSPED`/`Cercetare`/`ELD`/`ET`/`AR`) so our scope matches theirs; the source is cited
   in-code [`web-interface/taxonomy.py`]. It is in sync today; a future change on their side would
   need to be reflected on ours. Documenting it turns a silent drift into a traceable one.
2. **The future content schema.** When we wire real scores (§6.3), we will consume either their
   `feedback_contents/` + `users/` or their processed output. That schema is theirs; a change to
   it would reach us. It does not exist for us yet.

### 7.4 What this means for the coordinator

The honest framing raised to Răzvan: this was interface *implementation*, but not a simple UI —
consuming the data correctly required modelling the taxonomy (from the category tree) and
mirroring the pipeline's selection logic, which overlaps the refactoring team's area. The two
efforts have not collided, but there is a real coordination point: ideally there is **one
taxonomy model and one source of truth for selection rules**, so they converge rather than
diverge. Our category-tree model is offered as the candidate for that shared answer.

---

## 8. Current status & open items

### 8.1 Where it stands

- The work lives in **our team's own fork**, `MariaFudulia/feedback` — the shared repository for
  the three of us, separate from the central `cs-pub-ro/feedback`. Within that fork the data
  layer is merged into **`develop`**, our team's integration branch, through the normal flow
  (feature branch → PR → review → merge) [PR #4, merged; PR #5, merged for the test-suite fix].
  **Nothing was merged into the central repository or into `master`** — this is internal team
  integration only.
- On `develop` now: the taxonomy, cascade, course-detail explorer, offer-structure panel, and
  the real/demonstrative badge system. Structure is real; content (scores/cadre) is
  deterministic-synthetic behind the documented seam (§6).

### 8.2 Open items, and the source still owed

1. **The content export.** Real scores/cadre/enrolment need `feedback_contents/` + `users/` (or
   the pipeline's processed CSVs). This is the single dependency that turns the demonstrative
   numbers real and clears the badge — a concrete ask to the coordinator.
2. **The noise-filter policy.** The pipeline excludes master-research codes but nothing else, so
   ~39 non-teaching "courses" (voluntariat, practică, examene, educație fizică, limbi, pedagogie)
   currently pass through. Whether to exclude them is a policy decision, not a derivation — posed
   as one grouped question to the coordinator. The exclusion mechanism (mirroring the existing
   denylist) is ready either way.
3. **One mis-filed Moodle course.** "Practică pedagogică (2)" sits under a bare "Semestrul 2"
   category with no ciclu/domeniu/an above it, so it cannot be placed from the tree [empiric]. It
   is surfaced in the `/taxonomie` view, not silently dropped — a data-entry fix on the Moodle
   side.

### 8.3 Summary

The data layer stands on a real, authoritative source (the category tree), exposes a frozen
contract the rest of the team builds against, is honest in the UI about what is measured versus
placeholder, and has a single, tested seam for the one piece of real data still owed. The
decisions above were each made on evidence, and each cites where that evidence can be checked.
