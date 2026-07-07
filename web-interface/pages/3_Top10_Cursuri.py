"""Coleg C. Deck slides 10-12 (general / licență / after procentaj) — one page,
toggled by ciclu + order_by instead of three separate pages."""
import streamlit as st

import queries
from sidebar import render_filters

st.set_page_config(page_title="Top 10 cursuri", layout="wide")
render_filters()
st.title("Top 10 cursuri")
st.caption("Prag de selecție (fix): curs inclus doar dacă are ≥7% procentaj feedback și ≥3 feedback-uri.")

col1, col2 = st.columns(2)
order_by = col1.selectbox("Sortează după", ["evaluare_curs", "proc_feedback"], format_func=lambda x: {
    "evaluare_curs": "Evaluare", "proc_feedback": "Procentaj feedback"}[x])
ciclu = col2.selectbox("Ciclu", [None, "L", "M"], format_func=lambda x: {
    None: "Toate", "L": "Licență", "M": "Master"}[x])

df = queries.get_top_courses(order_by=order_by, ciclu=ciclu, limit=10)
st.dataframe(df, use_container_width=True, hide_index=True)
