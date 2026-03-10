from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import streamlit as st


_CSS_PATH = Path(__file__).resolve().parent / "assets" / "style.css"

_SESSION_DEFAULTS = {
    "calculation_done": False,
    "results": {},
    "current_project_id": None,
    "view_mode": "corporate_home",
    "supplier_id": None,
    "authenticated_user": {},
    "active_hotel_id": None,
    "last_activity_at": None,
    "session_started_at": None,
    "login_notice": "",
    "menu_open": False,
    "checklist_page": 0,
}


def load_global_css() -> None:
    """Load the shared application stylesheet from disk."""
    css = _CSS_PATH.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def init_session_state() -> None:
    """Initialize all shared Streamlit session keys in one place."""
    for key, default_value in _SESSION_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = deepcopy(default_value)
