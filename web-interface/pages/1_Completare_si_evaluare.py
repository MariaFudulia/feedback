"""Coleg B. Deck slides 4, 5, 6."""
import plotly.express as px
import streamlit as st

import queries
from sidebar import render_filters

st.set_page_config(page_title="Completare și evaluare", layout="wide")
render_filters()
st.title("Completare și evaluare pe an / semestru")

st.subheader("Cursuri cu feedback (> 7%)")
coverage = queries.get_course_coverage()
st.plotly_chart(px.pie(coverage, names="categorie", values="num_cursuri"), use_container_width=True)

period = queries.get_period_breakdown()

st.subheader("Procentaj completare feedback pe an / semestru")
st.plotly_chart(px.bar(period, x="bucket", y="proc_completare"), use_container_width=True)

st.subheader("Evaluare din feedback pe an / semestru")
st.plotly_chart(px.bar(period, x="bucket", y="evaluare", range_y=[0, 5]), use_container_width=True)
