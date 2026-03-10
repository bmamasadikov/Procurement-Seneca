from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import os
from typing import Any, Dict, List

from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from database import ProcurementDatabase
from models import (
    Base,
    HotelRecord,
    InvoiceRecord,
    LoginAuditRecord,
    NotificationRecord,
    PaymentRecord,
    ProjectItemRecord,
    ProjectRecord,
    ProjectWorkflowHistoryRecord,
    PurchaseOrderRecord,
    SupplierCatalogRecord,
    SupplierRecord,
    UserHotelAccessRecord,
    UserRecord,
)


class PostgresProcurementDatabase(ProcurementDatabase):
    """SQLAlchemy-backed database implementation for PostgreSQL."""

    def __init__(
        self,
        database_url: str,
        auto_create_schema: bool = False,
        engine_options: Dict[str, Any] | None = None,
    ):
        self.database_url = self._normalize_database_url(database_url)
        self.db_path = os.environ.get("APP_DATA_PATH", "procurement_data")
        self.engine_options = dict(engine_options or {})
        os.makedirs(self.db_path, exist_ok=True)
        self.engine = self._create_engine(self.database_url)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)
        if auto_create_schema:
            Base.metadata.create_all(self.engine)
        else:
            self._assert_schema_ready()

    def _normalize_database_url(self, database_url: str) -> str:
        """Normalize database URLs to SQLAlchemy-compatible driver strings."""
        if database_url.startswith("postgres://"):
            return database_url.replace("postgres://", "postgresql+psycopg://", 1)
        if database_url.startswith("postgresql://") and "+psycopg" not in database_url:
            return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return database_url

    def _create_engine(self, database_url: str):
        """Create a SQLAlchemy engine with sane defaults."""
        engine_kwargs = {"future": True}
        if database_url.startswith("sqlite"):
            engine_kwargs["connect_args"] = {"check_same_thread": False}
        else:
            engine_kwargs["pool_pre_ping"] = True
            engine_kwargs.update(self.engine_options)
        return create_engine(database_url, **engine_kwargs)

    def _assert_schema_ready(self):
        """Require migrations to be applied before the application starts."""
        inspector = inspect(self.engine)
        required_tables = {
            "alembic_version",
            "users",
            "hotels",
            "projects",
            "project_items",
            "login_audit",
            "notifications",
        }
        available_tables = set(inspector.get_table_names())
        missing_tables = sorted(required_tables - available_tables)
        if missing_tables:
            raise RuntimeError(
                "PostgreSQL schema is not initialized. "
                f"Missing tables: {', '.join(missing_tables)}. "
                "Run `alembic upgrade head` before starting the app."
            )
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        if "supplier_id" not in user_columns:
            raise RuntimeError(
                "PostgreSQL schema is out of date. Missing users.supplier_id. "
                "Run `alembic upgrade head` before starting the app."
            )
        hotel_columns = {column["name"] for column in inspector.get_columns("hotels")}
        supplier_columns = {column["name"] for column in inspector.get_columns("suppliers")}
        project_columns = {column["name"] for column in inspector.get_columns("projects")}
        if "workspace_links" not in hotel_columns or "workspace_links" not in supplier_columns or "workspace_links" not in project_columns:
            raise RuntimeError(
                "PostgreSQL schema is out of date. Missing workspace_links columns. "
                "Run `alembic upgrade head` before starting the app."
            )

    @contextmanager
    def _session_scope(self):
        """Transactional session scope."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _get_timestamp(self) -> str:
        """Current timestamp in ISO format."""
        return datetime.now().isoformat()

    def _next_project_id(self) -> str:
        return datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    def _next_counted_id(self, prefix: str, total_count: int) -> str:
        return f"{prefix}-{datetime.now().strftime('%Y%m%d')}-{total_count + 1:04d}"

    def _hotel_to_dict(self, record: HotelRecord) -> Dict:
        return self._normalize_hotel_record({
            "hotel_id": record.hotel_id,
            "name": record.name,
            "brand": record.brand,
            "city": record.city,
            "country": record.country,
            "total_rooms": record.total_rooms,
            "status": record.status,
            "notes": record.notes,
            "workspace_links": record.workspace_links or {},
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        })

    def _user_to_dict(self, record: UserRecord) -> Dict:
        hotel_ids = sorted(access.hotel_id for access in record.hotel_access)
        return self._sanitize_user(
            {
                "user_id": record.user_id,
                "full_name": record.full_name,
                "username": record.username,
                "password_hash": record.password_hash,
                "role": record.role,
                "hotel_ids": hotel_ids,
                "supplier_id": record.supplier_id or "",
                "email": record.email,
                "active": record.active,
                "created_at": record.created_at,
                "updated_at": record.updated_at,
            }
        )

    def _workflow_to_dict(self, record: ProjectWorkflowHistoryRecord) -> Dict:
        return {
            "timestamp": record.timestamp,
            "status": record.status,
            "user": record.user,
            "note": record.note,
        }

    def _project_to_dict(self, record: ProjectRecord) -> Dict:
        return self._normalize_project_record({
            "project_id": record.project_id,
            "hotel_id": record.hotel_id,
            "created_at": record.created_at,
            "created_by": record.created_by,
            "hotel_info": record.hotel_info or {},
            "configuration": record.configuration or {},
            "status": record.status,
            "review_status": record.review_status,
            "last_modified": record.last_modified,
            "last_modified_by": record.last_modified_by,
            "submitted_at": record.submitted_at,
            "reviewed_at": record.reviewed_at,
            "reviewed_by": record.reviewed_by,
            "latest_review_note": record.latest_review_note,
            "workspace_links": record.workspace_links or {},
            "workflow_history": [self._workflow_to_dict(entry) for entry in record.workflow_history],
        })

    def _project_item_to_dict(self, record: ProjectItemRecord) -> Dict:
        return self._normalize_project_item({
            "project_id": record.project_id,
            "category": record.category,
            "department": record.department,
            "item_data": record.item_data or {},
            "capex_info": record.capex_info or {},
            "procurement_status": record.procurement_status or {},
            "audit_trail": record.audit_trail or [],
        }, project_id=record.project_id, item_index=record.item_index)

    def _supplier_to_dict(self, record: SupplierRecord) -> Dict:
        return self._normalize_supplier_record({
            "supplier_id": record.supplier_id,
            "name": record.name,
            "email": record.email,
            "phone": record.phone,
            "website": record.website,
            "address": record.address,
            "categories": record.categories or [],
            "contact_person": record.contact_person,
            "notes": record.notes,
            "status": record.status,
            "workspace_links": record.workspace_links or {},
            "updated_at": record.updated_at,
            "created_at": record.created_at,
        })

    def _login_event_to_dict(self, record: LoginAuditRecord) -> Dict:
        return {
            "event_id": record.event_id,
            "timestamp": record.timestamp,
            "username": record.username,
            "success": record.success,
            "user_id": record.user_id,
            "role": record.role,
            "note": record.note,
        }

    def _notification_to_dict(self, record: NotificationRecord) -> Dict:
        return {
            "notification_id": record.notification_id,
            "created_at": record.created_at,
            "created_by": record.created_by,
            "notification_type": record.notification_type,
            "title": record.title,
            "message": record.message,
            "project_id": record.project_id,
            "item_index": record.item_index,
            "hotel_id": record.hotel_id,
            "supplier_id": record.supplier_id,
            "target_roles": record.target_roles or [],
            "target_usernames": record.target_usernames or [],
            "read_by": record.read_by or [],
        }

    def _catalog_to_dict(self, record: SupplierCatalogRecord) -> Dict:
        return {
            "catalog_id": record.catalog_id,
            "supplier_id": record.supplier_id,
            "name": record.name,
            "source_type": record.source_type,
            "source_name": record.source_name,
            "source_url": record.source_url,
            "uploaded_at": record.uploaded_at,
            "image_dir": record.image_dir,
            "image_count": record.image_count,
            "items": record.items or [],
        }

    def _purchase_order_to_dict(self, record: PurchaseOrderRecord) -> Dict:
        payload = dict(record.payload or {})
        payload.update(
            {
                "po_id": record.po_id,
                "project_id": record.project_id,
                "supplier_id": record.supplier_id,
                "status": record.status,
                "created_at": record.created_at,
                "updated_at": record.updated_at,
                "total_amount": record.total_amount,
                "approval_history": record.approval_history or [],
            }
        )
        return payload

    def _invoice_to_dict(self, record: InvoiceRecord) -> Dict:
        payload = dict(record.payload or {})
        payload.update(
            {
                "invoice_id": record.invoice_id,
                "po_id": record.po_id,
                "supplier_id": record.supplier_id,
                "status": record.status,
                "match_status": record.match_status,
                "created_at": record.created_at,
                "matched_at": record.matched_at,
                "paid_at": record.paid_at,
                "total_amount": record.total_amount,
                "matching_result": record.matching_result or {},
            }
        )
        return payload

    def _payment_to_dict(self, record: PaymentRecord) -> Dict:
        payload = dict(record.payload or {})
        payload.update(
            {
                "payment_id": record.payment_id,
                "invoice_id": record.invoice_id,
                "supplier_id": record.supplier_id,
                "amount": record.amount,
                "status": record.status,
                "payment_date": record.payment_date,
            }
        )
        return payload

    def _load_project(self, session: Session, project_id: str) -> ProjectRecord | None:
        stmt = (
            select(ProjectRecord)
            .options(
                selectinload(ProjectRecord.items),
                selectinload(ProjectRecord.workflow_history),
            )
            .where(ProjectRecord.project_id == project_id)
        )
        return session.execute(stmt).scalar_one_or_none()

    def _serialize_project_items(self, results: Dict) -> List[Dict]:
        project_items = []
        categories = [
            "guest_rooms",
            "linen",
            "bathroom",
            "furniture",
            "amenities",
            "restaurant",
            "kitchen",
            "spa",
            "pool",
            "gym",
            "public_areas",
            "conference",
            "back_of_house",
        ]

        for category in categories:
            if results.get(category):
                for item in results[category]:
                    project_items.append(
                        {
                            "category": category,
                            "department": self._get_department(category),
                            "item_data": item,
                            "capex_info": {
                                "expense_type": self._get_expense_type(category),
                                "depreciation_years": self._get_depreciation_years(category),
                                "budget_code": f"{self._get_budget_code(category)}-{item.get('Item', 'ITEM')[:10].upper().replace(' ', '-')}",
                                "cost_center": self._get_department(category),
                                "budget_amount": 0,
                                "actual_amount": 0,
                                "variance": 0,
                                "approval_status": "draft",
                                "approved_by": [],
                                "approved_date": None,
                            },
                            "procurement_status": {
                                **self._default_procurement_status(item.get("Item", item.get("item", ""))),
                            },
                            "audit_trail": [],
                        }
                    )
        return project_items

    def _upsert_project_bundle(self, session: Session, project_data: Dict, items_data: List[Dict]) -> str:
        project_id = project_data.get("project_id") or self._next_project_id()
        record = self._load_project(session, project_id)

        if record is None:
            record = ProjectRecord(project_id=project_id)
            session.add(record)

        record.hotel_id = project_data.get("hotel_id") or None
        record.created_at = project_data.get("created_at") or self._get_timestamp()
        record.created_by = project_data.get("created_by", "")
        record.hotel_info = dict(project_data.get("hotel_info", {}))
        record.configuration = dict(project_data.get("configuration", {}))
        record.status = project_data.get("status", "active")
        record.review_status = project_data.get("review_status", "draft")
        record.last_modified = project_data.get("last_modified") or self._get_timestamp()
        record.last_modified_by = project_data.get("last_modified_by", project_data.get("created_by", ""))
        record.submitted_at = project_data.get("submitted_at")
        record.reviewed_at = project_data.get("reviewed_at")
        record.reviewed_by = project_data.get("reviewed_by", "")
        record.latest_review_note = project_data.get("latest_review_note", "")
        record.workspace_links = self._normalize_workspace_links(project_data.get("workspace_links", {}))

        record.workflow_history.clear()
        for entry in project_data.get("workflow_history", []):
            record.workflow_history.append(
                ProjectWorkflowHistoryRecord(
                    timestamp=entry.get("timestamp") or self._get_timestamp(),
                    status=entry.get("status", "draft"),
                    user=entry.get("user", ""),
                    note=entry.get("note", ""),
                )
            )

        if not record.workflow_history:
            record.workflow_history.append(
                ProjectWorkflowHistoryRecord(
                    timestamp=record.created_at,
                    status=record.review_status,
                    user=record.created_by or "System",
                    note="Project created",
                )
            )

        record.items.clear()
        for index, item in enumerate(items_data):
            normalized_item = self._normalize_project_item(item, project_id=project_id, item_index=index)
            record.items.append(
                ProjectItemRecord(
                    item_index=index,
                    category=normalized_item.get("category", ""),
                    department=normalized_item.get("department", ""),
                    item_data=dict(normalized_item.get("item_data", {})),
                    capex_info=dict(normalized_item.get("capex_info", {})),
                    procurement_status=dict(normalized_item.get("procurement_status", {})),
                    audit_trail=list(normalized_item.get("audit_trail", [])),
                )
            )

        session.flush()
        return project_id

    def ensure_default_admin(self, username: str, password: str, full_name: str = "System Administrator") -> bool:
        with self._session_scope() as session:
            user_count = session.scalar(select(func.count()).select_from(UserRecord)) or 0
            if user_count:
                return False

        self.save_user(
            {
                "full_name": full_name,
                "username": username or "admin",
                "password": password or "admin123",
                "role": "admin",
                "hotel_ids": [],
                "active": True,
            }
        )
        return True

    def save_hotel(self, hotel_data: Dict) -> str:
        with self._session_scope() as session:
            hotel_id = hotel_data.get("hotel_id") or self._generate_id("HOTEL")
            record = session.get(HotelRecord, hotel_id)
            now = self._get_timestamp()

            if record is None:
                record = HotelRecord(hotel_id=hotel_id, created_at=hotel_data.get("created_at") or now, updated_at=now)
                session.add(record)

            record.name = hotel_data.get("name", record.name if record else "")
            record.brand = hotel_data.get("brand", record.brand if record else "")
            record.city = hotel_data.get("city", record.city if record else "")
            record.country = hotel_data.get("country", record.country if record else "")
            record.total_rooms = hotel_data.get("total_rooms", record.total_rooms if record else 0)
            record.status = hotel_data.get("status", getattr(record, "status", "active"))
            record.notes = hotel_data.get("notes", getattr(record, "notes", ""))
            record.workspace_links = self._normalize_workspace_links(
                hotel_data.get("workspace_links", getattr(record, "workspace_links", {}))
            )
            record.updated_at = hotel_data.get("updated_at") or now
            return hotel_id

    def get_all_hotels(self) -> List[Dict]:
        with self._session_scope() as session:
            records = session.execute(select(HotelRecord).order_by(HotelRecord.name, HotelRecord.city)).scalars().all()
            return [self._hotel_to_dict(record) for record in records]

    def get_hotel(self, hotel_id: str) -> Dict:
        with self._session_scope() as session:
            record = session.get(HotelRecord, hotel_id)
            return self._hotel_to_dict(record) if record else {}

    def save_user(self, user_data: Dict) -> str:
        username = self._normalize_username(user_data.get("username"))
        if not username:
            raise ValueError("Username is required.")

        with self._session_scope() as session:
            user_id = user_data.get("user_id") or self._generate_id("USER")
            duplicate_stmt = select(UserRecord).where(UserRecord.username == username, UserRecord.user_id != user_id)
            if session.execute(duplicate_stmt).scalar_one_or_none():
                raise ValueError("Username already exists.")

            stmt = select(UserRecord).options(selectinload(UserRecord.hotel_access)).where(UserRecord.user_id == user_id)
            record = session.execute(stmt).scalar_one_or_none()
            now = self._get_timestamp()

            if record is None:
                record = UserRecord(user_id=user_id, created_at=user_data.get("created_at") or now, updated_at=now)
                session.add(record)

            raw_password = user_data.get("password", "")
            if raw_password:
                password_hash = self._hash_password(raw_password)
            elif user_data.get("password_hash"):
                password_hash = user_data.get("password_hash")
            elif record.password_hash:
                password_hash = record.password_hash
            else:
                raise ValueError("Password is required for new users.")

            record.full_name = user_data.get("full_name", record.full_name or "")
            record.username = username
            record.password_hash = password_hash
            record.role = user_data.get("role", record.role or "hotel_editor")
            record.supplier_id = user_data.get("supplier_id", record.supplier_id)
            record.email = user_data.get("email", record.email or "")
            record.active = user_data.get("active", True if record.active is None else record.active)
            record.updated_at = user_data.get("updated_at") or now

            selected_hotel_ids = sorted(set(hotel_id for hotel_id in user_data.get("hotel_ids", []) if hotel_id))
            record.hotel_access.clear()
            for hotel_id in selected_hotel_ids:
                record.hotel_access.append(UserHotelAccessRecord(hotel_id=hotel_id))

            return user_id

    def get_all_users(self) -> List[Dict]:
        with self._session_scope() as session:
            stmt = select(UserRecord).options(selectinload(UserRecord.hotel_access)).order_by(UserRecord.full_name, UserRecord.username)
            records = session.execute(stmt).scalars().all()
            return [self._user_to_dict(record) for record in records]

    def get_user(self, user_id: str) -> Dict:
        with self._session_scope() as session:
            stmt = select(UserRecord).options(selectinload(UserRecord.hotel_access)).where(UserRecord.user_id == user_id)
            record = session.execute(stmt).scalar_one_or_none()
            return self._user_to_dict(record) if record else {}

    def get_user_by_username(self, username: str) -> Dict:
        username = self._normalize_username(username)
        with self._session_scope() as session:
            stmt = select(UserRecord).options(selectinload(UserRecord.hotel_access)).where(UserRecord.username == username)
            record = session.execute(stmt).scalar_one_or_none()
            return self._user_to_dict(record) if record else {}

    def authenticate_user(self, username: str, password: str) -> Dict:
        username = self._normalize_username(username)
        with self._session_scope() as session:
            stmt = (
                select(UserRecord)
                .options(selectinload(UserRecord.hotel_access))
                .where(UserRecord.username == username, UserRecord.active.is_(True))
            )
            record = session.execute(stmt).scalar_one_or_none()
            if record and self._verify_password(password, record.password_hash):
                return self._user_to_dict(record)
        return {}

    def record_login_event(self, username: str, success: bool, user_id: str = '', role: str = '', note: str = '') -> str:
        with self._session_scope() as session:
            event_id = self._generate_id("LOGIN")
            session.add(
                LoginAuditRecord(
                    event_id=event_id,
                    timestamp=self._get_timestamp(),
                    username=self._normalize_username(username),
                    success=success,
                    user_id=user_id,
                    role=role,
                    note=note,
                )
            )
            return event_id

    def get_login_events(self, limit: int = 100, username: str = '') -> List[Dict]:
        with self._session_scope() as session:
            stmt = select(LoginAuditRecord).order_by(LoginAuditRecord.timestamp.desc())
            normalized_username = self._normalize_username(username)
            if normalized_username:
                stmt = stmt.where(LoginAuditRecord.username == normalized_username)
            stmt = stmt.limit(limit)
            records = session.execute(stmt).scalars().all()
            return [self._login_event_to_dict(record) for record in records]

    def create_notification(self, notification_data: Dict) -> str:
        with self._session_scope() as session:
            notification_id = notification_data.get("notification_id") or self._generate_id("NOTIF")
            record = session.get(NotificationRecord, notification_id)
            now = self._get_timestamp()
            if record is None:
                record = NotificationRecord(notification_id=notification_id, created_at=notification_data.get("created_at") or now)
                session.add(record)

            record.created_at = notification_data.get("created_at", record.created_at or now)
            record.created_by = notification_data.get("created_by", record.created_by or "System")
            record.notification_type = notification_data.get("notification_type", record.notification_type or "general")
            record.title = notification_data.get("title", record.title or "")
            record.message = notification_data.get("message", record.message or "")
            record.project_id = notification_data.get("project_id", record.project_id)
            record.item_index = notification_data.get("item_index", record.item_index)
            record.hotel_id = notification_data.get("hotel_id", record.hotel_id)
            record.supplier_id = notification_data.get("supplier_id", record.supplier_id)
            record.target_roles = list(notification_data.get("target_roles", record.target_roles or []))
            record.target_usernames = [self._normalize_username(value) for value in notification_data.get("target_usernames", record.target_usernames or []) if value]
            record.read_by = list(notification_data.get("read_by", record.read_by or []))
            return notification_id

    def get_notifications(self, limit: int = 100) -> List[Dict]:
        with self._session_scope() as session:
            stmt = select(NotificationRecord).order_by(NotificationRecord.created_at.desc()).limit(limit)
            records = session.execute(stmt).scalars().all()
            return [self._notification_to_dict(record) for record in records]

    def mark_notification_read(self, notification_id: str, username: str) -> bool:
        with self._session_scope() as session:
            record = session.get(NotificationRecord, notification_id)
            if record is None:
                return False
            normalized_username = self._normalize_username(username)
            read_by = list(record.read_by or [])
            if normalized_username and normalized_username not in read_by:
                read_by.append(normalized_username)
                record.read_by = read_by
            return True

    def save_project(self, project_data: Dict, results: Dict) -> str:
        project_id = project_data.get("project_id") or self._next_project_id()
        now = self._get_timestamp()
        created_by = project_data.get("created_by", "")
        review_status = project_data.get("review_status", "draft")

        project_info = {
            "project_id": project_id,
            "hotel_id": project_data.get("hotel_id", ""),
            "created_at": project_data.get("created_at") or now,
            "created_by": created_by,
            "hotel_info": {
                "brand": project_data.get("hotel_brand", ""),
                "hotel_type": project_data.get("hotel_type", ""),
                "property_name": project_data.get("property_name", ""),
                "city": project_data.get("city", ""),
                "country": project_data.get("country", ""),
                "project_name": project_data.get("project_name", ""),
                "total_rooms": project_data.get("total_rooms", 0),
                "num_floors": project_data.get("num_floors", 0),
            },
            "configuration": {
                "hotel_type": project_data.get("hotel_type", ""),
                "room_types": project_data.get("room_types", []),
                "conference_rooms": project_data.get("conference_rooms", []),
                "facilities": {
                    "restaurants": project_data.get("num_restaurants", 0),
                    "outlets": project_data.get("num_outlets", project_data.get("num_restaurants", 0)),
                    "kitchens": project_data.get("num_kitchens", 0),
                    "spa": project_data.get("has_spa", False),
                    "spa_rooms": project_data.get("spa_rooms", 0),
                    "pool": project_data.get("has_pool", False),
                    "gym": project_data.get("has_gym", False),
                    "conference": project_data.get("num_conference", 0),
                    "has_conference_spaces": project_data.get("has_conference_spaces", False),
                    "back_of_house_areas": project_data.get("num_back_of_house_areas", 0),
                },
                "linen_standards": {
                    "par_level": project_data.get("par_level", 4),
                    "reserve_stock": project_data.get("reserve_stock", 10),
                },
            },
            "status": project_data.get("status", "active"),
            "review_status": review_status,
            "last_modified": project_data.get("last_modified") or now,
            "last_modified_by": project_data.get("last_modified_by", created_by),
            "submitted_at": project_data.get("submitted_at"),
            "reviewed_at": project_data.get("reviewed_at"),
            "reviewed_by": project_data.get("reviewed_by", ""),
            "latest_review_note": project_data.get("latest_review_note", ""),
            "workspace_links": self._normalize_workspace_links(project_data.get("workspace_links", {})),
            "workflow_history": project_data.get(
                "workflow_history",
                [
                    {
                        "timestamp": now,
                        "status": review_status,
                        "user": created_by or "System",
                        "note": "Project created",
                    }
                ],
            ),
        }

        items_data = self._serialize_project_items(results)
        with self._session_scope() as session:
            return self._upsert_project_bundle(session, project_info, items_data)

    def import_project_bundle(self, project_data: Dict, items: List[Dict]) -> str:
        """Migration helper that preserves existing project IDs and item statuses."""
        with self._session_scope() as session:
            return self._upsert_project_bundle(session, project_data, items)

    def get_all_projects(self, hotel_ids: List[str] = None) -> List[Dict]:
        with self._session_scope() as session:
            stmt = select(ProjectRecord).options(selectinload(ProjectRecord.workflow_history)).order_by(ProjectRecord.created_at)
            if hotel_ids is not None:
                stmt = stmt.where(ProjectRecord.hotel_id.in_(hotel_ids))
            records = session.execute(stmt).scalars().all()
            return [self._project_to_dict(record) for record in records]

    def get_project(self, project_id: str) -> Dict:
        with self._session_scope() as session:
            record = self._load_project(session, project_id)
            return self._project_to_dict(record) if record else {}

    def get_project_items(self, project_id: str) -> List[Dict]:
        with self._session_scope() as session:
            stmt = (
                select(ProjectItemRecord)
                .where(ProjectItemRecord.project_id == project_id)
                .order_by(ProjectItemRecord.item_index)
            )
            records = session.execute(stmt).scalars().all()
            return [self._project_item_to_dict(record) for record in records]

    def delete_project(self, project_id: str) -> bool:
        with self._session_scope() as session:
            record = session.get(ProjectRecord, project_id)
            if not record:
                return False
            session.delete(record)
            return True

    def save_supplier(self, supplier_data: Dict) -> str:
        with self._session_scope() as session:
            supplier_id = supplier_data.get("supplier_id") or self._generate_id("SUP")
            record = session.get(SupplierRecord, supplier_id)
            now = self._get_timestamp()

            if record is None:
                record = SupplierRecord(
                    supplier_id=supplier_id,
                    created_at=supplier_data.get("created_at") or now,
                    updated_at=now,
                )
                session.add(record)

            record.name = supplier_data.get("name", record.name if record else "")
            record.email = supplier_data.get("email", record.email if record else "")
            record.phone = supplier_data.get("phone", record.phone if record else "")
            record.website = supplier_data.get("website", record.website if record else "")
            record.address = supplier_data.get("address", record.address if record else "")
            categories = supplier_data.get("categories")
            if categories is None:
                categories = list(record.categories or [])
            record.categories = list(categories)
            record.contact_person = supplier_data.get("contact_person", record.contact_person if record else "")
            record.notes = supplier_data.get("notes", record.notes if record else "")
            record.status = supplier_data.get("status", record.status if record else "active")
            record.workspace_links = self._normalize_workspace_links(
                supplier_data.get("workspace_links", getattr(record, "workspace_links", {}))
            )
            record.updated_at = supplier_data.get("updated_at") or now
            return supplier_id

    def get_all_suppliers(self) -> List[Dict]:
        with self._session_scope() as session:
            records = session.execute(select(SupplierRecord).order_by(SupplierRecord.name)).scalars().all()
            return [self._supplier_to_dict(record) for record in records]

    def get_supplier(self, supplier_id: str) -> Dict:
        with self._session_scope() as session:
            record = session.get(SupplierRecord, supplier_id)
            return self._supplier_to_dict(record) if record else {}

    def save_supplier_catalog(self, supplier_id: str, catalog_data: Dict, items: List[Dict]) -> str:
        with self._session_scope() as session:
            catalog_id = catalog_data.get("catalog_id") or self._generate_id("CAT")
            record = session.get(SupplierCatalogRecord, catalog_id)
            if record is None:
                record = SupplierCatalogRecord(catalog_id=catalog_id, supplier_id=supplier_id, uploaded_at=self._get_timestamp())
                session.add(record)

            record.supplier_id = supplier_id
            record.name = catalog_data.get("name", "Catalog")
            record.source_type = catalog_data.get("source_type", "")
            record.source_name = catalog_data.get("source_name", "")
            record.source_url = catalog_data.get("source_url", "")
            record.uploaded_at = catalog_data.get("uploaded_at") or record.uploaded_at or self._get_timestamp()
            record.image_dir = catalog_data.get("image_dir", "")
            record.image_count = catalog_data.get("image_count", 0)
            record.items = list(items)
            return catalog_id

    def get_supplier_catalogs(self, supplier_id: str) -> List[Dict]:
        with self._session_scope() as session:
            stmt = (
                select(SupplierCatalogRecord)
                .where(SupplierCatalogRecord.supplier_id == supplier_id)
                .order_by(SupplierCatalogRecord.uploaded_at)
            )
            records = session.execute(stmt).scalars().all()
            return [self._catalog_to_dict(record) for record in records]

    def get_all_catalog_items(self, supplier_ids: List[str]) -> List[Dict]:
        if not supplier_ids:
            return []
        with self._session_scope() as session:
            stmt = select(SupplierCatalogRecord).where(SupplierCatalogRecord.supplier_id.in_(supplier_ids))
            records = session.execute(stmt).scalars().all()
            all_items = []
            for catalog in records:
                for item in catalog.items or []:
                    all_items.append(
                        {
                            "supplier_id": catalog.supplier_id,
                            "catalog_id": catalog.catalog_id,
                            "catalog_name": catalog.name,
                            **item,
                        }
                    )
            return all_items

    def update_item_status(self, project_id: str, item_index: int, status_update: Dict):
        with self._session_scope() as session:
            stmt = select(ProjectItemRecord).where(
                ProjectItemRecord.project_id == project_id,
                ProjectItemRecord.item_index == item_index,
            )
            record = session.execute(stmt).scalar_one_or_none()
            if record is None:
                return False

            item_name = (record.item_data or {}).get("Item", (record.item_data or {}).get("item", ""))
            record.procurement_status = self._normalize_status_update(
                dict(record.procurement_status or {}),
                status_update,
                project_id=project_id,
                item_index=item_index,
                item_name=item_name,
            )

            project = session.get(ProjectRecord, project_id)
            if project is not None:
                project.last_modified = self._get_timestamp()
            return True

    def update_project_workspace_links(self, project_id: str, workspace_links: Dict, updated_by: str = "") -> bool:
        with self._session_scope() as session:
            project = session.get(ProjectRecord, project_id)
            if project is None:
                return False
            project.workspace_links = self._normalize_workspace_links(
                {
                    **(project.workspace_links or {}),
                    **(workspace_links or {}),
                }
            )
            project.last_modified = self._get_timestamp()
            if updated_by:
                project.last_modified_by = updated_by
            return True

    def add_audit_entry(self, project_id: str, item_index: int, action: str, user: str, details: dict):
        with self._session_scope() as session:
            stmt = select(ProjectItemRecord).where(
                ProjectItemRecord.project_id == project_id,
                ProjectItemRecord.item_index == item_index,
            )
            record = session.execute(stmt).scalar_one_or_none()
            if record is None:
                return False

            audit_trail = list(record.audit_trail or [])
            audit_trail.append(
                {
                    "timestamp": self._get_timestamp(),
                    "action": action,
                    "user": user,
                    "details": details,
                }
            )
            record.audit_trail = audit_trail
            return True

    def assign_project_hotel(self, project_id: str, hotel_id: str, updated_by: str = "") -> bool:
        with self._session_scope() as session:
            project = session.get(ProjectRecord, project_id)
            if project is None:
                return False

            now = self._get_timestamp()
            project.hotel_id = hotel_id or None
            project.last_modified = now
            project.last_modified_by = updated_by
            project.workflow_history.append(
                ProjectWorkflowHistoryRecord(
                    timestamp=now,
                    status="hotel_reassigned",
                    user=updated_by or "System",
                    note=hotel_id,
                )
            )
            return True

    def update_project_workflow(self, project_id: str, review_status: str, user: str, note: str = "") -> bool:
        with self._session_scope() as session:
            project = session.get(ProjectRecord, project_id)
            if project is None:
                return False

            now = self._get_timestamp()
            project.review_status = review_status
            project.last_modified = now
            project.last_modified_by = user
            project.latest_review_note = note or project.latest_review_note

            if review_status in {"submitted", "resubmitted"}:
                project.submitted_at = now
            if review_status in {"needs_correction", "approved"}:
                project.reviewed_at = now
                project.reviewed_by = user

            project.workflow_history.append(
                ProjectWorkflowHistoryRecord(
                    timestamp=now,
                    status=review_status,
                    user=user,
                    note=note,
                )
            )
            return True

    def create_purchase_order(self, po_data: Dict) -> str:
        with self._session_scope() as session:
            total_count = session.scalar(select(func.count()).select_from(PurchaseOrderRecord)) or 0
            po_id = po_data.get("po_id") or self._next_counted_id("PO", total_count)
            payload = dict(po_data)
            payload["po_id"] = po_id
            payload.setdefault("created_at", self._get_timestamp())
            payload.setdefault("status", "Draft")
            payload.setdefault("approval_history", [])

            record = session.get(PurchaseOrderRecord, po_id)
            if record is None:
                record = PurchaseOrderRecord(po_id=po_id)
                session.add(record)

            record.project_id = payload.get("project_id")
            record.supplier_id = payload.get("supplier_id")
            record.status = payload.get("status", "Draft")
            record.created_at = payload.get("created_at")
            record.updated_at = payload.get("updated_at")
            record.total_amount = float(payload.get("total_amount", 0) or 0)
            record.approval_history = list(payload.get("approval_history", []))
            record.payload = payload
            return po_id

    def get_purchase_orders(self, filters: Dict = None) -> List[Dict]:
        with self._session_scope() as session:
            stmt = select(PurchaseOrderRecord).order_by(PurchaseOrderRecord.created_at.desc())
            if filters:
                if "status" in filters:
                    stmt = stmt.where(PurchaseOrderRecord.status == filters["status"])
                if "supplier_id" in filters:
                    stmt = stmt.where(PurchaseOrderRecord.supplier_id == filters["supplier_id"])
                if "project_id" in filters:
                    stmt = stmt.where(PurchaseOrderRecord.project_id == filters["project_id"])
            records = session.execute(stmt).scalars().all()
            return [self._purchase_order_to_dict(record) for record in records]

    def get_purchase_order(self, po_id: str) -> Dict:
        with self._session_scope() as session:
            record = session.get(PurchaseOrderRecord, po_id)
            return self._purchase_order_to_dict(record) if record else {}

    def update_purchase_order_status(self, po_id: str, status: str, approver: str = None, notes: str = None) -> bool:
        with self._session_scope() as session:
            record = session.get(PurchaseOrderRecord, po_id)
            if record is None:
                return False

            now = self._get_timestamp()
            approval_history = list(record.approval_history or [])
            approval_history.append(
                {
                    "status": status,
                    "timestamp": now,
                    "approver": approver or "System",
                    "notes": notes or "",
                }
            )
            record.status = status
            record.updated_at = now
            record.approval_history = approval_history
            record.payload = self._purchase_order_to_dict(record)
            return True

    def create_invoice(self, invoice_data: Dict) -> str:
        with self._session_scope() as session:
            total_count = session.scalar(select(func.count()).select_from(InvoiceRecord)) or 0
            invoice_id = invoice_data.get("invoice_id") or self._next_counted_id("INV", total_count)
            payload = dict(invoice_data)
            payload["invoice_id"] = invoice_id
            payload.setdefault("created_at", self._get_timestamp())
            payload.setdefault("status", "Pending")
            payload.setdefault("match_status", "Unmatched")
            payload.setdefault("status_history", [])

            record = session.get(InvoiceRecord, invoice_id)
            if record is None:
                record = InvoiceRecord(invoice_id=invoice_id)
                session.add(record)

            record.po_id = payload.get("po_id")
            record.supplier_id = payload.get("supplier_id")
            record.status = payload.get("status", "Pending")
            record.match_status = payload.get("match_status", "Unmatched")
            record.created_at = payload.get("created_at")
            record.matched_at = payload.get("matched_at")
            record.paid_at = payload.get("paid_at")
            record.total_amount = float(payload.get("total_amount", 0) or 0)
            record.matching_result = dict(payload.get("matching_result", {}))
            record.payload = payload
            return invoice_id

    def get_invoice(self, invoice_id: str) -> Dict:
        with self._session_scope() as session:
            record = session.get(InvoiceRecord, invoice_id)
            return self._invoice_to_dict(record) if record else {}

    def get_invoices(self, filters: Dict = None) -> List[Dict]:
        with self._session_scope() as session:
            stmt = select(InvoiceRecord).order_by(InvoiceRecord.created_at.desc())
            if filters:
                if "status" in filters:
                    stmt = stmt.where(InvoiceRecord.status == filters["status"])
                if "po_id" in filters:
                    stmt = stmt.where(InvoiceRecord.po_id == filters["po_id"])
                if "supplier_id" in filters:
                    stmt = stmt.where(InvoiceRecord.supplier_id == filters["supplier_id"])
                if "match_status" in filters:
                    stmt = stmt.where(InvoiceRecord.match_status == filters["match_status"])
            records = session.execute(stmt).scalars().all()
            return [self._invoice_to_dict(record) for record in records]

    def match_invoice_to_po(self, invoice_id: str, po_id: str) -> Dict:
        with self._session_scope() as session:
            invoice = session.get(InvoiceRecord, invoice_id)
            po = session.get(PurchaseOrderRecord, po_id)
            if invoice is None or po is None:
                return {"success": False, "message": "Invoice or PO not found"}

            matching_result = {
                "match_type": "2-Way",
                "po_amount": po.total_amount,
                "invoice_amount": invoice.total_amount,
                "variance": abs(po.total_amount - invoice.total_amount),
                "variance_pct": 0,
                "items_matched": False,
                "amounts_matched": False,
            }

            if po.total_amount > 0:
                matching_result["variance_pct"] = (matching_result["variance"] / po.total_amount) * 100
            if matching_result["variance_pct"] <= 5:
                matching_result["amounts_matched"] = True

            invoice.po_id = po_id
            invoice.match_status = "2-Way" if matching_result["amounts_matched"] else "Mismatched"
            if matching_result["amounts_matched"] and invoice.status in {"Pending", "Submitted", ""}:
                invoice.status = "Matched"
            elif not matching_result["amounts_matched"] and invoice.status not in {"Paid", "Approved"}:
                invoice.status = "Disputed"
            invoice.matched_at = self._get_timestamp()
            invoice.matching_result = matching_result
            invoice.payload = self._invoice_to_dict(invoice)
            return {"success": True, "matching_result": matching_result}

    def update_invoice_status(self, invoice_id: str, status: str, user: str = None, notes: str = None) -> bool:
        with self._session_scope() as session:
            record = session.get(InvoiceRecord, invoice_id)
            if record is None:
                return False

            now = self._get_timestamp()
            payload = self._invoice_to_dict(record)
            status_history = list(payload.get("status_history", []))
            status_history.append(
                {
                    "status": status,
                    "timestamp": now,
                    "user": user or "System",
                    "notes": notes or "",
                }
            )

            record.status = status
            if status == "Approved":
                payload["approved_at"] = now
            elif status == "Disputed":
                payload["disputed_at"] = now
            elif status == "Paid":
                record.paid_at = now
                payload["paid_at"] = now

            payload["status_history"] = status_history
            record.payload = payload
            return True

    def create_payment(self, payment_data: Dict) -> str:
        with self._session_scope() as session:
            total_count = session.scalar(select(func.count()).select_from(PaymentRecord)) or 0
            payment_id = payment_data.get("payment_id") or self._next_counted_id("PAY", total_count)
            payload = dict(payment_data)
            payload["payment_id"] = payment_id
            payload.setdefault("payment_date", self._get_timestamp())
            payload.setdefault("status", "Completed")

            record = session.get(PaymentRecord, payment_id)
            if record is None:
                record = PaymentRecord(payment_id=payment_id)
                session.add(record)

            record.invoice_id = payload.get("invoice_id")
            record.supplier_id = payload.get("supplier_id")
            record.amount = float(payload.get("amount", 0) or 0)
            record.status = payload.get("status", "Completed")
            record.payment_date = payload.get("payment_date")
            record.payload = payload
            session.flush()

            if record.invoice_id:
                invoice = session.get(InvoiceRecord, record.invoice_id)
                if invoice is not None:
                    total_paid = session.scalar(
                        select(func.coalesce(func.sum(PaymentRecord.amount), 0)).where(PaymentRecord.invoice_id == record.invoice_id)
                    ) or 0
                    if invoice.total_amount and total_paid >= invoice.total_amount:
                        invoice.status = "Paid"
                        invoice.paid_at = record.payment_date
                    elif total_paid > 0:
                        invoice.status = "Partially Paid"
                        invoice.paid_at = None
                    invoice.payload = self._invoice_to_dict(invoice)

            return payment_id

    def get_payments(self, filters: Dict = None) -> List[Dict]:
        with self._session_scope() as session:
            stmt = select(PaymentRecord).order_by(PaymentRecord.payment_date.desc())
            if filters:
                if "invoice_id" in filters:
                    stmt = stmt.where(PaymentRecord.invoice_id == filters["invoice_id"])
                if "supplier_id" in filters:
                    stmt = stmt.where(PaymentRecord.supplier_id == filters["supplier_id"])
            records = session.execute(stmt).scalars().all()
            return [self._payment_to_dict(record) for record in records]

    def get_p2p_analytics(self) -> Dict:
        """Get Procure-to-Pay analytics."""
        pos = self.get_purchase_orders()
        invoices = self.get_invoices()
        payments = self.get_payments()

        analytics = {
            "total_pos": len(pos),
            "total_po_value": sum(po.get("total_amount", 0) for po in pos),
            "pos_by_status": {},
            "total_invoices": len(invoices),
            "total_invoice_value": sum(invoice.get("total_amount", 0) for invoice in invoices),
            "invoices_by_status": {},
            "total_payments": len(payments),
            "total_paid": sum(payment.get("amount", 0) for payment in payments),
            "matching_stats": {
                "3-Way": 0,
                "2-Way": 0,
                "Unmatched": 0,
                "Mismatched": 0,
            },
            "avg_cycle_time": 0,
            "outstanding_payables": 0,
        }

        for po in pos:
            status = po.get("status", "Unknown")
            analytics["pos_by_status"][status] = analytics["pos_by_status"].get(status, 0) + 1

        for invoice in invoices:
            status = invoice.get("status", "Unknown")
            analytics["invoices_by_status"][status] = analytics["invoices_by_status"].get(status, 0) + 1
            match_status = invoice.get("match_status", "Unmatched")
            analytics["matching_stats"][match_status] = analytics["matching_stats"].get(match_status, 0) + 1

        analytics["outstanding_payables"] = analytics["total_invoice_value"] - analytics["total_paid"]
        return analytics
