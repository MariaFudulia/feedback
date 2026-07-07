"""Coleg C. Deck slides 17-19. 'Zone' = benzi de scor (4-5/3-4/2-3/1-2),
not zone geografice — distribuția evaluărilor pe categorii de scor."""
import plotly.express as px
import streamlit as st

import queries
from sidebar import render_filters

st.set_page_config(page_title="Evaluare pe zone", layout="wide")
render_filters()
st.title("Evaluare pe zone (benzi de scor)")

tab_curs, tab_titular, tab_asistent = st.tabs(["Cursuri", "Titulari", "Asistenți"])
for tab, entitate in [(tab_curs, "curs"), (tab_titular, "titular"), (tab_asistent, "asistent")]:
    with tab:
        df = queries.get_score_distribution(entitate)
        st.plotly_chart(px.pie(df, names="banda", values="num"), use_container_width=True)
