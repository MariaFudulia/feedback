"""Flask entry point. Routes only call into queries.py -- never mocks.py
directly, and queries.py never imports flask (see docs/index.html, "Stack").
"""

from flask import Flask, render_template, request

import queries

app = Flask(__name__)


@app.route("/")
def sumar():
    summary = queries.get_summary()
    latest_an = summary["an_universitar"].iloc[-1]
    latest = summary[summary["an_universitar"] == latest_an]
    total_row = latest[latest["nivel"] == "total"].iloc[0]
    return render_template(
        "sumar.html",
        total=total_row,
        rows=summary.to_dict("records"),
    )


@app.route("/completare-evaluare")
def completare_evaluare():
    coverage = queries.get_course_coverage()
    period = queries.get_period_breakdown()
    return render_template(
        "completare_evaluare.html",
        coverage=coverage.to_dict("records"),
        period=period.to_dict("records"),
    )


@app.route("/pe-ani-de-studiu")
def pe_ani_de_studiu():
    an = request.args.get("an", default=1, type=int)
    df = queries.get_year_breakdown(an)
    return render_template("pe_ani_de_studiu.html", an=an, rows=df.to_dict("records"))


@app.route("/top10-cursuri")
def top10_cursuri():
    order_by = request.args.get("order_by", default="evaluare_curs")
    ciclu = request.args.get("ciclu") or None
    df = queries.get_top_courses(order_by=order_by, ciclu=ciclu)
    return render_template("top10_cursuri.html", order_by=order_by, ciclu=ciclu, rows=df.to_dict("records"))


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
    df = queries.get_score_distribution(entitate)
    return render_template("evaluare_pe_zone.html", entitate=entitate, rows=df.to_dict("records"))


if __name__ == "__main__":
    app.run(debug=True)
