"""Coleg C. Deck slides 13-14 (by evaluare / by procentaj feedback)."""
import streamlit as st

import queries
from sidebar import render_filters

st.set_page_config(page_title="Top 10 titulari", layout="wide")
render_filters()
st.title("Top 10 titulari")
st.caption("Prag de selecție (fix): titular inclus doar dacă are, în medie, ≥7% procentaj "
           "feedback la cursurile unde e titular și ≥15 feedback-uri.")

order_by = st.selectbox("Sortează după", ["evaluare_prof", "evaluare_curs", "proc_feedback"], format_func=lambda x: {
    "evaluare_prof": "Evaluare profesor", "evaluare_curs": "Evaluare curs", "proc_feedback": "Procentaj feedback"}[x])

df = queries.get_top_titulari(order_by=order_by, limit=10)
st.dataframe(df, use_container_width=True, hide_index=True)
