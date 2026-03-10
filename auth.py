"""Authentication, session management, and role/hotel access for SENPRO.

Usage in app.py (after st.set_page_config and db init):

    from auth import (
        get_current_user, get_current_username, get_current_role, get_actor_name,
        is_supplier_user, get_current_supplier_id, refresh_authenticated_user,
        is_admin, can_view_portfolio, can_review_projects,
        get_accessible_hotels, get_accessible_hotel_ids, user_can_access_hotel,
        _hotel_label, _project_label,
        get_scoped_projects, get_visible_project,
        ensure_active_hotel_scope, logout,
        _enforce_view_permissions, _enforce_session_timeout,
        get_navigation_menu, show_login, show_account_settings,
    )

Once you add those imports, delete the duplicate definitions in app.py.
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List

import streamlit as st

_LEGACY_VIEW_ALIASES = {
    "procurement_list": "hotel_item_list",
    "checklist": "hotel_item_list",
    "supplier_comparison": "hotel_rfp",
}

_PAGE_SPECS = [
    {
        "group": "Overview",
        "view_mode": "corporate_home",
        "path": "pages/home.py",
        "title": "Home",
        "icon": "🏛️",
        "audience": "internal",
    },
    {
        "group": "Overview",
        "view_mode": "portfolio_dashboard",
        "path": "pages/portfolio_dashboard.py",
        "title": "Portfolio",
        "icon": "📊",
        "audience": "portfolio",
    },
    {
        "group": "Operations",
        "view_mode": "project_workspace",
        "path": "pages/project_workspace.py",
        "title": "Project Workspace",
        "icon": "📐",
        "audience": "internal",
    },
    {
        "group": "Operations",
        "view_mode": "finance_workspace",
        "path": "pages/finance_workspace.py",
        "title": "Finance & P2P",
        "icon": "⚖️",
        "audience": "internal",
    },
    {
        "group": "Intelligence",
        "view_mode": "ai_assistant",
        "path": "pages/ai_assistant.py",
        "title": "Seneca",
        "icon": "✨",
        "audience": "internal",
    },
    {
        "group": "System",
        "view_mode": "directories_workspace",
        "path": "pages/directories_workspace.py",
        "title": "Directories",
        "icon": "📁",
        "audience": "internal",
    },
    {
        "group": "Supplier",
        "view_mode": "supplier_portal",
        "path": "pages/supplier_portal.py",
        "title": "SENPROVEN",
        "icon": "🚚",
        "audience": "supplier",
    },
    {
        "group": "System",
        "view_mode": "admin_panel",
        "path": "pages/admin_panel.py",
        "title": "Settings",
        "icon": "⚙️",
        "audience": "admin",
    },
    {
        "group": "Account",
        "view_mode": "account_settings",
        "path": "pages/account_settings.py",
        "title": "Account Settings",
        "icon": "👤",
        "audience": "all",
    },
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_db():
    """Lazy-load the shared database instance to avoid import-order issues."""
    from database_factory import get_database
    return get_database()


def _get_secret_section(section_name: str) -> Dict:
    """Safely read a secrets section without raising on missing keys."""
    try:
        return dict(st.secrets.get(section_name, {}))
    except Exception:
        return {}


def _get_runtime_setting(name: str, default=""):
    """Read one setting from env first, then Streamlit secrets."""
    value = os.environ.get(name)
    if value not in {None, ""}:
        return value
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


def _parse_positive_minutes(value, default: int) -> int:
    """Return a safe positive minute value from config."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _parse_iso_datetime(value: str):
    """Parse an ISO timestamp when present."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def get_current_user() -> Dict:
    """Return the logged-in user dict (empty dict when unauthenticated)."""
    return st.session_state.get("authenticated_user") or {}


def get_current_username() -> str:
    return get_current_user().get("username", "")


def get_current_role() -> str:
    return get_current_user().get("role", "")


def get_actor_name() -> str:
    """Display name used for audit and workflow entries."""
    user = get_current_user()
    return user.get("full_name") or user.get("username") or "Unknown User"


def is_supplier_user() -> bool:
    return get_current_role() == "supplier"


def get_current_supplier_id() -> str:
    return get_current_user().get("supplier_id", "")


def refresh_authenticated_user():
    """Re-read the current user from storage (pick up admin edits mid-session)."""
    current_user = get_current_user()
    user_id = current_user.get("user_id")
    if not user_id:
        return
    refreshed = _get_db().get_user(user_id)
    if refreshed:
        st.session_state.authenticated_user = refreshed


def is_admin() -> bool:
    return get_current_role() == "admin"


def can_view_portfolio() -> bool:
    """Portfolio reporting is available to portfolio managers and admins."""
    return get_current_role() in {"admin", "portfolio_manager"}


def can_review_projects() -> bool:
    """Project approvals / correction requests are manager-level actions."""
    return get_current_role() in {"admin", "portfolio_manager", "hotel_manager"}


def _normalize_view_mode(view_mode: str) -> str:
    """Map legacy route names onto the canonical view modes."""
    return _LEGACY_VIEW_ALIASES.get(str(view_mode or "").strip(), str(view_mode or "").strip())


def is_ai_feature_enabled() -> bool:
    """Whether the AI assistant should be exposed in the UI."""
    value = _get_runtime_setting("AI_FEATURE_ENABLED", "true")
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _is_page_visible(spec: Dict) -> bool:
    """Return True when the current user should see the given page spec."""
    if spec.get("view_mode") == "ai_assistant" and not is_ai_feature_enabled():
        return False
    audience = spec.get("audience", "internal")
    if audience == "all":
        return True
    if audience == "supplier":
        return is_supplier_user()
    if audience == "internal":
        return not is_supplier_user()
    if audience == "portfolio":
        return not is_supplier_user() and can_view_portfolio()
    if audience == "admin":
        return is_admin()
    return False


def get_default_view_mode() -> str:
    """Default landing view for the current user."""
    return "supplier_portal" if is_supplier_user() else "corporate_home"


def get_navigation_page_specs() -> Dict[str, List[Dict]]:
    """Role-aware grouped page metadata for the multipage router."""
    grouped: Dict[str, List[Dict]] = {}
    for spec in _PAGE_SPECS:
        if not _is_page_visible(spec):
            continue
        grouped.setdefault(spec["group"], []).append(spec)
    return grouped


def get_allowed_view_modes() -> List[str]:
    """Canonical view modes available to the current user."""
    allowed = []
    for specs in get_navigation_page_specs().values():
        for spec in specs:
            allowed.append(spec["view_mode"])
    return allowed


def can_access_view(view_mode: str) -> bool:
    """Whether the current user may access the requested view."""
    normalized_view = _normalize_view_mode(view_mode)
    if normalized_view == "ai_assistant":
        return is_ai_feature_enabled() and not is_supplier_user()
    allowed_view_modes = set(get_allowed_view_modes())
    if normalized_view in allowed_view_modes:
        return True

    if is_supplier_user():
        return normalized_view in {"supplier_portal", "account_settings"}

    internal_views = {
        "new_project",
        "hotel_item_list",
        "hotel_rfp",
        "capex_dashboard",
        "history",
        "comparison",
        "p2p_dashboard",
        "po_center",
        "invoice_center",
        "payment_center",
        "hotel_directory",
        "hotel_details",
        "vendor_directory",
    }
    if normalized_view in internal_views:
        return True

    if normalized_view == "portfolio_dashboard":
        return can_view_portfolio()
    if normalized_view == "admin_panel":
        return is_admin()
    return False


# ---------------------------------------------------------------------------
# Hotel and project access
# ---------------------------------------------------------------------------

def get_accessible_hotels() -> List[Dict]:
    """Hotels the current user is allowed to access."""
    hotels = _get_db().get_all_hotels()
    if is_admin():
        return hotels
    if is_supplier_user():
        return []
    allowed_ids = set(get_current_user().get("hotel_ids", []))
    return [h for h in hotels if h.get("hotel_id") in allowed_ids]


def get_accessible_hotel_ids() -> List[str]:
    return [h["hotel_id"] for h in get_accessible_hotels() if h.get("hotel_id")]


def user_can_access_hotel(hotel_id: str) -> bool:
    if is_admin():
        return True
    if not hotel_id:
        return False
    return hotel_id in set(get_current_user().get("hotel_ids", []))


def _hotel_label(hotel: Dict) -> str:
    return f"{hotel.get('name', 'Unnamed Hotel')} - {hotel.get('city', 'Unknown City')}"


def _project_label(project: Dict) -> str:
    info = project.get("hotel_info", {})
    hotel_name = info.get("property_name", "Unnamed Hotel")
    city = info.get("city", "Unknown City")
    project_name = info.get("project_name", "")
    suffix = f" | {project_name}" if project_name else ""
    return f"{hotel_name} - {city} ({project.get('project_id', '')}){suffix}"


def get_scoped_projects(ignore_hotel_scope: bool = False) -> List[Dict]:
    """Projects visible to the current user, optionally ignoring the active hotel scope."""
    projects = _get_db().get_all_projects()
    if not is_admin():
        allowed_ids = set(get_accessible_hotel_ids())
        projects = [p for p in projects if p.get("hotel_id") in allowed_ids]
    active = st.session_state.get("active_hotel_id")
    if not ignore_hotel_scope and active and active != "ALL":
        projects = [p for p in projects if p.get("hotel_id") == active]
    return projects


def get_visible_project(project_id: str) -> Dict:
    """Fetch one project only if it is within the current user's scope."""
    project = _get_db().get_project(project_id)
    if not project:
        return {}
    hotel_id = project.get("hotel_id")
    if hotel_id and not user_can_access_hotel(hotel_id):
        return {}
    if not hotel_id and not is_admin():
        return {}
    active = st.session_state.get("active_hotel_id")
    if active not in {None, "ALL"} and hotel_id != active:
        return {}
    return project


def ensure_active_hotel_scope():
    """Keep the selected hotel scope valid for the current user."""
    if is_supplier_user():
        st.session_state.active_hotel_id = None
        return

    hotels = get_accessible_hotels()
    hotel_ids = [h["hotel_id"] for h in hotels if h.get("hotel_id")]
    current = st.session_state.get("active_hotel_id")

    if can_view_portfolio() and hotel_ids:
        if current not in set(hotel_ids) | {"ALL"}:
            st.session_state.active_hotel_id = "ALL"
        return

    if current not in hotel_ids:
        st.session_state.active_hotel_id = hotel_ids[0] if hotel_ids else None


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------

def logout():
    """Clear the authenticated session."""
    st.session_state.authenticated_user = {}
    st.session_state.active_hotel_id = None
    st.session_state.current_project_id = None
    st.session_state.view_mode = "corporate_home"
    st.session_state.menu_open = False
    st.session_state.ai_messages = []
    st.session_state.last_activity_at = None
    st.session_state.session_started_at = None


def _enforce_view_permissions():
    """Redirect legacy single-file routing onto an allowed destination."""
    current_view = _normalize_view_mode(st.session_state.get("view_mode", get_default_view_mode()))
    if not can_access_view(current_view):
        st.session_state.view_mode = get_default_view_mode()
        return
    st.session_state.view_mode = current_view


def _is_login_locked_out(username: str) -> bool:
    """Return True if the account has had 5 consecutive failures in the last 15 min."""
    normalized = (username or "").strip().lower()
    if not normalized:
        return False
    db = _get_db()
    recent = db.get_login_events(limit=5, username=normalized)
    if len(recent) < 5 or any(e.get("success") for e in recent):
        return False
    latest = recent[0].get("timestamp")
    if not latest:
        return False
    try:
        latest_dt = datetime.fromisoformat(latest)
    except ValueError:
        return False
    return datetime.now() - latest_dt < timedelta(minutes=15)


def _enforce_session_timeout():
    """Log out sessions that have been idle past the configured timeout."""
    if not get_current_user():
        return
    auth_config = _get_secret_section("auth")
    timeout_minutes = _parse_positive_minutes(auth_config.get("session_timeout_minutes", 480), 480)
    absolute_timeout_minutes = _parse_positive_minutes(
        auth_config.get("absolute_session_timeout_minutes", max(timeout_minutes, 720)),
        max(timeout_minutes, 720),
    )
    now = datetime.now()
    last_seen = _parse_iso_datetime(st.session_state.get("last_activity_at"))
    session_started_at = _parse_iso_datetime(st.session_state.get("session_started_at"))

    if session_started_at is None:
        session_started_at = last_seen or now
        st.session_state.session_started_at = session_started_at.isoformat()

    if last_seen and last_seen > now + timedelta(minutes=5):
        st.session_state.login_notice = "Session expired. Please sign in again."
        logout()
        st.rerun()

    if session_started_at > now + timedelta(minutes=5):
        st.session_state.login_notice = "Session expired. Please sign in again."
        logout()
        st.rerun()

    if last_seen and now - last_seen > timedelta(minutes=timeout_minutes):
        st.session_state.login_notice = "Session expired due to inactivity."
        logout()
        st.rerun()

    if now - session_started_at > timedelta(minutes=absolute_timeout_minutes):
        st.session_state.login_notice = "Session expired. Please sign in again."
        logout()
        st.rerun()

    st.session_state.last_activity_at = now.isoformat()


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

def get_navigation_menu() -> List[tuple]:
    """Return role-aware (label, view_mode) pairs using the shared page registry."""
    menu = []
    for specs in get_navigation_page_specs().values():
        for spec in specs:
            menu.append((spec["title"], spec["view_mode"]))
    return menu


# ---------------------------------------------------------------------------
# Login screen
# ---------------------------------------------------------------------------

def show_login():
    """Render the SENPRO login page."""
    db = _get_db()
    auth_config = _get_secret_section("auth")
    default_admin_created = db.ensure_default_admin(
        auth_config.get("admin_username", "admin"),
        auth_config.get("admin_password", "admin123"),
    )

    user_count = len(db.get_all_users())
    hotel_count = len(db.get_all_hotels())
    supplier_count = len(db.get_all_suppliers())

    st.markdown(
        """
        <div class="corporate-hero">
            <h1>SENPRO</h1>
            <p>Corporate Procurement Program</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="login-shell">', unsafe_allow_html=True)
    st.markdown("### Corporate Access")
    st.caption(f"Configured users: {user_count} | Hotels: {hotel_count} | Suppliers: {supplier_count}")

    if default_admin_created:
        st.info(
            "Bootstrap admin created. Sign in with "
            f"`{auth_config.get('admin_username', 'admin')}` / "
            f"`{auth_config.get('admin_password', 'admin123')}` and change it in production."
        )
    if st.session_state.get("login_notice"):
        st.warning(st.session_state.login_notice)
        st.session_state.login_notice = ""

    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("LOGIN")
        password = st.text_input("PASSWORD", type="password")
        submit = st.form_submit_button("ENTER SENPRO", use_container_width=True, type="primary")

    st.markdown("</div>", unsafe_allow_html=True)

    if submit:
        if _is_login_locked_out(username):
            st.error("Too many failed login attempts. Try again in 15 minutes.")
            db.record_login_event(username, False, note="Locked out")
            return
        user = db.authenticate_user(username, password)
        if not user:
            db.record_login_event(username, False, note="Invalid credentials")
            st.error("Invalid username or password.")
            return

        now = datetime.now().isoformat()
        db.record_login_event(username, True, user_id=user.get("user_id", ""), role=user.get("role", ""))
        st.session_state.authenticated_user = user
        st.session_state.last_activity_at = now
        st.session_state.session_started_at = now
        if user.get("role") == "supplier":
            st.session_state.active_hotel_id = None
        else:
            if user.get("role") in {"admin", "portfolio_manager"} and len(user.get("hotel_ids", [])) != 1:
                st.session_state.active_hotel_id = "ALL"
            else:
                st.session_state.active_hotel_id = (user.get("hotel_ids") or [None])[0]
        st.session_state.view_mode = get_default_view_mode()
        st.rerun()


# ---------------------------------------------------------------------------
# Account settings
# ---------------------------------------------------------------------------

def show_account_settings():
    """Current user account settings — change password, view assigned hotels."""
    st.markdown('<div class="main-header">Account Settings</div>', unsafe_allow_html=True)
    db = _get_db()
    user = get_current_user()

    col1, col2 = st.columns(2)
    with col1:
        st.write("Name:", user.get("full_name", ""))
        st.write("Username:", user.get("username", ""))
        st.write("Role:", user.get("role", "").replace("_", " ").title())
    with col2:
        st.write("Email:", user.get("email", "") or "N/A")
        st.write("Supplier Link:", user.get("supplier_id", "") or "None")
        hotels = get_accessible_hotels()
        st.write("Hotels:", ", ".join(h.get("name", "") for h in hotels) if hotels else "None")

    with st.form("account_password_form"):
        current_password = st.text_input("Current Password", type="password")
        new_password = st.text_input("New Password", type="password")
        confirm_password = st.text_input("Confirm New Password", type="password")
        change_password = st.form_submit_button("Change Password", type="primary")

    if change_password:
        if not current_password or not new_password or not confirm_password:
            st.error("Fill in all password fields.")
        elif new_password != confirm_password:
            st.error("New password confirmation does not match.")
        elif len(new_password) < 8:
            st.error("New password must be at least 8 characters.")
        elif not db.authenticate_user(user.get("username", ""), current_password):
            st.error("Current password is incorrect.")
        else:
            db.save_user({
                "user_id": user.get("user_id"),
                "full_name": user.get("full_name", ""),
                "username": user.get("username", ""),
                "email": user.get("email", ""),
                "role": user.get("role", ""),
                "hotel_ids": user.get("hotel_ids", []),
                "supplier_id": user.get("supplier_id", ""),
                "active": user.get("active", True),
                "password": new_password,
            })
            refresh_authenticated_user()
            st.success("Password updated.")
