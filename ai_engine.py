from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, Sequence


AI_TOOLS = [
    {
        "name": "navigate",
        "description": "Navigate to a specific section of the procurement app",
        "input_schema": {
            "type": "object",
            "properties": {
                "view": {
                    "type": "string",
                    "enum": [
                        "corporate_home",
                        "hotel_directory",
                        "hotel_details",
                        "hotel_item_list",
                        "hotel_rfp",
                        "vendor_directory",
                        "portfolio_dashboard",
                        "new_project",
                        "history",
                        "p2p_dashboard",
                        "po_center",
                        "invoice_center",
                        "payment_center",
                        "capex_dashboard",
                        "comparison",
                        "supplier_portal",
                        "account_settings",
                        "admin_panel",
                    ],
                    "description": "The section to navigate to",
                }
            },
            "required": ["view"],
        },
    },
    {
        "name": "get_projects",
        "description": "Get list of all saved hotel procurement projects",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_procurement_summary",
        "description": "Get detailed procurement status for a project",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "Project ID to summarize, or 'latest' for most recent",
                }
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "get_pending_items",
        "description": "Get procurement items not yet ordered, grouped by department",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID or 'latest'"},
                "department": {"type": "string", "description": "Optional department filter"},
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "get_suppliers",
        "description": "Get list of all registered suppliers with categories",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_capex_summary",
        "description": "Get CAPEX summary for the hotel",
        "input_schema": {"type": "object", "properties": {}},
    },
]


AI_SUGGESTIONS = [
    "What's the procurement status of the latest project?",
    "Show me all pending items",
    "List all suppliers",
    "Take me to Procurement",
    "Summarize CAPEX",
    "What's pending in Housekeeping?",
]


def resolve_project_id(project_id: str, get_scoped_projects: Callable[..., Sequence[Dict]]) -> str | None:
    """Resolve 'latest' to an actual project ID."""
    if project_id == "latest":
        projects = get_scoped_projects(ignore_hotel_scope=True)
        if not projects:
            return None
        return projects[-1]["project_id"]
    return project_id


def build_system_prompt(db, get_scoped_projects: Callable[..., Sequence[Dict]]) -> str:
    """Build the live system prompt for the procurement assistant."""
    projects = get_scoped_projects(ignore_hotel_scope=True)
    suppliers = db.get_all_suppliers()
    context = ""
    if projects:
        latest = projects[-1]
        summary = db.get_procurement_summary(latest["project_id"])
        context = (
            f"Active projects: {len(projects)} total. "
            f"Latest: {latest['hotel_info']['property_name']} (ID: {latest['project_id']}) — "
            f"{latest['hotel_info']['total_rooms']} rooms, {latest['hotel_info']['brand']}, {latest['hotel_info']['city']}. "
            f"Procurement: {summary['total_items']} items total, "
            f"{summary['total_items'] - summary['ordered_count']} pending. "
            f"Suppliers registered: {len(suppliers)}."
        )

    return (
        "You are an AI procurement assistant for a hotel management system. "
        "You help procurement managers check status, find pending items, navigate the app, and get summaries. "
        "Always use tools to fetch real data — never guess. Be concise and action-oriented. "
        f"Current context: {context} "
        f"Today: {datetime.now().strftime('%Y-%m-%d')}."
    )


def execute_ai_tool(
    tool_name: str,
    tool_input: dict,
    *,
    db,
    session_state,
    get_scoped_projects: Callable[..., Sequence[Dict]],
    get_visible_project: Callable[[str], Dict],
    normalize_view_mode: Callable[[str], str],
    set_view_mode: Callable[[str], None] | None,
    get_capex_blocks: Callable[[Dict], Sequence[str]],
    format_capex_floor_range: Callable[[Sequence[int]], str],
    av: Any,
) -> str:
    """Execute one assistant tool call with injected app dependencies."""
    if tool_name == "navigate":
        view = normalize_view_mode(tool_input.get("view", "corporate_home"))
        labels = {
            "corporate_home": "Corporate Home",
            "hotel_directory": "HOTEL",
            "hotel_details": "HOTEL DETAILS",
            "hotel_item_list": "Procurement",
            "hotel_rfp": "RFP",
            "vendor_directory": "Vendor Supplier List",
            "portfolio_dashboard": "Portfolio Dashboard",
            "new_project": "New Project",
            "history": "Project History",
            "p2p_dashboard": "P2P Dashboard",
            "po_center": "PO Center",
            "invoice_center": "Invoice Center",
            "payment_center": "Payment Center",
            "capex_dashboard": "CAPEX Dashboard",
            "comparison": "Comparison",
            "supplier_portal": "SENPROVEN",
            "account_settings": "Account Settings",
            "admin_panel": "Administration",
        }
        if set_view_mode is not None:
            set_view_mode(view)
        else:
            session_state.view_mode = view
        return f"Navigated to {labels.get(view, view)}"

    if tool_name == "get_projects":
        projects = get_scoped_projects(ignore_hotel_scope=True)
        if not projects:
            return "No projects found."
        return "\n".join(
            [
                (
                    f"- ID: {project['project_id']} | "
                    f"{project['hotel_info']['property_name']} ({project['hotel_info']['brand']}) | "
                    f"{project['hotel_info']['city']} | "
                    f"{project['hotel_info']['total_rooms']} rooms | "
                    f"Created: {project['created_at'][:10]}"
                )
                for project in projects
            ]
        )

    if tool_name == "get_procurement_summary":
        project_id = resolve_project_id(tool_input.get("project_id", "latest"), get_scoped_projects)
        if not project_id:
            return "No projects found."
        project = get_visible_project(project_id)
        if not project:
            return f"Project {project_id} not found or not accessible."
        summary = db.get_procurement_summary(project_id)
        info = project["hotel_info"]
        return (
            f"Project: {info['property_name']} ({project_id})\n"
            f"Brand: {info['brand']} | City: {info['city']} | Rooms: {info['total_rooms']}\n"
            f"Total Items: {summary['total_items']}\n"
            f"Ordered:   {summary['ordered_count']} ({summary['ordered_percent']}%)\n"
            f"Received:  {summary['received_count']} ({summary['received_percent']}%)\n"
            f"Installed: {summary['installed_count']} ({summary['installed_percent']}%)\n"
            f"Pending:   {summary['total_items'] - summary['ordered_count']} items not yet ordered"
        )

    if tool_name == "get_pending_items":
        project_id = resolve_project_id(tool_input.get("project_id", "latest"), get_scoped_projects)
        if not project_id:
            return "No projects found."
        project = get_visible_project(project_id)
        if not project:
            return f"Project {project_id} not found or not accessible."
        items = db.get_project_items(project_id)
        pending = [item for item in items if not item["procurement_status"]["ordered"]]
        department_filter = tool_input.get("department", "")
        if department_filter:
            pending = [
                item
                for item in pending
                if department_filter.lower() in item["department"].lower()
            ]
        if not pending:
            return "No pending items found."
        by_department: Dict[str, list[str]] = {}
        for item in pending:
            department = item["department"]
            by_department.setdefault(department, [])
            by_department[department].append(
                item["item_data"].get("Item", item["item_data"].get("item", "Unknown"))
            )
        lines = [f"Total pending: {len(pending)} items\n"]
        for department, department_items in sorted(by_department.items()):
            lines.append(f"{department} ({len(department_items)} items):")
            for name in department_items[:5]:
                lines.append(f"  - {name}")
            if len(department_items) > 5:
                lines.append(f"  ... and {len(department_items) - 5} more")
        return "\n".join(lines)

    if tool_name == "get_suppliers":
        suppliers = db.get_all_suppliers()
        if not suppliers:
            return "No suppliers registered yet."
        return "\n".join(
            [
                f"- {supplier['name']} | {supplier.get('email', 'N/A')} | Categories: {', '.join(supplier.get('categories', [])) or 'N/A'}"
                for supplier in suppliers
            ]
        )

    if tool_name == "get_capex_summary":
        if av is None:
            return "CAPEX loader not available."
        data = session_state.get("av_data") or av.load_data()
        if not session_state.get("av_data"):
            session_state.av_data = data
        totals = av.get_grand_totals(data)
        block_lines = []
        for block_name in get_capex_blocks(data):
            block_summary = av.get_block_summary(data, block_name)
            block_lines.append(
                f"Block {block_name} ({format_capex_floor_range(av.get_block_floors(block_name))}): "
                f"{block_summary['rooms']} rooms | {block_summary['items']} items | ${block_summary['cost']:,.0f}"
            )
        summary = (
            f"Hotel CAPEX Summary\n"
            f"Total Rooms: {totals['total_rooms']}\n"
            f"Room Furniture Items: {totals['room_furniture_items']}\n"
            f"Common Area Items:    {totals['common_area_items']}\n"
            f"Grand Total Items:    {totals['grand_total_items']}\n"
            f"Grand Total Cost:     ${totals['grand_total_cost']:,.0f}"
        )
        if block_lines:
            summary += "\n" + "\n".join(block_lines)
        return summary

    return f"Unknown tool: {tool_name}"
