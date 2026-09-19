"""Aevora dispatcher console entrypoint: `streamlit run ui/app.py`.

Sets the theme chrome and dispatcher auth gate once, then routes to a view.
No scoring logic in ui/ (CLAUDE.md rule 1) - views call ui/services.py.
"""

from __future__ import annotations

import streamlit as st

from ui.components import inject_css, render_sidebar, require_dispatcher

st.set_page_config(page_title="Aevora - Dispatch", page_icon=":material/electric_moped:", layout="wide")

session = require_dispatcher()
inject_css()
render_sidebar(session)

page = st.navigation(
    [
        st.Page("views/fleet.py", title="Live fleet", icon=":material/radar:", default=True),
        st.Page("views/dispatch.py", title="Plan & dispatch", icon=":material/route:"),
        st.Page("views/monitor.py", title="Air & alerts", icon=":material/air:"),
    ]
)
page.run()
