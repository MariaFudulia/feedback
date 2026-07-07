"""Coleg C. Deck slides 10-12 (general / licență / after procentaj) — one page,
toggled by ciclu + order_by instead of three separate pages."""
import streamlit as st

import queries
from sidebar import render_filters

st.set_page_config(page_title="Top 10 cursuri", layout="wide")
filters = render_filters()
st.title("Top 10 cursuri")
st.caption("Prag de selecție (fix): curs inclus doar dacă are ≥7% procentaj feedback și ≥3 feedback-uri.")

order_by = st.selectbox("Sortează după", ["evaluare_curs", "proc_feedback"], format_func=lambda x: {
    "evaluare_curs": "Evaluare", "proc_feedback": "Procentaj feedback"}[x])
ciclu = {"Toate": None, "Licență": "L", "Master": "M"}[filters["ciclu"]]

df = queries.get_top_courses(order_by=order_by, ciclu=ciclu, limit=10)
st.dataframe(df, use_container_width=True, hide_index=True)
