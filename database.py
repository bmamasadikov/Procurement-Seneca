"""
Database module for storing project history and procurement tracking
"""
import json
import os
import hashlib
import hmac
from datetime import datetime
from typing import Dict, List, Any
import pandas as pd


WORKSPACE_LINK_TEMPLATE = {
    'hotel_folder_id': '',
    'hotel_folder_url': '',
    'master_folder_id': '',
    'master_folder_url': '',
    'projects_folder_id': '',
    'projects_folder_url': '',
    'supplier_folder_id': '',
    'supplier_folder_url': '',
    'project_folder_id': '',
    'project_folder_url': '',
    'procurement_sheet_id': '',
    'procurement_sheet_url': '',
    'rfp_sheet_id': '',
    'rfp_sheet_url': '',
}


class ProcurementDatabase:
    """Simple JSON-based database for procurement projects"""

    def __init__(self, db_path='procurement_data'):
        self.db_path = db_path
        self.hotels_file = os.path.join(db_path, 'hotels.json')
        self.users_file = os.path.join(db_path, 'users.json')
        self.login_audit_file = os.path.join(db_path, 'login_audit.json')
        self.notifications_file = os.path.join(db_path, 'notifications.json')
        self.projects_file = os.path.join(db_path, 'projects.json')
        self.items_file = os.path.join(db_path, 'procurement_items.json')
        self.suppliers_file = os.path.join(db_path, 'suppliers.json')
        self.catalogs_file = os.path.join(db_path, 'supplier_catalogs.json')
        self.purchase_orders_file = os.path.join(db_path, 'purchase_orders.json')
        self.invoices_file = os.path.join(db_path, 'invoices.json')
        self.payments_file = os.path.join(db_path, 'payments.json')
        self._ensure_db_exists()

    def _ensure_db_exists(self):
        """Create database directory and files if they don't exist"""
        if not os.path.exists(self.db_path):
            os.makedirs(self.db_path)

        if not os.path.exists(self.hotels_file):
            self._write_json(self.hotels_file, {})

        if not os.path.exists(self.users_file):
            self._write_json(self.users_file, {})

        if not os.path.exists(self.login_audit_file):
            self._write_json(self.login_audit_file, [])

        if not os.path.exists(self.notifications_file):
            self._write_json(self.notifications_file, {})

        if not os.path.exists(self.projects_file):
            self._write_json(self.projects_file, {})

        if not os.path.exists(self.items_file):
            self._write_json(self.items_file, {})

        if not os.path.exists(self.suppliers_file):
            self._write_json(self.suppliers_file, {})

        if not os.path.exists(self.catalogs_file):
            self._write_json(self.catalogs_file, {})

        if not os.path.exists(self.purchase_orders_file):
            self._write_json(self.purchase_orders_file, {})

        if not os.path.exists(self.invoices_file):
            self._write_json(self.invoices_file, {})

        if not os.path.exists(self.payments_file):
            self._write_json(self.payments_file, {})

    def _read_json(self, file_path):
        """Read JSON file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return {}

    def _write_json(self, file_path, data):
        """Write JSON file"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error writing {file_path}: {e}")

    def _generate_id(self, prefix: str) -> str:
        """Generate a reasonably collision-resistant identifier."""
        return f"{prefix}{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

    def _normalize_username(self, username: str) -> str:
        """Normalize username values for comparison and login."""
        return (username or '').strip().lower()

    def _hash_password(self, password: str, salt: str = None) -> str:
        """Hash a password with PBKDF2-HMAC-SHA256."""
        if not password:
            raise ValueError("Password cannot be empty.")
        salt = salt or os.urandom(16).hex()
        digest = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            bytes.fromhex(salt),
            200000,
        ).hex()
        return f"{salt}${digest}"

    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a password against a stored hash."""
        if not password or not password_hash or '$' not in password_hash:
            return False
        salt, expected = password_hash.split('$', 1)
        actual = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            bytes.fromhex(salt),
            200000,
        ).hex()
        return hmac.compare_digest(actual, expected)

    def _sanitize_user(self, user: Dict) -> Dict:
        """Remove sensitive fields before returning user data."""
        if not user:
            return {}
        sanitized = dict(user)
        sanitized.pop('password_hash', None)
        return sanitized

    def _normalize_workspace_links(self, workspace_links: Dict | None = None) -> Dict:
        """Return a stable workspace link payload for hotels, suppliers, and projects."""
        normalized = dict(WORKSPACE_LINK_TEMPLATE)
        if isinstance(workspace_links, dict):
            for key, value in workspace_links.items():
                normalized[key] = value or ''
        return normalized

    def _build_google_row_key(self, project_id: str, item_index: int | None) -> str:
        """Stable row identifier used for Google Sheet round-trips."""
        if not project_id or item_index is None:
            return ''
        return f'{project_id}:{item_index}'

    def _default_installation_specs(self, item_name: str = '') -> Dict:
        """Default installation fields for one procurement item."""
        return {
            'height_cm': self._get_default_height(item_name),
            'distance_from_floor': '',
            'distance_from_fixture': '',
            'installation_notes': '',
            'installer_assigned': '',
            'installation_photo': '',
        }

    def _default_procurement_status(self, item_name: str = '', project_id: str = '', item_index: int | None = None) -> Dict:
        """Default operational state for one procurement item."""
        return {
            'ordered': False,
            'ordered_date': None,
            'ordered_qty': 0,
            'received': False,
            'received_date': None,
            'received_qty': 0,
            'installed': False,
            'installed_date': None,
            'supplier': '',
            'selected_supplier_id': '',
            'selected_supplier_name': '',
            'po_number': '',
            'unit_price': 0,
            'quoted_unit_price': 0,
            'lead_time': '',
            'supplier_notes': '',
            'rfp_status': 'not_started',
            'rfp_notes': '',
            'total_price': 0,
            'notes': '',
            'review_status': 'open',
            'correction_note': '',
            'reviewed_by': '',
            'reviewed_at': None,
            'corrected_by': '',
            'corrected_at': None,
            'google_row_key': self._build_google_row_key(project_id, item_index),
            'last_sheet_pull_at': None,
            'last_sheet_push_at': None,
            'last_updated': None,
            'installation_specs': self._default_installation_specs(item_name),
        }

    def _normalize_procurement_status(
        self,
        procurement_status: Dict | None,
        item_name: str = '',
        project_id: str = '',
        item_index: int | None = None,
    ) -> Dict:
        """Merge existing status data with the Stage 1 defaults."""
        normalized = self._default_procurement_status(item_name, project_id, item_index)
        existing = dict(procurement_status or {})
        normalized.update(existing)
        installation_specs = self._default_installation_specs(item_name)
        installation_specs.update(existing.get('installation_specs', {}) or {})
        normalized['installation_specs'] = installation_specs
        if not normalized.get('selected_supplier_name') and normalized.get('supplier'):
            normalized['selected_supplier_name'] = normalized.get('supplier', '')
        if not normalized.get('supplier') and normalized.get('selected_supplier_name'):
            normalized['supplier'] = normalized.get('selected_supplier_name', '')
        if not normalized.get('google_row_key'):
            normalized['google_row_key'] = self._build_google_row_key(project_id, item_index)
        normalized['total_price'] = float(normalized.get('unit_price', 0) or 0) * float(normalized.get('ordered_qty', 0) or 0)
        return normalized

    def _normalize_status_update(
        self,
        current_status: Dict,
        status_update: Dict,
        project_id: str = '',
        item_index: int | None = None,
        item_name: str = '',
    ) -> Dict:
        """Apply a status update while keeping derived fields and aliases consistent."""
        merged = self._normalize_procurement_status(current_status, item_name=item_name, project_id=project_id, item_index=item_index)
        merged.update(status_update or {})
        if 'selected_supplier_name' in (status_update or {}) and 'supplier' not in status_update:
            merged['supplier'] = merged.get('selected_supplier_name', '')
        if 'supplier' in (status_update or {}) and 'selected_supplier_name' not in status_update:
            merged['selected_supplier_name'] = merged.get('supplier', '')
        if 'quoted_unit_price' in merged and (merged.get('quoted_unit_price') in {'', None}):
            merged['quoted_unit_price'] = 0
        merged['total_price'] = float(merged.get('unit_price', 0) or 0) * float(merged.get('ordered_qty', 0) or 0)
        merged['last_updated'] = datetime.now().isoformat()
        if not merged.get('google_row_key'):
            merged['google_row_key'] = self._build_google_row_key(project_id, item_index)
        return merged

    def _normalize_project_item(self, item: Dict, project_id: str = '', item_index: int | None = None) -> Dict:
        """Return one project item with normalized Stage 1 fields."""
        item_data = dict(item.get('item_data', {}))
        normalized = {
            'project_id': project_id or item.get('project_id', ''),
            'category': item.get('category', ''),
            'department': item.get('department', ''),
            'item_data': item_data,
            'capex_info': dict(item.get('capex_info', {})),
            'procurement_status': self._normalize_procurement_status(
                item.get('procurement_status', {}),
                item_name=item_data.get('Item', item_data.get('item', '')),
                project_id=project_id or item.get('project_id', ''),
                item_index=item_index,
            ),
            'audit_trail': list(item.get('audit_trail', [])),
        }
        return normalized

    def _normalize_project_record(self, project: Dict) -> Dict:
        """Normalize one project payload returned to the app."""
        normalized = dict(project or {})
        normalized['workspace_links'] = self._normalize_workspace_links(normalized.get('workspace_links', {}))
        return normalized

    def _normalize_hotel_record(self, hotel: Dict) -> Dict:
        """Normalize one hotel payload returned to the app."""
        normalized = dict(hotel or {})
        normalized['workspace_links'] = self._normalize_workspace_links(normalized.get('workspace_links', {}))
        return normalized

    def _normalize_supplier_record(self, supplier: Dict) -> Dict:
        """Normalize one supplier payload returned to the app."""
        normalized = dict(supplier or {})
        normalized['workspace_links'] = self._normalize_workspace_links(normalized.get('workspace_links', {}))
        return normalized

    def ensure_default_admin(self, username: str, password: str, full_name: str = "System Administrator") -> bool:
        """Create the first admin account if no users exist yet."""
        users = self._read_json(self.users_file)
        if users:
            return False

        self.save_user({
            'full_name': full_name,
            'username': username or 'admin',
            'password': password or 'admin123',
            'role': 'admin',
            'hotel_ids': [],
            'active': True,
        })
        return True

    def save_hotel(self, hotel_data: Dict) -> str:
        """Create or update a hotel record."""
        hotels = self._read_json(self.hotels_file)
        hotel_id = hotel_data.get('hotel_id') or self._generate_id('HOTEL')
        existing = hotels.get(hotel_id, {})
        now = datetime.now().isoformat()

        hotels[hotel_id] = {
            'hotel_id': hotel_id,
            'name': hotel_data.get('name', existing.get('name', '')),
            'brand': hotel_data.get('brand', existing.get('brand', '')),
            'city': hotel_data.get('city', existing.get('city', '')),
            'country': hotel_data.get('country', existing.get('country', '')),
            'total_rooms': hotel_data.get('total_rooms', existing.get('total_rooms', 0)),
            'status': hotel_data.get('status', existing.get('status', 'active')),
            'notes': hotel_data.get('notes', existing.get('notes', '')),
            'workspace_links': self._normalize_workspace_links(
                hotel_data.get('workspace_links', existing.get('workspace_links', {}))
            ),
            'created_at': existing.get('created_at') or now,
            'updated_at': now,
        }

        self._write_json(self.hotels_file, hotels)
        return hotel_id

    def get_all_hotels(self) -> List[Dict]:
        """Return all hotels."""
        hotels = [self._normalize_hotel_record(hotel) for hotel in self._read_json(self.hotels_file).values()]
        hotels.sort(key=lambda hotel: (hotel.get('name', ''), hotel.get('city', '')))
        return hotels

    def get_hotel(self, hotel_id: str) -> Dict:
        """Return one hotel record."""
        hotels = self._read_json(self.hotels_file)
        return self._normalize_hotel_record(hotels.get(hotel_id, {}))

    def save_user(self, user_data: Dict) -> str:
        """Create or update an application user."""
        users = self._read_json(self.users_file)
        user_id = user_data.get('user_id') or self._generate_id('USER')
        username = self._normalize_username(user_data.get('username'))
        if not username:
            raise ValueError("Username is required.")

        for existing_id, existing_user in users.items():
            if existing_id != user_id and self._normalize_username(existing_user.get('username')) == username:
                raise ValueError("Username already exists.")

        existing = users.get(user_id, {})
        raw_password = user_data.get('password', '')
        password_hash = existing.get('password_hash', '')

        if raw_password:
            password_hash = self._hash_password(raw_password)
        elif not password_hash:
            raise ValueError("Password is required for new users.")

        now = datetime.now().isoformat()
        hotel_ids = [hotel_id for hotel_id in user_data.get('hotel_ids', existing.get('hotel_ids', [])) if hotel_id]

        users[user_id] = {
            'user_id': user_id,
            'full_name': user_data.get('full_name', existing.get('full_name', '')),
            'username': username,
            'password_hash': password_hash,
            'role': user_data.get('role', existing.get('role', 'hotel_editor')),
            'hotel_ids': sorted(set(hotel_ids)),
            'supplier_id': user_data.get('supplier_id', existing.get('supplier_id', '')),
            'email': user_data.get('email', existing.get('email', '')),
            'active': user_data.get('active', existing.get('active', True)),
            'created_at': existing.get('created_at') or now,
            'updated_at': now,
        }

        self._write_json(self.users_file, users)
        return user_id

    def get_all_users(self) -> List[Dict]:
        """Return all users without password hashes."""
        users = [self._sanitize_user(user) for user in self._read_json(self.users_file).values()]
        users.sort(key=lambda user: (user.get('full_name', ''), user.get('username', '')))
        return users

    def get_user(self, user_id: str) -> Dict:
        """Return one user without password hash."""
        users = self._read_json(self.users_file)
        return self._sanitize_user(users.get(user_id, {}))

    def get_user_by_username(self, username: str) -> Dict:
        """Return a user by username without password hash."""
        username = self._normalize_username(username)
        users = self._read_json(self.users_file)
        for user in users.values():
            if self._normalize_username(user.get('username')) == username:
                return self._sanitize_user(user)
        return {}

    def authenticate_user(self, username: str, password: str) -> Dict:
        """Authenticate a user by username and password."""
        username = self._normalize_username(username)
        users = self._read_json(self.users_file)

        for user in users.values():
            if not user.get('active', True):
                continue
            if self._normalize_username(user.get('username')) != username:
                continue
            if self._verify_password(password, user.get('password_hash', '')):
                return self._sanitize_user(user)

        return {}

    def record_login_event(self, username: str, success: bool, user_id: str = '', role: str = '', note: str = '') -> str:
        """Record a login attempt for auditing and lockout checks."""
        events = self._read_json(self.login_audit_file)
        if not isinstance(events, list):
            events = []

        event_id = self._generate_id('LOGIN')
        events.append({
            'event_id': event_id,
            'timestamp': datetime.now().isoformat(),
            'username': self._normalize_username(username),
            'success': success,
            'user_id': user_id,
            'role': role,
            'note': note,
        })
        self._write_json(self.login_audit_file, events[-5000:])
        return event_id

    def get_login_events(self, limit: int = 100, username: str = '') -> List[Dict]:
        """Return recent login audit events."""
        events = self._read_json(self.login_audit_file)
        if not isinstance(events, list):
            return []

        normalized_username = self._normalize_username(username)
        if normalized_username:
            events = [event for event in events if self._normalize_username(event.get('username')) == normalized_username]

        events.sort(key=lambda event: event.get('timestamp', ''), reverse=True)
        return events[:limit]

    def create_notification(self, notification_data: Dict) -> str:
        """Create an in-app notification."""
        notifications = self._read_json(self.notifications_file)
        notification_id = notification_data.get('notification_id') or self._generate_id('NOTIF')
        now = datetime.now().isoformat()
        existing = notifications.get(notification_id, {})

        notifications[notification_id] = {
            'notification_id': notification_id,
            'created_at': notification_data.get('created_at', existing.get('created_at', now)),
            'created_by': notification_data.get('created_by', existing.get('created_by', 'System')),
            'notification_type': notification_data.get('notification_type', existing.get('notification_type', 'general')),
            'title': notification_data.get('title', existing.get('title', '')),
            'message': notification_data.get('message', existing.get('message', '')),
            'project_id': notification_data.get('project_id', existing.get('project_id', '')),
            'item_index': notification_data.get('item_index', existing.get('item_index')),
            'hotel_id': notification_data.get('hotel_id', existing.get('hotel_id', '')),
            'supplier_id': notification_data.get('supplier_id', existing.get('supplier_id', '')),
            'target_roles': notification_data.get('target_roles', existing.get('target_roles', [])),
            'target_usernames': notification_data.get('target_usernames', existing.get('target_usernames', [])),
            'read_by': notification_data.get('read_by', existing.get('read_by', [])),
        }
        self._write_json(self.notifications_file, notifications)
        return notification_id

    def get_notifications(self, limit: int = 100) -> List[Dict]:
        """Return recent notifications."""
        notifications = list(self._read_json(self.notifications_file).values())
        notifications.sort(key=lambda notification: notification.get('created_at', ''), reverse=True)
        return notifications[:limit]

    def mark_notification_read(self, notification_id: str, username: str) -> bool:
        """Mark a notification as read by username."""
        notifications = self._read_json(self.notifications_file)
        if notification_id not in notifications:
            return False

        normalized_username = self._normalize_username(username)
        read_by = notifications[notification_id].get('read_by', [])
        if normalized_username and normalized_username not in read_by:
            read_by.append(normalized_username)
            notifications[notification_id]['read_by'] = read_by
            self._write_json(self.notifications_file, notifications)
        return True

    def save_project(self, project_data: Dict, results: Dict) -> str:
        """Save a new project"""
        projects = self._read_json(self.projects_file)
        items = self._read_json(self.items_file)

        # Generate project ID
        project_id = datetime.now().strftime('%Y%m%d_%H%M%S_%f')

        # Prepare project metadata
        project_info = {
            'project_id': project_id,
            'hotel_id': project_data.get('hotel_id', ''),
            'created_at': datetime.now().isoformat(),
            'created_by': project_data.get('created_by', ''),
            'hotel_info': {
                'brand': project_data.get('hotel_brand', ''),
                'hotel_type': project_data.get('hotel_type', ''),
                'property_name': project_data.get('property_name', ''),
                'city': project_data.get('city', ''),
                'country': project_data.get('country', ''),
                'project_name': project_data.get('project_name', ''),
                'total_rooms': project_data.get('total_rooms', 0),
                'num_floors': project_data.get('num_floors', 0),
            },
            'configuration': {
                'hotel_type': project_data.get('hotel_type', ''),
                'room_types': project_data.get('room_types', []),
                'conference_rooms': project_data.get('conference_rooms', []),
                'facilities': {
                    'restaurants': project_data.get('num_restaurants', 0),
                    'outlets': project_data.get('num_outlets', project_data.get('num_restaurants', 0)),
                    'kitchens': project_data.get('num_kitchens', 0),
                    'spa': project_data.get('has_spa', False),
                    'spa_rooms': project_data.get('spa_rooms', 0),
                    'pool': project_data.get('has_pool', False),
                    'gym': project_data.get('has_gym', False),
                    'conference': project_data.get('num_conference', 0),
                    'has_conference_spaces': project_data.get('has_conference_spaces', False),
                    'back_of_house_areas': project_data.get('num_back_of_house_areas', 0),
                },
                'linen_standards': {
                    'par_level': project_data.get('par_level', 4),
                    'reserve_stock': project_data.get('reserve_stock', 10),
                }
            },
            'status': 'active',
            'review_status': project_data.get('review_status', 'draft'),
            'last_modified': datetime.now().isoformat(),
            'last_modified_by': project_data.get('created_by', ''),
            'submitted_at': None,
            'reviewed_at': None,
            'reviewed_by': '',
            'latest_review_note': '',
            'workspace_links': self._normalize_workspace_links(project_data.get('workspace_links', {})),
            'workflow_history': [
                {
                    'timestamp': datetime.now().isoformat(),
                    'status': project_data.get('review_status', 'draft'),
                    'user': project_data.get('created_by', '') or 'System',
                    'note': 'Project created',
                }
            ]
        }

        # Save project
        projects[project_id] = project_info
        self._write_json(self.projects_file, projects)

        # Save procurement items
        project_items = []

        # Process all categories
        item_index = 0
        for category in ['guest_rooms', 'linen', 'bathroom', 'furniture', 'amenities',
                        'restaurant', 'kitchen', 'spa', 'pool', 'gym', 'public_areas',
                        'conference', 'back_of_house']:
            if results.get(category):
                for item in results[category]:
                    item_record = {
                        'project_id': project_id,
                        'category': category,
                        'department': self._get_department(category),
                        'item_data': item,
                        # CAPEX Management
                        'capex_info': {
                            'expense_type': self._get_expense_type(category),  # FF&E, OS&E, or OPEX
                            'depreciation_years': self._get_depreciation_years(category),
                            'budget_code': f"{self._get_budget_code(category)}-{item.get('Item', 'ITEM')[:10].upper().replace(' ', '-')}",
                            'cost_center': self._get_department(category),
                            'budget_amount': 0,  # To be set by user
                            'actual_amount': 0,  # Calculated from unit_price * ordered_qty
                            'variance': 0,  # budget_amount - actual_amount
                            'approval_status': 'draft',  # draft, submitted, dept_approved, finance_approved, rejected
                            'approved_by': [],  # List of approvers
                            'approved_date': None
                        },
                        'procurement_status': self._default_procurement_status(
                            item.get('Item', item.get('item', '')),
                            project_id=project_id,
                            item_index=item_index,
                        ),
                        # Audit Trail
                        'audit_trail': []
                    }
                    project_items.append(item_record)
                    item_index += 1

        items[project_id] = project_items
        self._write_json(self.items_file, items)

        return project_id

    def _get_department(self, category):
        """Map category to department"""
        mapping = {
            'guest_rooms': 'Rooms Division',
            'linen': 'Housekeeping',
            'bathroom': 'Housekeeping',
            'furniture': 'Rooms Division',
            'amenities': 'Rooms Division',
            'restaurant': 'Food & Beverage',
            'kitchen': 'Food & Beverage',
            'spa': 'Spa & Wellness',
            'pool': 'Recreation',
            'gym': 'Recreation',
            'public_areas': 'Front Office',
            'conference': 'Meeting & Events',
            'back_of_house': 'Back of House'
        }
        return mapping.get(category, 'General')

    def get_all_projects(self, hotel_ids: List[str] = None) -> List[Dict]:
        """Get all projects"""
        projects = self._read_json(self.projects_file)
        project_list = [
            self._normalize_project_record({
                'project_id': pid,
                **pdata
            })
            for pid, pdata in projects.items()
        ]
        if hotel_ids is not None:
            allowed_hotels = set(hotel_ids)
            project_list = [project for project in project_list if project.get('hotel_id') in allowed_hotels]
        project_list.sort(key=lambda project: project.get('created_at', ''))
        return project_list

    def get_project(self, project_id: str) -> Dict:
        """Get a specific project"""
        projects = self._read_json(self.projects_file)
        return self._normalize_project_record(projects.get(project_id, {}))

    def get_project_items(self, project_id: str) -> List[Dict]:
        """Get all items for a project"""
        items = self._read_json(self.items_file)
        return [
            self._normalize_project_item(item, project_id=project_id, item_index=index)
            for index, item in enumerate(items.get(project_id, []))
        ]

    def update_project_workspace_links(self, project_id: str, workspace_links: Dict, updated_by: str = '') -> bool:
        """Persist Google workspace metadata for one project."""
        projects = self._read_json(self.projects_file)
        if project_id not in projects:
            return False
        projects[project_id]['workspace_links'] = self._normalize_workspace_links(
            {
                **projects[project_id].get('workspace_links', {}),
                **(workspace_links or {}),
            }
        )
        projects[project_id]['last_modified'] = datetime.now().isoformat()
        if updated_by:
            projects[project_id]['last_modified_by'] = updated_by
        self._write_json(self.projects_file, projects)
        return True

    def save_supplier(self, supplier_data: Dict) -> str:
        """Create or update a supplier record"""
        suppliers = self._read_json(self.suppliers_file)
        supplier_id = supplier_data.get('supplier_id')

        if not supplier_id:
            supplier_id = datetime.now().strftime('SUP%Y%m%d_%H%M%S')

        suppliers[supplier_id] = {
            'supplier_id': supplier_id,
            'name': supplier_data.get('name', ''),
            'email': supplier_data.get('email', ''),
            'phone': supplier_data.get('phone', ''),
            'website': supplier_data.get('website', ''),
            'address': supplier_data.get('address', ''),
            'categories': supplier_data.get('categories', []),
            'contact_person': supplier_data.get('contact_person', ''),
            'notes': supplier_data.get('notes', ''),
            'status': supplier_data.get('status', suppliers.get(supplier_id, {}).get('status', 'active')),
            'workspace_links': self._normalize_workspace_links(
                supplier_data.get('workspace_links', suppliers.get(supplier_id, {}).get('workspace_links', {}))
            ),
            'updated_at': datetime.now().isoformat(),
            'created_at': supplier_data.get('created_at') or suppliers.get(supplier_id, {}).get('created_at') or datetime.now().isoformat(),
        }

        self._write_json(self.suppliers_file, suppliers)
        return supplier_id

    def get_all_suppliers(self) -> List[Dict]:
        """Return all suppliers"""
        suppliers = self._read_json(self.suppliers_file)
        return [self._normalize_supplier_record(supplier) for supplier in suppliers.values()]

    def get_supplier(self, supplier_id: str) -> Dict:
        """Return a single supplier"""
        suppliers = self._read_json(self.suppliers_file)
        return self._normalize_supplier_record(suppliers.get(supplier_id, {}))

    def save_supplier_catalog(self, supplier_id: str, catalog_data: Dict, items: List[Dict]) -> str:
        """Save a catalog upload for a supplier"""
        catalogs = self._read_json(self.catalogs_file)
        supplier_catalogs = catalogs.get(supplier_id, [])
        catalog_id = datetime.now().strftime('CAT%Y%m%d_%H%M%S')

        catalog_record = {
            'catalog_id': catalog_id,
            'supplier_id': supplier_id,
            'name': catalog_data.get('name', 'Catalog'),
            'source_type': catalog_data.get('source_type', ''),
            'source_name': catalog_data.get('source_name', ''),
            'source_url': catalog_data.get('source_url', ''),
            'uploaded_at': datetime.now().isoformat(),
            'image_dir': catalog_data.get('image_dir', ''),
            'image_count': catalog_data.get('image_count', 0),
            'items': items,
        }

        supplier_catalogs.append(catalog_record)
        catalogs[supplier_id] = supplier_catalogs
        self._write_json(self.catalogs_file, catalogs)
        return catalog_id

    def get_supplier_catalogs(self, supplier_id: str) -> List[Dict]:
        """Return all catalogs for a supplier"""
        catalogs = self._read_json(self.catalogs_file)
        return catalogs.get(supplier_id, [])

    def get_all_catalog_items(self, supplier_ids: List[str]) -> List[Dict]:
        """Return all catalog items for selected suppliers"""
        catalogs = self._read_json(self.catalogs_file)
        all_items = []

        for supplier_id in supplier_ids:
            supplier_catalogs = catalogs.get(supplier_id, [])
            for catalog in supplier_catalogs:
                for item in catalog.get('items', []):
                    enriched = {
                        'supplier_id': supplier_id,
                        'catalog_id': catalog.get('catalog_id'),
                        'catalog_name': catalog.get('name', ''),
                        **item
                    }
                    all_items.append(enriched)

        return all_items

    def update_item_status(self, project_id: str, item_index: int, status_update: Dict):
        """Update procurement status of an item"""
        items = self._read_json(self.items_file)

        if project_id in items and item_index < len(items[project_id]):
            item_record = items[project_id][item_index]
            item_name = item_record.get('item_data', {}).get('Item', item_record.get('item_data', {}).get('item', ''))
            item_record['procurement_status'] = self._normalize_status_update(
                item_record.get('procurement_status', {}),
                status_update,
                project_id=project_id,
                item_index=item_index,
                item_name=item_name,
            )
            self._write_json(self.items_file, items)
            return True
        return False

    def get_items_by_department(self, project_id: str, department: str) -> List[Dict]:
        """Get items filtered by department"""
        all_items = self.get_project_items(project_id)
        return [item for item in all_items if item['department'] == department]

    def get_procurement_summary(self, project_id: str) -> Dict:
        """Get procurement status summary"""
        items = self.get_project_items(project_id)

        total_items = len(items)
        ordered = sum(1 for item in items if item['procurement_status']['ordered'])
        received = sum(1 for item in items if item['procurement_status']['received'])
        installed = sum(1 for item in items if item['procurement_status']['installed'])

        total_budget = sum(item['procurement_status']['total_price'] for item in items)
        spent = sum(
            item['procurement_status']['total_price']
            for item in items
            if item['procurement_status']['ordered']
        )

        return {
            'total_items': total_items,
            'ordered_count': ordered,
            'received_count': received,
            'installed_count': installed,
            'ordered_percent': round(ordered / total_items * 100, 1) if total_items > 0 else 0,
            'received_percent': round(received / total_items * 100, 1) if total_items > 0 else 0,
            'installed_percent': round(installed / total_items * 100, 1) if total_items > 0 else 0,
            'total_budget': total_budget,
            'spent': spent,
            'remaining': total_budget - spent
        }

    def export_project_to_excel(self, project_id: str, output_path: str):
        """Export project with status to Excel"""
        from io import BytesIO

        project = self.get_project(project_id)
        items = self.get_project_items(project_id)

        output = BytesIO()

        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Project info
            project_info_df = pd.DataFrame([{
                'Project ID': project_id,
                'Property Name': project['hotel_info'].get('property_name', ''),
                'Brand': project['hotel_info'].get('brand', ''),
                'City': project['hotel_info'].get('city', ''),
                'Total Rooms': project['hotel_info'].get('total_rooms', 0),
                'Created': project.get('created_at', ''),
                'Last Modified': project.get('last_modified', '')
            }])
            project_info_df.to_excel(writer, sheet_name='Project Info', index=False)

            # Procurement items
            items_data = []
            for idx, item in enumerate(items):
                item_data = item['item_data']
                status = item['procurement_status']

                record = {
                    'Index': idx,
                    'Department': item['department'],
                    'Category': item['category'],
                    'Item': item_data.get('Item', item_data.get('item', 'N/A')),
                    'Specification': item_data.get('Specification', ''),
                    'Total Qty': item_data.get('Total Qty', item_data.get('Total_Qty', 0)),
                    'Unit': item_data.get('Unit', 'pcs'),
                    'Ordered': '✓' if status['ordered'] else '',
                    'Ordered Date': status['ordered_date'] or '',
                    'Received': '✓' if status['received'] else '',
                    'Received Date': status['received_date'] or '',
                    'Installed': '✓' if status['installed'] else '',
                    'Supplier': status['supplier'],
                    'PO Number': status['po_number'],
                    'Unit Price': status['unit_price'],
                    'Total Price': status['total_price'],
                    'Notes': status['notes']
                }
                items_data.append(record)

            items_df = pd.DataFrame(items_data)
            items_df.to_excel(writer, sheet_name='Procurement Items', index=False)

            # Summary by department
            summary_data = []
            for dept in items_df['Department'].unique():
                dept_items = items_df[items_df['Department'] == dept]
                summary_data.append({
                    'Department': dept,
                    'Total Items': len(dept_items),
                    'Ordered': dept_items['Ordered'].str.contains('✓').sum(),
                    'Received': dept_items['Received'].str.contains('✓').sum(),
                    'Installed': dept_items['Installed'].str.contains('✓').sum(),
                    'Total Budget': dept_items['Total Price'].sum()
                })

            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary by Department', index=False)

        output.seek(0)
        return output.getvalue()

    def compare_projects(self, project_id_1: str, project_id_2: str) -> Dict:
        """Compare two projects"""
        project1 = self.get_project(project_id_1)
        project2 = self.get_project(project_id_2)

        items1 = self.get_project_items(project_id_1)
        items2 = self.get_project_items(project_id_2)

        comparison = {
            'project1': {
                'id': project_id_1,
                'name': project1['hotel_info'].get('property_name', 'Project 1'),
                'rooms': project1['hotel_info'].get('total_rooms', 0),
                'total_items': len(items1),
                'total_budget': sum(item['procurement_status']['total_price'] for item in items1)
            },
            'project2': {
                'id': project_id_2,
                'name': project2['hotel_info'].get('property_name', 'Project 2'),
                'rooms': project2['hotel_info'].get('total_rooms', 0),
                'total_items': len(items2),
                'total_budget': sum(item['procurement_status']['total_price'] for item in items2)
            },
            'differences': {
                'rooms_diff': project1['hotel_info'].get('total_rooms', 0) - project2['hotel_info'].get('total_rooms', 0),
                'items_diff': len(items1) - len(items2),
                'budget_diff': sum(item['procurement_status']['total_price'] for item in items1) -
                              sum(item['procurement_status']['total_price'] for item in items2)
            }
        }

        return comparison

    def _get_default_height(self, item_name: str) -> int:
        """Get default installation height in cm based on item type (from WHITE STONE standards)"""
        item_lower = item_name.lower()

        # Installation heights from WHITE STONE archive
        height_standards = {
            'towel': 180,  # Towel shelf/bar: 180cm from floor
            'hook': 180,  # Door hooks: 180cm from floor
            'mirror': 130,  # Mirrors: 120-140cm from floor (using 130 as default)
            'cosmetic': 125,  # Cosmetics shelf: 120-130cm from floor
            'dispenser': 110,  # Sink dispenser: 100-120cm from floor
            'hairdryer': 110,  # Hair dryer: 100-120cm from floor
            'hand towel': 130,  # Hand towel holder: 120-140cm from floor
            'toilet paper': 65,  # TP holder: 20cm from toilet (approx 65cm from floor)
            'spare tp': 44,  # Spare TP: under main holder (approx 44cm from floor)
            'toilet brush': 15,  # Toilet brush: 15cm from floor
        }

        for keyword, height in height_standards.items():
            if keyword in item_lower:
                return height

        return 0  # No default height specified

    def _get_expense_type(self, category: str) -> str:
        """Determine if item is FF&E, OS&E, or OPEX"""
        # FF&E: Furniture, Fixtures & Equipment (capitalized, depreciated over 7-10 years)
        ffe_categories = ['furniture', 'guest_rooms', 'bathroom', 'conference',
                         'restaurant', 'kitchen', 'spa', 'pool', 'gym']

        # OS&E: Operating Supplies & Equipment (expensed immediately or short depreciation)
        ose_categories = ['linen', 'amenities']

        # OPEX: Operational Expenditure (ongoing costs, fully expensed)
        opex_categories = ['back_of_house']  # Some back of house items

        if category in ffe_categories:
            return 'FF&E'
        elif category in ose_categories:
            return 'OS&E'
        elif category in opex_categories:
            return 'OPEX'
        else:
            return 'FF&E'  # Default to FF&E

    def _get_depreciation_years(self, category: str) -> int:
        """Get depreciation period in years"""
        expense_type = self._get_expense_type(category)

        if expense_type == 'FF&E':
            return 7  # Standard FF&E depreciation
        elif expense_type == 'OS&E':
            return 1  # OS&E typically expensed in first year
        else:  # OPEX
            return 0  # Fully expensed immediately

    def _get_budget_code(self, category: str) -> str:
        """Generate budget code prefix for cost center tracking"""
        codes = {
            'guest_rooms': '4100-GR',
            'linen': '4200-LN',
            'bathroom': '4150-BA',
            'furniture': '4100-FU',
            'amenities': '4120-AM',
            'restaurant': '5100-FB',
            'kitchen': '5200-KT',
            'spa': '6100-SP',
            'pool': '6200-PL',
            'gym': '6300-GY',
            'public_areas': '4300-PA',
            'conference': '4400-CF',
            'back_of_house': '7100-BH'
        }
        return codes.get(category, '9999-XX')

    def add_audit_entry(self, project_id: str, item_index: int, action: str, user: str, details: dict):
        """Add audit trail entry for CAPEX tracking"""
        items = self._read_json(self.items_file)

        if project_id in items and item_index < len(items[project_id]):
            audit_entry = {
                'timestamp': datetime.now().isoformat(),
                'action': action,  # e.g., 'created', 'approved', 'ordered', 'price_changed'
                'user': user,
                'details': details
            }

            if 'audit_trail' not in items[project_id][item_index]:
                items[project_id][item_index]['audit_trail'] = []

            items[project_id][item_index]['audit_trail'].append(audit_entry)
            self._write_json(self.items_file, items)
            return True
        return False

    def get_budget_summary(self, project_id: str) -> Dict:
        """Get budget vs actual summary by department"""
        items = self.get_project_items(project_id)

        summary = {}
        for item in items:
            dept = item['department']
            capex_info = item.get('capex_info', {})

            if dept not in summary:
                summary[dept] = {
                    'budget_total': 0,
                    'actual_total': 0,
                    'variance': 0,
                    'item_count': 0,
                    'ffe_total': 0,
                    'ose_total': 0,
                    'opex_total': 0
                }

            summary[dept]['budget_total'] += capex_info.get('budget_amount', 0)
            summary[dept]['actual_total'] += capex_info.get('actual_amount', 0)
            summary[dept]['item_count'] += 1

            expense_type = capex_info.get('expense_type', 'FF&E')
            actual = capex_info.get('actual_amount', 0)

            if expense_type == 'FF&E':
                summary[dept]['ffe_total'] += actual
            elif expense_type == 'OS&E':
                summary[dept]['ose_total'] += actual
            elif expense_type == 'OPEX':
                summary[dept]['opex_total'] += actual

        # Calculate variances
        for dept in summary:
            summary[dept]['variance'] = summary[dept]['budget_total'] - summary[dept]['actual_total']

        return summary

    def delete_project(self, project_id: str) -> bool:
        """Delete a project"""
        projects = self._read_json(self.projects_file)
        items = self._read_json(self.items_file)

        if project_id in projects:
            del projects[project_id]
            self._write_json(self.projects_file, projects)

        if project_id in items:
            del items[project_id]
            self._write_json(self.items_file, items)

        return True

    def assign_project_hotel(self, project_id: str, hotel_id: str, updated_by: str = '') -> bool:
        """Assign or reassign a project to a hotel."""
        projects = self._read_json(self.projects_file)
        if project_id not in projects:
            return False

        projects[project_id]['hotel_id'] = hotel_id
        projects[project_id]['last_modified'] = datetime.now().isoformat()
        projects[project_id]['last_modified_by'] = updated_by
        projects[project_id].setdefault('workflow_history', []).append({
            'timestamp': datetime.now().isoformat(),
            'status': 'hotel_reassigned',
            'user': updated_by or 'System',
            'note': hotel_id,
        })
        self._write_json(self.projects_file, projects)
        return True

    def update_project_workflow(self, project_id: str, review_status: str, user: str, note: str = '') -> bool:
        """Update project workflow state and store review/correction notes."""
        projects = self._read_json(self.projects_file)
        project = projects.get(project_id)
        if not project:
            return False

        now = datetime.now().isoformat()
        project['review_status'] = review_status
        project['last_modified'] = now
        project['last_modified_by'] = user
        project['latest_review_note'] = note or project.get('latest_review_note', '')

        if review_status in {'submitted', 'resubmitted'}:
            project['submitted_at'] = now
        if review_status in {'needs_correction', 'approved'}:
            project['reviewed_at'] = now
            project['reviewed_by'] = user

        project.setdefault('workflow_history', []).append({
            'timestamp': now,
            'status': review_status,
            'user': user,
            'note': note,
        })

        projects[project_id] = project
        self._write_json(self.projects_file, projects)
        return True

    # ==================== PROCURE-TO-PAY (P2P) METHODS ====================

    def create_purchase_order(self, po_data: Dict) -> str:
        """Create a new purchase order"""
        pos = self._read_json(self.purchase_orders_file)

        po_id = f"PO-{datetime.now().strftime('%Y%m%d')}-{len(pos) + 1:04d}"

        po_data['po_id'] = po_id
        po_data['created_at'] = datetime.now().isoformat()
        po_data['status'] = 'Draft'  # Draft, Submitted, Approved, Rejected, Completed
        po_data['approval_history'] = []

        pos[po_id] = po_data
        self._write_json(self.purchase_orders_file, pos)

        return po_id

    def get_purchase_orders(self, filters: Dict = None) -> List[Dict]:
        """Get purchase orders with optional filters"""
        pos = self._read_json(self.purchase_orders_file)

        result = list(pos.values())

        if filters:
            if 'status' in filters:
                result = [po for po in result if po['status'] == filters['status']]
            if 'supplier_id' in filters:
                result = [po for po in result if po.get('supplier_id') == filters['supplier_id']]
            if 'project_id' in filters:
                result = [po for po in result if po.get('project_id') == filters['project_id']]

        # Sort by created_at desc
        result.sort(key=lambda x: x.get('created_at', ''), reverse=True)

        return result

    def get_purchase_order(self, po_id: str) -> Dict:
        """Get a specific purchase order"""
        pos = self._read_json(self.purchase_orders_file)
        return pos.get(po_id, {})

    def update_purchase_order_status(self, po_id: str, status: str, approver: str = None, notes: str = None) -> bool:
        """Update PO status with approval tracking"""
        pos = self._read_json(self.purchase_orders_file)

        if po_id not in pos:
            return False

        pos[po_id]['status'] = status
        pos[po_id]['updated_at'] = datetime.now().isoformat()

        # Add to approval history
        approval_entry = {
            'status': status,
            'timestamp': datetime.now().isoformat(),
            'approver': approver or 'System',
            'notes': notes or ''
        }

        if 'approval_history' not in pos[po_id]:
            pos[po_id]['approval_history'] = []

        pos[po_id]['approval_history'].append(approval_entry)

        self._write_json(self.purchase_orders_file, pos)
        return True

    def create_invoice(self, invoice_data: Dict) -> str:
        """Create a new invoice"""
        invoices = self._read_json(self.invoices_file)

        invoice_id = f"INV-{datetime.now().strftime('%Y%m%d')}-{len(invoices) + 1:04d}"

        invoice_data['invoice_id'] = invoice_id
        invoice_data['created_at'] = datetime.now().isoformat()
        invoice_data['status'] = invoice_data.get('status', 'Pending')
        invoice_data['match_status'] = invoice_data.get('match_status', 'Unmatched')
        invoice_data['status_history'] = invoice_data.get('status_history', [])

        invoices[invoice_id] = invoice_data
        self._write_json(self.invoices_file, invoices)

        return invoice_id

    def get_invoice(self, invoice_id: str) -> Dict:
        """Get a specific invoice."""
        invoices = self._read_json(self.invoices_file)
        return invoices.get(invoice_id, {})

    def get_invoices(self, filters: Dict = None) -> List[Dict]:
        """Get invoices with optional filters"""
        invoices = self._read_json(self.invoices_file)

        result = list(invoices.values())

        if filters:
            if 'status' in filters:
                result = [inv for inv in result if inv['status'] == filters['status']]
            if 'po_id' in filters:
                result = [inv for inv in result if inv.get('po_id') == filters['po_id']]
            if 'supplier_id' in filters:
                result = [inv for inv in result if inv.get('supplier_id') == filters['supplier_id']]
            if 'match_status' in filters:
                result = [inv for inv in result if inv.get('match_status') == filters['match_status']]

        result.sort(key=lambda x: x.get('created_at', ''), reverse=True)

        return result

    def match_invoice_to_po(self, invoice_id: str, po_id: str) -> Dict:
        """Perform 3-way matching: PO vs Invoice vs Receipt"""
        invoices = self._read_json(self.invoices_file)
        pos = self._read_json(self.purchase_orders_file)

        if invoice_id not in invoices or po_id not in pos:
            return {'success': False, 'message': 'Invoice or PO not found'}

        invoice = invoices[invoice_id]
        po = pos[po_id]

        # 2-way match: PO vs Invoice
        matching_result = {
            'match_type': '2-Way',  # PO vs Invoice
            'po_amount': po.get('total_amount', 0),
            'invoice_amount': invoice.get('total_amount', 0),
            'variance': abs(po.get('total_amount', 0) - invoice.get('total_amount', 0)),
            'variance_pct': 0,
            'items_matched': False,
            'amounts_matched': False
        }

        # Calculate variance percentage
        if po.get('total_amount', 0) > 0:
            matching_result['variance_pct'] = (matching_result['variance'] / po['total_amount']) * 100

        # Check if amounts match within tolerance (5%)
        if matching_result['variance_pct'] <= 5:
            matching_result['amounts_matched'] = True

        # Update invoice
        invoice['po_id'] = po_id
        invoice['match_status'] = '2-Way' if matching_result['amounts_matched'] else 'Mismatched'
        if matching_result['amounts_matched'] and invoice.get('status') in {'Pending', 'Submitted', ''}:
            invoice['status'] = 'Matched'
        elif not matching_result['amounts_matched'] and invoice.get('status') not in {'Paid', 'Approved'}:
            invoice['status'] = 'Disputed'
        invoice['matching_result'] = matching_result
        invoice['matched_at'] = datetime.now().isoformat()

        invoices[invoice_id] = invoice
        self._write_json(self.invoices_file, invoices)

        return {'success': True, 'matching_result': matching_result}

    def update_invoice_status(self, invoice_id: str, status: str, user: str = None, notes: str = None) -> bool:
        """Update invoice status with history tracking."""
        invoices = self._read_json(self.invoices_file)
        if invoice_id not in invoices:
            return False

        now = datetime.now().isoformat()
        invoices[invoice_id]['status'] = status
        invoices[invoice_id]['updated_at'] = now
        invoices[invoice_id].setdefault('status_history', []).append({
            'status': status,
            'timestamp': now,
            'user': user or 'System',
            'notes': notes or '',
        })

        if status == 'Approved':
            invoices[invoice_id]['approved_at'] = now
        elif status == 'Disputed':
            invoices[invoice_id]['disputed_at'] = now
        elif status == 'Paid':
            invoices[invoice_id]['paid_at'] = now

        self._write_json(self.invoices_file, invoices)
        return True

    def create_payment(self, payment_data: Dict) -> str:
        """Record a payment"""
        payments = self._read_json(self.payments_file)

        payment_id = f"PAY-{datetime.now().strftime('%Y%m%d')}-{len(payments) + 1:04d}"

        payment_data['payment_id'] = payment_id
        payment_data['payment_date'] = payment_data.get('payment_date', datetime.now().isoformat())
        payment_data['status'] = payment_data.get('status', 'Completed')

        payments[payment_id] = payment_data
        self._write_json(self.payments_file, payments)

        # Update invoice payment status
        if 'invoice_id' in payment_data:
            invoices = self._read_json(self.invoices_file)
            invoice_id = payment_data['invoice_id']
            if invoice_id in invoices:
                total_paid = sum(
                    float(payment.get('amount', 0) or 0)
                    for payment in payments.values()
                    if payment.get('invoice_id') == invoice_id
                )
                invoice_total = float(invoices[invoice_id].get('total_amount', 0) or 0)
                if invoice_total and total_paid >= invoice_total:
                    invoices[invoice_id]['status'] = 'Paid'
                    invoices[invoice_id]['paid_at'] = payment_data['payment_date']
                elif total_paid > 0:
                    invoices[invoice_id]['status'] = 'Partially Paid'
                    invoices[invoice_id]['paid_at'] = None
                self._write_json(self.invoices_file, invoices)

        return payment_id

    def get_payments(self, filters: Dict = None) -> List[Dict]:
        """Get payments with optional filters"""
        payments = self._read_json(self.payments_file)

        result = list(payments.values())

        if filters:
            if 'invoice_id' in filters:
                result = [pay for pay in result if pay.get('invoice_id') == filters['invoice_id']]
            if 'supplier_id' in filters:
                result = [pay for pay in result if pay.get('supplier_id') == filters['supplier_id']]

        result.sort(key=lambda x: x.get('payment_date', ''), reverse=True)

        return result

    def get_p2p_analytics(self) -> Dict:
        """Get Procure-to-Pay analytics"""
        pos = self._read_json(self.purchase_orders_file)
        invoices = self._read_json(self.invoices_file)
        payments = self._read_json(self.payments_file)

        analytics = {
            'total_pos': len(pos),
            'total_po_value': sum([po.get('total_amount', 0) for po in pos.values()]),
            'pos_by_status': {},
            'total_invoices': len(invoices),
            'total_invoice_value': sum([inv.get('total_amount', 0) for inv in invoices.values()]),
            'invoices_by_status': {},
            'total_payments': len(payments),
            'total_paid': sum([pay.get('amount', 0) for pay in payments.values()]),
            'matching_stats': {
                '3-Way': 0,
                '2-Way': 0,
                'Unmatched': 0,
                'Mismatched': 0
            },
            'avg_cycle_time': 0,
            'outstanding_payables': 0
        }

        # PO status breakdown
        for po in pos.values():
            status = po.get('status', 'Unknown')
            analytics['pos_by_status'][status] = analytics['pos_by_status'].get(status, 0) + 1

        # Invoice status breakdown
        for inv in invoices.values():
            status = inv.get('status', 'Unknown')
            analytics['invoices_by_status'][status] = analytics['invoices_by_status'].get(status, 0) + 1

            match_status = inv.get('match_status', 'Unmatched')
            if match_status in analytics['matching_stats']:
                analytics['matching_stats'][match_status] += 1

            # Outstanding payables
            if inv.get('status') in ['Pending', 'Matched', 'Approved']:
                analytics['outstanding_payables'] += inv.get('total_amount', 0)

        return analytics
