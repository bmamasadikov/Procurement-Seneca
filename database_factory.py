"""Shared database singleton for SENPRO modules.

Import ``get_database()`` from here wherever you need the db instance.
Because ``@st.cache_resource`` caches on the function object, importing the
same function from the same module returns the same backend instance until the
cache is explicitly cleared.
"""
import os

import streamlit as st

from database import ProcurementDatabase


def _get_runtime_setting(name: str, default: str = "") -> str:
    """Read one runtime setting from env first, then Streamlit secrets."""
    value = os.environ.get(name)
    if value not in {None, ""}:
        return value
    try:
        return str(st.secrets.get(name, default) or default)
    except Exception:
        return default


def _get_runtime_int(name: str, default: int) -> int:
    """Read one integer runtime setting with a safe fallback."""
    raw_value = _get_runtime_setting(name, str(default))
    try:
        return int(str(raw_value).strip())
    except (TypeError, ValueError):
        return default


def _get_runtime_bool(name: str, default: bool = False) -> bool:
    """Read one boolean runtime setting with a safe fallback."""
    raw_value = _get_runtime_setting(name, "")
    if raw_value in {None, ""}:
        return default
    return str(raw_value).strip().lower() in {"1", "true", "yes", "on"}


def _get_postgres_engine_options() -> dict:
    """Build SQLAlchemy pool options for PostgreSQL deployments."""
    return {
        "pool_size": _get_runtime_int("DB_POOL_SIZE", 20),
        "max_overflow": _get_runtime_int("DB_MAX_OVERFLOW", 10),
        "pool_timeout": _get_runtime_int("DB_POOL_TIMEOUT", 30),
        "pool_recycle": _get_runtime_int("DB_POOL_RECYCLE", 3600),
    }


@st.cache_resource(show_spinner=False)
def get_database():
    """Initialize and cache the database backend (JSON or PostgreSQL)."""
    database_url = _get_runtime_setting("DATABASE_URL", "")
    if database_url:
        from postgres_database import PostgresProcurementDatabase

        return PostgresProcurementDatabase(
            database_url,
            engine_options=_get_postgres_engine_options(),
        )

    if _get_runtime_bool("REQUIRE_DATABASE_URL", False):
        raise RuntimeError(
            "DATABASE_URL is required when REQUIRE_DATABASE_URL=true. "
            "Configure PostgreSQL or disable REQUIRE_DATABASE_URL."
        )

    app_data_path = _get_runtime_setting("APP_DATA_PATH", "")
    return ProcurementDatabase(app_data_path or "procurement_data")


def clear_database_cache() -> None:
    """Clear the cached database instance for tests or controlled reloads."""
    get_database.clear()
