"""Flask entry point. Routes only call into queries.py -- never mocks.py or
taxonomy.py directly, and queries.py never imports flask (see docs/index.html).

Filter model: a coupled cascade. The sidebar's structural filters
(ciclu -> domeniu -> specializare -> an -> sem -> serie -> curs) are derived
from the real Moodle category tree (queries.get_filter_options), so a
contradictory scope is impossible to build -- picking Ciclu narrows the valid
years, a domeniu with no specializare level hides that filter, a course only
exposes its own series.
"""

import plotly.express as px
from flask import Flask, abort, redirect, render_template, request, session, url_for

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


def _safe_next(target):
    """Only follow an in-app `next` (relative path) -- an absolute URL in the
    form/query would make /set-filters an open redirect."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return None


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
    return {
        "filters": filters,
        "cascade_rows": rows,
        "academic_years": queries.get_academic_years(),
    }


@app.route("/set-filters", methods=["POST"])
def set_filters():
    session["an_universitar"] = request.form.get("an_universitar", "")
    # Revalidate the structural cascade top-down against the real combination
    # space: keep every submitted value that is still legal given the accepted
    # upstream, drop (to "Toate") anything that became contradictory. Because
    # each dim's legality is computed against the *accepted* prefix (eff), a
    # change high in the cascade cleanly cascades the clearing downstream.
    eff = {}
    for dim in STRUCT:
        legal = {o["value"] for o in queries.get_filter_options(eff)[dim]}
        v = request.form.get(dim, "")
        if v and v in legal:
            session[dim] = v
            eff[dim] = v
        else:
            session[dim] = ""
    return redirect(_safe_next(request.form.get("next")) or url_for("sumar"))


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
    if summary.empty:
        return render_template("sumar.html", oferta=oferta, total=None, rows=[], plot_div=None)
    latest_an = summary["an_universitar"].iloc[-1]
    latest = summary[summary["an_universitar"] == latest_an]
    total_rows = latest[latest["nivel"] == "total"]
    total_row = total_rows.iloc[0] if not total_rows.empty else latest.iloc[0]

    plot_div = None
    if not summary.empty:
        df_chart = summary
        # narrow the chart to the chosen ciclu; guard on nivel -- domeniu (track)
        # can stay selected after ciclu is cleared, and nivel==None matches nothing
        if track and nivel:
            df_chart = summary[summary["nivel"] == nivel]

        df_sorted = df_chart.sort_values("an_universitar")
        fig = px.bar(
            df_sorted,
            x="an_universitar",
            y="num_feedback",
            color="nivel",
            barmode="group",
            title="Evoluția volumului de feedback primit",
            labels={"an_universitar": "An Universitar", "num_feedback": "Număr Feedback-uri"},
        )

        plot_div = fig.to_html(full_html=False, include_plotlyjs="cdn")

    return render_template(
        "sumar.html", oferta=oferta, total=total_row, rows=summary.to_dict("records"), plot_div=plot_div
    )


@app.route("/completare-evaluare")
def completare_evaluare():
    ciclu, _track, semestru, _an = _coarse_scope()
    coverage = queries.get_course_coverage()
    period = queries.get_period_breakdown(ciclu=ciclu, semestru=semestru)
    plot_coverage_div = None
    plot_proc_div = None
    plot_eval_div = None

    if not coverage.empty:
        fig_cov = px.pie(
            coverage, names="categorie", values="num_cursuri", title="Acoperire cursuri pe categorii"
        )
        plot_coverage_div = fig_cov.to_html(full_html=False, include_plotlyjs="cdn")

    if not period.empty:
        df_period = period.sort_values("bucket")

        fig_proc = px.bar(
            df_period,
            x="bucket",
            y="proc_completare",
            title="Procentaj completare pe bucket",
            labels={"bucket": "Bucket", "proc_completare": "Grad Completare (%)"},
        )
        plot_proc_div = fig_proc.to_html(full_html=False, include_plotlyjs="cdn")

        fig_eval = px.bar(
            df_period,
            x="bucket",
            y="evaluare",
            title="Evaluare medie pe bucket",
            labels={"bucket": "Bucket", "evaluare": "Notă Evaluare"},
        )
        plot_eval_div = fig_eval.to_html(full_html=False, include_plotlyjs="cdn")

    return render_template(
        "completare_evaluare.html",
        coverage=coverage.to_dict("records"),
        period=period.to_dict("records"),
        plot_coverage_div=plot_coverage_div,
        plot_proc_div=plot_proc_div,
        plot_eval_div=plot_eval_div,
    )


@app.route("/pe-ani-de-studiu")
def pe_ani_de_studiu():
    _ciclu, _track, _sem, an = _coarse_scope()
    an = an or 1  # no year filtered yet -> default to An 1
    df = queries.get_year_breakdown(an)
    return render_template("pe_ani_de_studiu.html", an=an, rows=df.to_dict("records"))


@app.route("/top10-cursuri")
def top10_cursuri():
    order_by = request.args.get("order_by", default="evaluare_curs")
    ciclu, track, semestru, _an = _coarse_scope()
    df = queries.get_top_courses(order_by=order_by, ciclu=ciclu, track=track, semestru=semestru)
    return render_template("top10_cursuri.html", order_by=order_by, rows=df.to_dict("records"))


@app.route("/top10-titulari")
def top10_titulari():
    order_by = request.args.get("order_by", default="evaluare_prof")
    df = queries.get_top_titulari(order_by=order_by)
    return render_template("top10_titulari.html", order_by=order_by, rows=df.to_dict("records"))


@app.route("/top10-asistenti")
def top10_asistenti():
    order_by = request.args.get("order_by", default="evaluare_prof")
    df = queries.get_top_asistenti(order_by=order_by)
    return render_template("top10_asistenti.html", order_by=order_by, rows=df.to_dict("records"))


@app.route("/evaluare-pe-zone")
def evaluare_pe_zone():
    entitate = request.args.get("entitate", default="curs")
    if entitate not in ("curs", "titular", "asistent"):
        abort(400, "entitate necunoscută (curs / titular / asistent)")
    df = queries.get_score_distribution(entitate)
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

    order_by = request.args.get("order_by", default="eval_gen")
    # the sortable columns of the cadre table (mirrors `cols` in curs_detaliu.html)
    sortable = (
        "nume",
        "tip",
        "num_feedback",
        "eval_gen",
        "preg",
        "expl_clare",
        "interes",
        "comport",
        "indepl_ob",
    )
    if order_by not in sortable:
        abort(400, "order_by necunoscut")
    reverse = order_by != "nume"
    cadre = sorted(cadre, key=lambda c: c[order_by], reverse=reverse)

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
