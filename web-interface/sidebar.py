"""Shared cascading sidebar filters. Every page calls render_filters() so the
same widgets/behavior appear everywhere. Coleg B owns this file.

Streamlit multipage apps don't share widget state across pages automatically,
so pages read filters via st.session_state (populated here) rather than via
a return value alone — call render_filters() at the top of every page.
"""
import streamlit as st

CICLURI = ["Licență", "Master"]
TRACKURI = ["CTI", "IS"]


def render_filters():
    st.sidebar.title("Feedback POLITEHNICA")
    st.sidebar.caption("conectat ca **admin** · acces la toate datele")

    an_universitar = st.sidebar.selectbox(
        "An universitar",
        ["2025-2026 sem1", "2024-2025 sem1", "2023-2024 sem1", "2022-2023", "2022-2023 sem1",
         "2021-2022", "2020-2021", "2019-2020", "2018-2019"],
        key="an_universitar",
    )
    ciclu = st.sidebar.selectbox("Ciclu", ["Toate"] + CICLURI, key="ciclu")
    an_studiu = st.sidebar.selectbox("An de studiu", ["Toate", 1, 2, 3, 4], key="an_studiu")
    semestru = st.sidebar.selectbox("Semestru", ["Toate", "Semestrul 1", "Semestrul 2"], key="semestru")
    track = st.sidebar.multiselect("Track", TRACKURI, default=TRACKURI, key="track")

    if st.sidebar.button("↻ Resetează filtrele"):
        for k in ("an_universitar", "ciclu", "an_studiu", "semestru", "track"):
            st.session_state.pop(k, None)
        st.rerun()

    return dict(an_universitar=an_universitar, ciclu=ciclu, an_studiu=an_studiu,
                semestru=semestru, track=track)
