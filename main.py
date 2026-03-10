import streamlit as st

from app import (
    _MULTIPAGE_NAVIGATION_FLAG,
    enforce_authenticated_app_access,
    initialize_app_runtime,
    render_footer,
    render_shared_sidebar,
)
from auth import get_navigation_page_specs


def _build_pages():
    """Return the role-aware Streamlit page registry."""
    pages = {}
    for group_name, specs in get_navigation_page_specs().items():
        pages[group_name] = [
            st.Page(spec["path"], title=spec["title"], icon=spec["icon"])
            for spec in specs
        ]
    return pages


def main() -> None:
    """Run the multipage Streamlit entrypoint."""
    st.set_page_config(page_title="SENPRO", page_icon="📋", layout="wide")
    initialize_app_runtime()
    st.session_state[_MULTIPAGE_NAVIGATION_FLAG] = True
    enforce_authenticated_app_access()
    pages = _build_pages()
    navigator = st.navigation(pages)
    render_shared_sidebar()
    navigator.run()
    render_footer()


if __name__ == "__main__":
    main()
