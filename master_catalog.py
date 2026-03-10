from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import streamlit as st


CATALOG_PATH = Path(__file__).resolve().parent / "config" / "master_catalog.json"


@lru_cache(maxsize=1)
def load_master_catalog() -> list[dict[str, Any]]:
    """Load the static master catalog from disk once per process."""
    if not CATALOG_PATH.exists():
        return []
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def load_master_catalog_for_app() -> list[dict[str, Any]]:
    """Streamlit-friendly cached wrapper for app usage."""
    return load_master_catalog()
