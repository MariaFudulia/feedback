"""Coleg C. Deck slides 7-9 ('An 1' / 'An 2' / 'An 3').

One reusable component parameterized by an de studiu, rather than three
near-identical copies — the three slides only differ by which an they filter to.
"""
import plotly.graph_objects as go
import streamlit as st

import queries
from sidebar import render_filters

st.set_page_config(page_title="Pe ani de studiu", layout="wide")
render_filters()
st.title("Completare și evaluare pe serie, per an de studiu")

an = st.radio("An de studiu", [1, 2, 3], horizontal=True)
df = queries.get_year_breakdown(an)

fig = go.Figure()
fig.add_bar(name="Procent", x=df["serie"], y=df["proc_completare"], yaxis="y1")
fig.add_bar(name="Evaluare", x=df["serie"], y=df["evaluare"], yaxis="y2")
fig.update_layout(
    barmode="group",
    yaxis=dict(title="Procent", range=[0, 30]),
    yaxis2=dict(title="Evaluare", range=[0, 5], overlaying="y", side="right"),
)
st.plotly_chart(fig, use_container_width=True)
