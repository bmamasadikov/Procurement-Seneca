from __future__ import annotations

import json
import os
from typing import Dict, List


FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
SHEET_MIME_TYPE = "application/vnd.google-apps.spreadsheet"


class GoogleWorkspaceError(RuntimeError):
    """Raised when Google Workspace automation cannot proceed."""


class GoogleWorkspaceService:
    """Manage Google Drive folders and Sheets used by Stage 1 workflows."""

    def __init__(
        self,
        service_account_json: str = "",
        shared_drive_id: str = "",
        root_folder_id: str = "",
        enabled: bool = True,
        drive_service=None,
        sheets_service=None,
    ):
        self.enabled = enabled
        self.service_account_json = service_account_json or ""
        self.shared_drive_id = shared_drive_id or ""
        self.root_folder_id = root_folder_id or ""
        self.drive_service = drive_service
        self.sheets_service = sheets_service

        if self.enabled and (self.drive_service is None or self.sheets_service is None):
            self.drive_service, self.sheets_service = self._build_services()

    @classmethod
    def from_environment(cls) -> "GoogleWorkspaceService":
        """Build a service from process environment."""
        return cls(
            service_account_json=os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", ""),
            shared_drive_id=os.environ.get("GOOGLE_SHARED_DRIVE_ID", ""),
            root_folder_id=os.environ.get("GOOGLE_DRIVE_ROOT_FOLDER_ID", ""),
            enabled=os.environ.get("GOOGLE_WORKSPACE_ENABLED", "true").strip().lower() not in {"0", "false", "no"},
        )

    def is_configured(self) -> bool:
        """Whether Google Workspace is configured enough to run."""
        return bool(self.enabled and self.service_account_json and self.root_folder_id)

    def _build_services(self):
        """Create Google API clients when the required packages are installed."""
        if not self.is_configured():
            raise GoogleWorkspaceError(
                "Google Workspace is not configured. Set GOOGLE_WORKSPACE_ENABLED, "
                "GOOGLE_SERVICE_ACCOUNT_JSON and GOOGLE_DRIVE_ROOT_FOLDER_ID. "
                "GOOGLE_SHARED_DRIVE_ID is optional and only required for Shared Drive mode."
            )

        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise GoogleWorkspaceError(
                "Google Workspace dependencies are missing. Install google-api-python-client and google-auth."
            ) from exc

        service_account_info = self._load_service_account_info(self.service_account_json)
        scopes = [
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/spreadsheets",
        ]
        credentials = service_account.Credentials.from_service_account_info(service_account_info, scopes=scopes)
        drive_service = build("drive", "v3", credentials=credentials, cache_discovery=False)
        sheets_service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
        return drive_service, sheets_service

    def _load_service_account_info(self, raw_value: str) -> Dict:
        """Accept either raw JSON content or a path to the service account file."""
        raw_value = (raw_value or "").strip()
        if not raw_value:
            raise GoogleWorkspaceError("GOOGLE_SERVICE_ACCOUNT_JSON is empty.")

        if raw_value.startswith("{"):
            return json.loads(raw_value)
        if os.path.exists(raw_value):
            with open(raw_value, "r", encoding="utf-8") as handle:
                return json.load(handle)
        raise GoogleWorkspaceError("GOOGLE_SERVICE_ACCOUNT_JSON must be raw JSON or a readable file path.")

    def _escape_drive_query_value(self, value: str) -> str:
        return (value or "").replace("\\", "\\\\").replace("'", "\\'")

    def _ensure_ready(self) -> None:
        if self.drive_service is None or self.sheets_service is None:
            raise GoogleWorkspaceError("Google Workspace services are not initialized.")

    def _drive_files(self):
        self._ensure_ready()
        return self.drive_service.files()

    def _sheet_values(self):
        self._ensure_ready()
        return self.sheets_service.spreadsheets().values()

    def _drive_list_kwargs(self) -> Dict:
        kwargs = {
            "spaces": "drive",
            "includeItemsFromAllDrives": True,
            "supportsAllDrives": True,
            "fields": "files(id, name, webViewLink, parents)",
            "pageSize": 1,
        }
        if self.shared_drive_id:
            kwargs["corpora"] = "drive"
            kwargs["driveId"] = self.shared_drive_id
        return kwargs

    def _find_child(self, parent_id: str, name: str, mime_type: str) -> Dict:
        """Return the first matching Drive item inside one parent folder."""
        query = (
            f"'{self._escape_drive_query_value(parent_id)}' in parents and "
            f"name = '{self._escape_drive_query_value(name)}' and "
            f"mimeType = '{mime_type}' and trashed = false"
        )
        response = self._drive_files().list(q=query, **self._drive_list_kwargs()).execute()
        return (response.get("files") or [{}])[0]

    def _get_drive_item(self, file_id: str) -> Dict:
        """Return one Drive item by id."""
        return self._drive_files().get(
            fileId=file_id,
            fields="id, name, webViewLink, parents",
            supportsAllDrives=True,
        ).execute()

    def _ensure_folder(self, parent_id: str, name: str) -> Dict:
        """Return one folder, creating it if needed."""
        existing = self._find_child(parent_id, name, FOLDER_MIME_TYPE)
        if existing.get("id"):
            return {
                "id": existing["id"],
                "url": existing.get("webViewLink", ""),
            }

        created = self._drive_files().create(
            body={
                "name": name,
                "mimeType": FOLDER_MIME_TYPE,
                "parents": [parent_id],
            },
            fields="id, webViewLink",
            supportsAllDrives=True,
        ).execute()
        return {
            "id": created.get("id", ""),
            "url": created.get("webViewLink", ""),
        }

    def _ensure_spreadsheet(self, parent_id: str, title: str, worksheet_title: str) -> Dict:
        """Return one spreadsheet file in a folder, creating it if needed."""
        existing = self._find_child(parent_id, title, SHEET_MIME_TYPE)
        if existing.get("id"):
            return {
                "id": existing["id"],
                "url": existing.get("webViewLink", f"https://docs.google.com/spreadsheets/d/{existing['id']}"),
                "worksheet_title": worksheet_title,
            }

        created = self.sheets_service.spreadsheets().create(
            body={
                "properties": {"title": title},
                "sheets": [{"properties": {"title": worksheet_title}}],
            },
            fields="spreadsheetId,spreadsheetUrl",
        ).execute()
        spreadsheet_id = created.get("spreadsheetId", "")
        self._move_file_to_parent(spreadsheet_id, parent_id)
        return {
            "id": spreadsheet_id,
            "url": created.get("spreadsheetUrl", f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"),
            "worksheet_title": worksheet_title,
        }

    def _move_file_to_parent(self, file_id: str, parent_id: str) -> None:
        """Move a newly created Google Sheet into the managed project folder."""
        file_metadata = self._drive_files().get(
            fileId=file_id,
            fields="parents",
            supportsAllDrives=True,
        ).execute()
        current_parents = ",".join(file_metadata.get("parents", []))
        self._drive_files().update(
            fileId=file_id,
            addParents=parent_id,
            removeParents=current_parents or None,
            fields="id, parents",
            supportsAllDrives=True,
        ).execute()

    def _write_sheet(self, spreadsheet_id: str, worksheet_title: str, rows: List[List]) -> None:
        """Replace the worksheet contents with a header row plus data rows."""
        sheet_range = f"{worksheet_title}!A:ZZ"
        self._sheet_values().clear(
            spreadsheetId=spreadsheet_id,
            range=sheet_range,
        ).execute()
        self._sheet_values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{worksheet_title}!A1",
            valueInputOption="USER_ENTERED",
            body={"values": rows},
        ).execute()

    def _read_sheet(self, spreadsheet_id: str, worksheet_title: str) -> List[Dict]:
        """Return the sheet rows as dictionaries keyed by header."""
        response = self._sheet_values().get(
            spreadsheetId=spreadsheet_id,
            range=f"{worksheet_title}!A:ZZ",
        ).execute()
        values = response.get("values", [])
        if not values:
            return []

        headers = [str(header).strip() for header in values[0]]
        rows = []
        for row_index, raw_row in enumerate(values[1:], start=2):
            row = {header: raw_row[idx] if idx < len(raw_row) else "" for idx, header in enumerate(headers)}
            row["_row_number"] = row_index
            rows.append(row)
        return rows

    def _ensure_senpro_root(self) -> Dict:
        root_item = self._get_drive_item(self.root_folder_id)
        if root_item.get("name") == "SENPRO":
            return {
                "id": root_item.get("id", self.root_folder_id),
                "url": root_item.get("webViewLink", ""),
            }
        return self._ensure_folder(self.root_folder_id, "SENPRO")

    def ensure_hotel_workspace(self, hotel: Dict) -> Dict:
        """Ensure the shared-drive folder structure exists for one hotel."""
        senpro_root = self._ensure_senpro_root()
        hotels_root = self._ensure_folder(senpro_root["id"], "Hotels")
        hotel_folder = self._ensure_folder(hotels_root["id"], hotel.get("name", "Unnamed Hotel"))
        master_folder = self._ensure_folder(hotel_folder["id"], "Master")
        projects_folder = self._ensure_folder(hotel_folder["id"], "Projects")
        return {
            "hotel_folder_id": hotel_folder["id"],
            "hotel_folder_url": hotel_folder["url"],
            "master_folder_id": master_folder["id"],
            "master_folder_url": master_folder["url"],
            "projects_folder_id": projects_folder["id"],
            "projects_folder_url": projects_folder["url"],
        }

    def ensure_supplier_workspace(self, supplier: Dict) -> Dict:
        """Ensure the shared-drive folder structure exists for one supplier."""
        senpro_root = self._ensure_senpro_root()
        suppliers_root = self._ensure_folder(senpro_root["id"], "Suppliers")
        supplier_folder = self._ensure_folder(suppliers_root["id"], supplier.get("name", "Unnamed Supplier"))
        return {
            "supplier_folder_id": supplier_folder["id"],
            "supplier_folder_url": supplier_folder["url"],
        }

    def ensure_project_workspace(self, project: Dict) -> Dict:
        """Ensure the hotel/project folder structure and managed spreadsheets exist."""
        hotel_workspace = self.ensure_hotel_workspace(
            {
                "hotel_id": project.get("hotel_id", ""),
                "name": project.get("hotel_info", {}).get("property_name", "Unnamed Hotel"),
            }
        )
        project_name = project.get("hotel_info", {}).get("project_name") or project.get("hotel_info", {}).get("property_name", "Project")
        project_folder_name = f"{project.get('project_id', '')} - {project_name}"
        project_folder = self._ensure_folder(hotel_workspace["projects_folder_id"], project_folder_name)
        procurement_sheet = self._ensure_spreadsheet(project_folder["id"], "Procurement List", "Procurement List")
        rfp_sheet = self._ensure_spreadsheet(project_folder["id"], "Vendor Comparison RFP", "Vendor Comparison RFP")
        return {
            **hotel_workspace,
            "project_folder_id": project_folder["id"],
            "project_folder_url": project_folder["url"],
            "procurement_sheet_id": procurement_sheet["id"],
            "procurement_sheet_url": procurement_sheet["url"],
            "rfp_sheet_id": rfp_sheet["id"],
            "rfp_sheet_url": rfp_sheet["url"],
        }

    def _procurement_headers(self) -> List[str]:
        return [
            "row_key",
            "project_id",
            "item_index",
            "item_name",
            "department",
            "category",
            "specification",
            "base_quantity",
            "unit",
            "review_status",
            "selected_supplier_id",
            "Selected Supplier",
            "PO Number",
            "Unit Price",
            "Ordered Qty",
            "Received Qty",
            "Notes",
            "ordered",
            "received",
            "installed",
            "Total Price",
            "last_updated",
            "last_sheet_pull_at",
            "last_sheet_push_at",
        ]

    def _rfp_headers(self) -> List[str]:
        return [
            "row_key",
            "project_id",
            "item_index",
            "item_name",
            "department",
            "category",
            "specification",
            "base_quantity",
            "unit",
            "review_status",
            "selected_supplier_id",
            "Selected Supplier",
            "Quoted Unit Price",
            "Lead Time",
            "Supplier Notes",
            "RFP Status",
            "RFP Notes",
            "last_updated",
            "last_sheet_pull_at",
            "last_sheet_push_at",
        ]

    def _procurement_rows(self, project: Dict, items: List[Dict]) -> List[List]:
        rows = [self._procurement_headers()]
        for index, item in enumerate(items):
            item_data = item.get("item_data", {})
            status = item.get("procurement_status", {})
            rows.append(
                [
                    status.get("google_row_key", f"{project.get('project_id', '')}:{index}"),
                    project.get("project_id", ""),
                    index,
                    item_data.get("Item", item_data.get("item", "")),
                    item.get("department", ""),
                    item.get("category", ""),
                    item_data.get("Specification", item_data.get("specification", "")),
                    item_data.get("Total Qty", item_data.get("Total_Qty", 0)),
                    item_data.get("Unit", "pcs"),
                    status.get("review_status", "open"),
                    status.get("selected_supplier_id", ""),
                    status.get("selected_supplier_name", status.get("supplier", "")),
                    status.get("po_number", ""),
                    status.get("unit_price", 0),
                    status.get("ordered_qty", 0),
                    status.get("received_qty", 0),
                    status.get("notes", ""),
                    status.get("ordered", False),
                    status.get("received", False),
                    status.get("installed", False),
                    status.get("total_price", 0),
                    status.get("last_updated", ""),
                    status.get("last_sheet_pull_at", ""),
                    status.get("last_sheet_push_at", ""),
                ]
            )
        return rows

    def _rfp_rows(self, project: Dict, items: List[Dict]) -> List[List]:
        rows = [self._rfp_headers()]
        for index, item in enumerate(items):
            item_data = item.get("item_data", {})
            status = item.get("procurement_status", {})
            rows.append(
                [
                    status.get("google_row_key", f"{project.get('project_id', '')}:{index}"),
                    project.get("project_id", ""),
                    index,
                    item_data.get("Item", item_data.get("item", "")),
                    item.get("department", ""),
                    item.get("category", ""),
                    item_data.get("Specification", item_data.get("specification", "")),
                    item_data.get("Total Qty", item_data.get("Total_Qty", 0)),
                    item_data.get("Unit", "pcs"),
                    status.get("review_status", "open"),
                    status.get("selected_supplier_id", ""),
                    status.get("selected_supplier_name", status.get("supplier", "")),
                    status.get("quoted_unit_price", 0),
                    status.get("lead_time", ""),
                    status.get("supplier_notes", ""),
                    status.get("rfp_status", "not_started"),
                    status.get("rfp_notes", ""),
                    status.get("last_updated", ""),
                    status.get("last_sheet_pull_at", ""),
                    status.get("last_sheet_push_at", ""),
                ]
            )
        return rows

    def push_procurement_sheet(self, project: Dict, items: List[Dict]) -> Dict:
        """Write the current procurement state into the managed procurement sheet."""
        workspace_links = self.ensure_project_workspace(project)
        self._write_sheet(
            workspace_links["procurement_sheet_id"],
            "Procurement List",
            self._procurement_rows(project, items),
        )
        return workspace_links

    def pull_procurement_sheet(self, project: Dict) -> Dict:
        """Read the managed procurement sheet back into the app."""
        workspace_links = self.ensure_project_workspace(project)
        return {
            "workspace_links": workspace_links,
            "rows": self._read_sheet(workspace_links["procurement_sheet_id"], "Procurement List"),
        }

    def push_rfp_sheet(self, project: Dict, items: List[Dict]) -> Dict:
        """Write the vendor assignment and RFP state into the managed sheet."""
        workspace_links = self.ensure_project_workspace(project)
        self._write_sheet(
            workspace_links["rfp_sheet_id"],
            "Vendor Comparison RFP",
            self._rfp_rows(project, items),
        )
        return workspace_links

    def pull_rfp_sheet(self, project: Dict) -> Dict:
        """Read the managed RFP sheet back into the app."""
        workspace_links = self.ensure_project_workspace(project)
        return {
            "workspace_links": workspace_links,
            "rows": self._read_sheet(workspace_links["rfp_sheet_id"], "Vendor Comparison RFP"),
        }
