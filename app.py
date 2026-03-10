import streamlit as st
import pandas as pd
import openpyxl
from io import BytesIO
from datetime import datetime, timedelta
import json
import os
import re
from difflib import SequenceMatcher
from typing import Dict, List
from urllib.parse import quote
from ai_engine import AI_SUGGESTIONS, AI_TOOLS, build_system_prompt, execute_ai_tool
from app_bootstrap import init_session_state, load_global_css
from calculator import ProcurementCalculator
from conference_planning import (
    ROOM_TYPE_OPTIONS,
    SEATING_STYLE_OPTIONS,
    calculate_conference_room_plan,
)
from data_loader import BrandStandards
from database_factory import get_database
from google_workspace import GoogleWorkspaceError, GoogleWorkspaceService
from master_catalog import load_master_catalog_for_app
from stage1_exports import (
    EXPORT_PDF_AVAILABLE as STAGE1_EXPORT_PDF_AVAILABLE,
    PROCUREMENT_TABLE_COLUMNS,
    build_export_file_stem,
    build_export_summary_df,
    build_procurement_export_df,
    build_rfp_export_df,
    generate_csv_bytes,
    generate_excel_export as generate_stage1_excel_export,
    generate_table_pdf,
)
try:
    import avenue1936_loader as av
except ImportError:
    av = None

try:
    from google import genai as _google_genai_module
    from google.genai import types as _google_genai_types
    GEMINI_AVAILABLE = True
except ImportError:
    _google_genai_module = None
    _google_genai_types = None
    GEMINI_AVAILABLE = False

db = get_database()

# Shared auth and notification modules.
from auth import (  # noqa: E402
    get_current_user, get_current_username, get_current_role, get_actor_name,
    is_supplier_user, get_current_supplier_id, refresh_authenticated_user,
    is_admin, can_view_portfolio, can_review_projects, is_ai_feature_enabled,
    get_accessible_hotels, get_accessible_hotel_ids, user_can_access_hotel,
    _hotel_label, _project_label,
    get_scoped_projects, get_visible_project,
    ensure_active_hotel_scope, logout,
    _enforce_view_permissions, _enforce_session_timeout,
    get_navigation_menu, show_login, show_account_settings,
)
from notification_utils import (  # noqa: E402
    get_user_notifications, show_notification_center,
    _create_notification,
    _notify_project_workflow, _notify_item_review,
    _notify_purchase_order_status, _notify_invoice_status,
    _notify_payment_recorded,
    _get_smtp_config, queue_email_smtp,
)
_MULTIPAGE_NAVIGATION_FLAG = "_multipage_navigation_enabled"


def initialize_app_runtime() -> None:
    """Load global CSS and bootstrap shared Streamlit session state."""
    load_global_css()
    init_session_state()


def _get_secret_section(section_name: str) -> Dict:
    """Safely read a secrets section."""
    try:
        return dict(st.secrets.get(section_name, {}))
    except Exception:
        return {}

def can_manage_master_data() -> bool:
    """Corporate record management is reserved for managers and admins."""
    return get_current_role() in {"admin", "portfolio_manager", "hotel_manager"}


def _parse_bool(value, default: bool = False) -> bool:
    """Best-effort bool parsing for env/secrets values."""
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() not in {"", "0", "false", "no", "off"}


def _get_runtime_setting(name: str, default=""):
    """Read one setting from env first, then Streamlit secrets."""
    value = os.environ.get(name)
    if value not in {None, ""}:
        return value
    try:
        value = st.secrets.get(name, default)
    except Exception:
        value = default
    if isinstance(value, dict):
        return json.dumps(value)
    return value


CATALOG_MATCH_THRESHOLD = 0.70
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
SENECA_GREETING = "I am Seneca. How may I bring clarity to your procurement matrix today?"


def _get_gemini_api_key() -> str:
    """Resolve the Gemini API key from config only."""
    api_key = ""
    try:
        api_key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        api_key = ""
    if api_key:
        return api_key
    return os.environ.get("GEMINI_API_KEY", "")


def _get_gemini_model() -> str:
    """Resolve the Gemini model name from env or Streamlit secrets."""
    return str(_get_runtime_setting("GEMINI_MODEL", DEFAULT_GEMINI_MODEL) or DEFAULT_GEMINI_MODEL).strip()


@st.cache_data(show_spinner=False)
def _get_master_catalog_context() -> str:
    """Serialize the master catalog once for assistant grounding."""
    catalog = load_master_catalog_for_app()
    if not catalog:
        return "Catalog data not found."
    return json.dumps(catalog, ensure_ascii=False, indent=2)


def _get_gemini_runtime_config() -> Dict[str, str]:
    """Return the Gemini runtime configuration or an actionable error."""
    gemini_api_key = _get_gemini_api_key()

    if gemini_api_key and not GEMINI_AVAILABLE:
        return {
            "message": "Install the Gemini SDK: `pip install google-genai`",
        }
    if not GEMINI_AVAILABLE:
        return {
            "message": "Install the Gemini SDK: `pip install google-genai`",
        }
    if not gemini_api_key:
        return {
            "message": "Configure `GEMINI_API_KEY` in `.streamlit/secrets.toml` or your environment.",
        }

    return {
        "model": _get_gemini_model(),
        "api_key": gemini_api_key,
        "message": "",
    }


def _get_google_workspace_config() -> Dict:
    """Runtime configuration for Google Workspace integration."""
    return {
        "enabled": _parse_bool(_get_runtime_setting("GOOGLE_WORKSPACE_ENABLED", "")),
        "service_account_json": _get_runtime_setting("GOOGLE_SERVICE_ACCOUNT_JSON", ""),
        "shared_drive_id": _get_runtime_setting("GOOGLE_SHARED_DRIVE_ID", ""),
        "root_folder_id": _get_runtime_setting("GOOGLE_DRIVE_ROOT_FOLDER_ID", ""),
    }


def _get_senproven_url() -> str:
    """Optional configured URL for the separate SENPROVEN application."""
    return str(_get_runtime_setting("SENPROVEN_URL", "") or "").strip()


@st.cache_resource
def _build_google_workspace_service(service_account_json: str, shared_drive_id: str, root_folder_id: str):
    """Create the cached Google Workspace service."""
    return GoogleWorkspaceService(
        service_account_json=service_account_json,
        shared_drive_id=shared_drive_id,
        root_folder_id=root_folder_id,
        enabled=True,
    )


def get_google_workspace_service():
    """Return the Google Workspace service plus an optional status message."""
    config = _get_google_workspace_config()
    if not config.get("enabled"):
        return None, "Google Workspace is disabled."
    try:
        service = _build_google_workspace_service(
            config.get("service_account_json", ""),
            config.get("shared_drive_id", ""),
            config.get("root_folder_id", ""),
        )
    except GoogleWorkspaceError as exc:
        return None, str(exc)
    return service, ""


def _senprocure_destination() -> str:
    """Role-aware destination for the SENPROCURE dashboard card."""
    return "portfolio_dashboard" if can_view_portfolio() or is_admin() else "new_project"


_LEGACY_VIEW_ALIASES = {
    "procurement_list": "hotel_item_list",
    "checklist": "hotel_item_list",
    "supplier_comparison": "hotel_rfp",
}

_VIEW_ROUTE_TARGETS = {
    "corporate_home": {"page": "pages/home.py"},
    "portfolio_dashboard": {"page": "pages/portfolio_dashboard.py"},
    "project_workspace": {"page": "pages/project_workspace.py"},
    "new_project": {"page": "pages/project_workspace.py", "state": {"project_workspace_section": "Calculator"}},
    "hotel_item_list": {"page": "pages/project_workspace.py", "state": {"project_workspace_section": "Procurement List"}},
    "hotel_rfp": {"page": "pages/project_workspace.py", "state": {"project_workspace_section": "Vendor RFP"}},
    "capex_dashboard": {"page": "pages/project_workspace.py", "state": {"project_workspace_section": "CAPEX"}},
    "history": {"page": "pages/project_workspace.py", "state": {"project_workspace_section": "Project History"}},
    "comparison": {"page": "pages/project_workspace.py", "state": {"project_workspace_section": "Comparison"}},
    "finance_workspace": {"page": "pages/finance_workspace.py"},
    "p2p_dashboard": {"page": "pages/finance_workspace.py", "state": {"finance_workspace_section": "Dashboard"}},
    "po_center": {"page": "pages/finance_workspace.py", "state": {"finance_workspace_section": "PO Center"}},
    "invoice_center": {"page": "pages/finance_workspace.py", "state": {"finance_workspace_section": "Invoices"}},
    "payment_center": {"page": "pages/finance_workspace.py", "state": {"finance_workspace_section": "Payments"}},
    "directories_workspace": {"page": "pages/directories_workspace.py"},
    "hotel_directory": {"page": "pages/directories_workspace.py", "state": {"directories_workspace_section": "Hotels"}},
    "hotel_details": {"page": "pages/directories_workspace.py", "state": {"directories_workspace_section": "Hotel Details"}},
    "vendor_directory": {"page": "pages/directories_workspace.py", "state": {"directories_workspace_section": "Vendors"}},
    "supplier_portal": {"page": "pages/supplier_portal.py"},
    "ai_assistant": {"page": "pages/ai_assistant.py"},
    "account_settings": {"page": "pages/account_settings.py"},
    "admin_panel": {"page": "pages/admin_panel.py"},
}


def _normalize_view_mode(view_mode: str) -> str:
    """Map legacy route names onto the current canonical workspaces."""
    return _LEGACY_VIEW_ALIASES.get(str(view_mode or "").strip(), str(view_mode or "").strip())


def _is_multipage_navigation_enabled() -> bool:
    """Whether the new `main.py` router is driving navigation."""
    return bool(st.session_state.get(_MULTIPAGE_NAVIGATION_FLAG, False))


def _rerun_if_legacy() -> None:
    """Avoid duplicate reruns when `st.switch_page()` already handles navigation."""
    if not _is_multipage_navigation_enabled():
        st.rerun()


def _set_view_mode(view_mode: str, hotel_id: str = "", project_id: str = ""):
    """Central navigation helper for Stage 1 views."""
    normalized_view = _normalize_view_mode(view_mode)
    st.session_state.view_mode = normalized_view
    if hotel_id:
        st.session_state.active_hotel_id = hotel_id
    if project_id:
        st.session_state.current_project_id = project_id
    if _is_multipage_navigation_enabled():
        route_target = _VIEW_ROUTE_TARGETS.get(normalized_view, {})
        for state_key, state_value in route_target.get("state", {}).items():
            st.session_state[state_key] = state_value
        page_path = route_target.get("page")
        if page_path:
            st.switch_page(page_path)


def _build_stage1_project_meta(project: Dict, filters: Dict[str, object]) -> Dict[str, object]:
    """Metadata block used in Stage 1 download and print files."""
    hotel_info = project.get("hotel_info", {})
    metadata = {
        "Hotel": hotel_info.get("property_name", ""),
        "Project ID": project.get("project_id", ""),
        "Project Name": hotel_info.get("project_name", ""),
        "Brand": hotel_info.get("brand", ""),
        "Rooms": hotel_info.get("total_rooms", 0),
    }
    for label, value in (filters or {}).items():
        metadata[label] = value
    return metadata


def _build_procurement_export_bundle(
    project: Dict,
    items: List[Dict],
    filters: Dict[str, object],
    file_suffix: str = "hotel_item_list",
    export_name: str = "Procurement List",
) -> Dict[str, object]:
    """Build the shared procurement export payload used by current and legacy views."""
    rows_df = build_procurement_export_df(items)
    return {
        "rows_df": rows_df,
        "summary_df": build_export_summary_df(export_name, project, filters, rows_df),
        "project_meta": _build_stage1_project_meta(project, filters),
        "file_stem": build_export_file_stem(project, file_suffix),
        "export_name": export_name,
    }


def _render_stage1_export_toolbar(
    kind: str,
    file_stem: str,
    rows_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    project_meta: Dict[str, object],
    pdf_title: str,
    pdf_group_by: str | None = None,
    pdf_repeat_columns: List[str] | None = None,
    context_column: str | None = None,
    table_columns: List[str] | None = None,
    flat_when_multi_context: bool = False,
) -> None:
    """Render local CSV, Excel, PDF, and print-PDF actions for Stage 1 views."""
    if rows_df.empty:
        st.caption("No rows available to download or print.")
        return

    csv_bytes = generate_csv_bytes(
        rows_df,
        context_column=context_column,
        table_columns=table_columns,
        flat_when_multi_context=flat_when_multi_context,
    )
    excel_bytes = generate_stage1_excel_export(
        kind,
        rows_df,
        summary_df,
        context_column=context_column,
        table_columns=table_columns,
    )

    pdf_bytes = None
    print_pdf_bytes = None
    if STAGE1_EXPORT_PDF_AVAILABLE:
        pdf_bytes = generate_table_pdf(
            pdf_title,
            project_meta,
            rows_df,
            mode="download",
            repeat_columns=pdf_repeat_columns,
            context_column=context_column,
            table_columns=table_columns,
        )
        print_pdf_bytes = generate_table_pdf(
            pdf_title,
            project_meta,
            rows_df,
            mode="print",
            group_by=pdf_group_by,
            repeat_columns=pdf_repeat_columns,
            context_column=context_column,
            table_columns=table_columns,
        )

    st.markdown("### Download & Print")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.download_button(
            "Download CSV",
            data=csv_bytes,
            file_name=f"{file_stem}.csv",
            mime="text/csv",
            use_container_width=True,
            key=f"{file_stem}_csv",
        )
    with col2:
        st.download_button(
            "Download Excel",
            data=excel_bytes,
            file_name=f"{file_stem}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key=f"{file_stem}_xlsx",
        )
    with col3:
        if STAGE1_EXPORT_PDF_AVAILABLE:
            st.download_button(
                "Download PDF",
                data=pdf_bytes,
                file_name=f"{file_stem}.pdf",
                mime="application/pdf",
                use_container_width=True,
                key=f"{file_stem}_pdf",
            )
        else:
            st.button("Download PDF", disabled=True, use_container_width=True, key=f"{file_stem}_pdf_disabled")
    with col4:
        if STAGE1_EXPORT_PDF_AVAILABLE:
            st.download_button(
                "Print PDF",
                data=print_pdf_bytes,
                file_name=f"{file_stem}_print.pdf",
                mime="application/pdf",
                use_container_width=True,
                key=f"{file_stem}_print_pdf",
            )
        else:
            st.button("Print PDF", disabled=True, use_container_width=True, key=f"{file_stem}_print_disabled")

    if not STAGE1_EXPORT_PDF_AVAILABLE:
        st.caption("PDF export is unavailable because `reportlab` is not installed.")


def _format_conference_table_recommendation(room_plan: Dict) -> str:
    """Readable table recommendation for conference planning."""
    shape = room_plan.get("recommended_table_shape", "") or "Not set"
    length = room_plan.get("recommended_table_length_m")
    if shape == "No Main Table":
        return "No main table recommended for theater layout."
    if length:
        return f"{shape} | {length:.1f} m"
    return shape


def _conference_plan_state_key(room_index: int) -> str:
    """Stable session-state key for one calculated conference room plan."""
    return f"conference_room_plan_{room_index}"


def _collect_conference_room_plans(room_count: int) -> Dict:
    """Aggregate calculated room plans stored by the conference fragments."""
    conference_rooms = []
    errors: List[str] = []
    warnings: List[str] = []

    for room_index in range(room_count):
        room_plan = st.session_state.get(_conference_plan_state_key(room_index), {}) or {}
        conference_rooms.append(room_plan)
        room_label = room_plan.get("room_name") or f"Room {room_index + 1}"
        errors.extend([f"{room_label}: {error}" for error in room_plan.get("errors", [])])
        warnings.extend([f"{room_label}: {warning}" for warning in room_plan.get("warnings", [])])

    total_final_capacity = sum(int(room.get("final_procurement_occupancy", 0) or 0) for room in conference_rooms)
    total_chairs = sum(
        int(item.get("Total Qty", 0) or 0)
        for room in conference_rooms
        for item in room.get("procurement_preview", [])
        if "Chair" in str(item.get("Item", ""))
    )
    return {
        "conference_rooms": conference_rooms,
        "errors": errors,
        "warnings": warnings,
        "total_final_capacity": total_final_capacity,
        "total_chairs": total_chairs,
    }


def _clear_stale_conference_room_plans(room_count: int) -> None:
    """Remove saved room plans that are no longer visible after count changes."""
    stale_keys = []
    prefix = _conference_plan_state_key("")
    for key in st.session_state.keys():
        if not str(key).startswith(prefix):
            continue
        try:
            room_index = int(str(key).replace(prefix, "", 1))
        except ValueError:
            continue
        if room_index >= room_count:
            stale_keys.append(key)

    for key in stale_keys:
        del st.session_state[key]


@st.fragment
def _render_conference_room_editor(room_index: int) -> Dict:
    """Render one conference room form with fragment-scoped live calculations."""
    with st.expander(f"Conference / Meeting Room {room_index + 1}", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            room_name = st.text_input(
                "Room Name *",
                value=f"Meeting Room {room_index + 1}",
                key=f"conference_room_name_{room_index}",
            )
            room_code = st.text_input(
                "Room Code / Identifier",
                value=f"CONF-{room_index + 1:02d}",
                key=f"conference_room_code_{room_index}",
            )
            room_type = st.selectbox(
                "Room Type *",
                [""] + ROOM_TYPE_OPTIONS,
                index=1 if room_index == 0 else 0,
                key=f"conference_room_type_{room_index}",
            )
            seating_style = st.selectbox(
                "Seating Style *",
                [""] + SEATING_STYLE_OPTIONS,
                index=2 if room_index == 0 else 0,
                key=f"conference_seating_style_{room_index}",
            )

        with col2:
            length_m = st.number_input(
                "Length (m)",
                min_value=0.0,
                max_value=200.0,
                value=0.0,
                step=0.1,
                key=f"conference_length_{room_index}",
            )
            width_m = st.number_input(
                "Width (m)",
                min_value=0.0,
                max_value=200.0,
                value=0.0,
                step=0.1,
                key=f"conference_width_{room_index}",
            )
            total_area_override = st.checkbox(
                "Override calculated total area",
                value=False,
                key=f"conference_total_area_override_{room_index}",
            )
            total_area_m2 = st.number_input(
                "Total Area (m²) *",
                min_value=0.0,
                max_value=10000.0,
                value=0.0,
                step=0.1,
                key=f"conference_total_area_{room_index}",
                disabled=not total_area_override and length_m > 0 and width_m > 0,
            )

        non_usable_area_m2 = st.number_input(
            "Non-Usable Area (m²)",
            min_value=0.0,
            max_value=10000.0,
            value=0.0,
            step=0.1,
            key=f"conference_non_usable_area_{room_index}",
            help="Sideboards, cabinets, AV stations, columns, or fixed furniture.",
        )
        notes = st.text_area(
            "Notes",
            key=f"conference_notes_{room_index}",
            placeholder="Planning notes, installation constraints, accessibility notes, or supplier guidance.",
        )

        room_plan = calculate_conference_room_plan(
            {
                "room_name": room_name,
                "room_code": room_code,
                "room_type": room_type,
                "seating_style": seating_style,
                "length_m": length_m,
                "width_m": width_m,
                "total_area_m2": total_area_m2,
                "total_area_override": total_area_override,
                "non_usable_area_m2": non_usable_area_m2,
                "notes": notes,
            }
        )
        st.session_state[_conference_plan_state_key(room_index)] = room_plan

        if room_plan.get("auto_total_area_m2") and total_area_override:
            st.caption(f"Auto area from dimensions: {room_plan['auto_total_area_m2']:.2f} m²")

        metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
        with metric_col1:
            st.metric("Total Area", f"{room_plan.get('total_area_m2', 0):,.2f} m²")
        with metric_col2:
            st.metric("Usable Area", f"{room_plan.get('usable_area_m2', 0):,.2f} m²")
        with metric_col3:
            st.metric("Theoretical Capacity", int(room_plan.get("theoretical_occupancy", 0) or 0))
        with metric_col4:
            st.metric("Final Procurement Capacity", int(room_plan.get("final_procurement_occupancy", 0) or 0))

        summary_col1, summary_col2 = st.columns(2)
        with summary_col1:
            st.write("Recommended Table:", _format_conference_table_recommendation(room_plan))
        with summary_col2:
            st.write("Default Planning Factor:", f"{room_plan.get('default_area_per_person_m2', 0):.2f} m² / person")

        for error in room_plan.get("errors", []):
            st.error(error)
        for warning in room_plan.get("warnings", []):
            st.warning(warning)

        preview_rows = [
            {
                "Item": item.get("Item", ""),
                "Calculated Qty": item.get("Total Qty", 0),
                "Unit": item.get("Unit", ""),
                "Calculation Basis": item.get("Calculation Basis", ""),
                "Notes": item.get("Notes", ""),
            }
            for item in room_plan.get("procurement_preview", [])
        ]
        if preview_rows:
            st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)
        else:
            st.caption("Procurement quantities will appear once the room has valid planning inputs.")

        return room_plan


def _render_conference_planning_section() -> Dict:
    """Render the conference planning section inside New Project."""
    st.markdown('<div class="section-header">Conference & Meeting Spaces</div>', unsafe_allow_html=True)
    conference_presence = st.radio(
        "Does this hotel have conference or meeting rooms?",
        ["No", "Yes"],
        horizontal=True,
        key="has_conference_spaces",
    )
    has_conference_spaces = conference_presence == "Yes"
    if not has_conference_spaces:
        _clear_stale_conference_room_plans(0)
        st.info("Conference / meeting spaces are set to zero for this project.")
        return {
            "has_conference_spaces": False,
            "conference_room_count": 0,
            "conference_rooms": [],
            "errors": [],
            "warnings": [],
        }

    conference_room_count = int(
        st.number_input(
            "Conference / Meeting Room Count *",
            min_value=1,
            max_value=50,
            value=1,
            step=1,
            key="conference_room_count",
        )
    )
    _clear_stale_conference_room_plans(conference_room_count)
    st.caption("Each room planner updates independently for faster editing.")

    for room_index in range(conference_room_count):
        _render_conference_room_editor(room_index)

    conference_plan = _collect_conference_room_plans(conference_room_count)
    st.markdown("### Conference Portfolio Summary")
    summary_col1, summary_col2, summary_col3 = st.columns(3)
    with summary_col1:
        st.metric("Rooms Planned", conference_room_count)
    with summary_col2:
        st.metric("Total Final Capacity", conference_plan["total_final_capacity"])
    with summary_col3:
        st.metric("Calculated Chair Qty", conference_plan["total_chairs"])

    return {
        "has_conference_spaces": True,
        "conference_room_count": conference_room_count,
        "conference_rooms": conference_plan["conference_rooms"],
        "errors": conference_plan["errors"],
        "warnings": conference_plan["warnings"],
    }


def _merge_workspace_links(existing: Dict, updates: Dict) -> Dict:
    """Merge workspace link payloads while preserving existing values."""
    merged = dict(existing or {})
    for key, value in (updates or {}).items():
        merged[key] = value or ""
    return merged


def _render_workspace_links(workspace_links: Dict, labels: Dict[str, str]):
    """Render only the workspace links that are currently available."""
    available_links = [
        f"[{label}]({workspace_links.get(key, '')})"
        for key, label in labels.items()
        if workspace_links.get(key)
    ]
    if not available_links:
        st.caption("No Google Workspace links have been created yet.")
        return
    st.markdown(" | ".join(available_links))


def _render_supplier_catalog_library_preview(supplier_id: str, key_prefix: str = "vendor_directory"):
    """Read-only supplier catalog preview for SENPRO consumers."""
    catalogs = db.get_supplier_catalogs(supplier_id)
    st.markdown("### SENPROVEN Catalogue Data")
    st.caption("Read-only catalogue access from SENPRO. Vendors manage uploads, specifications, and notes in the separate SENPROVEN application.")
    if not catalogs:
        st.info("No vendor catalogues have been published yet.")
        return

    catalog_lookup = {
        f"{catalog.get('name', 'Catalogue')} ({len(catalog.get('items', []))} items)": catalog
        for catalog in catalogs
    }
    selected_catalog_label = st.selectbox("Catalogue", list(catalog_lookup.keys()), key=f"{key_prefix}_catalog_select")
    selected_catalog = catalog_lookup[selected_catalog_label]
    items = selected_catalog.get("items", [])

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Items", len(items))
    with col2:
        st.metric("Images", selected_catalog.get("image_count", 0))
    with col3:
        st.metric("Uploaded", str(selected_catalog.get("uploaded_at", ""))[:10])

    source_type = selected_catalog.get("source_type", "") or "manual"
    st.caption(f"Source type: {source_type}")
    preview_rows = [
        {
            "Item": item.get("item_name", ""),
            "Specification": item.get("specification", ""),
            "Notes": item.get("notes", ""),
            "Description": item.get("description", ""),
            "Unit": item.get("unit", ""),
            "Price": item.get("price", ""),
            "Currency": item.get("currency", ""),
            "Price Available": "Yes" if item.get("price_available") else "No",
        }
        for item in items
    ]
    preview_df = pd.DataFrame(preview_rows)
    if not preview_df.empty:
        st.dataframe(preview_df, use_container_width=True, hide_index=True)


def _persist_hotel_workspace_links(hotel_id: str, workspace_links: Dict):
    """Write merged workspace metadata back to one hotel record."""
    hotel = db.get_hotel(hotel_id)
    if not hotel:
        return
    db.save_hotel(
        {
            "hotel_id": hotel.get("hotel_id"),
            "name": hotel.get("name", ""),
            "brand": hotel.get("brand", ""),
            "city": hotel.get("city", ""),
            "country": hotel.get("country", ""),
            "total_rooms": hotel.get("total_rooms", 0),
            "status": hotel.get("status", "active"),
            "notes": hotel.get("notes", ""),
            "workspace_links": _merge_workspace_links(hotel.get("workspace_links", {}), workspace_links),
            "created_at": hotel.get("created_at"),
        }
    )


def _persist_supplier_workspace_links(supplier_id: str, workspace_links: Dict):
    """Write merged workspace metadata back to one supplier record."""
    supplier = db.get_supplier(supplier_id)
    if not supplier:
        return
    db.save_supplier(
        {
            "supplier_id": supplier.get("supplier_id"),
            "name": supplier.get("name", ""),
            "email": supplier.get("email", ""),
            "phone": supplier.get("phone", ""),
            "website": supplier.get("website", ""),
            "address": supplier.get("address", ""),
            "categories": supplier.get("categories", []),
            "contact_person": supplier.get("contact_person", ""),
            "notes": supplier.get("notes", ""),
            "status": supplier.get("status", "active"),
            "workspace_links": _merge_workspace_links(supplier.get("workspace_links", {}), workspace_links),
            "created_at": supplier.get("created_at"),
        }
    )


def _persist_project_workspace_links(project_id: str, workspace_links: Dict):
    """Write merged workspace metadata back to one project record."""
    db.update_project_workspace_links(
        project_id,
        _merge_workspace_links(db.get_project(project_id).get("workspace_links", {}), workspace_links),
        updated_by=get_actor_name(),
    )


def _parse_sheet_number(value, default: float = 0.0) -> float:
    """Best-effort numeric parsing for Google Sheet values."""
    if value in {None, ""}:
        return default
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return default


def _find_supplier_by_sheet_value(supplier_id: str, supplier_name: str) -> Dict:
    """Resolve a supplier from a pulled sheet row."""
    suppliers = db.get_all_suppliers()
    by_id = {supplier.get("supplier_id", ""): supplier for supplier in suppliers}
    if supplier_id and supplier_id in by_id:
        return by_id[supplier_id]
    normalized_name = (supplier_name or "").strip().lower()
    for supplier in suppliers:
        if supplier.get("name", "").strip().lower() == normalized_name:
            return supplier
    return {}


def _parse_row_key(row_key: str, project_id: str):
    """Validate and parse one immutable Google Sheet row key."""
    row_key = str(row_key or "").strip()
    if ":" not in row_key:
        return None
    row_project_id, item_index = row_key.split(":", 1)
    if row_project_id != project_id:
        return None
    try:
        return int(item_index)
    except ValueError:
        return None


def _mark_sheet_push(project_id: str, items: List[Dict], timestamp: str):
    """Persist the push timestamp after a successful Google write."""
    for index, _ in enumerate(items):
        db.update_item_status(project_id, index, {"last_sheet_push_at": timestamp})


def _apply_procurement_sheet_pull(project: Dict, rows: List[Dict]) -> Dict:
    """Apply whitelisted procurement edits from Google Sheets."""
    applied = 0
    ignored_rows = []
    project_id = project.get("project_id", "")
    timestamp = datetime.now().isoformat()

    for row in rows:
        item_index = _parse_row_key(row.get("row_key", ""), project_id)
        if item_index is None:
            ignored_rows.append(row.get("_row_number"))
            continue

        supplier = _find_supplier_by_sheet_value(
            row.get("selected_supplier_id", ""),
            row.get("Selected Supplier", ""),
        )
        status_update = {
            "unit_price": _parse_sheet_number(row.get("Unit Price", 0)),
            "po_number": str(row.get("PO Number", "")).strip(),
            "ordered_qty": _parse_sheet_number(row.get("Ordered Qty", 0)),
            "received_qty": _parse_sheet_number(row.get("Received Qty", 0)),
            "notes": str(row.get("Notes", "")).strip(),
            "selected_supplier_id": supplier.get("supplier_id", ""),
            "selected_supplier_name": supplier.get("name", str(row.get("Selected Supplier", "")).strip()),
            "supplier": supplier.get("name", str(row.get("Selected Supplier", "")).strip()),
            "last_sheet_pull_at": timestamp,
        }
        db.update_item_status(project_id, item_index, status_update)
        db.add_audit_entry(project_id, item_index, "google_procurement_pull", get_actor_name(), status_update)
        applied += 1

    return {"applied": applied, "ignored_rows": ignored_rows}


def _apply_rfp_sheet_pull(project: Dict, rows: List[Dict]) -> Dict:
    """Apply whitelisted vendor assignment edits from Google Sheets."""
    applied = 0
    ignored_rows = []
    project_id = project.get("project_id", "")
    timestamp = datetime.now().isoformat()

    for row in rows:
        item_index = _parse_row_key(row.get("row_key", ""), project_id)
        if item_index is None:
            ignored_rows.append(row.get("_row_number"))
            continue

        supplier = _find_supplier_by_sheet_value(
            row.get("selected_supplier_id", ""),
            row.get("Selected Supplier", ""),
        )
        status_update = {
            "selected_supplier_id": supplier.get("supplier_id", ""),
            "selected_supplier_name": supplier.get("name", str(row.get("Selected Supplier", "")).strip()),
            "supplier": supplier.get("name", str(row.get("Selected Supplier", "")).strip()),
            "quoted_unit_price": _parse_sheet_number(row.get("Quoted Unit Price", 0)),
            "lead_time": str(row.get("Lead Time", "")).strip(),
            "supplier_notes": str(row.get("Supplier Notes", "")).strip(),
            "rfp_status": str(row.get("RFP Status", "not_started")).strip() or "not_started",
            "rfp_notes": str(row.get("RFP Notes", "")).strip(),
            "last_sheet_pull_at": timestamp,
        }
        db.update_item_status(project_id, item_index, status_update)
        db.add_audit_entry(project_id, item_index, "google_rfp_pull", get_actor_name(), status_update)
        applied += 1

    return {"applied": applied, "ignored_rows": ignored_rows}


def _sync_project_workspace_metadata(project: Dict, workspace_links: Dict):
    """Persist workspace metadata to the project and its hotel."""
    if project.get("hotel_id"):
        _persist_hotel_workspace_links(project.get("hotel_id", ""), workspace_links)
    _persist_project_workspace_links(project.get("project_id", ""), workspace_links)


def _run_project_workspace_action(project: Dict, items: List[Dict], mode: str, action: str):
    """Execute one explicit Google Workspace action for a project."""
    service, status_message = get_google_workspace_service()
    if service is None:
        st.error(status_message)
        return

    timestamp = datetime.now().isoformat()
    try:
        if action == "create":
            workspace_links = service.ensure_project_workspace(project)
            _sync_project_workspace_metadata(project, workspace_links)
            st.success("Google Workspace folders and Sheets are ready.")
        elif action == "push":
            sheet_items = json.loads(json.dumps(items))
            for item in sheet_items:
                item.setdefault("procurement_status", {})["last_sheet_push_at"] = timestamp
            workspace_links = (
                service.push_procurement_sheet(project, sheet_items)
                if mode == "procurement"
                else service.push_rfp_sheet(project, sheet_items)
            )
            _sync_project_workspace_metadata(project, workspace_links)
            _mark_sheet_push(project.get("project_id", ""), items, timestamp)
            st.success("Google Sheet updated from SENPRO.")
        elif action == "pull":
            result = (
                service.pull_procurement_sheet(project)
                if mode == "procurement"
                else service.pull_rfp_sheet(project)
            )
            _sync_project_workspace_metadata(project, result.get("workspace_links", {}))
            apply_result = (
                _apply_procurement_sheet_pull(project, result.get("rows", []))
                if mode == "procurement"
                else _apply_rfp_sheet_pull(project, result.get("rows", []))
            )
            if apply_result["ignored_rows"]:
                st.warning(f"Ignored Google rows without a valid row_key: {apply_result['ignored_rows']}")
            st.success(f"Imported {apply_result['applied']} rows from Google Sheets.")
        else:
            st.error("Unknown Google Workspace action.")
            return
    except GoogleWorkspaceError as exc:
        st.error(str(exc))
        return

    st.rerun()


def _render_project_workspace_toolbar(project: Dict, items: List[Dict], mode: str):
    """Toolbar for explicit project-level Google Workspace actions."""
    workspace_links = project.get("workspace_links", {})
    link_labels = {
        "project_folder_url": "Project Folder",
        "procurement_sheet_url": "Procurement Sheet",
        "rfp_sheet_url": "Vendor RFP Sheet",
    }
    st.markdown("### Google Workspace")
    _render_workspace_links(workspace_links, link_labels)

    workspace_service, status_message = get_google_workspace_service()
    if status_message:
        st.caption(status_message)

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Create Google Workspace", use_container_width=True, key=f"{mode}_workspace_create", disabled=workspace_service is None):
            _run_project_workspace_action(project, items, mode, "create")
    with col2:
        if st.button("Push to Google Sheet", use_container_width=True, key=f"{mode}_workspace_push", disabled=workspace_service is None):
            _run_project_workspace_action(project, items, mode, "push")
    with col3:
        if st.button("Pull from Google Sheet", use_container_width=True, key=f"{mode}_workspace_pull", disabled=workspace_service is None):
            _run_project_workspace_action(project, items, mode, "pull")


def _render_stage1_quick_nav(active_view: str = ""):
    """Top-of-page quick navigation between Stage 1 workspaces."""
    if is_supplier_user():
        return

    nav_items = [
        ("Corporate Home", "corporate_home"),
        ("New Project", "new_project"),
        ("SENPROCURE", _senprocure_destination()),
        ("HOTEL", "hotel_directory"),
        ("HOTEL DETAILS", "hotel_details"),
        ("HOTEL ITEM LIST", "hotel_item_list"),
        ("HOTEL RFP", "hotel_rfp"),
        ("VENDOR SUPPLIER LIST", "vendor_directory"),
    ]
    cols = st.columns(len(nav_items))
    for col, (label, destination) in zip(cols, nav_items):
        with col:
            if st.button(label, use_container_width=True, key=f"quick_nav_{label}", disabled=destination == active_view):
                _set_view_mode(destination)
                _rerun_if_legacy()


def enforce_authenticated_app_access() -> None:
    """Apply the shared login gate and permission checks."""
    if not get_current_user():
        show_login()
        st.stop()

    _enforce_session_timeout()
    ensure_active_hotel_scope()
    _enforce_view_permissions()


def render_page_banner(view_mode: str) -> None:
    """Render the shared title used outside the home screen."""
    if _normalize_view_mode(view_mode) != "corporate_home":
        st.markdown('<div class="main-header">SENPRO</div>', unsafe_allow_html=True)
        st.markdown("### Corporate Procurement Program")


def render_shared_sidebar() -> None:
    """Render the shared sidebar chrome used by legacy and multipage entrypoints."""
    with st.sidebar:
        current_user = get_current_user()
        accessible_hotels = get_accessible_hotels()

        st.markdown("""
        <div style='text-align: center; padding: 1rem 0;'>
            <div style='font-size: 2rem; font-weight: bold; color: #000000;'>SENPRO</div>
            <div style='font-size: 0.8rem; color: #000000;'>SaaS</div>
        </div>
        """, unsafe_allow_html=True)

        st.caption(f"{current_user.get('full_name', current_user.get('username', 'User'))}")
        st.caption(f"Role: {get_current_role().replace('_', ' ').title() or 'Unknown'}")

        if accessible_hotels and not is_supplier_user():
            hotel_scope_options = {}
            if can_view_portfolio():
                hotel_scope_options["All Hotels"] = "ALL"
            for hotel in accessible_hotels:
                hotel_scope_options[_hotel_label(hotel)] = hotel["hotel_id"]

            current_scope = st.session_state.get("active_hotel_id")
            option_labels = list(hotel_scope_options.keys())
            default_index = 0
            for idx, label in enumerate(option_labels):
                if hotel_scope_options[label] == current_scope:
                    default_index = idx
                    break

            selected_scope_label = st.selectbox(
                "Hotel Scope",
                option_labels,
                index=default_index,
                key="sidebar_hotel_scope",
            )
            st.session_state.active_hotel_id = hotel_scope_options[selected_scope_label]
        elif not is_admin() and not is_supplier_user():
            st.warning("No hotels assigned to this user yet.")

        if is_supplier_user():
            supplier_id = get_current_supplier_id()
            supplier = db.get_supplier(supplier_id) if supplier_id else {}
            st.caption(f"Supplier: {supplier.get('name', 'Unlinked Supplier')}")

        st.markdown("---")
        show_notification_center()

        st.markdown("---")
        if not _is_multipage_navigation_enabled():
            if not is_supplier_user():
                if st.button("Corporate Home", use_container_width=True, key="sidebar_home"):
                    _set_view_mode("corporate_home")
                    _rerun_if_legacy()
                if st.button("New Project", use_container_width=True, key="sidebar_new_project"):
                    _set_view_mode("new_project")
                    _rerun_if_legacy()

        if is_ai_feature_enabled():
            if st.button("Seneca", use_container_width=True, key="sidebar_ai_assistant"):
                _set_view_mode("ai_assistant")
                _rerun_if_legacy()

        if _is_multipage_navigation_enabled():
            st.caption("Use the workspace navigation above for Home, Projects, Finance, and Directories.")

        if not _is_multipage_navigation_enabled():
            if st.button("Account Settings", use_container_width=True, key="sidebar_account_settings"):
                _set_view_mode("account_settings")
                _rerun_if_legacy()

            if is_admin():
                if st.button("Administration", use_container_width=True, key="sidebar_admin_panel"):
                    _set_view_mode("admin_panel")
                    _rerun_if_legacy()

        if st.button("Log Out", use_container_width=True, key="logout_button"):
            logout()
            st.rerun()
# ============================================================================
# CAPEX DASHBOARD
# ============================================================================


def _get_capex_blocks(data: Dict) -> List[str]:
    """Return sorted CAPEX block identifiers from loaded room data."""
    return sorted(
        {
            str(room.get("block", "")).strip()
            for room in data.get("rooms", {}).values()
            if str(room.get("block", "")).strip()
        }
    )


def _format_capex_floor_range(floors: List[int]) -> str:
    """Human-friendly floor range label for one CAPEX block."""
    if not floors:
        return "No floors"
    if len(floors) == 1:
        return f"Floor {floors[0]}"
    return f"Floors {min(floors)}-{max(floors)}"


def show_capex_dashboard(show_header: bool = True):
    """Hotel Furniture CAPEX Tracking"""
    if av is None:
        st.error("CAPEX loader module not found.")
        return

    if show_header:
        st.markdown('<div class="main-header">CAPEX Dashboard</div>', unsafe_allow_html=True)
    # Show hotel info dynamically if available
    if 'av_data' in st.session_state and st.session_state.av_data.get("hotel_info"):
        info = st.session_state.av_data["hotel_info"]
        st.caption(f"{info.get('name', '')} | {info.get('rooms', '')} Rooms | {info.get('location', '')}")

    # Auto-load hotel data
    if 'av_data' not in st.session_state:
        st.session_state.av_data = av.load_data()
    data = st.session_state.av_data
    blocks = _get_capex_blocks(data)

    # Main tabs
    tab_overview, tab_rooms, tab_common, tab_export = st.tabs([
        "Overview", "Room Furniture", "Common Areas", "Export"
    ])

    # ── OVERVIEW TAB ──
    with tab_overview:
        totals = av.get_grand_totals(data)

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Rooms", totals["total_rooms"])
        with col2:
            st.metric("Room Furniture Pieces", totals["room_furniture_items"])
        with col3:
            st.metric("Common Area Pieces", totals["common_area_items"])
        with col4:
            st.metric("Grand Total Items", totals["grand_total_items"])

        if totals["grand_total_cost"] > 0:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Room Furniture Cost", f"${totals['room_furniture_cost']:,.0f}")
            with col2:
                st.metric("Common Area Cost", f"${totals['common_area_cost']:,.0f}")
            with col3:
                st.metric("Total CAPEX", f"${totals['grand_total_cost']:,.0f}")

        st.markdown("---")

        # Block comparison
        st.markdown("### Block Comparison")
        if blocks:
            block_columns = st.columns(len(blocks))
            for column, block_name in zip(block_columns, blocks):
                block_summary = av.get_block_summary(data, block_name)
                block_floors = av.get_block_floors(block_name)
                with column:
                    st.markdown(f"**Block {block_name}** ({_format_capex_floor_range(block_floors)})")
                    st.write(f"Rooms: {block_summary['rooms']} | Items: {block_summary['items']}")
                    if block_summary['cost'] > 0:
                        st.write(f"Cost: ${block_summary['cost']:,.0f}")
        else:
            st.caption("No block data found.")

        st.markdown("---")

        # Floor-by-floor breakdown
        st.markdown("### Floor Breakdown")
        floor_rows = []
        for block in blocks:
            for floor in av.get_block_floors(block):
                fs = av.get_floor_summary(data, block, floor)
                rooms_on_floor = av.get_rooms_for_block_floor(data, block, floor)
                floor_rows.append({
                    "Block": block,
                    "Floor": floor,
                    "Rooms": fs["rooms"],
                    "Room Numbers": ", ".join(rooms_on_floor),
                    "Total Items": fs["total_items"],
                    "Total Cost": f"${fs['total_cost']:,.0f}" if fs['total_cost'] > 0 else "-",
                })
        st.dataframe(pd.DataFrame(floor_rows), use_container_width=True, hide_index=True)

        st.markdown("---")

        # Room type summary
        st.markdown("### Room Type Summary")
        type_counts = {}
        for room in data["rooms"].values():
            rt = room["room_type_name"]
            if rt not in type_counts:
                type_counts[rt] = {"count": 0, "items": 0, "cost": 0}
            type_counts[rt]["count"] += 1
            for item in room["furniture_items"]:
                type_counts[rt]["items"] += item["qty"]
                type_counts[rt]["cost"] += item["qty"] * item.get("unit_price", 0)

        type_rows = []
        for rt_name, info in sorted(type_counts.items(), key=lambda x: -x[1]["count"]):
            type_rows.append({
                "Room Type": rt_name,
                "Count": info["count"],
                "Items per Room": info["items"] // info["count"] if info["count"] > 0 else 0,
                "Total Items": info["items"],
                "Total Cost": f"${info['cost']:,.0f}" if info['cost'] > 0 else "-",
            })
        st.dataframe(pd.DataFrame(type_rows), use_container_width=True, hide_index=True)

    # ── ROOM FURNITURE TAB ──
    with tab_rooms:
        st.markdown("### Room Furniture Inventory")
        if not blocks:
            st.warning("No room block data found.")
            return

        col1, col2, col3 = st.columns(3)

        with col1:
            block = st.selectbox("Block", blocks, key="capex_block")
        with col2:
            floors = av.get_block_floors(block)
            floor = st.selectbox("Floor", floors, key="capex_floor")
        with col3:
            rooms_list = av.get_rooms_for_block_floor(data, block, floor)
            if rooms_list:
                room_labels = []
                for r in rooms_list:
                    ri = data["rooms"][r]
                    label = f"{r} ({ri['room_type_name']})"
                    if ri.get("suite_group"):
                        label += f" [Suite {ri['suite_group']}]"
                    room_labels.append(label)
                selected_label = st.selectbox("Room", room_labels, key="capex_room")
                room_number = rooms_list[room_labels.index(selected_label)]
            else:
                st.warning("No rooms on this floor")
                room_number = None

        if room_number:
            room = data["rooms"][room_number]

            # Room info cards
            st.markdown("---")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Room", room_number)
            with col2:
                st.metric("Type", room["room_type_name"])
            with col3:
                st.metric("Size", f"{room['size_sqm']} m\u00b2")
            with col4:
                st.metric("Items", sum(i["qty"] for i in room["furniture_items"]))

            if room.get("suite_group"):
                st.info(f"Part of Two Bedroom Suite: {room['suite_group']}")
            if room.get("note"):
                st.info(room["note"])

            st.markdown("---")

            # Build editable dataframe
            items_for_edit = []
            for item in room["furniture_items"]:
                items_for_edit.append({
                    "Item": item["item_name"],
                    "Category": item["category"],
                    "Qty": item["qty"],
                    "Unit": item["unit"],
                    "Unit Price ($)": item.get("unit_price", 0),
                    "Total ($)": item["qty"] * item.get("unit_price", 0),
                    "Supplier": item.get("supplier", ""),
                    "Status": item.get("status", "pending"),
                })

            df_items = pd.DataFrame(items_for_edit)

            edited_df = st.data_editor(
                df_items,
                use_container_width=True,
                num_rows="fixed",
                key=f"editor_{room_number}",
                column_config={
                    "Item": st.column_config.TextColumn("Item", disabled=True),
                    "Category": st.column_config.TextColumn("Category", disabled=True),
                    "Qty": st.column_config.NumberColumn("Qty", min_value=0, max_value=50),
                    "Unit": st.column_config.TextColumn("Unit", disabled=True),
                    "Unit Price ($)": st.column_config.NumberColumn("Unit Price ($)", min_value=0, format="%.0f"),
                    "Total ($)": st.column_config.NumberColumn("Total ($)", disabled=True, format="%.0f"),
                    "Supplier": st.column_config.TextColumn("Supplier"),
                    "Status": st.column_config.SelectboxColumn(
                        "Status",
                        options=["pending", "ordered", "received", "installed"],
                    ),
                },
            )

            # Room total
            room_total = sum(
                edited_df.iloc[i]["Qty"] * edited_df.iloc[i]["Unit Price ($)"]
                for i in range(len(edited_df))
            )
            st.markdown(f"**Room {room_number} Total: ${room_total:,.0f}**")

            # Save button
            if st.button(f"Save Room {room_number}", key=f"save_{room_number}", type="primary"):
                updated = []
                for i in range(len(edited_df)):
                    row = edited_df.iloc[i]
                    updated.append({
                        "qty": int(row["Qty"]),
                        "unit_price": float(row["Unit Price ($)"]),
                        "supplier": str(row["Supplier"]),
                        "status": str(row["Status"]),
                    })
                data = av.update_room_items(data, room_number, updated)
                st.session_state.av_data = data
                st.success(f"Room {room_number} saved!")

    # ── COMMON AREAS TAB ──
    with tab_common:
        st.markdown("### Common Areas Furniture")

        area_names = list(data.get("common_areas", {}).keys())
        if area_names:
            selected_area = st.selectbox("Select Area", area_names, key="capex_area")

            area_items = data["common_areas"][selected_area]

            items_for_edit = []
            for item in area_items:
                items_for_edit.append({
                    "Item": item["item_name"],
                    "Qty": item["qty"],
                    "Unit": item.get("unit", "pcs"),
                    "Unit Price ($)": item.get("unit_price", 0),
                    "Total ($)": item["qty"] * item.get("unit_price", 0),
                    "Status": item.get("status", "pending"),
                })

            df_area = pd.DataFrame(items_for_edit)

            edited_area = st.data_editor(
                df_area,
                use_container_width=True,
                num_rows="fixed",
                key=f"area_editor_{selected_area}",
                column_config={
                    "Item": st.column_config.TextColumn("Item", disabled=True),
                    "Qty": st.column_config.NumberColumn("Qty", min_value=0, max_value=200),
                    "Unit": st.column_config.TextColumn("Unit", disabled=True),
                    "Unit Price ($)": st.column_config.NumberColumn("Unit Price ($)", min_value=0, format="%.0f"),
                    "Total ($)": st.column_config.NumberColumn("Total ($)", disabled=True, format="%.0f"),
                    "Status": st.column_config.SelectboxColumn(
                        "Status",
                        options=["pending", "ordered", "received", "installed"],
                    ),
                },
            )

            area_total = sum(
                edited_area.iloc[i]["Qty"] * edited_area.iloc[i]["Unit Price ($)"]
                for i in range(len(edited_area))
            )
            st.markdown(f"**{selected_area} Total: ${area_total:,.0f}**")

            if st.button(f"Save {selected_area}", key=f"save_area_{selected_area}", type="primary"):
                updated = []
                for i in range(len(edited_area)):
                    row = edited_area.iloc[i]
                    updated.append({
                        "qty": int(row["Qty"]),
                        "unit_price": float(row["Unit Price ($)"]),
                        "status": str(row["Status"]),
                    })
                data = av.update_common_area_items(data, selected_area, updated)
                st.session_state.av_data = data
                st.success(f"{selected_area} saved!")
        else:
            st.warning("No common areas data found.")

    # ── EXPORT TAB ──
    with tab_export:
        st.markdown("### Export CAPEX Report")

        if st.button("Generate Excel Report", type="primary"):
            df_all = av.export_to_dataframe(data)
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_all.to_excel(writer, sheet_name="All Rooms", index=False)

                for block_name in blocks:
                    df_block = df_all[df_all["Block"] == block_name]
                    if not df_block.empty:
                        df_block.to_excel(writer, sheet_name=f"Block {block_name}", index=False)

                common_rows = []
                for area_name, items in data.get("common_areas", {}).items():
                    for item in items:
                        common_rows.append({
                            "Area": area_name,
                            "Item": item["item_name"],
                            "Qty": item["qty"],
                            "Unit": item.get("unit", "pcs"),
                            "Unit Price": item.get("unit_price", 0),
                            "Total": item["qty"] * item.get("unit_price", 0),
                            "Status": item.get("status", "pending"),
                        })
                if common_rows:
                    pd.DataFrame(common_rows).to_excel(writer, sheet_name="Common Areas", index=False)

                totals = av.get_grand_totals(data)
                summary_rows = [
                    {"Metric": "Total Rooms", "Value": totals["total_rooms"]},
                    {"Metric": "Room Furniture Items", "Value": totals["room_furniture_items"]},
                    {"Metric": "Room Furniture Cost", "Value": totals["room_furniture_cost"]},
                    {"Metric": "Common Area Items", "Value": totals["common_area_items"]},
                    {"Metric": "Common Area Cost", "Value": totals["common_area_cost"]},
                    {"Metric": "Grand Total Items", "Value": totals["grand_total_items"]},
                    {"Metric": "Grand Total Cost", "Value": totals["grand_total_cost"]},
                ]
                pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Summary", index=False)

            output.seek(0)
            st.download_button(
                label="Download CAPEX Report",
                data=output.getvalue(),
                file_name="CAPEX_Report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )


def _format_review_status(status: str) -> str:
    """Human-friendly project review status label."""
    labels = {
        "draft": "Draft",
        "submitted": "Submitted",
        "resubmitted": "Resubmitted",
        "needs_correction": "Needs Correction",
        "approved": "Approved",
        "hotel_reassigned": "Hotel Reassigned",
    }
    return labels.get(status, status.replace("_", " ").title())


def show_portfolio_dashboard():
    """Portfolio-level reporting for all accessible hotels."""
    st.markdown('<div class="main-header">Portfolio Dashboard</div>', unsafe_allow_html=True)

    if not can_view_portfolio() and not is_admin():
        st.error("Portfolio reporting is available only to portfolio managers and admins.")
        return

    hotels = get_accessible_hotels()
    active_scope = st.session_state.get("active_hotel_id")
    if active_scope not in {None, "ALL"}:
        hotels = [hotel for hotel in hotels if hotel.get("hotel_id") == active_scope]
    scoped_projects = get_scoped_projects()

    if not hotels and not scoped_projects:
        st.info("No hotels available yet. Create hotels in Administration first.")
        return

    hotel_lookup = {hotel["hotel_id"]: hotel for hotel in hotels}
    rows = []
    total_items = 0
    total_pending = 0
    total_budget = 0

    for hotel in hotels:
        hotel_projects = [project for project in scoped_projects if project.get("hotel_id") == hotel["hotel_id"]]
        hotel_total_items = 0
        hotel_pending = 0
        hotel_budget = 0
        needs_correction = 0

        for project in hotel_projects:
            summary = db.get_procurement_summary(project["project_id"])
            hotel_total_items += summary["total_items"]
            hotel_pending += summary["total_items"] - summary["ordered_count"]
            hotel_budget += summary["total_budget"]
            if project.get("review_status") == "needs_correction":
                needs_correction += 1

        total_items += hotel_total_items
        total_pending += hotel_pending
        total_budget += hotel_budget

        rows.append({
            "Hotel": hotel.get("name", "Unnamed Hotel"),
            "City": hotel.get("city", ""),
            "Brand": hotel.get("brand", ""),
            "Projects": len(hotel_projects),
            "Total Items": hotel_total_items,
            "Pending": hotel_pending,
            "Budget": hotel_budget,
            "Needs Correction": needs_correction,
        })

    unassigned_projects = [project for project in scoped_projects if not project.get("hotel_id")]
    if is_admin() and unassigned_projects:
        orphan_items = 0
        orphan_pending = 0
        orphan_budget = 0
        orphan_corrections = 0

        for project in unassigned_projects:
            summary = db.get_procurement_summary(project["project_id"])
            orphan_items += summary["total_items"]
            orphan_pending += summary["total_items"] - summary["ordered_count"]
            orphan_budget += summary["total_budget"]
            if project.get("review_status") == "needs_correction":
                orphan_corrections += 1

        total_items += orphan_items
        total_pending += orphan_pending
        total_budget += orphan_budget
        rows.append({
            "Hotel": "Unassigned / Legacy",
            "City": "",
            "Brand": "",
            "Projects": len(unassigned_projects),
            "Total Items": orphan_items,
            "Pending": orphan_pending,
            "Budget": orphan_budget,
            "Needs Correction": orphan_corrections,
        })

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Hotels", len(rows))
    with col2:
        st.metric("Projects", len(scoped_projects))
    with col3:
        st.metric("Items", total_items)
    with col4:
        st.metric("Pending", total_pending)

    st.markdown("---")
    if rows:
        portfolio_df = pd.DataFrame(rows)
        portfolio_df["Budget"] = portfolio_df["Budget"].map(lambda value: f"${value:,.2f}")
        st.dataframe(portfolio_df, use_container_width=True, hide_index=True)

    if scoped_projects:
        st.markdown("### Recent Projects")
        recent_rows = []
        for project in reversed(scoped_projects[-10:]):
            hotel = hotel_lookup.get(project.get("hotel_id"), {})
            summary = db.get_procurement_summary(project["project_id"])
            recent_rows.append({
                "Project ID": project["project_id"],
                "Hotel": hotel.get("name") or project.get("hotel_info", {}).get("property_name", "Unassigned"),
                "Project Name": project.get("hotel_info", {}).get("project_name", ""),
                "Status": _format_review_status(project.get("review_status", "draft")),
                "Pending": summary["total_items"] - summary["ordered_count"],
                "Created": project.get("created_at", "")[:10],
            })
        st.dataframe(pd.DataFrame(recent_rows), use_container_width=True, hide_index=True)

    st.caption(f"Current budget in scope: ${total_budget:,.2f}")


def show_corporate_home():
    """Corporate home with Stoic Transparency landing copy and module navigation."""
    if is_supplier_user():
        show_supplier_portal()
        return

    hotels = get_accessible_hotels()
    projects = get_scoped_projects(ignore_hotel_scope=True)
    suppliers = db.get_all_suppliers()

    st.markdown(
        """
        <div class="hero">
            <div class="grid-overlay"></div>
            <div class="hero-content">
                <div class="glass-cube"></div>
                <span class="matrix-text">Stoic Transparency / System Ready</span>
                <h1>Foundational Order for the Digital Age.</h1>
                <p>SENPRO is the procurement matrix for structured complexity, designed for calm execution, visible logic, and disciplined operational control.</p>
                <div class="hero-subcopy">
                    Every workflow stays legible. Every quantity has a basis. Every supplier decision can be traced back to a clear operational frame.
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Hotels", len(hotels))
    with col2:
        st.metric("Projects", len(projects))
    with col3:
        st.metric("Suppliers", len(suppliers))

    st.markdown('<div class="matrix-text" style="margin: 2rem 0 1.1rem 0;">>> Design Principles</div>', unsafe_allow_html=True)
    philosophy_cols = st.columns(3)
    philosophy_cards = [
        (
            "Matrix Structure",
            "Pure logic with visible operational relationships. No black-box workflow, no hidden quantity assumptions.",
        ),
        (
            "Stoic Workflow",
            "Focus attention on controllable decisions: scope, quantities, suppliers, approvals, and execution status.",
        ),
        (
            "Transparent Scaling",
            "Build procurement systems block by block so growth stays coherent across hotels, vendors, and project phases.",
        ),
    ]
    for col, (title, body) in zip(philosophy_cols, philosophy_cards):
        with col:
            st.markdown(
                f"""
                <div class="transparency-card">
                    <span class="card-kicker">Principle</span>
                    <h3>{title}</h3>
                    <p>{body}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)
    action_col1, action_col2 = st.columns(2)
    with action_col1:
        if st.button("New Project", use_container_width=True, type="primary", key="home_new_project"):
            _set_view_mode("new_project")
            _rerun_if_legacy()
    with action_col2:
        if st.button("Open SENPROCURE", use_container_width=True, key="home_open_senprocure"):
            _set_view_mode(_senprocure_destination())
            _rerun_if_legacy()

    st.markdown("---")
    st.markdown('<div class="matrix-text" style="margin-bottom: 2rem;">>> Operational Modules</div>', unsafe_allow_html=True)

    row1 = st.columns(2)
    with row1[0]:
        st.markdown(
            """
            <div class="voxel-card">
                <div class="pixel-icon"></div>
                <span class="card-kicker">Directory</span>
                <h3>HOTEL DIRECTORY</h3>
                <p>Hotel master records, property scope, and workspace-linked operational context.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Initialize Directory", use_container_width=True, key="home_hotel_open"):
            _set_view_mode("hotel_directory")
            _rerun_if_legacy()

    with row1[1]:
        st.markdown(
            """
            <div class="voxel-card">
                <div class="pixel-icon"></div>
                <span class="card-kicker">Vendor Layer</span>
                <h3>VENDOR SUPPLIER LIST</h3>
                <p>Supplier identity, contact visibility, and catalogue-linked reference across procurement flows.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Open Supplier List", use_container_width=True, key="home_vendor_open"):
            _set_view_mode("vendor_directory")
            _rerun_if_legacy()

    st.markdown("<br>", unsafe_allow_html=True)

    row2 = st.columns(2)
    with row2[0]:
        st.markdown(
            """
            <div class="voxel-card">
                <div class="pixel-icon"></div>
                <span class="card-kicker">Execution</span>
                <h3>PROCUREMENT LOGIC</h3>
                <p>Editable project item matrix with quantity control, price capture, and traceable workflow status.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Execute Procurement", use_container_width=True, type="primary", key="home_hotel_item_list_open"):
            _set_view_mode("hotel_item_list")
            _rerun_if_legacy()

    with row2[1]:
        st.markdown(
            """
            <div class="voxel-card">
                <div class="pixel-icon"></div>
                <span class="card-kicker">Quotation</span>
                <h3>RFP PROTOCOL</h3>
                <p>Vendor comparison, quotation capture, and supplier assignment with explicit decision history.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Deploy RFP", use_container_width=True, type="primary", key="home_hotel_rfp_open"):
            _set_view_mode("hotel_rfp")
            _rerun_if_legacy()


def show_hotel_directory(show_header: bool = True, show_workspace_nav: bool = True):
    """Stage 1 hotel directory and selector."""
    if show_header:
        st.markdown('<div class="main-header">HOTEL</div>', unsafe_allow_html=True)
    if show_workspace_nav:
        _render_stage1_quick_nav("hotel_directory")

    hotels = get_accessible_hotels()
    if not hotels:
        st.info("No hotels are assigned to the current scope.")
        return

    hotel_df = pd.DataFrame(
        [
            {
                "Hotel": hotel.get("name", ""),
                "Brand": hotel.get("brand", ""),
                "City": hotel.get("city", ""),
                "Country": hotel.get("country", ""),
                "Rooms": hotel.get("total_rooms", 0),
                "Workspace": "Linked" if hotel.get("workspace_links", {}).get("hotel_folder_url") else "Not Linked",
            }
            for hotel in hotels
        ]
    )
    st.dataframe(hotel_df, use_container_width=True, hide_index=True)

    selected_hotel = select_accessible_hotel("Hotel", key="hotel_directory_select", hotels=hotels)
    selected_hotel_id = selected_hotel.get("hotel_id", "")
    if not selected_hotel_id:
        st.info("Select a hotel to continue.")
        return

    if st.button("Open HOTEL DETAILS", use_container_width=True, key="hotel_directory_details"):
        _set_view_mode("hotel_details", hotel_id=selected_hotel_id)
        _rerun_if_legacy()
    st.caption("The selected hotel is now active. Use the quick navigation above for Procurement or RFP.")

    st.markdown("### Current Selection")
    st.write(f"**Hotel:** {selected_hotel.get('name', '')}")
    st.write(f"**Location:** {selected_hotel.get('city', '')}, {selected_hotel.get('country', '')}")
    _render_workspace_links(selected_hotel.get("workspace_links", {}), {"hotel_folder_url": "Hotel Folder", "master_folder_url": "Master Folder", "projects_folder_url": "Projects Folder"})


def show_hotel_details(show_header: bool = True, show_workspace_nav: bool = True):
    """Stage 1 hotel master record and workspace links."""
    if show_header:
        st.markdown('<div class="main-header">HOTEL DETAILS</div>', unsafe_allow_html=True)
    if show_workspace_nav:
        _render_stage1_quick_nav("hotel_details")

    hotels = get_accessible_hotels()
    if not hotels and not can_manage_master_data():
        st.info("No hotels are available.")
        return

    selected_hotel = select_accessible_hotel(
        "Select Hotel",
        key="stage1_hotel_details_select",
        hotels=hotels,
    ) if hotels else {}

    if selected_hotel:
        st.markdown("### Workspace Links")
        _render_workspace_links(
            selected_hotel.get("workspace_links", {}),
            {
                "hotel_folder_url": "Hotel Folder",
                "master_folder_url": "Master Folder",
                "projects_folder_url": "Projects Folder",
            },
        )

        workspace_service, workspace_message = get_google_workspace_service()
        if workspace_message:
            st.caption(workspace_message)
        if st.button("Create Google Workspace", use_container_width=True, key="hotel_details_workspace_create", disabled=workspace_service is None):
            try:
                workspace_links = workspace_service.ensure_hotel_workspace(selected_hotel)
            except GoogleWorkspaceError as exc:
                st.error(str(exc))
            else:
                _persist_hotel_workspace_links(selected_hotel.get("hotel_id", ""), workspace_links)
                st.success("Hotel workspace created.")
                st.rerun()

    if not can_manage_master_data():
        return

    with st.form("stage1_hotel_details_form"):
        st.markdown("### Hotel Master Data")
        hotel_name = st.text_input("Hotel Name *", value=selected_hotel.get("name", ""))
        hotel_brand = st.text_input("Brand *", value=selected_hotel.get("brand", ""))
        hotel_city = st.text_input("City *", value=selected_hotel.get("city", ""))
        hotel_country = st.text_input("Country", value=selected_hotel.get("country", "Uzbekistan"))
        hotel_rooms = st.number_input("Room Count", min_value=1, max_value=5000, value=int(selected_hotel.get("total_rooms", 1) or 1))
        hotel_status = st.selectbox("Status", ["active", "inactive"], index=0 if selected_hotel.get("status", "active") == "active" else 1)
        hotel_notes = st.text_area("Notes", value=selected_hotel.get("notes", ""))
        submitted = st.form_submit_button("Save Hotel", type="primary")

    if submitted:
        if not hotel_name or not hotel_brand or not hotel_city:
            st.error("Hotel name, brand, and city are required.")
        else:
            db.save_hotel(
                {
                    "hotel_id": selected_hotel.get("hotel_id"),
                    "name": hotel_name,
                    "brand": hotel_brand,
                    "city": hotel_city,
                    "country": hotel_country,
                    "total_rooms": hotel_rooms,
                    "status": hotel_status,
                    "notes": hotel_notes,
                    "workspace_links": selected_hotel.get("workspace_links", {}),
                    "created_at": selected_hotel.get("created_at"),
                }
            )
            st.success("Hotel saved.")
            st.rerun()


def show_vendor_directory(show_header: bool = True, show_workspace_nav: bool = True):
    """Simple alphabetical supplier directory."""
    if show_header:
        st.markdown('<div class="main-header">VENDOR SUPPLIER LIST</div>', unsafe_allow_html=True)
    if show_workspace_nav:
        _render_stage1_quick_nav("vendor_directory")

    suppliers = sorted(
        db.get_all_suppliers(),
        key=lambda supplier: supplier.get("name", "").casefold(),
    )
    if suppliers:
        supplier_df = pd.DataFrame(
            [
                {
                    "Name": supplier.get("name", ""),
                    "Address": supplier.get("address", ""),
                    "PO Box": supplier.get("po_box", ""),
                    "Contact": " | ".join(
                        [
                            value
                            for value in [
                                supplier.get("contact_person", ""),
                                supplier.get("phone", ""),
                                supplier.get("email", ""),
                            ]
                            if value
                        ]
                    ),
                }
                for supplier in suppliers
            ]
        )
        st.caption("Alphabetical supplier directory.")
        st.dataframe(supplier_df, use_container_width=True, hide_index=True)
    else:
        st.info("No suppliers created yet.")


def show_hotel_item_list():
    """Stage 1 wrapper around the editable procurement checklist."""
    _render_stage1_quick_nav("hotel_item_list")
    show_procurement_checklist(
        page_title="HOTEL ITEM LIST WITH QTY AND PRICE",
        show_workspace_toolbar=True,
    )


def show_hotel_rfp():
    """Stage 1 wrapper around supplier comparison and RFP."""
    _render_stage1_quick_nav("hotel_rfp")
    show_supplier_comparison(
        page_title="HOTEL ITEM LIST WITH QTY AND PRICE AND VENDOR WITH RFP",
        show_workspace_toolbar=True,
    )


def show_admin_panel():
    """Manage hotels, users, and legacy project assignments."""
    st.markdown('<div class="main-header">Administration</div>', unsafe_allow_html=True)

    if not is_admin():
        st.error("Administration is available only to admins.")
        return

    hotels = db.get_all_hotels()
    users = db.get_all_users()
    suppliers = db.get_all_suppliers()
    hotel_label_to_id = {_hotel_label(hotel): hotel["hotel_id"] for hotel in hotels}
    supplier_label_to_id = {
        f"{supplier.get('name', 'Unnamed')} ({supplier.get('email', 'no-email')})": supplier["supplier_id"]
        for supplier in suppliers
    }

    tab1, tab2, tab3, tab4 = st.tabs(["Hotels", "Users", "Assignments", "Security"])

    with tab1:
        st.markdown("### Hotels")
        if hotels:
            hotel_df = pd.DataFrame([
                {
                    "Hotel": hotel.get("name", ""),
                    "Brand": hotel.get("brand", ""),
                    "City": hotel.get("city", ""),
                    "Country": hotel.get("country", ""),
                    "Rooms": hotel.get("total_rooms", 0),
                    "Status": hotel.get("status", "active"),
                }
                for hotel in hotels
            ])
            st.dataframe(hotel_df, use_container_width=True, hide_index=True)
        else:
            st.info("No hotels created yet.")

        with st.form("admin_create_hotel_form", clear_on_submit=True):
            hotel_name = st.text_input("Hotel Name *")
            hotel_brand = st.text_input("Brand *")
            hotel_city = st.text_input("City *")
            hotel_country = st.text_input("Country", value="Uzbekistan")
            hotel_rooms = st.number_input("Default Room Count", min_value=1, max_value=5000, value=50)
            hotel_notes = st.text_area("Notes")
            create_hotel = st.form_submit_button("Save Hotel", type="primary")

        if create_hotel:
            if not hotel_name or not hotel_brand or not hotel_city:
                st.error("Hotel name, brand, and city are required.")
            else:
                db.save_hotel({
                    "name": hotel_name,
                    "brand": hotel_brand,
                    "city": hotel_city,
                    "country": hotel_country,
                    "total_rooms": hotel_rooms,
                    "notes": hotel_notes,
                })
                st.success(f"Hotel '{hotel_name}' created.")
                st.rerun()

        if hotels:
            st.markdown("---")
            st.markdown("### Edit Existing Hotel")
            selected_hotel_label = st.selectbox("Select Hotel", list(hotel_label_to_id.keys()), key="admin_edit_hotel_select")
            selected_hotel = db.get_hotel(hotel_label_to_id[selected_hotel_label])

            with st.form("admin_edit_hotel_form"):
                edit_name = st.text_input("Hotel Name *", value=selected_hotel.get("name", ""))
                edit_brand = st.text_input("Brand *", value=selected_hotel.get("brand", ""))
                edit_city = st.text_input("City *", value=selected_hotel.get("city", ""))
                edit_country = st.text_input("Country", value=selected_hotel.get("country", ""))
                edit_rooms = st.number_input("Default Room Count", min_value=1, max_value=5000, value=int(selected_hotel.get("total_rooms", 1) or 1))
                edit_status = st.selectbox("Status", ["active", "inactive"], index=0 if selected_hotel.get("status", "active") == "active" else 1)
                edit_notes = st.text_area("Notes", value=selected_hotel.get("notes", ""))
                update_hotel = st.form_submit_button("Update Hotel", type="primary")

            if update_hotel:
                if not edit_name or not edit_brand or not edit_city:
                    st.error("Hotel name, brand, and city are required.")
                else:
                    db.save_hotel({
                        "hotel_id": selected_hotel.get("hotel_id"),
                        "name": edit_name,
                        "brand": edit_brand,
                        "city": edit_city,
                        "country": edit_country,
                        "total_rooms": edit_rooms,
                        "status": edit_status,
                        "notes": edit_notes,
                    })
                    st.success("Hotel updated.")
                    st.rerun()

    with tab2:
        st.markdown("### Users")
        if users:
            hotel_lookup = {hotel["hotel_id"]: hotel for hotel in hotels}
            supplier_lookup = {supplier["supplier_id"]: supplier for supplier in suppliers}
            user_df = pd.DataFrame([
                {
                    "Name": user.get("full_name", ""),
                    "Username": user.get("username", ""),
                    "Role": user.get("role", "").replace("_", " ").title(),
                    "Hotels": (
                        ", ".join(
                            hotel_lookup.get(hotel_id, {}).get("name", hotel_id)
                            for hotel_id in user.get("hotel_ids", [])
                        )
                        or ("All Hotels" if user.get("role") == "admin" else "")
                    ),
                    "Supplier": supplier_lookup.get(user.get("supplier_id", ""), {}).get("name", ""),
                    "Active": "Yes" if user.get("active", True) else "No",
                }
                for user in users
            ])
            st.dataframe(user_df, use_container_width=True, hide_index=True)
        else:
            st.info("No users available.")

        with st.form("admin_create_user_form", clear_on_submit=True):
            full_name = st.text_input("Full Name *")
            username = st.text_input("Username *")
            email = st.text_input("Email")
            password = st.text_input("Password *", type="password")
            role = st.selectbox("Role", ["hotel_editor", "hotel_manager", "portfolio_manager", "supplier", "admin"])
            selected_hotel_labels = st.multiselect("Hotel Access", list(hotel_label_to_id.keys()))
            supplier_options = [""] + list(supplier_label_to_id.keys())
            linked_supplier_label = st.selectbox("Linked Supplier", supplier_options)
            active = st.checkbox("Active", value=True)
            create_user = st.form_submit_button("Save User", type="primary")

        if create_user:
            if not full_name or not username or not password:
                st.error("Full name, username, and password are required.")
            elif role not in {"admin", "supplier"} and not selected_hotel_labels:
                st.error("Select at least one hotel for hotel users.")
            elif role == "supplier" and not linked_supplier_label:
                st.error("Select a supplier for supplier users.")
            else:
                try:
                    db.save_user({
                        "full_name": full_name,
                        "username": username,
                        "email": email,
                        "password": password,
                        "role": role,
                        "hotel_ids": [] if role in {"admin", "supplier"} else [hotel_label_to_id[label] for label in selected_hotel_labels],
                        "supplier_id": supplier_label_to_id.get(linked_supplier_label, ""),
                        "active": active,
                    })
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    st.success(f"User '{username}' created.")
                    st.rerun()

        if users:
            st.markdown("---")
            st.markdown("### Edit Existing User")
            user_options = {
                f"{user.get('full_name', user.get('username', 'User'))} ({user.get('username', '')})": user["user_id"]
                for user in users
            }
            selected_user_label = st.selectbox("Select User", list(user_options.keys()), key="admin_edit_user_select")
            selected_user = db.get_user(user_options[selected_user_label])
            default_hotel_labels = [
                label for label, hotel_id in hotel_label_to_id.items()
                if hotel_id in selected_user.get("hotel_ids", [])
            ]
            selected_supplier_value = ""
            for label, supplier_id in supplier_label_to_id.items():
                if supplier_id == selected_user.get("supplier_id", ""):
                    selected_supplier_value = label
                    break

            with st.form("admin_edit_user_form"):
                edit_full_name = st.text_input("Full Name *", value=selected_user.get("full_name", ""))
                edit_username = st.text_input("Username *", value=selected_user.get("username", ""))
                edit_email = st.text_input("Email", value=selected_user.get("email", ""))
                edit_role = st.selectbox(
                    "Role",
                    ["hotel_editor", "hotel_manager", "portfolio_manager", "supplier", "admin"],
                    index=["hotel_editor", "hotel_manager", "portfolio_manager", "supplier", "admin"].index(selected_user.get("role", "hotel_editor")),
                )
                edit_hotel_labels = st.multiselect("Hotel Access", list(hotel_label_to_id.keys()), default=default_hotel_labels)
                edit_supplier_label = st.selectbox(
                    "Linked Supplier",
                    [""] + list(supplier_label_to_id.keys()),
                    index=([""] + list(supplier_label_to_id.keys())).index(selected_supplier_value) if selected_supplier_value in ([""] + list(supplier_label_to_id.keys())) else 0,
                )
                edit_active = st.checkbox("Active", value=selected_user.get("active", True))
                reset_password = st.text_input("Reset Password (optional)", type="password")
                update_user = st.form_submit_button("Update User", type="primary")

            if update_user:
                if not edit_full_name or not edit_username:
                    st.error("Full name and username are required.")
                elif edit_role not in {"admin", "supplier"} and not edit_hotel_labels:
                    st.error("Select at least one hotel for hotel users.")
                elif edit_role == "supplier" and not edit_supplier_label:
                    st.error("Select a supplier for supplier users.")
                else:
                    try:
                        payload = {
                            "user_id": selected_user.get("user_id"),
                            "full_name": edit_full_name,
                            "username": edit_username,
                            "email": edit_email,
                            "role": edit_role,
                            "hotel_ids": [] if edit_role in {"admin", "supplier"} else [hotel_label_to_id[label] for label in edit_hotel_labels],
                            "supplier_id": supplier_label_to_id.get(edit_supplier_label, ""),
                            "active": edit_active,
                        }
                        if reset_password:
                            payload["password"] = reset_password
                        db.save_user(payload)
                    except ValueError as exc:
                        st.error(str(exc))
                    else:
                        if selected_user.get("user_id") == get_current_user().get("user_id"):
                            refresh_authenticated_user()
                        st.success("User updated.")
                        st.rerun()

    with tab3:
        st.markdown("### Legacy Project Assignments")
        unassigned_projects = [project for project in db.get_all_projects() if not project.get("hotel_id")]

        if not unassigned_projects:
            st.info("All projects are assigned to hotels.")
        elif not hotels:
            st.warning("Create at least one hotel before assigning legacy projects.")
        else:
            for project in unassigned_projects:
                with st.container():
                    st.markdown(f"**{_project_label(project)}**")
                    selected_hotel_label = st.selectbox(
                        "Assign Hotel",
                        list(hotel_label_to_id.keys()),
                        key=f"assign_hotel_{project['project_id']}",
                    )
                    if st.button("Save Assignment", key=f"assign_btn_{project['project_id']}"):
                        db.assign_project_hotel(
                            project["project_id"],
                            hotel_label_to_id[selected_hotel_label],
                            updated_by=get_actor_name(),
                        )
                        st.success("Project assigned.")
                        st.rerun()
                    st.markdown("---")

    with tab4:
        st.markdown("### Login Audit")
        login_events = db.get_login_events(limit=100)
        if login_events:
            login_df = pd.DataFrame([
                {
                    "Timestamp": event.get("timestamp", "")[:19].replace("T", " "),
                    "Username": event.get("username", ""),
                    "Success": "Yes" if event.get("success") else "No",
                    "Role": event.get("role", ""),
                    "Note": event.get("note", ""),
                }
                for event in login_events
            ])
            st.dataframe(login_df, use_container_width=True, hide_index=True)
        else:
            st.caption("No login audit events yet.")

        st.markdown("---")
        st.markdown("### Notifications")
        notifications = db.get_notifications(limit=100)
        if notifications:
            notifications_df = pd.DataFrame([
                {
                    "Created": notification.get("created_at", "")[:19].replace("T", " "),
                    "Type": notification.get("notification_type", ""),
                    "Title": notification.get("title", ""),
                    "Hotel ID": notification.get("hotel_id", ""),
                    "Project ID": notification.get("project_id", ""),
                    "Target Roles": ", ".join(notification.get("target_roles", [])),
                    "Read By": ", ".join(notification.get("read_by", [])),
                }
                for notification in notifications
            ])
            st.dataframe(notifications_df, use_container_width=True, hide_index=True)
        else:
            st.caption("No notifications yet.")


# ============================================================================
# EXISTING FUNCTIONS (from deployed version)
# ============================================================================

def display_results():
    """Display calculation results"""
    results = st.session_state.results

    # Summary metrics
    st.markdown("### Summary")
    summary = results.get('summary', {})

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Hotel", summary.get('hotel_name', 'N/A'))
    with col2:
        st.metric("Total Rooms", summary.get('total_rooms', 0))
    with col3:
        st.metric("Total Beds", summary.get('total_beds', 0))
    with col4:
        st.metric("Brand", summary.get('brand', 'N/A'))
    with col5:
        st.metric("Floors", summary.get('num_floors', 0))

    st.markdown("---")

    # Category counts
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        linen_count = len(results.get('linen', []))
        st.metric("Linen SKUs", linen_count)
    with col2:
        furniture_count = len(results.get('furniture', []))
        st.metric("Furniture Items", furniture_count)
    with col3:
        restaurant_count = len(results.get('restaurant', []))
        st.metric("Restaurant Items", restaurant_count)
    with col4:
        total_items = sum([
            len(results.get('guest_rooms', [])),
            len(results.get('linen', [])),
            len(results.get('furniture', [])),
            len(results.get('restaurant', [])),
            len(results.get('kitchen', [])),
            len(results.get('spa', [])),
            len(results.get('public_areas', []))
        ])
        st.metric("Total Line Items", total_items)

    st.markdown("---")

    # Detailed tables
    tabs = st.tabs([
        "Guest Rooms", "Linen", "Bathroom", "Furniture", "Amenities",
        "Restaurant", "Kitchen", "Spa", "Pool", "Gym",
        "Public Areas", "Conference", "Back of House"
    ])

    categories = [
        'guest_rooms', 'linen', 'bathroom', 'furniture', 'amenities',
        'restaurant', 'kitchen', 'spa', 'pool', 'gym',
        'public_areas', 'conference', 'back_of_house'
    ]

    for i, cat in enumerate(categories):
        with tabs[i]:
            if results.get(cat):
                df = pd.DataFrame(results[cat])
                st.dataframe(df, use_container_width=True, hide_index=True)

                # Linen summary
                if cat == 'linen' and 'Final Qty' in df.columns:
                    st.markdown("#### Linen Summary by Item")
                    linen_summary = df.groupby('Item')['Final Qty'].sum().reset_index()
                    linen_summary.columns = ['Item', 'Total Quantity']
                    linen_summary = linen_summary.sort_values('Total Quantity', ascending=False)
                    st.dataframe(linen_summary, use_container_width=True, hide_index=True)
            else:
                st.info(f"No {cat.replace('_', ' ')} items calculated")

    # Export
    st.markdown("---")
    st.markdown("### Export Results")
    col1, col2 = st.columns(2)
    with col1:
        excel_file = _generate_results_excel_export(results)
        st.download_button(
            label="Download Excel Report",
            data=excel_file,
            file_name=f"Procurement_List_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    with col2:
        st.button("New Calculation", on_click=reset_calculation, use_container_width=True)


def _generate_results_excel_export(results):
    """Generate Excel file with all results"""
    output = BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        summary_data = {
            'Metric': list(results['summary'].keys()),
            'Value': list(results['summary'].values())
        }
        pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)

        categories = [
            ('guest_rooms', 'Guest Rooms'),
            ('linen', 'Linen'),
            ('bathroom', 'Bathroom'),
            ('furniture', 'Furniture'),
            ('amenities', 'Amenities'),
            ('restaurant', 'Restaurant'),
            ('kitchen', 'Kitchen'),
            ('spa', 'Spa'),
            ('pool', 'Pool'),
            ('gym', 'Gym'),
            ('public_areas', 'Public Areas'),
            ('conference', 'Conference'),
            ('back_of_house', 'Back of House')
        ]

        for key, sheet_name in categories:
            if results.get(key):
                df = pd.DataFrame(results[key])
                df.to_excel(writer, sheet_name=sheet_name, index=False)

                worksheet = writer.sheets[sheet_name]
                for idx, col in enumerate(df.columns):
                    max_length = max(
                        df[col].astype(str).apply(len).max(),
                        len(str(col))
                    )
                    worksheet.column_dimensions[openpyxl.utils.get_column_letter(idx + 1)].width = min(max_length + 2, 50)

    output.seek(0)
    return output.getvalue()


def reset_calculation():
    """Reset calculation state"""
    st.session_state.calculation_done = False
    st.session_state.results = {}


def show_project_history(show_header: bool = True):
    """Display project history"""
    if show_header:
        st.markdown('<div class="main-header">Project History</div>', unsafe_allow_html=True)

    projects = get_scoped_projects()

    if not projects:
        st.info("No projects available in the current hotel scope.")
        return

    st.markdown(f"### Total Projects: {len(projects)}")
    hotels = {hotel["hotel_id"]: hotel for hotel in db.get_all_hotels()}

    for project in reversed(projects):
        hotel = hotels.get(project.get("hotel_id"), {})
        review_status = _format_review_status(project.get("review_status", "draft"))
        expander_label = f"{_project_label(project)} • {review_status}"

        with st.expander(expander_label):
            summary = db.get_procurement_summary(project['project_id'])
            project_items = db.get_project_items(project["project_id"])
            history_export_bundle = _build_procurement_export_bundle(
                project,
                project_items,
                {"Department": "All", "Status Filter": "All", "Search": "All"},
                file_suffix="project_procurement",
                export_name="Procurement List",
            )
            history_excel_bytes = generate_stage1_excel_export(
                history_export_bundle["export_name"],
                history_export_bundle["rows_df"],
                history_export_bundle["summary_df"],
                context_column="Department",
                table_columns=PROCUREMENT_TABLE_COLUMNS,
            )
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.write("**Brand:**", project['hotel_info']['brand'])
                st.write("**Hotel:**", hotel.get("name", "Unassigned"))
                st.write("**City:**", project['hotel_info']['city'])
                st.write("**Country:**", project['hotel_info'].get('country', hotel.get("country", "")))

            with col2:
                st.write("**Project Name:**", project['hotel_info'].get('project_name', '') or "N/A")
                st.write("**Total Rooms:**", project['hotel_info']['total_rooms'])
                st.write("**Floors:**", project['hotel_info']['num_floors'])
                st.write("**Created:**", project['created_at'][:10])

            with col3:
                st.metric("Total Items", summary['total_items'])
                st.metric("Ordered", f"{summary['ordered_percent']}%")
                st.metric("Pending", summary['total_items'] - summary['ordered_count'])

            with col4:
                st.write("**Review Status:**", review_status)
                st.write("**Created By:**", project.get('created_by', 'N/A') or "N/A")
                st.write("**Reviewed By:**", project.get('reviewed_by', 'N/A') or "N/A")
                st.write("**Last Note:**", project.get('latest_review_note', '') or "None")

            note_value = project.get('latest_review_note', '')
            review_note = st.text_area(
                "Review / Correction Note",
                value=note_value,
                key=f"workflow_note_{project['project_id']}",
            )

            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("Open Procurement", key=f"view_{project['project_id']}"):
                    _set_view_mode("hotel_item_list", project_id=project["project_id"])
                    _rerun_if_legacy()
            with col2:
                st.download_button(
                    label="Download Excel",
                    data=history_excel_bytes,
                    file_name=f"{history_export_bundle['file_stem']}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"download_{project['project_id']}",
                    use_container_width=True,
                )
            with col3:
                if STAGE1_EXPORT_PDF_AVAILABLE:
                    history_print_pdf_bytes = generate_table_pdf(
                        "PROCUREMENT",
                        history_export_bundle["project_meta"],
                        history_export_bundle["rows_df"],
                        mode="print",
                        group_by="Department",
                        context_column="Department",
                        table_columns=PROCUREMENT_TABLE_COLUMNS,
                    )
                    st.download_button(
                        label="Print PDF",
                        data=history_print_pdf_bytes,
                        file_name=f"{history_export_bundle['file_stem']}_print.pdf",
                        mime="application/pdf",
                        key=f"history_print_{project['project_id']}",
                        use_container_width=True,
                    )
                else:
                    st.button(
                        "Print PDF",
                        disabled=True,
                        use_container_width=True,
                        key=f"history_print_disabled_{project['project_id']}",
                    )

            workflow_col1, workflow_col2 = st.columns(2)
            with workflow_col1:
                if not can_review_projects():
                    submit_label = "Resubmit for Review" if project.get("review_status") == "needs_correction" else "Submit for Review"
                    if st.button(submit_label, key=f"submit_{project['project_id']}", use_container_width=True):
                        next_status = "resubmitted" if project.get("review_status") == "needs_correction" else "submitted"
                        db.update_project_workflow(
                            project["project_id"],
                            next_status,
                            get_actor_name(),
                            review_note.strip(),
                        )
                        _notify_project_workflow(project, next_status, review_note.strip())
                        st.success("Project submitted.")
                        st.rerun()
                else:
                    if st.button("Request Correction", key=f"correction_{project['project_id']}", use_container_width=True):
                        if not review_note.strip():
                            st.error("Add a correction note before sending back the project.")
                        else:
                            db.update_project_workflow(
                                project["project_id"],
                                "needs_correction",
                                get_actor_name(),
                                review_note.strip(),
                            )
                            _notify_project_workflow(project, "needs_correction", review_note.strip())
                            st.success("Correction requested.")
                            st.rerun()

            with workflow_col2:
                if can_review_projects():
                    if st.button("Approve Project", key=f"approve_{project['project_id']}", use_container_width=True):
                        db.update_project_workflow(
                            project["project_id"],
                            "approved",
                            get_actor_name(),
                            review_note.strip(),
                        )
                        _notify_project_workflow(project, "approved", review_note.strip())
                        st.success("Project approved.")
                        st.rerun()

            if is_admin() and db.get_all_hotels():
                hotel_options = {"Unassigned": ""}
                for hotel_record in db.get_all_hotels():
                    hotel_options[_hotel_label(hotel_record)] = hotel_record["hotel_id"]
                current_hotel_id = project.get("hotel_id", "")
                hotel_labels = list(hotel_options.keys())
                current_index = 0
                for idx, label in enumerate(hotel_labels):
                    if hotel_options[label] == current_hotel_id:
                        current_index = idx
                        break

                selected_hotel_label = st.selectbox(
                    "Project Hotel",
                    hotel_labels,
                    index=current_index,
                    key=f"project_hotel_assign_{project['project_id']}",
                )
                selected_hotel_id = hotel_options[selected_hotel_label]
                if selected_hotel_id != current_hotel_id:
                    if st.button("Update Hotel Assignment", key=f"project_hotel_assign_btn_{project['project_id']}"):
                        db.assign_project_hotel(project["project_id"], selected_hotel_id, updated_by=get_actor_name())
                        st.success("Hotel assignment updated.")
                        st.rerun()

            workflow_history = project.get("workflow_history", [])
            if workflow_history:
                with st.expander("Workflow History", expanded=False):
                    history_df = pd.DataFrame([
                        {
                            "Timestamp": entry.get("timestamp", "")[:19].replace("T", " "),
                            "Status": _format_review_status(entry.get("status", "")),
                            "User": entry.get("user", ""),
                            "Note": entry.get("note", ""),
                        }
                        for entry in reversed(workflow_history[-10:])
                    ])
                    st.dataframe(history_df, use_container_width=True, hide_index=True)


def _apply_item_filters(items, filter_dept, filter_status, search_term):
    """Filter procurement items by department, status, and search term."""
    filtered = items.copy()
    if filter_dept != "All":
        filtered = [item for item in filtered if item['department'] == filter_dept]
    if filter_status == "Not Ordered":
        filtered = [item for item in filtered if not item['procurement_status']['ordered']]
    elif filter_status == "Ordered":
        filtered = [item for item in filtered if item['procurement_status']['ordered'] and not item['procurement_status']['received']]
    elif filter_status == "Received":
        filtered = [item for item in filtered if item['procurement_status']['received'] and not item['procurement_status']['installed']]
    elif filter_status == "Installed":
        filtered = [item for item in filtered if item['procurement_status']['installed']]
    if search_term:
        filtered = [
            item for item in filtered
            if search_term.lower() in str(item['item_data'].get('Item', item['item_data'].get('item', ''))).lower()
        ]
    return filtered


def _build_project_options(projects: List[Dict]) -> Dict[str, str]:
    """Map user-facing project labels to project IDs."""
    return {_project_label(project): project["project_id"] for project in projects}


def _build_hotel_options(hotels: List[Dict]) -> Dict[str, str]:
    """Map user-facing hotel labels to hotel IDs."""
    return {_hotel_label(hotel): hotel["hotel_id"] for hotel in hotels}


def _get_default_option_index(options: Dict[str, str], selected_value: str) -> int:
    """Return the option index for a saved selection, or zero."""
    for index, option_value in enumerate(options.values()):
        if option_value == selected_value:
            return index
    return 0


def _get_default_project_index(project_options: Dict[str, str]) -> int:
    """Keep project selectors aligned with the last opened project."""
    return _get_default_option_index(project_options, st.session_state.get("current_project_id", ""))


def _get_default_hotel_index(hotel_options: Dict[str, str]) -> int:
    """Keep hotel selectors aligned with the active hotel scope."""
    return _get_default_option_index(hotel_options, st.session_state.get("active_hotel_id", ""))


def select_scoped_project(
    label: str = "Select Project",
    key: str = "project_select",
    ignore_hotel_scope: bool = False,
    reset_checklist_pagination: bool = False,
) -> tuple[str, Dict]:
    """Render one shared scoped-project selector and persist the active project."""
    projects = get_scoped_projects(ignore_hotel_scope=ignore_hotel_scope)
    if not projects:
        return "", {}

    project_options = _build_project_options(projects)
    project_labels = list(project_options.keys())
    selected_project_name = st.selectbox(
        label,
        project_labels,
        index=_get_default_project_index(project_options),
        key=key,
    )
    project_id = project_options[selected_project_name]
    if reset_checklist_pagination and project_id != st.session_state.get("current_project_id"):
        st.session_state.checklist_page = 0
    st.session_state.current_project_id = project_id
    return project_id, get_visible_project(project_id)


def select_scoped_project_filter(
    label: str = "Project Filter",
    key: str = "project_filter_select",
    ignore_hotel_scope: bool = False,
    all_label: str = "All Scoped Projects",
) -> str:
    """Render a project filter selector that can also target all scoped projects."""
    projects = get_scoped_projects(ignore_hotel_scope=ignore_hotel_scope)
    if not projects:
        return ""

    project_options = {all_label: ""} | _build_project_options(projects)
    selected_project_name = st.selectbox(label, list(project_options.keys()), key=key)
    project_id = project_options[selected_project_name]
    if project_id:
        st.session_state.current_project_id = project_id
    return project_id


def select_accessible_hotel(
    label: str = "Select Hotel",
    key: str = "hotel_select",
    hotels: List[Dict] | None = None,
) -> Dict:
    """Render one shared hotel selector and persist the active hotel scope."""
    if hotels is None:
        hotels = get_accessible_hotels()
    if not hotels:
        return {}

    hotel_options = _build_hotel_options(hotels)
    selected_hotel_label = st.selectbox(
        label,
        list(hotel_options.keys()),
        index=_get_default_hotel_index(hotel_options),
        key=key,
    )
    selected_hotel_id = hotel_options[selected_hotel_label]
    st.session_state.active_hotel_id = selected_hotel_id

    for hotel in hotels:
        if hotel.get("hotel_id") == selected_hotel_id:
            return hotel
    return db.get_hotel(selected_hotel_id)


def _seed_editor_dataframe(
    rows: List[Dict],
    state_key: str,
    identity_column: str | None = None,
) -> pd.DataFrame:
    """Restore a saved data-editor draft when the current shape still matches."""
    base_df = pd.DataFrame(rows)
    stored_rows = st.session_state.get(state_key)
    if not stored_rows:
        return base_df

    stored_df = pd.DataFrame(stored_rows)
    if base_df.empty or stored_df.empty:
        return base_df

    if identity_column and identity_column in base_df.columns and identity_column in stored_df.columns:
        stored_lookup = {
            str(row[identity_column]): row
            for _, row in stored_df.iterrows()
        }
        merged_rows = []
        for _, row in base_df.iterrows():
            merged_row = row.to_dict()
            stored_row = stored_lookup.get(str(row[identity_column]))
            if stored_row is not None:
                for column in base_df.columns:
                    if column == identity_column:
                        continue
                    merged_row[column] = stored_row.get(column, merged_row[column])
            merged_rows.append(merged_row)
        return pd.DataFrame(merged_rows, columns=base_df.columns)

    if list(stored_df.columns) == list(base_df.columns) and len(stored_df) == len(base_df):
        return stored_df[base_df.columns]
    return base_df


def _persist_editor_dataframe(state_key: str, edited_df: pd.DataFrame) -> None:
    """Store the latest data-editor state for reuse after navigation."""
    st.session_state[state_key] = edited_df.to_dict("records")


def _get_item_review_status(item: Dict) -> str:
    """Return item-level review state."""
    return item.get("procurement_status", {}).get("review_status", "open")


def _format_item_review_status(status: str) -> str:
    """Human-friendly item review status."""
    labels = {
        "open": "Open",
        "needs_correction": "Needs Correction",
        "corrected": "Corrected",
        "approved": "Approved",
    }
    return labels.get(status, status.replace("_", " ").title())


def _update_item_with_audit(project_id: str, item_index: int, status_update: Dict, action: str, details: Dict = None):
    """Persist item changes and append an audit event."""
    success = db.update_item_status(project_id, item_index, status_update)
    if success:
        db.add_audit_entry(project_id, item_index, action, get_actor_name(), details or status_update)
    return success


def show_procurement_checklist(
    page_title: str = "Procurement Checklist",
    show_workspace_toolbar: bool = False,
    show_header: bool = True,
):
    """Show procurement checklist"""
    if show_header:
        st.markdown(f'<div class="main-header">{page_title}</div>', unsafe_allow_html=True)

    project_id, project = select_scoped_project(
        "Select Project",
        key="procurement_checklist_project",
        reset_checklist_pagination=True,
    )
    if not project_id:
        st.warning("No projects found in the current hotel scope.")
        return

    if not project:
        st.error("You do not have access to that project.")
        return

    items = db.get_project_items(project_id)
    summary = db.get_procurement_summary(project_id)
    correction_count = sum(1 for item in items if _get_item_review_status(item) == "needs_correction")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Items", summary['total_items'])
    with col2:
        st.metric("Ordered", f"{summary['ordered_count']} ({summary['ordered_percent']}%)")
    with col3:
        st.metric("Received", f"{summary['received_count']} ({summary['received_percent']}%)")
    with col4:
        st.metric("Installed", f"{summary['installed_count']} ({summary['installed_percent']}%)")
    if correction_count:
        st.caption(f"Items needing correction: {correction_count}")

    if show_workspace_toolbar:
        st.markdown("---")
        _render_project_workspace_toolbar(project, items, mode="procurement")

    st.markdown("---")

    col1, col2, col3 = st.columns(3)
    with col1:
        filter_dept = st.selectbox("Filter by Department", ["All"] + list(set(item['department'] for item in items)))
    with col2:
        filter_status = st.selectbox("Filter by Status", ["All", "Not Ordered", "Ordered", "Received", "Installed"])
    with col3:
        search_term = st.text_input("Search Items", "")

    filtered_items = _apply_item_filters(items, filter_dept, filter_status, search_term)
    procurement_filters = {
        "Department": filter_dept,
        "Status Filter": filter_status,
        "Search": search_term or "All",
    }
    export_bundle = _build_procurement_export_bundle(
        project,
        filtered_items,
        procurement_filters,
        file_suffix="hotel_item_list",
        export_name="Procurement List",
    )

    _render_stage1_export_toolbar(
        "Procurement List",
        export_bundle["file_stem"],
        export_bundle["rows_df"],
        export_bundle["summary_df"],
        export_bundle["project_meta"],
        pdf_title=page_title,
        pdf_group_by="Department",
        context_column="Department",
        table_columns=PROCUREMENT_TABLE_COLUMNS,
        flat_when_multi_context=True,
    )

    _PAGE_SIZE = 25
    total_filtered = len(filtered_items)
    total_pages = max(1, (total_filtered + _PAGE_SIZE - 1) // _PAGE_SIZE)
    current_page = min(st.session_state.get("checklist_page", 0), total_pages - 1)
    st.session_state.checklist_page = current_page

    st.markdown(f"### Showing {total_filtered} items")

    if total_pages > 1:
        col_prev, col_info, col_next = st.columns([1, 4, 1])
        with col_prev:
            if current_page > 0 and st.button("← Prev", key="checklist_prev"):
                st.session_state.checklist_page = current_page - 1
                st.rerun()
        with col_info:
            start = current_page * _PAGE_SIZE + 1
            end = min((current_page + 1) * _PAGE_SIZE, total_filtered)
            st.caption(f"Page {current_page + 1} of {total_pages}  •  items {start}–{end}")
        with col_next:
            if current_page < total_pages - 1 and st.button("Next →", key="checklist_next"):
                st.session_state.checklist_page = current_page + 1
                st.rerun()

    page_items = filtered_items[current_page * _PAGE_SIZE:(current_page + 1) * _PAGE_SIZE]

    for idx, item in enumerate(page_items):
        item_data = item['item_data']
        status = item['procurement_status']
        original_idx = items.index(item)

        status_badges = []
        if status['ordered']:
            status_badges.append("Ordered")
        if status['received']:
            status_badges.append("Received")
        if status['installed']:
            status_badges.append("Installed")
        review_status = _get_item_review_status(item)
        status_badges.append(_format_item_review_status(review_status))
        status_text = " | ".join(status_badges) if status_badges else "Pending"

        with st.container():
            col1, col2 = st.columns([3, 1])

            with col1:
                st.markdown(f"**{item_data.get('Item', item_data.get('item', 'N/A'))}**")
                st.caption(f"{item['department']} - {item['category']}")
                st.caption(f"Qty: {item_data.get('Total Qty', item_data.get('Total_Qty', 0))} {item_data.get('Unit', 'pcs')}")

            with col2:
                st.write(status_text)

            if not status['ordered']:
                if st.button("Mark Ordered", key=f"order_{original_idx}"):
                    _update_item_with_audit(project_id, original_idx, {
                        'ordered': True,
                        'ordered_date': datetime.now().strftime('%Y-%m-%d')
                    }, "ordered", {"ordered": True})
                    st.rerun()
            elif not status['received']:
                if st.button("Mark Received", key=f"receive_{original_idx}"):
                    _update_item_with_audit(project_id, original_idx, {
                        'received': True,
                        'received_date': datetime.now().strftime('%Y-%m-%d')
                    }, "received", {"received": True})
                    st.rerun()
            elif not status['installed']:
                if st.button("Mark Installed", key=f"install_{original_idx}"):
                    _update_item_with_audit(project_id, original_idx, {
                        'installed': True,
                        'installed_date': datetime.now().strftime('%Y-%m-%d')
                    }, "installed", {"installed": True})
                    st.rerun()

            with st.expander("Details & Notes"):
                col1, col2 = st.columns(2)

                with col1:
                    supplier = st.text_input("Supplier", value=status['supplier'], key=f"supplier_{original_idx}")
                    po_number = st.text_input("PO Number", value=status['po_number'], key=f"po_{original_idx}")
                    unit_price = st.number_input("Unit Price", value=float(status['unit_price']), key=f"price_{original_idx}")

                with col2:
                    ordered_qty = st.number_input("Ordered Qty", value=status['ordered_qty'], key=f"oqty_{original_idx}")
                    received_qty = st.number_input("Received Qty", value=status['received_qty'], key=f"rqty_{original_idx}")

                notes = st.text_area("Notes", value=status['notes'], key=f"notes_{original_idx}")
                review_note = st.text_area(
                    "Correction / Review Note",
                    value=status.get('correction_note', ''),
                    key=f"review_note_{original_idx}",
                )
                st.caption(
                    f"Review Status: {_format_item_review_status(review_status)}"
                    + (f" | Reviewed By: {status.get('reviewed_by', '')}" if status.get('reviewed_by') else "")
                )

                if st.button("Save Details", key=f"save_{original_idx}"):
                    _update_item_with_audit(project_id, original_idx, {
                        'supplier': supplier,
                        'po_number': po_number,
                        'unit_price': unit_price,
                        'ordered_qty': ordered_qty,
                        'received_qty': received_qty,
                        'total_price': unit_price * ordered_qty,
                        'notes': notes,
                    }, "details_updated", {
                        'supplier': supplier,
                        'po_number': po_number,
                        'unit_price': unit_price,
                        'ordered_qty': ordered_qty,
                        'received_qty': received_qty,
                        'total_price': unit_price * ordered_qty,
                    })
                    st.success("Saved!")
                    st.rerun()

                review_col1, review_col2 = st.columns(2)
                with review_col1:
                    if can_review_projects():
                        if st.button("Request Item Correction", key=f"request_item_correction_{original_idx}", use_container_width=True):
                            if not review_note.strip():
                                st.error("Add a correction note before requesting correction.")
                            else:
                                _update_item_with_audit(project_id, original_idx, {
                                    'review_status': 'needs_correction',
                                    'correction_note': review_note.strip(),
                                    'reviewed_by': get_actor_name(),
                                    'reviewed_at': datetime.now().isoformat(),
                                }, "item_correction_requested", {"note": review_note.strip()})
                                _notify_item_review(project, item_data.get('Item', item_data.get('item', 'Item')), original_idx, 'needs_correction', review_note.strip())
                                st.success("Correction requested for item.")
                                st.rerun()
                    elif review_status == "needs_correction":
                        if st.button("Mark Corrected", key=f"mark_item_corrected_{original_idx}", use_container_width=True):
                            _update_item_with_audit(project_id, original_idx, {
                                'review_status': 'corrected',
                                'correction_note': review_note.strip(),
                                'corrected_by': get_actor_name(),
                                'corrected_at': datetime.now().isoformat(),
                            }, "item_corrected", {"note": review_note.strip()})
                            _notify_item_review(project, item_data.get('Item', item_data.get('item', 'Item')), original_idx, 'corrected', review_note.strip())
                            st.success("Item marked as corrected.")
                            st.rerun()

                with review_col2:
                    if can_review_projects():
                        if st.button("Approve Item", key=f"approve_item_{original_idx}", use_container_width=True):
                            _update_item_with_audit(project_id, original_idx, {
                                'review_status': 'approved',
                                'correction_note': review_note.strip(),
                                'reviewed_by': get_actor_name(),
                                'reviewed_at': datetime.now().isoformat(),
                            }, "item_approved", {"note": review_note.strip()})
                            _notify_item_review(project, item_data.get('Item', item_data.get('item', 'Item')), original_idx, 'approved', review_note.strip())
                            st.success("Item approved.")
                            st.rerun()

                audit_trail = item.get("audit_trail", [])
                if audit_trail:
                    with st.expander("Item Audit Trail", expanded=False):
                        audit_df = pd.DataFrame([
                            {
                                "Timestamp": entry.get("timestamp", "")[:19].replace("T", " "),
                                "Action": entry.get("action", ""),
                                "User": entry.get("user", ""),
                                "Details": json.dumps(entry.get("details", {}), ensure_ascii=False),
                            }
                            for entry in reversed(audit_trail[-10:])
                        ])
                        st.dataframe(audit_df, use_container_width=True, hide_index=True)

            st.markdown("---")


def show_project_comparison(show_header: bool = True):
    """Compare two projects"""
    if show_header:
        st.markdown('<div class="main-header">Project Comparison</div>', unsafe_allow_html=True)

    projects = get_scoped_projects(ignore_hotel_scope=True)

    if len(projects) < 2:
        st.warning("Need at least 2 accessible projects to compare.")
        return

    project_options = _build_project_options(projects)
    project_labels = list(project_options.keys())

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### Project 1")
        project1_name = st.selectbox("Select Project 1", project_labels, key="p1")
        project1_id = project_options[project1_name]

    with col2:
        st.markdown("### Project 2")
        project2_name = st.selectbox("Select Project 2", project_labels, key="p2")
        project2_id = project_options[project2_name]

    if project1_id == project2_id:
        st.warning("Please select different projects to compare.")
        return

    comparison = db.compare_projects(project1_id, project2_id)

    st.markdown("### Comparison Summary")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Rooms", comparison['project1']['rooms'],
                   delta=comparison['differences']['rooms_diff'])
    with col2:
        st.metric("Total Items", comparison['project1']['total_items'],
                   delta=comparison['differences']['items_diff'])
    with col3:
        st.metric("Total Budget", f"${comparison['project1']['total_budget']:,.0f}",
                   delta=f"${comparison['differences']['budget_diff']:,.0f}")

    st.markdown("### Detailed Comparison")
    items1 = db.get_project_items(project1_id)
    items2 = db.get_project_items(project2_id)

    depts1 = {}
    for item in items1:
        dept = item['department']
        if dept not in depts1:
            depts1[dept] = []
        depts1[dept].append(item)

    depts2 = {}
    for item in items2:
        dept = item['department']
        if dept not in depts2:
            depts2[dept] = []
        depts2[dept].append(item)

    all_depts = set(list(depts1.keys()) + list(depts2.keys()))

    for dept in sorted(all_depts):
        with st.expander(f"{dept}"):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**{comparison['project1']['name']}**")
                st.write(f"Items: {len(depts1.get(dept, []))}")
            with col2:
                st.markdown(f"**{comparison['project2']['name']}**")
                st.write(f"Items: {len(depts2.get(dept, []))}")


# ============================================================================
# P2P HELPERS AND VIEWS
# ============================================================================

def _safe_float(value, default: float = 0.0) -> float:
    """Best-effort float conversion."""
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return default


def _format_currency(value) -> str:
    """Consistent currency formatting."""
    return f"${_safe_float(value):,.2f}"


def _parse_datetime(value: str):
    """Best-effort datetime parsing for dashboard aging."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _get_scoped_project_lookup(ignore_hotel_scope: bool = False) -> Dict[str, Dict]:
    """Map visible project IDs to project records."""
    return {
        project["project_id"]: project
        for project in get_scoped_projects(ignore_hotel_scope=ignore_hotel_scope)
    }


def _get_scoped_purchase_orders(project_id: str = "", supplier_id: str = "") -> List[Dict]:
    """Purchase orders limited to the current user's project scope."""
    filters = {}
    if project_id:
        filters["project_id"] = project_id
    if supplier_id:
        filters["supplier_id"] = supplier_id

    pos = db.get_purchase_orders(filters or None)
    visible_project_ids = set(_get_scoped_project_lookup().keys())
    return [po for po in pos if po.get("project_id") in visible_project_ids]


def _get_scoped_invoices(project_id: str = "", supplier_id: str = "", po_id: str = "") -> List[Dict]:
    """Invoices limited to the current user's project scope."""
    filters = {}
    if supplier_id:
        filters["supplier_id"] = supplier_id
    if po_id:
        filters["po_id"] = po_id

    visible_project_ids = set(_get_scoped_project_lookup().keys())
    po_lookup = {po.get("po_id"): po for po in _get_scoped_purchase_orders(project_id=project_id)}
    invoices = db.get_invoices(filters or None)
    scoped = []
    for invoice in invoices:
        invoice_project_id = invoice.get("project_id", "")
        if invoice.get("po_id") in po_lookup:
            scoped.append(invoice)
        elif invoice_project_id and invoice_project_id in visible_project_ids:
            scoped.append(invoice)
    return scoped


def _get_scoped_payments(project_id: str = "", supplier_id: str = "", invoice_id: str = "") -> List[Dict]:
    """Payments limited to the current user's project scope."""
    filters = {}
    if supplier_id:
        filters["supplier_id"] = supplier_id
    if invoice_id:
        filters["invoice_id"] = invoice_id

    invoice_lookup = {invoice.get("invoice_id"): invoice for invoice in _get_scoped_invoices(project_id=project_id)}
    payments = db.get_payments(filters or None)
    return [payment for payment in payments if payment.get("invoice_id") in invoice_lookup]


def _invoice_paid_amount(invoice_id: str, payments: List[Dict] = None) -> float:
    """Total paid amount for one invoice."""
    payments = payments if payments is not None else _get_scoped_payments(invoice_id=invoice_id)
    return sum(_safe_float(payment.get("amount", 0)) for payment in payments if payment.get("invoice_id") == invoice_id)


def _build_po_item_candidates(project_id: str, include_linked: bool = False) -> List[Dict]:
    """Build editable PO candidate rows from procurement items."""
    rows = []
    for idx, item in enumerate(db.get_project_items(project_id)):
        item_data = item.get("item_data", {})
        status = item.get("procurement_status", {})
        if not include_linked and status.get("po_number"):
            continue
        if status.get("installed"):
            continue

        qty = status.get("ordered_qty") or item_data.get("Total Qty", item_data.get("Total_Qty", 0)) or 0
        rows.append({
            "Include": False,
            "Item Index": idx,
            "Department": item.get("department", ""),
            "Item": item_data.get("Item", item_data.get("item", "Item")),
            "Specification": item_data.get("Specification", item_data.get("specification", "")),
            "Order Qty": int(_safe_float(qty)),
            "Unit": item_data.get("Unit", "pcs"),
            "Unit Price": _safe_float(status.get("unit_price", 0)),
            "Current Supplier": status.get("supplier", ""),
            "Existing PO": status.get("po_number", ""),
        })
    return rows


def _po_status_badge(po: Dict) -> str:
    """Readable PO status label."""
    return po.get("status", "Draft") or "Draft"


def show_p2p_dashboard(show_header: bool = True, show_navigation_buttons: bool = True):
    """Management dashboard for procure-to-pay activity."""
    if show_header:
        st.markdown('<div class="main-header">P2P Dashboard</div>', unsafe_allow_html=True)

    scoped_projects = get_scoped_projects()
    if not scoped_projects:
        st.info("No projects available in the current hotel scope.")
        return

    scoped_pos = _get_scoped_purchase_orders()
    scoped_invoices = _get_scoped_invoices()
    scoped_payments = _get_scoped_payments()

    total_po_value = sum(_safe_float(po.get("total_amount", 0)) for po in scoped_pos)
    total_invoice_value = sum(_safe_float(invoice.get("total_amount", 0)) for invoice in scoped_invoices)
    total_paid = sum(_safe_float(payment.get("amount", 0)) for payment in scoped_payments)
    outstanding = max(total_invoice_value - total_paid, 0)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("POs", len(scoped_pos), delta=_format_currency(total_po_value))
    with col2:
        st.metric("Invoices", len(scoped_invoices), delta=_format_currency(total_invoice_value))
    with col3:
        st.metric("Payments", len(scoped_payments), delta=_format_currency(total_paid))
    with col4:
        st.metric("Outstanding", _format_currency(outstanding))

    po_status_counts = {}
    for po in scoped_pos:
        status = po.get("status", "Draft")
        po_status_counts[status] = po_status_counts.get(status, 0) + 1

    invoice_match_counts = {}
    for invoice in scoped_invoices:
        match_status = invoice.get("match_status", "Unmatched")
        invoice_match_counts[match_status] = invoice_match_counts.get(match_status, 0) + 1

    overdue_pos = []
    for po in scoped_pos:
        if po.get("status") in {"Completed", "Rejected"}:
            continue
        created_at = _parse_datetime(po.get("created_at"))
        if created_at and (datetime.now() - created_at).days >= 7:
            overdue_pos.append(po)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### PO Status Breakdown")
        if po_status_counts:
            st.bar_chart(po_status_counts)
        else:
            st.caption("No purchase orders yet.")
    with col2:
        st.markdown("### Invoice Match Breakdown")
        if invoice_match_counts:
            st.bar_chart(invoice_match_counts)
        else:
            st.caption("No invoices yet.")

    supplier_value = {}
    for po in scoped_pos:
        supplier_name = po.get("supplier_name") or db.get_supplier(po.get("supplier_id", "")).get("name") or "Unknown Supplier"
        supplier_value[supplier_name] = supplier_value.get(supplier_name, 0) + _safe_float(po.get("total_amount", 0))

    if supplier_value:
        st.markdown("### Spend by Supplier")
        supplier_df = pd.DataFrame([
            {"Supplier": supplier, "PO Value": value}
            for supplier, value in sorted(supplier_value.items(), key=lambda item: item[1], reverse=True)
        ])
        supplier_df["PO Value"] = supplier_df["PO Value"].map(_format_currency)
        st.dataframe(supplier_df, use_container_width=True, hide_index=True)

    st.markdown("### Exceptions")
    mismatched = [invoice for invoice in scoped_invoices if invoice.get("match_status") == "Mismatched"]
    unpaid = []
    for invoice in scoped_invoices:
        paid_amount = _invoice_paid_amount(invoice.get("invoice_id", ""), scoped_payments)
        outstanding_amount = max(_safe_float(invoice.get("total_amount", 0)) - paid_amount, 0)
        if outstanding_amount > 0:
            unpaid.append({
                "Invoice ID": invoice.get("invoice_id", ""),
                "Status": invoice.get("status", ""),
                "Outstanding": outstanding_amount,
            })

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Overdue Purchase Orders")
        if overdue_pos:
            overdue_df = pd.DataFrame([
                {
                    "PO ID": po.get("po_id", ""),
                    "Project ID": po.get("project_id", ""),
                    "Supplier": po.get("supplier_name", ""),
                    "Status": po.get("status", ""),
                    "Created": str(po.get("created_at", ""))[:10],
                }
                for po in overdue_pos
            ])
            st.dataframe(overdue_df, use_container_width=True, hide_index=True)
        else:
            st.caption("No overdue purchase orders.")
    with col2:
        st.markdown("#### Mismatched / Unpaid Invoices")
        issue_rows = [
            {
                "Invoice ID": invoice.get("invoice_id", ""),
                "Match": invoice.get("match_status", ""),
                "Status": invoice.get("status", ""),
                "Amount": _format_currency(invoice.get("total_amount", 0)),
            }
            for invoice in mismatched
        ] + [
            {
                "Invoice ID": row["Invoice ID"],
                "Match": "",
                "Status": row["Status"],
                "Amount": _format_currency(row["Outstanding"]),
            }
            for row in unpaid[:10]
        ]
        if issue_rows:
            st.dataframe(pd.DataFrame(issue_rows), use_container_width=True, hide_index=True)
        else:
            st.caption("No invoice exceptions.")

    if show_navigation_buttons:
        action_col1, action_col2, action_col3 = st.columns(3)
        with action_col1:
            if st.button("Open PO Center", use_container_width=True, key="p2p_open_po"):
                _set_view_mode("po_center")
                _rerun_if_legacy()
        with action_col2:
            if st.button("Open Invoice Center", use_container_width=True, key="p2p_open_invoice"):
                _set_view_mode("invoice_center")
                _rerun_if_legacy()
        with action_col3:
            if st.button("Open Payment Center", use_container_width=True, key="p2p_open_payment"):
                _set_view_mode("payment_center")
                _rerun_if_legacy()


def show_po_center(show_header: bool = True):
    """Hotel-side purchase order workflow."""
    if show_header:
        st.markdown('<div class="main-header">PO Center</div>', unsafe_allow_html=True)

    project_id, project = select_scoped_project("Select Project", key="po_center_project")
    if not project_id:
        st.info("No projects available in the current hotel scope.")
        return
    if not project:
        st.error("You do not have access to that project.")
        return

    suppliers = [supplier for supplier in db.get_all_suppliers() if supplier.get("status", "active") == "active"]
    supplier_lookup = {f"{supplier.get('name', 'Unnamed')} ({supplier.get('email', 'no-email')})": supplier for supplier in suppliers}
    scoped_pos = _get_scoped_purchase_orders(project_id=project_id)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Project POs", len(scoped_pos))
    with col2:
        st.metric("Submitted / Approved", sum(1 for po in scoped_pos if po.get("status") in {"Submitted", "Approved", "Supplier Acknowledged"}))
    with col3:
        st.metric("PO Value", _format_currency(sum(_safe_float(po.get("total_amount", 0)) for po in scoped_pos)))

    tab_create, tab_manage = st.tabs(["Create PO", "Manage POs"])

    with tab_create:
        if not suppliers:
            st.warning("No active suppliers available. Create supplier profiles first.")
        else:
            selected_supplier_label = st.selectbox("Supplier", list(supplier_lookup.keys()), key="po_supplier_select")
            selected_supplier = supplier_lookup[selected_supplier_label]
            include_linked_items = st.checkbox("Show items already linked to a PO", value=False, key="po_include_linked")
            po_notes = st.text_area("PO Notes", key="po_notes")

            candidate_rows = _build_po_item_candidates(project_id, include_linked=include_linked_items)
            for row in candidate_rows:
                if row["Current Supplier"] == selected_supplier.get("name") and not row["Existing PO"]:
                    row["Include"] = True

            if candidate_rows:
                po_editor_key = (
                    f"po_editor_{project_id}_{selected_supplier.get('supplier_id')}_{int(include_linked_items)}"
                )
                po_editor_state_key = f"{po_editor_key}_rows"
                editor_df = _seed_editor_dataframe(
                    candidate_rows,
                    po_editor_state_key,
                    identity_column="Item Index",
                )
                edited_df = st.data_editor(
                    editor_df,
                    use_container_width=True,
                    hide_index=True,
                    key=po_editor_key,
                    column_config={
                        "Include": st.column_config.CheckboxColumn("Include"),
                        "Item Index": st.column_config.NumberColumn("Item Index", disabled=True),
                        "Department": st.column_config.TextColumn("Department", disabled=True),
                        "Item": st.column_config.TextColumn("Item", disabled=True),
                        "Specification": st.column_config.TextColumn("Specification", disabled=True),
                        "Order Qty": st.column_config.NumberColumn("Order Qty", min_value=0),
                        "Unit": st.column_config.TextColumn("Unit", disabled=True),
                        "Unit Price": st.column_config.NumberColumn("Unit Price", min_value=0, format="%.2f"),
                        "Current Supplier": st.column_config.TextColumn("Current Supplier", disabled=True),
                        "Existing PO": st.column_config.TextColumn("Existing PO", disabled=True),
                    },
                )
                _persist_editor_dataframe(po_editor_state_key, edited_df)

                selected_rows = edited_df[edited_df["Include"] == True]
                draft_total = sum(
                    _safe_float(row["Order Qty"]) * _safe_float(row["Unit Price"])
                    for _, row in selected_rows.iterrows()
                ) if not selected_rows.empty else 0
                st.caption(f"Draft PO total: {_format_currency(draft_total)}")

                if st.button("Create Draft PO", type="primary", key="po_create_btn", use_container_width=True):
                    if selected_rows.empty:
                        st.error("Select at least one item for the purchase order.")
                    else:
                        po_items = []
                        for _, row in selected_rows.iterrows():
                            po_items.append({
                                "item_index": int(row["Item Index"]),
                                "item_name": row["Item"],
                                "specification": row["Specification"],
                                "department": row["Department"],
                                "quantity": int(_safe_float(row["Order Qty"])),
                                "unit": row["Unit"],
                                "unit_price": _safe_float(row["Unit Price"]),
                                "line_total": _safe_float(row["Order Qty"]) * _safe_float(row["Unit Price"]),
                            })

                        po_data = {
                            "project_id": project_id,
                            "hotel_id": project.get("hotel_id", ""),
                            "supplier_id": selected_supplier.get("supplier_id", ""),
                            "supplier_name": selected_supplier.get("name", ""),
                            "created_by": get_actor_name(),
                            "notes": po_notes.strip(),
                            "items": po_items,
                            "total_amount": sum(item["line_total"] for item in po_items),
                        }
                        po_id = db.create_purchase_order(po_data)

                        for item in po_items:
                            _update_item_with_audit(project_id, item["item_index"], {
                                "ordered": True,
                                "ordered_date": datetime.now().strftime("%Y-%m-%d"),
                                "ordered_qty": item["quantity"],
                                "supplier": selected_supplier.get("name", ""),
                                "po_number": po_id,
                                "unit_price": item["unit_price"],
                                "total_price": item["line_total"],
                            }, "po_created", {
                                "po_id": po_id,
                                "supplier": selected_supplier.get("name", ""),
                                "ordered_qty": item["quantity"],
                                "unit_price": item["unit_price"],
                            })

                        st.session_state.pop(po_editor_state_key, None)
                        st.success(f"Draft PO created: {po_id}")
                        st.rerun()
            else:
                st.info("No procurement items are currently available for PO creation.")

    with tab_manage:
        status_filter = st.selectbox(
            "Filter by Status",
            ["All", "Draft", "Submitted", "Supplier Acknowledged", "Approved", "Rejected", "Completed"],
            key="po_status_filter",
        )
        filtered_pos = scoped_pos if status_filter == "All" else [po for po in scoped_pos if po.get("status") == status_filter]

        if not filtered_pos:
            st.info("No purchase orders found for this project.")
        else:
            po_df = pd.DataFrame([
                {
                    "PO ID": po.get("po_id", ""),
                    "Supplier": po.get("supplier_name") or db.get_supplier(po.get("supplier_id", "")).get("name", ""),
                    "Status": po.get("status", ""),
                    "Created": str(po.get("created_at", ""))[:10],
                    "Total": _format_currency(po.get("total_amount", 0)),
                }
                for po in filtered_pos
            ])
            st.dataframe(po_df, use_container_width=True, hide_index=True)

            for po in filtered_pos:
                with st.expander(f"{po.get('po_id', '')} • {_po_status_badge(po)} • {_format_currency(po.get('total_amount', 0))}"):
                    if po.get("items"):
                        st.dataframe(pd.DataFrame(po.get("items", [])), use_container_width=True, hide_index=True)
                    else:
                        st.caption("No line items stored for this PO.")

                    approval_history = po.get("approval_history", [])
                    if approval_history:
                        history_df = pd.DataFrame([
                            {
                                "Timestamp": entry.get("timestamp", "")[:19].replace("T", " "),
                                "Status": entry.get("status", ""),
                                "By": entry.get("approver", ""),
                                "Notes": entry.get("notes", ""),
                            }
                            for entry in approval_history
                        ])
                        st.dataframe(history_df, use_container_width=True, hide_index=True)

                    po_action_note = st.text_area("Workflow Note", key=f"po_action_note_{po.get('po_id', '')}")
                    action_col1, action_col2, action_col3 = st.columns(3)

                    with action_col1:
                        if po.get("status") == "Draft":
                            if st.button("Submit PO", key=f"po_submit_{po['po_id']}", use_container_width=True):
                                db.update_purchase_order_status(po["po_id"], "Submitted", get_actor_name(), po_action_note.strip())
                                _notify_purchase_order_status(project, {**po, "po_id": po["po_id"]}, "Submitted", po_action_note.strip())
                                st.success("PO submitted.")
                                st.rerun()
                    with action_col2:
                        if can_review_projects() and po.get("status") in {"Submitted", "Supplier Acknowledged"}:
                            if st.button("Approve PO", key=f"po_approve_{po['po_id']}", use_container_width=True):
                                db.update_purchase_order_status(po["po_id"], "Approved", get_actor_name(), po_action_note.strip())
                                _notify_purchase_order_status(project, {**po, "po_id": po["po_id"]}, "Approved", po_action_note.strip())
                                st.success("PO approved.")
                                st.rerun()
                    with action_col3:
                        if can_review_projects() and po.get("status") in {"Approved", "Supplier Acknowledged"}:
                            if st.button("Mark Completed", key=f"po_complete_{po['po_id']}", use_container_width=True):
                                db.update_purchase_order_status(po["po_id"], "Completed", get_actor_name(), po_action_note.strip())
                                _notify_purchase_order_status(project, {**po, "po_id": po["po_id"]}, "Completed", po_action_note.strip())
                                st.success("PO marked completed.")
                                st.rerun()

                    if can_review_projects() and po.get("status") not in {"Rejected", "Completed"}:
                        if st.button("Reject PO", key=f"po_reject_mgr_{po['po_id']}", use_container_width=True):
                            if not po_action_note.strip():
                                st.error("Add a note before rejecting the PO.")
                            else:
                                db.update_purchase_order_status(po["po_id"], "Rejected", get_actor_name(), po_action_note.strip())
                                _notify_purchase_order_status(project, {**po, "po_id": po["po_id"]}, "Rejected", po_action_note.strip())
                                st.warning("PO rejected.")
                                st.rerun()


def show_invoice_center(show_header: bool = True):
    """Invoice recording and matching workflow."""
    if show_header:
        st.markdown('<div class="main-header">Invoice Center</div>', unsafe_allow_html=True)

    projects = get_scoped_projects()
    if not projects:
        st.info("No projects available in the current hotel scope.")
        return

    selected_project_id = select_scoped_project_filter("Project Filter", key="invoice_center_project")
    project_lookup = _get_scoped_project_lookup()
    scoped_pos = _get_scoped_purchase_orders(project_id=selected_project_id)
    scoped_invoices = _get_scoped_invoices(project_id=selected_project_id)
    scoped_payments = _get_scoped_payments(project_id=selected_project_id)
    po_lookup = {po.get("po_id"): po for po in scoped_pos}

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Invoices", len(scoped_invoices))
    with col2:
        st.metric("Matched", sum(1 for invoice in scoped_invoices if invoice.get("match_status") == "2-Way"))
    with col3:
        st.metric("Outstanding", _format_currency(sum(max(_safe_float(invoice.get("total_amount", 0)) - _invoice_paid_amount(invoice.get("invoice_id", ""), scoped_payments), 0) for invoice in scoped_invoices)))

    tab_record, tab_review = st.tabs(["Record Invoice", "Review & Match"])

    with tab_record:
        eligible_pos = [po for po in scoped_pos if po.get("status") not in {"Draft", "Rejected"}]
        if not eligible_pos:
            st.info("No submitted or approved purchase orders are available for invoicing.")
        else:
            po_label_map = {
                f"{po.get('po_id', '')} • {po.get('supplier_name', '')} • {_format_currency(po.get('total_amount', 0))}": po
                for po in eligible_pos
            }
            selected_po_label = st.selectbox("Purchase Order", list(po_label_map.keys()), key="invoice_po_select")
            selected_po = po_label_map[selected_po_label]
            project = project_lookup.get(selected_po.get("project_id", ""), db.get_project(selected_po.get("project_id", "")))

            st.caption(
                f"Supplier: {selected_po.get('supplier_name', '')} | "
                f"Status: {selected_po.get('status', '')} | "
                f"Project: {project.get('hotel_info', {}).get('property_name', '')}"
            )

            external_invoice_number = st.text_input("Supplier Invoice Number", key="invoice_external_number")
            invoice_amount = st.number_input(
                "Invoice Amount",
                min_value=0.0,
                value=_safe_float(selected_po.get("total_amount", 0)),
                key="invoice_amount",
            )
            auto_match = st.checkbox("Match to PO after save", value=True, key="invoice_auto_match")
            invoice_notes = st.text_area("Invoice Notes", key="invoice_notes")

            if st.button("Record Invoice", type="primary", key="invoice_record_btn", use_container_width=True):
                invoice_id = db.create_invoice({
                    "po_id": selected_po.get("po_id", ""),
                    "project_id": selected_po.get("project_id", ""),
                    "supplier_id": selected_po.get("supplier_id", ""),
                    "supplier_name": selected_po.get("supplier_name", ""),
                    "external_invoice_number": external_invoice_number.strip(),
                    "notes": invoice_notes.strip(),
                    "total_amount": invoice_amount,
                })
                if auto_match:
                    db.match_invoice_to_po(invoice_id, selected_po.get("po_id", ""))
                created_invoice = db.get_invoice(invoice_id)
                _notify_invoice_status(project, created_invoice, created_invoice.get("status", "Pending"), invoice_notes.strip())
                st.success(f"Invoice recorded: {invoice_id}")
                st.rerun()

    with tab_review:
        status_filter = st.selectbox("Status Filter", ["All", "Pending", "Matched", "Approved", "Disputed", "Partially Paid", "Paid"], key="invoice_status_filter")
        match_filter = st.selectbox("Match Filter", ["All", "Unmatched", "2-Way", "Mismatched"], key="invoice_match_filter")
        filtered_invoices = scoped_invoices
        if status_filter != "All":
            filtered_invoices = [invoice for invoice in filtered_invoices if invoice.get("status") == status_filter]
        if match_filter != "All":
            filtered_invoices = [invoice for invoice in filtered_invoices if invoice.get("match_status") == match_filter]

        if not filtered_invoices:
            st.info("No invoices match the current filters.")
        else:
            invoice_df = pd.DataFrame([
                {
                    "Invoice ID": invoice.get("invoice_id", ""),
                    "PO ID": invoice.get("po_id", ""),
                    "Status": invoice.get("status", ""),
                    "Match": invoice.get("match_status", ""),
                    "Amount": _format_currency(invoice.get("total_amount", 0)),
                    "Created": str(invoice.get("created_at", ""))[:10],
                }
                for invoice in filtered_invoices
            ])
            st.dataframe(invoice_df, use_container_width=True, hide_index=True)

            for invoice in filtered_invoices:
                project = project_lookup.get(invoice.get("project_id", ""))
                if not project and invoice.get("po_id") in po_lookup:
                    project = project_lookup.get(po_lookup[invoice["po_id"]].get("project_id", ""), {})
                with st.expander(f"{invoice.get('invoice_id', '')} • {invoice.get('status', '')} • {_format_currency(invoice.get('total_amount', 0))}"):
                    st.write(f"**PO:** {invoice.get('po_id', '')}")
                    st.write(f"**Supplier:** {invoice.get('supplier_name', '') or db.get_supplier(invoice.get('supplier_id', '')).get('name', '')}")
                    st.write(f"**Match Status:** {invoice.get('match_status', '')}")
                    if invoice.get("matching_result"):
                        match_df = pd.DataFrame([invoice.get("matching_result", {})])
                        st.dataframe(match_df, use_container_width=True, hide_index=True)

                    paid_amount = _invoice_paid_amount(invoice.get("invoice_id", ""), scoped_payments)
                    st.caption(f"Paid: {_format_currency(paid_amount)} | Outstanding: {_format_currency(max(_safe_float(invoice.get('total_amount', 0)) - paid_amount, 0))}")

                    invoice_action_note = st.text_area("Action Note", key=f"invoice_note_{invoice.get('invoice_id', '')}")
                    action_col1, action_col2, action_col3 = st.columns(3)
                    with action_col1:
                        if invoice.get("po_id"):
                            if st.button("Run Match", key=f"invoice_match_{invoice['invoice_id']}", use_container_width=True):
                                result = db.match_invoice_to_po(invoice["invoice_id"], invoice.get("po_id", ""))
                                refreshed = db.get_invoice(invoice["invoice_id"])
                                _notify_invoice_status(project, refreshed, refreshed.get("status", "Pending"), invoice_action_note.strip())
                                if result.get("success"):
                                    st.success("Invoice matched.")
                                else:
                                    st.error(result.get("message", "Matching failed."))
                                st.rerun()
                    with action_col2:
                        if can_review_projects() and invoice.get("status") not in {"Approved", "Paid"}:
                            if st.button("Approve Invoice", key=f"invoice_approve_{invoice['invoice_id']}", use_container_width=True):
                                db.update_invoice_status(invoice["invoice_id"], "Approved", get_actor_name(), invoice_action_note.strip())
                                refreshed = db.get_invoice(invoice["invoice_id"])
                                _notify_invoice_status(project, refreshed, "Approved", invoice_action_note.strip())
                                st.success("Invoice approved.")
                                st.rerun()
                    with action_col3:
                        if can_review_projects() and invoice.get("status") != "Paid":
                            if st.button("Mark Disputed", key=f"invoice_dispute_{invoice['invoice_id']}", use_container_width=True):
                                if not invoice_action_note.strip():
                                    st.error("Add a note before disputing the invoice.")
                                else:
                                    db.update_invoice_status(invoice["invoice_id"], "Disputed", get_actor_name(), invoice_action_note.strip())
                                    refreshed = db.get_invoice(invoice["invoice_id"])
                                    _notify_invoice_status(project, refreshed, "Disputed", invoice_action_note.strip())
                                    st.warning("Invoice marked disputed.")
                                    st.rerun()


def show_payment_center(show_header: bool = True):
    """Payment recording and register."""
    if show_header:
        st.markdown('<div class="main-header">Payment Center</div>', unsafe_allow_html=True)

    projects = get_scoped_projects()
    if not projects:
        st.info("No projects available in the current hotel scope.")
        return

    selected_project_id = select_scoped_project_filter("Project Filter", key="payment_center_project")

    scoped_invoices = _get_scoped_invoices(project_id=selected_project_id)
    scoped_payments = _get_scoped_payments(project_id=selected_project_id)
    project_lookup = _get_scoped_project_lookup()

    total_paid = sum(_safe_float(payment.get("amount", 0)) for payment in scoped_payments)
    total_outstanding = sum(
        max(_safe_float(invoice.get("total_amount", 0)) - _invoice_paid_amount(invoice.get("invoice_id", ""), scoped_payments), 0)
        for invoice in scoped_invoices
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Payments", len(scoped_payments))
    with col2:
        st.metric("Paid", _format_currency(total_paid))
    with col3:
        st.metric("Outstanding", _format_currency(total_outstanding))

    tab_record, tab_register = st.tabs(["Record Payment", "Payment Register"])

    with tab_record:
        unpaid_invoices = []
        for invoice in scoped_invoices:
            paid_amount = _invoice_paid_amount(invoice.get("invoice_id", ""), scoped_payments)
            outstanding_amount = max(_safe_float(invoice.get("total_amount", 0)) - paid_amount, 0)
            if outstanding_amount > 0:
                unpaid_invoices.append((invoice, paid_amount, outstanding_amount))

        if not can_review_projects():
            st.info("Only hotel managers, portfolio managers, and admins can record payments.")
        elif not unpaid_invoices:
            st.info("No unpaid invoices found in the current scope.")
        else:
            invoice_label_map = {
                f"{invoice.get('invoice_id', '')} • {invoice.get('supplier_name', '')} • Outstanding {_format_currency(outstanding)}": (invoice, paid_amount, outstanding)
                for invoice, paid_amount, outstanding in unpaid_invoices
            }
            selected_invoice_label = st.selectbox("Invoice", list(invoice_label_map.keys()), key="payment_invoice_select")
            invoice, paid_amount, outstanding_amount = invoice_label_map[selected_invoice_label]
            project = project_lookup.get(invoice.get("project_id", ""), {})

            st.caption(
                f"Supplier: {invoice.get('supplier_name', '')} | "
                f"Total: {_format_currency(invoice.get('total_amount', 0))} | "
                f"Paid: {_format_currency(paid_amount)} | "
                f"Outstanding: {_format_currency(outstanding_amount)}"
            )

            payment_amount = st.number_input(
                "Payment Amount",
                min_value=0.0,
                value=outstanding_amount,
                key="payment_amount_input",
            )
            payment_method = st.selectbox("Payment Method", ["Bank Transfer", "Cash", "Card", "Cheque", "Other"], key="payment_method")
            payment_reference = st.text_input("Reference", key="payment_reference")
            payment_status = st.selectbox("Payment Status", ["Completed", "Pending"], key="payment_status")
            payment_notes = st.text_area("Payment Notes", key="payment_notes")

            if st.button("Record Payment", type="primary", key="payment_record_btn", use_container_width=True):
                if payment_amount <= 0:
                    st.error("Payment amount must be greater than zero.")
                elif payment_amount > outstanding_amount + 0.01:
                    st.error("Payment amount exceeds the outstanding balance.")
                else:
                    payment_id = db.create_payment({
                        "invoice_id": invoice.get("invoice_id", ""),
                        "project_id": invoice.get("project_id", ""),
                        "supplier_id": invoice.get("supplier_id", ""),
                        "amount": payment_amount,
                        "payment_method": payment_method,
                        "reference": payment_reference.strip(),
                        "notes": payment_notes.strip(),
                        "status": payment_status,
                    })
                    created_payment = db.get_payments({"invoice_id": invoice.get("invoice_id", "")})[0]
                    refreshed_invoice = db.get_invoice(invoice.get("invoice_id", ""))
                    _notify_payment_recorded(project, created_payment, refreshed_invoice)
                    st.success(f"Payment recorded: {payment_id}")
                    st.rerun()

    with tab_register:
        if not scoped_payments:
            st.info("No payments recorded in the current scope.")
        else:
            payment_df = pd.DataFrame([
                {
                    "Payment ID": payment.get("payment_id", ""),
                    "Invoice ID": payment.get("invoice_id", ""),
                    "Status": payment.get("status", ""),
                    "Date": str(payment.get("payment_date", ""))[:10],
                    "Amount": _format_currency(payment.get("amount", 0)),
                    "Reference": payment.get("reference", ""),
                }
                for payment in scoped_payments
            ])
            st.dataframe(payment_df, use_container_width=True, hide_index=True)

            invoice_lookup = {invoice.get("invoice_id"): invoice for invoice in scoped_invoices}
            for payment in scoped_payments:
                invoice = invoice_lookup.get(payment.get("invoice_id", ""), {})
                with st.expander(f"{payment.get('payment_id', '')} • {_format_currency(payment.get('amount', 0))} • {payment.get('status', '')}"):
                    st.write(f"**Invoice:** {payment.get('invoice_id', '')}")
                    st.write(f"**Supplier:** {invoice.get('supplier_name', '') or db.get_supplier(payment.get('supplier_id', '')).get('name', '')}")
                    st.write(f"**Method:** {payment.get('payment_method', '') or 'N/A'}")
                    st.write(f"**Reference:** {payment.get('reference', '') or 'N/A'}")
                    st.write(f"**Notes:** {payment.get('notes', '') or 'None'}")


def _render_workspace_section_picker(
    label: str,
    options: List[str],
    state_key: str,
) -> str:
    """Shared horizontal selector for composite workspace pages."""
    current_value = st.session_state.get(state_key, options[0])
    if current_value not in options:
        st.session_state[state_key] = options[0]
    return st.radio(
        label,
        options,
        horizontal=True,
        key=state_key,
        label_visibility="collapsed",
    )


def show_project_workspace():
    """Minimalist project workspace combining project execution pages."""
    st.markdown('<div class="main-header">Project Workspace</div>', unsafe_allow_html=True)
    section = _render_workspace_section_picker(
        "Project Workspace Section",
        ["Calculator", "Procurement List", "Vendor RFP", "CAPEX", "Project History", "Comparison"],
        "project_workspace_section",
    )
    st.caption("Select one project flow and stay inside a single operational workspace.")
    st.markdown("---")

    if section == "Calculator":
        show_new_project()
    elif section == "Procurement List":
        show_procurement_checklist(
            page_title="Editable Item List",
            show_workspace_toolbar=True,
            show_header=False,
        )
    elif section == "Vendor RFP":
        show_supplier_comparison(
            page_title="Vendor Comparison",
            show_workspace_toolbar=True,
            show_header=False,
        )
    elif section == "CAPEX":
        show_capex_dashboard(show_header=False)
    elif section == "Project History":
        show_project_history(show_header=False)
    else:
        show_project_comparison(show_header=False)


def show_finance_workspace():
    """Minimalist finance workspace combining P2P pages."""
    st.markdown('<div class="main-header">Finance & P2P</div>', unsafe_allow_html=True)
    section = _render_workspace_section_picker(
        "Finance Workspace Section",
        ["Dashboard", "PO Center", "Invoices", "Payments"],
        "finance_workspace_section",
    )
    st.caption("Move between P2P stages without leaving the finance workspace.")
    st.markdown("---")

    if section == "Dashboard":
        show_p2p_dashboard(show_header=False, show_navigation_buttons=False)
    elif section == "PO Center":
        show_po_center(show_header=False)
    elif section == "Invoices":
        show_invoice_center(show_header=False)
    else:
        show_payment_center(show_header=False)


def show_directories_workspace():
    """Minimalist directory workspace for hotel and supplier reference records."""
    st.markdown('<div class="main-header">Directories</div>', unsafe_allow_html=True)
    section = _render_workspace_section_picker(
        "Directories Workspace Section",
        ["Hotels", "Hotel Details", "Vendors"],
        "directories_workspace_section",
    )
    st.caption("Reference master data without adding more sidebar destinations.")
    st.markdown("---")

    if section == "Hotels":
        show_hotel_directory(show_header=False, show_workspace_nav=False)
    elif section == "Hotel Details":
        show_hotel_details(show_header=False, show_workspace_nav=False)
    else:
        show_vendor_directory(show_header=False, show_workspace_nav=False)

# ============================================================================
# SUPPLIER HELPERS
# ============================================================================

def _normalize_text(value: str) -> str:
    """Normalize text for fuzzy matching and column detection."""
    if value is None:
        return ""
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def _similarity_score(a: str, b: str) -> float:
    """Name similarity score for item matching."""
    return SequenceMatcher(None, _normalize_text(a), _normalize_text(b)).ratio()


def _match_catalog_item(proc_name: str, catalog_items: List[Dict]) -> Dict:
    """Find best matching supplier catalog item for a procurement line."""
    best_match = None
    best_score = 0.0

    for item in catalog_items:
        candidate_name = item.get("item_name", "")
        score = _similarity_score(proc_name, candidate_name)
        if score > best_score:
            best_score = score
            best_match = item

    if best_match and best_score >= CATALOG_MATCH_THRESHOLD:
        return {**best_match, "match_score": best_score}
    return {}


def _compose_rfp_email(project: Dict, supplier: Dict, items: List[Dict]) -> Dict:
    """Create RFP email subject/body for selected supplier items."""
    hotel = project.get("hotel_info", {})
    subject = f"RFP: {hotel.get('property_name', 'Hotel')} - {project.get('project_id', '')}"

    lines = [
        f"Hello {supplier.get('contact_person') or supplier.get('name')},",
        "",
        "Please provide a quotation for the following items:",
        "",
    ]
    for item in items:
        line = f"- {item['item_name']} | Qty: {item['quantity']}"
        if item.get("specification"):
            line += f" | Spec: {item['specification']}"
        if item.get("price_available"):
            line += f" | Target Price: {item.get('price')} {item.get('currency', '')}".rstrip()
        lines.append(line)
    lines.extend([
        "",
        "Please confirm lead times, delivery terms, and any alternatives.",
        "",
        "Thank you,",
        hotel.get("project_name", "Procurement Team"),
    ])

    return {"subject": subject, "body": "\n".join(lines)}


# ============================================================================
# SUPPLIER PORTAL
# ============================================================================

def show_supplier_portal():
    """SENPRO handoff page for the separate vendor self-service application."""
    st.markdown('<div class="main-header">SENPROVEN</div>', unsafe_allow_html=True)
    st.markdown("### Vendor self-service is now handled in the separate SENPROVEN application.")

    senproven_url = _get_senproven_url()
    if senproven_url:
        st.markdown(f"[Open SENPROVEN]({senproven_url})")
    else:
        st.code(".venv/bin/streamlit run senproven_app.py")

    if is_supplier_user():
        supplier_id = get_current_supplier_id()
        if not supplier_id:
            st.error("This supplier account is not linked to a supplier profile.")
            return
        supplier = db.get_supplier(supplier_id)
        st.markdown("### Linked Supplier")
        st.write(f"**Company:** {supplier.get('name', 'Unlinked Supplier')}")
        st.write(f"**Email:** {supplier.get('email', '') or 'N/A'}")
        st.write(f"**Contact Person:** {supplier.get('contact_person', '') or 'N/A'}")
        st.write(f"**Categories:** {', '.join(supplier.get('categories', [])) or 'N/A'}")
        st.caption("Use SENPROVEN to update company information, upload PDF/CSV/Excel catalogues, or add manual product entries with specifications and notes.")
        _render_supplier_catalog_library_preview(supplier_id, key_prefix="supplier_portal")
    else:
        st.info("Use `VENDOR SUPPLIER LIST` inside SENPRO for the supplier directory. Vendors should log in through SENPROVEN to manage their own data.")


def show_supplier_comparison(
    page_title: str = "Supplier Comparison & RFP",
    show_workspace_toolbar: bool = False,
    show_header: bool = True,
):
    """Compare project procurement items against supplier catalogs and persist vendor decisions."""
    if show_header:
        st.markdown(f'<div class="main-header">{page_title}</div>', unsafe_allow_html=True)

    project_id, project = select_scoped_project("Select Project", key="supplier_cmp_project")
    if not project_id:
        st.info("No saved projects found in the current hotel scope.")
        return
    if not project:
        st.error("You do not have access to that project.")
        return

    project_items = db.get_project_items(project_id)
    if not project_items:
        st.info("Selected project has no procurement items.")
        return

    if show_workspace_toolbar:
        _render_project_workspace_toolbar(project, project_items, mode="rfp")

    suppliers = db.get_all_suppliers()
    if not suppliers:
        st.info("No suppliers available. Add suppliers in SENPRO and publish catalogues from SENPROVEN first.")
        return

    supplier_choices = {f"{supplier.get('name', 'Unnamed')} ({supplier.get('email', 'no-email')})": supplier["supplier_id"] for supplier in suppliers}
    supplier_lookup = {supplier["supplier_id"]: supplier for supplier in suppliers}
    selected_supplier_defaults = []
    for item in project_items:
        supplier_id = item.get("procurement_status", {}).get("selected_supplier_id", "")
        if supplier_id:
            for label, mapped_supplier_id in supplier_choices.items():
                if mapped_supplier_id == supplier_id and label not in selected_supplier_defaults:
                    selected_supplier_defaults.append(label)

    selected_suppliers = st.multiselect(
        "Select Suppliers",
        list(supplier_choices.keys()),
        default=selected_supplier_defaults,
        key="supplier_cmp_suppliers",
    )
    if not selected_suppliers:
        st.info("Select at least one supplier to compare.")
        return

    selected_supplier_ids = [supplier_choices[name] for name in selected_suppliers]
    catalog_items = db.get_all_catalog_items(selected_supplier_ids)
    catalog_by_supplier = {}
    for item in catalog_items:
        catalog_by_supplier.setdefault(item["supplier_id"], []).append(item)

    comparison_rows = []
    match_map = {}
    for idx, proj_item in enumerate(project_items):
        item_data = proj_item.get("item_data", {})
        status = proj_item.get("procurement_status", {})
        proc_name = item_data.get("Item") or item_data.get("item") or "Item"
        quantity = item_data.get("Total Qty", item_data.get("Total_Qty", 0))
        specification = item_data.get("Specification", item_data.get("specification", ""))
        selected_supplier_id = status.get("selected_supplier_id", "")
        selected_supplier_label = ""
        for label, supplier_id in supplier_choices.items():
            if supplier_id == selected_supplier_id:
                selected_supplier_label = label
                break

        row = {
            "Item": proc_name,
            "Qty": quantity,
            "Specification": specification,
            "Selected Supplier": selected_supplier_label,
            "Quoted Unit Price": status.get("quoted_unit_price", 0),
            "Lead Time": status.get("lead_time", ""),
            "Supplier Notes": status.get("supplier_notes", ""),
            "RFP Status": status.get("rfp_status", "not_started"),
            "RFP Notes": status.get("rfp_notes", ""),
        }
        match_map[idx] = {}

        for supplier_label in selected_suppliers:
            supplier_id = supplier_choices.get(supplier_label)
            match = _match_catalog_item(proc_name, catalog_by_supplier.get(supplier_id, []))
            match_map[idx][supplier_id] = match
            if match:
                price_label = match["price"] if match.get("price_available") else "POR"
                row[f"{supplier_label} Price"] = price_label
                row[f"{supplier_label} Match"] = match.get("item_name", "")
                if selected_supplier_id == supplier_id and not row["Quoted Unit Price"] and match.get("price_available"):
                    row["Quoted Unit Price"] = match.get("price", 0)
            else:
                row[f"{supplier_label} Price"] = "No match"
                row[f"{supplier_label} Match"] = ""

        comparison_rows.append(row)

    supplier_signature = "_".join(selected_supplier_ids) or "none"
    rfp_editor_key = f"supplier_cmp_editor_{project_id}_{supplier_signature}"
    rfp_editor_state_key = f"{rfp_editor_key}_rows"
    df = _seed_editor_dataframe(comparison_rows, rfp_editor_state_key)
    st.markdown("### Comparison Table")
    edited_df = st.data_editor(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Selected Supplier": st.column_config.SelectboxColumn("Selected Supplier", options=[""] + selected_suppliers),
            "Quoted Unit Price": st.column_config.NumberColumn("Quoted Unit Price", min_value=0.0, step=1.0),
            "RFP Status": st.column_config.SelectboxColumn(
                "RFP Status",
                options=["not_started", "drafted", "sent", "supplier_review", "quoted", "closed"],
            ),
        },
        key=rfp_editor_key,
    )
    _persist_editor_dataframe(rfp_editor_state_key, edited_df)

    rfp_export_df = build_rfp_export_df(edited_df)
    rfp_filters = {"Selected Suppliers": selected_suppliers}
    rfp_summary_df = build_export_summary_df("Vendor Comparison RFP", project, rfp_filters, rfp_export_df)
    rfp_project_meta = _build_stage1_project_meta(project, rfp_filters)
    rfp_file_stem = build_export_file_stem(project, "hotel_rfp")

    _render_stage1_export_toolbar(
        "Vendor Comparison RFP",
        rfp_file_stem,
        rfp_export_df,
        rfp_summary_df,
        rfp_project_meta,
        pdf_title=page_title,
        pdf_repeat_columns=["Item", "Qty", "Specification", "Selected Supplier", "RFP Status"],
    )

    save_col, send_col = st.columns(2)
    with save_col:
        if st.button("Save Vendor Decisions", use_container_width=True, key="rfp_save_decisions_btn"):
            for row_index, row in edited_df.iterrows():
                chosen_supplier_label = row.get("Selected Supplier", "")
                chosen_supplier_id = supplier_choices.get(chosen_supplier_label, "")
                chosen_supplier = supplier_lookup.get(chosen_supplier_id, {})
                matched = match_map.get(row_index, {}).get(chosen_supplier_id, {}) if chosen_supplier_id else {}
                quoted_unit_price = _safe_float(row.get("Quoted Unit Price", 0))
                if not quoted_unit_price and matched.get("price_available"):
                    quoted_unit_price = _safe_float(matched.get("price", 0))

                status_update = {
                    "selected_supplier_id": chosen_supplier_id,
                    "selected_supplier_name": chosen_supplier.get("name", ""),
                    "supplier": chosen_supplier.get("name", ""),
                    "quoted_unit_price": quoted_unit_price,
                    "lead_time": str(row.get("Lead Time", "")).strip(),
                    "supplier_notes": str(row.get("Supplier Notes", "")).strip(),
                    "rfp_status": str(row.get("RFP Status", "not_started")).strip() or "not_started",
                    "rfp_notes": str(row.get("RFP Notes", "")).strip(),
                }
                db.update_item_status(project_id, row_index, status_update)
                db.add_audit_entry(project_id, row_index, "rfp_selection_updated", get_actor_name(), status_update)
            st.session_state.pop(rfp_editor_state_key, None)
            st.success("Vendor decisions saved.")
            st.rerun()

    selected_items_by_supplier = {}
    for row_index, row in edited_df.iterrows():
        chosen_supplier_label = row.get("Selected Supplier")
        if not chosen_supplier_label:
            continue

        supplier_id = supplier_choices.get(chosen_supplier_label)
        if not supplier_id:
            continue

        match = match_map.get(row_index, {}).get(supplier_id, {})
        qty_value = _safe_float(row.get("Qty", 0))
        quoted_unit_price = _safe_float(row.get("Quoted Unit Price", 0))
        if not quoted_unit_price and match.get("price_available"):
            quoted_unit_price = _safe_float(match.get("price", 0))

        selected_items_by_supplier.setdefault(supplier_id, []).append(
            {
                "item_name": row.get("Item"),
                "quantity": qty_value,
                "specification": row.get("Specification", ""),
                "price": quoted_unit_price,
                "currency": match.get("currency"),
                "price_available": quoted_unit_price > 0,
            }
        )

    if not selected_items_by_supplier:
        st.info("Select suppliers for items to generate the RFP summary.")
        return

    st.markdown("### RFP Summary")
    for supplier_id, items in selected_items_by_supplier.items():
        supplier = supplier_lookup.get(supplier_id, {})
        total_items = len(items)
        total_value = sum((item["price"] or 0) * item["quantity"] for item in items if item.get("price_available"))
        st.write(f"- {supplier.get('name', supplier_id)}: {total_items} items | Estimated: {total_value:,.2f}")

    smtp_config = _get_smtp_config()
    with send_col:
        if st.button("Send RFP Emails", key="rfp_send_btn", use_container_width=True):
            for supplier_id, items in selected_items_by_supplier.items():
                supplier = supplier_lookup.get(supplier_id, {})
                email_content = _compose_rfp_email(project, supplier, items)
                to_email = supplier.get("email")
                if not to_email:
                    st.warning(f"Skipping supplier without email: {supplier.get('name', supplier_id)}")
                    continue

                if smtp_config.get("host"):
                    queue_email_smtp(smtp_config, to_email, email_content["subject"], email_content["body"])
                    st.success(f"Email queued for {supplier.get('name')}")
                else:
                    mailto = f"mailto:{to_email}?subject={quote(email_content['subject'])}&body={quote(email_content['body'])}"
                    st.markdown(f"[Open email draft for {supplier.get('name')}]({mailto})")


def show_ai_assistant():
    """AI Procurement Assistant powered by Gemini."""
    if not is_ai_feature_enabled():
        st.info("Seneca is temporarily disabled.")
        return

    st.markdown('<div class="main-header">Seneca</div>', unsafe_allow_html=True)
    gemini_config = _get_gemini_runtime_config()

    st.markdown("Search SENPRO standards, inspect procurement status, or research live vendor specifications.")

    if not gemini_config.get("api_key"):
        with st.expander("API Key Required", expanded=True):
            st.warning(gemini_config.get("message", "Gemini is not configured."))
            st.code('GEMINI_API_KEY = "..."')
        return

    model_name = gemini_config.get("model", "")
    api_key = gemini_config.get("api_key", "")
    live_grounding_enabled = st.toggle(
        "Web Research Mode",
        value=True,
        help="Use Google Search for live vendor specifications and recent web information. Turn this off to restore SENPRO app actions and navigation tools.",
        key="ai_live_grounding",
    )
    grounding_status = "Web Research On" if live_grounding_enabled else "Internal Actions On"
    st.caption(f"Powered by Gemini • {model_name} • {grounding_status}")
    if live_grounding_enabled:
        st.caption("Web Research Mode uses Google Search only. SENPRO navigation and internal app actions are unavailable until you turn it off.")
    else:
        st.caption("Internal Action Mode uses SENPRO tools for navigation and live app data. Web search is off in this mode.")

    base_system_prompt = build_system_prompt(db, get_scoped_projects)
    catalog_context = _get_master_catalog_context()
    system_prompt = (
        "You are Seneca, the Intelligence Oracle for the SENPRO hotel procurement system. "
        "Your communication style is clear, professional, concise, stoic, and highly analytical. "
        "Do not use fluff or unnecessary pleasantries. Provide clarity and logic.\n\n"
        f"{base_system_prompt}\n\n"
        "If a user asks about internal standards, calculations, or master items, use this catalog:\n"
        f"{catalog_context}\n\n"
        "If a user asks about real-world vendor equipment, specifications, or current market information, "
        "use live grounded web results when available and prefer official manufacturer or vendor sources."
    )
    if live_grounding_enabled:
        system_prompt += (
            "\n\nLive Web Grounding is enabled for this turn. "
            "Do not attempt SENPRO app actions or function calls. "
            "Answer from the internal catalog plus grounded web search only."
        )
    else:
        system_prompt += (
            "\n\nLive Web Grounding is disabled for this turn. "
            "Use SENPRO app tools for navigation and live internal data when needed."
    )

    # Chat history
    if "ai_messages" not in st.session_state:
        st.session_state.ai_messages = [{"role": "assistant", "content": SENECA_GREETING}]

    # Suggested prompts on fresh start
    if len(st.session_state.ai_messages) == 1 and st.session_state.ai_messages[0] == {"role": "assistant", "content": SENECA_GREETING}:
        st.markdown("**Try asking:**")
        cols = st.columns(2)
        for i, suggestion in enumerate(AI_SUGGESTIONS):
            with cols[i % 2]:
                if st.button(suggestion, key=f"ai_sug_{i}", use_container_width=True):
                    st.session_state.ai_messages.append({"role": "user", "content": suggestion})
                    st.rerun()
        st.markdown("---")

    # Render history
    for msg in st.session_state.ai_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    def _run_ai_tool(tool_name: str, tool_input: Dict) -> str:
        """Execute one assistant tool with the current app dependencies."""
        return execute_ai_tool(
            tool_name,
            tool_input,
            db=db,
            session_state=st.session_state,
            get_scoped_projects=get_scoped_projects,
            get_visible_project=get_visible_project,
            normalize_view_mode=_normalize_view_mode,
            set_view_mode=_set_view_mode,
            get_capex_blocks=_get_capex_blocks,
            format_capex_floor_range=_format_capex_floor_range,
            av=av,
        )

    def _extract_gemini_text(response) -> str:
        """Best-effort text extraction from a Gemini SDK response."""
        if getattr(response, "text", None):
            return str(response.text).strip()

        parts = []
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            content = getattr(candidates[0], "content", None)
            for part in getattr(content, "parts", []) or []:
                text = getattr(part, "text", None)
                if text:
                    parts.append(str(text))
        return "".join(parts).strip()

    def _build_gemini_contents(messages: List[Dict]):
        """Translate Streamlit chat history into Gemini content objects."""
        contents = []
        for message in messages:
            role = "user" if message.get("role") == "user" else "model"
            contents.append(
                _google_genai_types.Content(
                    role=role,
                    parts=[_google_genai_types.Part.from_text(text=str(message.get("content", "")))],
                )
            )
        return contents

    def _extract_gemini_grounding_sources(response) -> List[Dict[str, str]]:
        """Collect grounded web sources from Gemini metadata when available."""
        sources = []
        seen_uris = set()
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            return sources

        grounding_metadata = getattr(candidates[0], "grounding_metadata", None)
        for chunk in getattr(grounding_metadata, "grounding_chunks", []) or []:
            web_chunk = getattr(chunk, "web", None)
            uri = getattr(web_chunk, "uri", None)
            if not uri or uri in seen_uris:
                continue
            seen_uris.add(uri)
            sources.append(
                {
                    "title": getattr(web_chunk, "title", "") or getattr(web_chunk, "domain", "") or uri,
                    "uri": uri,
                }
            )
        return sources

    def _run_gemini_turn():
        """Run one Gemini assistant turn with manual tool invocation."""
        client = _google_genai_module.Client(api_key=api_key)
        app_tool = _google_genai_types.Tool(
            function_declarations=[
                _google_genai_types.FunctionDeclaration(
                    name=tool_def["name"],
                    description=tool_def.get("description", ""),
                    parameters_json_schema=tool_def.get("input_schema", {"type": "object", "properties": {}}),
                )
                for tool_def in AI_TOOLS
            ]
        )
        if live_grounding_enabled:
            tools = [_google_genai_types.Tool(google_search=_google_genai_types.GoogleSearch())]
        else:
            tools = [app_tool]
        response_placeholder.markdown("Thinking…")
        contents = _build_gemini_contents(st.session_state.ai_messages)
        tool_actions = []
        navigated = False
        full_response = ""
        grounding_sources = []

        for _ in range(6):
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=_google_genai_types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.2,
                    tools=tools,
                ),
            )

            response_text = _extract_gemini_text(response)
            if response_text:
                full_response = response_text
                response_placeholder.markdown(full_response)
            grounding_sources.extend(_extract_gemini_grounding_sources(response))

            function_calls = list(getattr(response, "function_calls", None) or [])
            if not function_calls:
                if not full_response:
                    full_response = "Sorry, something went wrong."
                    response_placeholder.markdown(full_response)
                break

            candidates = getattr(response, "candidates", None) or []
            model_content = getattr(candidates[0], "content", None) if candidates else None
            if model_content is not None:
                contents.append(model_content)

            tool_response_parts = []
            for function_call in function_calls:
                tool_input = dict(getattr(function_call, "args", {}) or {})
                result = _run_ai_tool(function_call.name, tool_input)
                tool_actions.append((function_call.name, result))
                if function_call.name == "navigate":
                    navigated = True
                tool_response_parts.append(
                    _google_genai_types.Part.from_function_response(
                        name=function_call.name,
                        response={"result": result},
                    )
                )

            contents.append(_google_genai_types.Content(role="tool", parts=tool_response_parts))

        deduped_sources = []
        seen_uris = set()
        for source in grounding_sources:
            uri = source.get("uri", "")
            if not uri or uri in seen_uris:
                continue
            seen_uris.add(uri)
            deduped_sources.append(source)

        return full_response, tool_actions, navigated, deduped_sources

    # Input
    if prompt := st.chat_input("Consult Seneca..."):
        st.session_state.ai_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            full_response = ""
            tool_actions = []
            navigated = False
            grounding_sources = []

            try:
                full_response, tool_actions, navigated, grounding_sources = _run_gemini_turn()

            except Exception as exc:
                error_text = str(exc)
                if isinstance(exc, OSError) or "[Errno 8]" in error_text or "nodename nor servname provided" in error_text.lower():
                    st.error("Network or DNS issue while contacting Gemini. Check internet access, VPN or proxy settings, then restart Streamlit and try again.")
                else:
                    st.error(f"Error: {exc}")
                full_response = full_response or "Sorry, something went wrong."

            if tool_actions:
                with st.expander(f"Actions taken ({len(tool_actions)})", expanded=False):
                    for action_name, action_result in tool_actions:
                        st.markdown(f"**`{action_name}`**")
                        st.text(action_result[:400] + ("…" if len(action_result) > 400 else ""))

            if grounding_sources:
                with st.expander(f"Sources ({len(grounding_sources)})", expanded=False):
                    for source in grounding_sources:
                        st.markdown(f"- [{source['title']}]({source['uri']})")

            st.session_state.ai_messages.append({"role": "assistant", "content": full_response})

            if navigated:
                st.rerun()

    # Clear button
    if len(st.session_state.get("ai_messages", [])) > 1:
        if st.button("Clear Memory", key="ai_clear"):
            st.session_state.ai_messages = [{"role": "assistant", "content": SENECA_GREETING}]
            st.rerun()


# ============================================================================
# NEW PROJECT
# ============================================================================

def show_new_project():
    """Render the new project workflow as a first-class page."""
    accessible_hotels = get_accessible_hotels()
    if not accessible_hotels:
        st.warning("No hotels are assigned to your account yet.")
        if is_admin():
            if st.button("Open Administration", key="open_admin_from_new_project"):
                _set_view_mode("admin_panel")
                _rerun_if_legacy()
        return

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["Basic Info", "Room Configuration", "Facilities", "Conference & Meetings", "Results"]
    )

    with tab1:
        st.markdown('<div class="section-header">Hotel Information</div>', unsafe_allow_html=True)

        selected_hotel = select_accessible_hotel(
            "Assigned Hotel *",
            key="new_project_hotel_select",
            hotels=accessible_hotels,
        )

        if st.session_state.get("new_project_source_hotel_id") != selected_hotel.get("hotel_id"):
            st.session_state.new_project_source_hotel_id = selected_hotel.get("hotel_id")
            st.session_state.new_project_property_name = selected_hotel.get("name", "")
            st.session_state.new_project_city = selected_hotel.get("city", "")
            st.session_state.new_project_country = selected_hotel.get("country", "")

        available_brands = BrandStandards.get_available_brands()
        default_brand = selected_hotel.get("brand") or "Independent"
        if default_brand not in available_brands:
            available_brands = available_brands + [default_brand]

        col1, col2 = st.columns(2)

        with col1:
            hotel_brand = st.selectbox(
                "Hotel Brand *",
                available_brands,
                index=available_brands.index(default_brand),
                key=f"hotel_brand_{selected_hotel['hotel_id']}",
            )
            hotel_type = st.selectbox(
                "Hotel Type *",
                [
                    "City Hotel",
                    "Resort",
                    "Boutique Hotel",
                    "Lifestyle Hotel",
                    "Extended Stay",
                    "Conference Hotel",
                    "Serviced Apartments",
                    "Independent",
                ],
                key="hotel_type",
            )
            property_name = st.text_input(
                "Property Name",
                key="new_project_property_name",
            )
            city = st.text_input(
                "City",
                key="new_project_city",
            )
            country = st.text_input(
                "Country",
                key="new_project_country",
            )

        with col2:
            project_name = st.text_input(
                "Project / CAPEX Name *",
                placeholder="e.g., Pre-Opening Budget 2026",
                key="project_name",
            )
            developer = st.text_input(
                "Prepared By",
                value=get_actor_name(),
                disabled=True,
            )
            total_rooms = st.number_input(
                "Total Number of Rooms *",
                min_value=1,
                max_value=1000,
                value=int(selected_hotel.get("total_rooms", 50) or 50),
                key=f"total_rooms_{selected_hotel['hotel_id']}",
            )
            num_floors = st.number_input(
                "Number of Floors",
                min_value=1,
                max_value=100,
                value=5,
                key="num_floors"
            )

        col1, col2, col3 = st.columns(3)
        with col1:
            num_outlets = st.number_input(
                "F&B Outlets",
                min_value=0,
                max_value=20,
                value=1,
                key="num_outlets"
            )
        with col2:
            num_kitchens = st.number_input(
                "Kitchens",
                min_value=0,
                max_value=10,
                value=1,
                key="num_kitchens"
            )
        with col3:
            num_room_types = st.number_input(
                "How many room types?",
                min_value=1,
                max_value=10,
                value=3,
                key="num_room_types"
            )

        hotel_name = f"{hotel_brand} - {property_name}, {city}"
        num_restaurants = num_outlets

    with tab2:
        st.markdown('<div class="section-header">Room Type Configuration</div>', unsafe_allow_html=True)
        st.info("Define your room categories. The system will calculate all FF&E and OS&E items based on these.")

        room_types = []
        total_configured_rooms = 0

        for i in range(num_room_types):
            st.markdown(f"#### Room Type {i+1}")
            col1, col2, col3, col4, col5 = st.columns(5)

            with col1:
                room_name = st.text_input(
                    "Room Type Name",
                    value="Standard" if i == 0 else f"Type {i+1}",
                    key=f"room_name_{i}"
                )
            with col2:
                room_count = st.number_input(
                    "Number of Rooms",
                    min_value=0,
                    max_value=1000,
                    value=25 if i == 0 else 0,
                    key=f"room_count_{i}"
                )
            with col3:
                bed_type = st.selectbox(
                    "Bed Type",
                    ["King", "Twin", "Queen"],
                    key=f"bed_type_{i}"
                )
            with col4:
                bed_size = st.selectbox(
                    "Bed Size",
                    ["200x200 (King)", "100x200 (Twin - Convertible)"] if bed_type in ["King", "Twin"] else ["200x200", "180x200"],
                    key=f"bed_size_{i}",
                    help="Twin rooms: 100x200 with Zip & Link. King: 200x200 only"
                )
            with col5:
                num_beds = st.number_input(
                    "Beds per Room",
                    min_value=1,
                    max_value=5,
                    value=2 if bed_type == "Twin" else 1,
                    key=f"num_beds_{i}"
                )

            if room_count > 0:
                room_types.append({
                    "name": room_name,
                    "count": room_count,
                    "bed_type": bed_type,
                    "bed_size": bed_size,
                    "num_beds": num_beds
                })
                total_configured_rooms += room_count

        if total_configured_rooms != total_rooms:
            st.warning(f"Room count mismatch: Configured {total_configured_rooms} rooms, but total is {total_rooms}")
        else:
            st.success(f"All {total_rooms} rooms configured correctly")

    with tab3:
        st.markdown('<div class="section-header">Facilities & Amenities</div>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### Wellness & Recreation")
            has_spa = st.checkbox("Spa Facility")
            if has_spa:
                spa_rooms = st.number_input("Number of Treatment Rooms", min_value=1, max_value=50, value=4)
            else:
                spa_rooms = 0

            has_pool = st.checkbox("Swimming Pool")
            if has_pool:
                pool_type = st.selectbox("Pool Type", ["Indoor", "Outdoor", "Both"])
            else:
                pool_type = "None"

            has_gym = st.checkbox("Gym/Fitness Center", value=True)

        with col2:
            st.markdown("#### Business & Events")
            has_business_center = st.checkbox("Business Center", value=True)
            num_back_of_house_areas = st.number_input(
                "Back-of-House Areas",
                min_value=0,
                max_value=50,
                value=3,
                key="num_back_of_house_areas",
            )

        st.markdown("#### Linen Standards")
        col1, col2, col3 = st.columns(3)
        with col1:
            linen_standard = st.selectbox("Linen Quality Standard", ["Economy", "Standard", "Premium", "Luxury"])
        with col2:
            par_level = st.number_input(
                "Par Level (sets per bed)",
                min_value=2,
                max_value=10,
                value=4,
                help="How many complete sets of linen per bed (for rotation)",
            )
        with col3:
            reserve_stock = st.slider(
                "Reserve Stock %",
                min_value=0,
                max_value=50,
                value=10,
                help="Additional backup inventory percentage",
            )

    with tab4:
        conference_plan = _render_conference_planning_section()
        if conference_plan.get("warnings"):
            st.caption(f"Conference planning warnings: {len(conference_plan['warnings'])}")

    with tab5:
        st.markdown('<div class="section-header">Calculation Results</div>', unsafe_allow_html=True)

        col1, col2 = st.columns([3, 1])
        with col1:
            calculate_btn = st.button("Calculate & Save Project", type="primary", use_container_width=True)
        with col2:
            preview_btn = st.button("Preview Only", use_container_width=True)

        if calculate_btn or preview_btn:
            if not property_name or not city or not project_name:
                st.error("Please complete the hotel and project details in Basic Info.")
            elif total_configured_rooms != total_rooms:
                st.error("Please configure all rooms in Room Configuration tab")
            elif conference_plan.get("has_conference_spaces") and conference_plan.get("conference_room_count", 0) <= 0:
                st.error("Add at least one conference or meeting room when conference spaces are present.")
            elif conference_plan.get("has_conference_spaces") and conference_plan.get("errors"):
                st.error("Fix conference room validation errors before calculation.")
            else:
                with st.spinner("Calculating procurement requirements..."):
                    st.session_state.calculation_done = True
                    conference_rooms = conference_plan.get("conference_rooms", [])
                    num_conference = len(conference_rooms) if conference_plan.get("has_conference_spaces") else 0

                    config = {
                        'hotel_id': selected_hotel['hotel_id'],
                        'hotel_name': hotel_name,
                        'hotel_brand': hotel_brand,
                        'hotel_type': hotel_type,
                        'property_name': property_name,
                        'city': city,
                        'country': country,
                        'project_name': project_name,
                        'developer': developer,
                        'created_by': get_actor_name(),
                        'room_types': room_types,
                        'total_rooms': total_rooms,
                        'num_floors': num_floors,
                        'par_level': par_level,
                        'reserve_stock': reserve_stock,
                        'has_spa': has_spa,
                        'spa_rooms': spa_rooms,
                        'has_pool': has_pool,
                        'pool_type': pool_type,
                        'has_gym': has_gym,
                        'num_restaurants': num_restaurants,
                        'num_outlets': num_outlets,
                        'num_kitchens': num_kitchens,
                        'num_back_of_house_areas': num_back_of_house_areas,
                        'has_conference_spaces': conference_plan.get("has_conference_spaces", False),
                        'conference_rooms': conference_rooms,
                        'num_conference': num_conference,
                        'linen_standard': linen_standard,
                        'has_business_center': has_business_center
                    }

                    calculator = ProcurementCalculator(config)
                    results = calculator.calculate_all()
                    st.session_state.results = results

                    if calculate_btn:
                        project_id = db.save_project(config, results)
                        st.session_state.current_project_id = project_id
                        st.success(f"Project saved successfully! ID: {project_id}")
                    else:
                        st.info("Preview mode - Project not saved")

                    st.rerun()

        if st.session_state.calculation_done:
            output_mode = st.radio(
                "Output Mode",
                ["Procurement List", "Supplier Comparison"],
                horizontal=True,
                key="results_output_mode",
            )
            if output_mode == "Supplier Comparison":
                show_supplier_comparison()
            else:
                display_results()


# ============================================================================
# MAIN ROUTING
# ============================================================================

_VIEW_HANDLERS = {
    "corporate_home": show_corporate_home,
    "project_workspace": show_project_workspace,
    "finance_workspace": show_finance_workspace,
    "directories_workspace": show_directories_workspace,
    "hotel_directory": show_hotel_directory,
    "hotel_details": show_hotel_details,
    "hotel_item_list": show_hotel_item_list,
    "hotel_rfp": show_hotel_rfp,
    "vendor_directory": show_vendor_directory,
    "portfolio_dashboard": show_portfolio_dashboard,
    "new_project": show_new_project,
    "p2p_dashboard": show_p2p_dashboard,
    "po_center": show_po_center,
    "invoice_center": show_invoice_center,
    "payment_center": show_payment_center,
    "capex_dashboard": show_capex_dashboard,
    "history": show_project_history,
    "comparison": show_project_comparison,
    "supplier_portal": show_supplier_portal,
    "ai_assistant": show_ai_assistant,
    "account_settings": show_account_settings,
    "admin_panel": show_admin_panel,
}


def render_navigation_page(view_mode: str, page_renderer) -> None:
    """Render one page through the new multipage router."""
    st.session_state.view_mode = _normalize_view_mode(view_mode)
    render_page_banner(view_mode)
    page_renderer()


def render_current_view() -> None:
    """Legacy string-based router preserved for backward compatibility."""
    st.session_state.view_mode = _normalize_view_mode(st.session_state.get("view_mode", "corporate_home"))
    current_view_mode = st.session_state.view_mode

    if current_view_mode == "ai_assistant" and not is_ai_feature_enabled():
        _set_view_mode("corporate_home")
        _rerun_if_legacy()
        return

    if current_view_mode in _VIEW_HANDLERS:
        _VIEW_HANDLERS[current_view_mode]()
        return

    _set_view_mode("new_project")
    _rerun_if_legacy()


def render_footer() -> None:
    """Shared footer text."""
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #000000;'>
        <p>SENPRO POWERED BY SENECA</p>
    </div>
    """, unsafe_allow_html=True)


def run_legacy_app() -> None:
    """Run the original single-file application flow."""
    st.set_page_config(
        page_title="SENPRO",
        page_icon="📋",
        layout="wide"
    )
    initialize_app_runtime()
    st.session_state[_MULTIPAGE_NAVIGATION_FLAG] = False
    enforce_authenticated_app_access()
    render_page_banner(st.session_state.get("view_mode", "corporate_home"))
    render_shared_sidebar()
    render_current_view()
    render_footer()


if __name__ == "__main__":
    run_legacy_app()
