"""Coleg C. Deck slides 15-16 (by evaluare / by procentaj completare)."""
import streamlit as st

import queries
from sidebar import render_filters

st.set_page_config(page_title="Top 10 asistenți", layout="wide")
render_filters()
st.title("Top 10 asistenți")
st.caption("Prag de selecție (fix): asistent inclus doar dacă are ≥10 feedback-uri.")

order_by = st.selectbox("Sortează după", ["evaluare_prof", "evaluare_curs"], format_func=lambda x: {
    "evaluare_prof": "Evaluare profesor", "evaluare_curs": "Evaluare curs"}[x])

df = queries.get_top_asistenti(order_by=order_by, limit=10)
st.dataframe(df, use_container_width=True, hide_index=True)
