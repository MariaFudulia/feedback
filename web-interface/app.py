"""Flask entry point. Routes only call into queries.py -- never mocks.py or
taxonomy.py directly, and queries.py never imports flask (see docs/index.html).

Filter model: a coupled cascade. The sidebar's structural filters
(ciclu -> domeniu -> specializare -> an -> sem -> serie -> curs) are derived
from the real Moodle category tree (queries.get_filter_options), so a
contradictory scope is impossible to build -- picking Ciclu narrows the valid
years, a domeniu with no specializare level hides that filter, a course only
exposes its own series.
"""

import math
from urllib.parse import urlencode

import pandas as pd
from flask import Flask, Response, abort, redirect, render_template, request, session, url_for

import config
import queries

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

STRUCT = queries.get_struct_order()  # ciclu, domeniu, specializare, an, sem, serie, curs
FILTER_KEYS = ["an_universitar", *STRUCT]

DIM_LABEL = {
    "ciclu": "Ciclu",
    "domeniu": "Domeniu",
    "specializare": "Specializare",
    "an": "An de studiu",
    "sem": "Semestru",
    "serie": "Serie / grupă",
    "curs": "Curs",
}
TOATE_LABEL = {
    "serie": "Toate seriile",
    "curs": "Toate cursurile",
    "specializare": "Toate specializările",
}

# Theme is a per-session preference, stored like the filters. "auto" defers to
# the OS setting (prefers-color-scheme) -- the default, so a first visit already
# matches the machine it lands on.
THEMES = ("auto", "light", "dark")
THEME_LABEL = {"auto": "Auto", "light": "Luminos", "dark": "Întunecat"}

# fixed nivel -> chart color, so filtering never repaints the surviving series
NIVEL_SERIES = [
    {"key": "total", "label": "Total", "color": "red", "unit": ""},
    {"key": "licenta", "label": "Licență", "color": "blue", "unit": ""},
    {"key": "masterat", "label": "Master", "color": "green", "unit": ""},
]


def _nice_max(v):
    """0-anchored top of a chart scale: the value rounded up at its leading digit
    (4.43 -> 5, 27.7 -> 30, 8119 -> 9000)."""
    if v <= 0:
        return 1
    mag = 10 ** (len(str(int(v))) - 1)
    return math.ceil(v / mag) * mag


def _safe_next(target):
    """Only follow an in-app `next` (relative path) -- an absolute URL in the
    form/query would make /set-filters an open redirect."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return None


def current_theme():
    t = session.get("tema", "auto")
    return t if t in THEMES else "auto"


def current_filters():
    f = {k: session.get(k, "") for k in FILTER_KEYS}
    if not f["an_universitar"]:
        years = queries.get_academic_years()
        f["an_universitar"] = years[-1] if years else ""
    return f


def _dim_visible(dim, f, opts_all):
    """Progressive reveal: a filter appears only once the choices that give it
    meaning are made -- never out of context. The *option values* are always
    data-derived (opts_all); this only decides *when* to surface the widget.
      ciclu             -> always
      domeniu           -> once ciclu is chosen
      specializare      -> once domeniu is chosen AND the branch actually has a
                           specializare level (empty otherwise -> stays hidden)
      an                -> once domeniu is chosen
      sem, serie, curs  -> once an is chosen
    """
    if dim == "ciclu":
        return True
    if dim in ("domeniu", "an"):
        return bool(f.get("ciclu"))
    if dim == "specializare":
        return bool(f.get("domeniu")) and len(opts_all["specializare"]) > 0
    if dim in ("sem", "serie", "curs"):
        return bool(f.get("an"))
    return True


def build_cascade(filters):
    """Structural filters to render, progressively revealed and contradiction-
    proof. Every rendered filter carries a 'Toate' option so the user can
    broaden again."""
    opts_all = queries.get_filter_options(filters)  # each dim uses only its upstream from `filters`
    rows = []
    for dim in STRUCT:
        if not _dim_visible(dim, filters, opts_all):
            continue
        opts = opts_all[dim]
        if not opts and not filters.get(dim):
            continue
        rows.append(
            {
                "dim": dim,
                "label": DIM_LABEL[dim],
                "toate": TOATE_LABEL.get(dim, "Toate"),
                "options": opts,
                "value": filters.get(dim, ""),
            }
        )
    return rows, filters


@app.context_processor
def inject_sidebar():
    filters = current_filters()
    rows, _eff = build_cascade(filters)
    # shareable link for the current scope (only offered once something is filtered)
    share_qs = urlencode({k: v for k, v in filters.items() if v}) if any(filters[d] for d in STRUCT) else ""
    return {
        "filters": filters,
        "cascade_rows": rows,
        "academic_years": queries.get_academic_years(),
        "share_qs": share_qs,
        "export_url": _export_url,
        "tema": current_theme(),
        "teme": THEMES,
        "theme_label": THEME_LABEL,
    }


def _apply_scope(values):
    """Write a submitted scope into the session, revalidating the structural
    cascade top-down against the real combination space: keep every value that
    is still legal given the accepted upstream, drop (to "Toate") anything
    contradictory. Because each dim's legality is computed against the
    *accepted* prefix (eff), a change high in the cascade cleanly cascades the
    clearing downstream. `values` is any mapping with .get (form or args)."""
    session["an_universitar"] = values.get("an_universitar", "")
    eff = {}
    for dim in STRUCT:
        legal = {o["value"] for o in queries.get_filter_options(eff)[dim]}
        v = values.get(dim, "")
        if v and v in legal:
            session[dim] = v
            eff[dim] = v
        else:
            session[dim] = ""
    return eff


@app.before_request
def scope_from_url():
    """Shareable scope: a GET carrying structural filter params applies them
    exactly like a sidebar submission (same top-down revalidation), so a URL
    like /top10-cursuri?ciclu=L&domeniu=CTI&an=2 reproduces that view for
    whoever opens it. Params define the WHOLE scope (absent dim = 'Toate')."""
    if request.method != "GET" or request.endpoint in (None, "static"):
        return
    if any(k in request.args for k in FILTER_KEYS):
        _apply_scope(request.args)


@app.route("/set-filters", methods=["POST"])
def set_filters():
    _apply_scope(request.form)
    return redirect(_safe_next(request.form.get("next")) or url_for("sumar"))


@app.route("/tema", methods=["POST"])
def set_theme():
    """Remember the theme picked in the sidebar.

    The CSS has already flipped on the client the instant the radio was checked
    (the stylesheet keys off :checked -- see `body:has()` in style.css), so this
    request has nothing to re-render: it only makes the choice survive the next
    navigation. Hence 204 and hx-swap="none" on the form.
    """
    tema = request.form.get("tema", "")
    session["tema"] = tema if tema in THEMES else "auto"
    return "", 204


@app.route("/reset-filters")
def reset_filters():
    for k in FILTER_KEYS:
        session.pop(k, None)
    dest = _safe_next(request.args.get("next")) or url_for("sumar")
    return redirect(dest.split("?")[0])


# ---- coarse scope bridge for the (stage-1) report pages -------------------
# The report pages still use the deck aggregates; map the cascade scope onto
# their coarser parameters. Stage 2 re-derives these pages from the taxonomy.


def _coarse_scope():
    f = current_filters()
    ciclu = f["ciclu"] or None
    # bridge the real domeniu onto the deck's old CTI/IS track param
    track = {"CTI": "CTI", "IS": "IS"}.get(f["domeniu"])
    semestru = ("S" + f["sem"]) if f["sem"] else None
    an = int(f["an"]) if f["an"] else None
    return ciclu, track, semestru, an


@app.route("/")
def sumar():
    ciclu, track, semestru, _an = _coarse_scope()
    nivel = {"L": "licenta", "M": "masterat"}.get(ciclu)
    oferta = queries.get_offer_structure()  # real, no scores
    summary = queries.get_summary(nivel=nivel, track=track)  # deck mock, demonstrative
    if request.args.get("export") == "csv":
        return _csv(summary, "sumar-evolutie")
    if summary.empty:
        return render_template("sumar.html", oferta=oferta, total=None, rows=[], chart=None)
    latest_an = summary["an_universitar"].iloc[-1]
    latest = summary[summary["an_universitar"] == latest_an]
    total_rows = latest[latest["nivel"] == "total"]
    total_row = total_rows.iloc[0] if not total_rows.empty else latest.iloc[0]

    df_chart = summary
    # narrow the chart to the chosen ciclu; guard on nivel -- domeniu (track)
    # can stay selected after ciclu is cleared, and nivel==None matches nothing
    if track and nivel:
        df_chart = summary[summary["nivel"] == nivel]
    groups = {}
    for r in df_chart.sort_values("an_universitar").to_dict("records"):
        groups.setdefault(r["an_universitar"], {})[r["nivel"]] = r["num_feedback"]
    vmax = _nice_max(df_chart["num_feedback"].max())
    chart = {
        "groups": [{"label": an, "values": v} for an, v in groups.items()],
        "series": [s for s in NIVEL_SERIES if any(s["key"] in v for v in groups.values())],
        "vmax": vmax,
        "note": f"scală 0–{vmax}",
    }

    return render_template(
        "sumar.html", oferta=oferta, total=total_row, rows=summary.to_dict("records"), chart=chart
    )


@app.route("/completare-evaluare")
def completare_evaluare():
    ciclu, _track, semestru, _an = _coarse_scope()
    coverage = queries.get_course_coverage()
    period = queries.get_period_breakdown(ciclu=ciclu, semestru=semestru)
    export = request.args.get("export")
    if export == "coverage":
        return _csv(coverage, "cursuri-cu-feedback")
    if export == "buckets":
        return _csv(period, "completare-evaluare-buckets")
    period_records = period.to_dict("records")
    chart_proc = chart_eval = None
    if period_records:
        vmax = _nice_max(max(r["proc_completare"] for r in period_records))
        chart_proc = {
            "groups": [{"label": r["bucket"], "values": {"v": r["proc_completare"]}} for r in period_records],
            "series": [{"key": "v", "label": "Grad completare", "color": "red", "unit": "%"}],
            "vmax": vmax,
            "note": f"scală 0–{vmax}%",
        }
        chart_eval = {
            "groups": [{"label": r["bucket"], "values": {"v": r["evaluare"]}} for r in period_records],
            "series": [{"key": "v", "label": "Evaluare", "color": "red", "unit": ""}],
            "vmax": 5,
            "note": "scală 0–5",
        }

    return render_template(
        "completare_evaluare.html",
        coverage=coverage.to_dict("records"),
        period=period_records,
        chart_proc=chart_proc,
        chart_eval=chart_eval,
    )


@app.route("/pe-ani-de-studiu")
def pe_ani_de_studiu():
    _ciclu, _track, _sem, an = _coarse_scope()
    an = an or 1  # no year filtered yet -> default to An 1
    df = queries.get_year_breakdown(an)
    if request.args.get("export") == "csv":
        return _csv(df, f"pe-ani-de-studiu-an{an}")
    return render_template("pe_ani_de_studiu.html", an=an, rows=df.to_dict("records"))


def _export_url(kind="csv"):
    """Current page's URL with export=<kind> added (keeps sort/scope params)."""
    return url_for(request.endpoint, **{**request.args.to_dict(), "export": kind})


def _csv(df, name):
    """The displayed table (post-filter, post-sort) as a CSV download."""
    return Response(
        df.to_csv(index=False),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}.csv"'},
    )


def _order_by(default, allowed):
    """order_by from the query string, constrained to the page's sortable keys."""
    v = request.args.get("order_by", default=default)
    if v not in allowed:
        abort(400, "order_by necunoscut")
    return v


def _one_of(param, default, allowed):
    """A query param constrained to an allowlist -- same discipline as _order_by: an unknown
    value is a 400, never a silent fallback to the default."""
    v = request.args.get(param, default=default)
    if v not in allowed:
        abort(400, f"{param} necunoscut")
    return v


def _page(total, per_page):
    """1-based page number, clamped. `request.args.get(type=int)` quietly returns None on
    garbage, which would swallow ?page=abc; this page count is user-visible, so say 400."""
    raw = request.args.get("page", "1")
    if not raw.isdigit() or raw == "0":
        abort(400, "page invalid")
    pages = max(1, math.ceil(total / per_page))
    return min(int(raw), pages), pages


@app.route("/top10-cursuri")
def top10_cursuri():
    order_by = _order_by("evaluare_curs", ("evaluare_curs", "proc_feedback"))
    ciclu, track, semestru, _an = _coarse_scope()
    df = queries.get_top_courses(order_by=order_by, ciclu=ciclu, track=track, semestru=semestru)
    if request.args.get("export") == "csv":
        return _csv(df, "top10-cursuri")
    return render_template("top10_cursuri.html", order_by=order_by, rows=df.to_dict("records"))


@app.route("/top10-titulari")
def top10_titulari():
    order_by = _order_by("evaluare_prof", ("evaluare_prof", "evaluare_curs", "proc_feedback"))
    df = queries.get_top_titulari(order_by=order_by)
    if request.args.get("export") == "csv":
        return _csv(df, "top10-titulari")
    return render_template("top10_titulari.html", order_by=order_by, rows=df.to_dict("records"))


@app.route("/top10-asistenti")
def top10_asistenti():
    order_by = _order_by("evaluare_prof", ("evaluare_prof", "evaluare_curs"))
    df = queries.get_top_asistenti(order_by=order_by)
    if request.args.get("export") == "csv":
        return _csv(df, "top10-asistenti")
    return render_template("top10_asistenti.html", order_by=order_by, rows=df.to_dict("records"))


@app.route("/evaluare-pe-zone")
def evaluare_pe_zone():
    entitate = request.args.get("entitate", default="curs")
    if entitate not in ("curs", "titular", "asistent"):
        abort(400, "entitate necunoscută (curs / titular / asistent)")
    df = queries.get_score_distribution(entitate)
    if request.args.get("export") == "csv":
        return _csv(df, f"evaluare-pe-zone-{entitate}")
    return render_template("evaluare_pe_zone.html", entitate=entitate, rows=df.to_dict("records"))


# ---- the explorer lens: fully scope-driven from the taxonomy --------------

CICLU_LABEL = {"L": "Licență", "M": "Master", "P": "Postuniversitar"}


@app.route("/curs-detaliu")
def curs_detaliu():
    f = current_filters()
    _rows, eff = build_cascade(f)
    an_universitar = f["an_universitar"]

    # the course in scope: explicit selection, else the first course the scope allows
    scope = queries.get_scope_courses({d: eff.get(d, "") for d in STRUCT})
    curs = eff.get("curs") or (scope[0]["curs"] if scope else None)

    cadre = queries.get_course_detail(curs, an_universitar) if curs else []
    denumire = next((c["denumire"] for c in scope if c["curs"] == curs), "")
    if not denumire and curs:
        full = queries.get_scope_courses({})
        denumire = next((c["denumire"] for c in full if c["curs"] == curs), curs)
    num_studenti = queries.get_course_students(curs, an_universitar) if curs else 0

    doar_titulari = request.args.get("doar_titulari") == "1"
    if doar_titulari:
        cadre = [c for c in cadre if c["tip"] == "titular"]

    # the sortable columns of the cadre table (mirrors `cols` in curs_detaliu.html)
    order_by = _order_by(
        "eval_gen",
        ("nume", "tip", "num_feedback", "eval_gen", "preg", "expl_clare", "interes", "comport", "indepl_ob"),
    )
    reverse = order_by != "nume"
    cadre = sorted(cadre, key=lambda c: c[order_by], reverse=reverse)
    if request.args.get("export") == "csv":
        return _csv(pd.DataFrame(cadre), f"detaliu-{curs or 'curs'}")

    faculty_avg = queries.get_faculty_average(an_universitar)
    # top-line "Răspunsuri" = unique student submissions (<= enrolled); the
    # per-teacher counts sum higher because each student rates every teacher.
    raspunsuri = queries.get_course_responses(curs, an_universitar) if curs else 0
    total_ratings = sum(c["num_feedback"] for c in cadre)
    medie_curs = (
        round(sum(c["eval_gen"] * c["num_feedback"] for c in cadre) / total_ratings, 2)
        if total_ratings
        else 0
    )
    delta = round(medie_curs - faculty_avg["eval_gen"], 2) if total_ratings else 0
    proc = min(100, round(raspunsuri / num_studenti * 100)) if num_studenti else 0
    evals = [c["eval_gen"] for c in cadre]
    num_tit = sum(1 for c in cadre if c["tip"] == "titular")
    num_asi = sum(1 for c in cadre if c["tip"] == "asistent")

    selected_nume = request.args.get("cadru") or (cadre[0]["nume"] if cadre else None)
    selected_row = next((c for c in cadre if c["nume"] == selected_nume), None)

    crumbs = []
    if eff.get("ciclu"):
        crumbs.append(CICLU_LABEL.get(eff["ciclu"], eff["ciclu"]))
    if eff.get("domeniu"):
        crumbs.append(eff["domeniu"])
    if eff.get("specializare"):
        crumbs.append(eff["specializare"])
    if eff.get("an"):
        crumbs.append(f"Anul {eff['an']}")
    if eff.get("sem"):
        crumbs.append("Sem. " + eff["sem"])
    crumbs.append(an_universitar)

    return render_template(
        "curs_detaliu.html",
        curs=curs,
        denumire=denumire,
        breadcrumb=" · ".join(crumbs),
        serie=eff.get("serie", ""),
        order_by=order_by,
        cadre=cadre,
        raspunsuri=raspunsuri,
        num_studenti=num_studenti,
        proc_completare=proc,
        medie_curs=medie_curs,
        delta_facultate=delta,
        eval_min=round(min(evals), 2) if evals else 0,
        eval_max=round(max(evals), 2) if evals else 0,
        num_titulari=num_tit,
        num_asistenti=num_asi,
        doar_titulari=doar_titulari,
        selected_nume=selected_nume,
        selected_row=selected_row,
        faculty_avg=faculty_avg,
        date_demonstrative=queries.get_content_is_synthetic(),
    )


COMMENTS_PER_PAGE = 25
SENTIMENTE = ("toate", "pozitiv", "neutru", "negativ", "incert")


@app.route("/comentarii")
def comentarii():
    """The free-text answers, one question at a time.

    Two things this page does NOT do, on purpose:

    * it ignores the `serie` filter, and says so. The response gate is applied per logical
      course; if comments honoured `serie`, a reader could pull seria A, then seria B, and
      difference the two -- reconstructing per-series sets that each sit below the gate.

    * it never shows an attempt id, an index, or a row number. taxonomy destroyed the link
      between a comment and its author (and its author's other three answers); re-introducing
      any stable per-comment identifier here would hand it straight back.

    The gate itself lives in the data layer, not here -- `_export_url` re-emits every query
    argument by design, so a check in this function or in the template would be walked around
    by ?export=csv.
    """
    f = current_filters()
    _rows, eff = build_cascade(f)
    an_universitar = f["an_universitar"]

    scope = queries.get_scope_courses({d: eff.get(d, "") for d in STRUCT})
    curs = eff.get("curs") or (scope[0]["curs"] if scope else None)
    denumire = next((c["denumire"] for c in scope if c["curs"] == curs), "")
    if not denumire and curs:
        denumire = next((c["denumire"] for c in queries.get_scope_courses({}) if c["curs"] == curs), curs)

    intrebari = queries.get_comments_questions()
    intrebare = _one_of("intrebare", "positive", tuple(intrebari))
    # `difficulty` asks for a cause, not an opinion, and carries no sentiment label at all --
    # so there is nothing to filter by. Forcing it here keeps a stale ?sentiment= in the URL
    # from silently emptying the list.
    sentiment_filter = "toate" if intrebare == "difficulty" else _one_of("sentiment", "toate", SENTIMENTE)

    gate = (
        queries.get_comments_gate(curs, an_universitar)
        if curs
        else {"gated": True, "responses": 0, "min": 5, "has_content": False}
    )
    rows = queries.get_course_comments(
        curs,
        intrebare=intrebare,
        sentiment=None if sentiment_filter == "toate" else sentiment_filter,
        an_universitar=an_universitar,
    )

    if request.args.get("export") == "csv":
        # deliberately the FULL filtered list, not the page on screen: one page of 25 comments
        # is a useless export. Said out loud in the caption and the button's title.
        return _csv(
            pd.DataFrame(rows, columns=["intrebare", "sentiment", "comentariu"]),
            f"comentarii-{intrebare}-{curs or 'curs'}",
        )

    page, pages = _page(len(rows), COMMENTS_PER_PAGE)
    start = (page - 1) * COMMENTS_PER_PAGE
    counts = queries.get_comment_counts(curs, an_universitar) if curs else {}
    model = queries.get_sentiment_model_info()

    dist = []
    row = counts.get(intrebare, {})
    total_labelled = sum(row.get(k, 0) for k in ("pozitiv", "neutru", "negativ", "incert"))
    if total_labelled:
        for label in ("pozitiv", "neutru", "negativ", "incert"):
            n = row.get(label, 0)
            if n:
                dist.append({"eticheta": label, "num": n, "pct": round(100 * n / total_labelled, 1)})

    crumbs = [denumire or "—", an_universitar]
    return render_template(
        "comentarii.html",
        curs=curs,
        denumire=denumire,
        breadcrumb=" · ".join(crumbs),
        intrebari=intrebari,
        intrebare=intrebare,
        sentiment_filter=sentiment_filter,
        sentimente=SENTIMENTE,
        rows=rows[start : start + COMMENTS_PER_PAGE],
        total=len(rows),
        page=page,
        pages=pages,
        counts=counts,
        dist=dist,
        gate=gate,
        model=model,
        date_demonstrative=queries.get_content_is_synthetic(),
    )


@app.route("/despre-date")
def despre_date():
    """What is measured vs. demonstrative, and where every number comes from --
    written for a first-time viewer of the (synthetic) public demo."""
    return render_template(
        "despre_date.html",
        source=queries.get_data_source(),
        model=queries.get_sentiment_model_info(),
        comments_min=queries.get_comments_gate(None)["min"],
    )


@app.route("/taxonomie")
def taxonomie():
    """Debug view: the entire valid combination space as a tree, plus any
    structural gaps. Lets you check every interaction the cascade allows."""
    return render_template(
        "taxonomie.html",
        tree=queries.get_taxonomy_tree(),
        issues=queries.get_taxonomy_issues(),
        source=queries.get_data_source(),
    )


if __name__ == "__main__":
    app.run(debug=True)
