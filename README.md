# Feedback Analysis

Tooling for extracting, processing and presenting course-feedback results from a
[Moodle](https://moodle.org) instance — built against the
[ACS UPB Moodle instance](https://acs.curs.pub.ro/), adaptable to another one.

Three things live here: a **pipeline** that pulls feedback out of Moodle and crunches it, a
**web interface** that presents it, and a **generator** that fabricates realistic data so
neither of the first two needs real student responses to be developed or demoed.

## The directories

| Directory | What it is |
|---|---|
| `retrieve-feedback/` | Pulls from a live Moodle over its web-service API: the category tree, courses, feedback forms, the responses themselves, and enrolled users. Needs credentials (`moodle.conf`). |
| `process-feedback/` | Turns the retrieved responses into per-course / per-teacher statistics. |
| `analysis/`, `summarize/`, `statistics/`, `mappings/` | ACS-specific reporting on top of that: rankings, per-series and per-semester rollups, the selection thresholds. |
| `web-interface/` | A Flask dashboard over the results — filter cascade, rankings, per-course detail, free-text comments with estimated sentiment. See [`web-interface/README.md`](web-interface/README.md). |
| `generate-feedback/` | Generates a **synthetic** feedback dataset in the exact shape a real Moodle export has, so the pipeline and the dashboard can be run without touching real student data. See [`generate-feedback/README.md`](generate-feedback/README.md). |
| `docs/` | The original planning doc. Superseded — see `web-interface/docs/` for what is actually true today. |

## Real data, and the lack of it

We have **no access to real feedback responses**, and the code is built around that fact
rather than around a promise that they will arrive.

The Moodle **structure** (categories, courses, series) is real — that is what
`retrieve-feedback` pulls and what the dashboard's filter cascade is derived from. The
**content** — scores, teacher names, enrolment, free text — is fabricated by
`generate-feedback/`, which emits exactly the files a real export would
(`feedback_contents/<id>.json`, `users/<course_id>.json`) so nothing downstream has to know
the difference.

Because nothing downstream can tell the difference, **the app is careful to**. It refuses to
present generated numbers as real: content counts as real only when someone explicitly says
so, and an export that declares itself synthetic can never be promoted. Every page built on
fabricated numbers carries a visible badge. That rule is the point, not decoration — see
[`web-interface/docs/data-layer-decisions.md`](web-interface/docs/data-layer-decisions.md).

## Quick start

```bash
# the dashboard, on synthetic data, needs nothing but a clone
cd web-interface
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
flask --app app run

# a full synthetic dataset (real structure, fabricated content)
cd generate-feedback
python3 convert_script.py     # jsons/ -> pickles/
python3 main.py --seed 1 --report
python3 validate.py --out out # proves both consumers will accept it
```

Point the dashboard at that dataset with `FEEDBACK_DATA_DIR=../generate-feedback/out`
(the pickles must sit alongside `feedback_contents/` and `users/`).
