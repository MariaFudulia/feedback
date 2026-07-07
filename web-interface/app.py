"""Entry point + 'Sumar comparativ' page (deck slide 3). Coleg B owns this file.

Additional pages live in pages/ (Streamlit's native multipage convention —
any file there gets its own nav entry automatically).
"""
import streamlit as st

import queries
from sidebar import render_filters

st.set_page_config(page_title="Feedback POLITEHNICA", layout="wide")
filters = render_filters()

st.title("Sumar comparativ")
st.caption("Echivalentul slide-ului 3 din deck: evoluția feedback-ului pe ani universitari.")

summary = queries.get_summary()
latest = summary[summary["an_universitar"] == summary["an_universitar"].iloc[-1]]
total_row = latest[latest["nivel"] == "total"].iloc[0]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Feedback-uri", int(total_row["num_feedback"]))
col2.metric("Grad de completare", f'{total_row["proc_completare"]:.1f}%')
col3.metric("Cursuri cu feedback", int(total_row["num_cursuri"]))
col4.metric("Evaluare generală", f'{total_row["evaluare"]:.2f}')

st.divider()
st.subheader("Pe ani universitari")
pivot = summary.pivot(index="an_universitar", columns="nivel",
                       values=["num_feedback", "proc_completare", "num_cursuri", "evaluare"])
st.dataframe(pivot, use_container_width=True)
