from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, MetaData, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


metadata = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)


class Base(DeclarativeBase):
    metadata = metadata


json_type = JSON().with_variant(JSONB, "postgresql")


class HotelRecord(Base):
    __tablename__ = "hotels"

    hotel_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    brand: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    city: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    country: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    total_rooms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    workspace_links: Mapped[dict] = mapped_column(json_type, default=dict, nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(40), nullable=False)

    projects: Mapped[list["ProjectRecord"]] = relationship(back_populates="hotel")
    user_access: Mapped[list["UserHotelAccessRecord"]] = relationship(
        back_populates="hotel",
        cascade="all, delete-orphan",
    )


class UserRecord(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="hotel_editor", nullable=False)
    supplier_id: Mapped[str | None] = mapped_column(ForeignKey("suppliers.supplier_id", ondelete="SET NULL"))
    email: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(40), nullable=False)

    hotel_access: Mapped[list["UserHotelAccessRecord"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    supplier: Mapped["SupplierRecord | None"] = relationship(back_populates="users")


class UserHotelAccessRecord(Base):
    __tablename__ = "user_hotel_access"
    __table_args__ = (UniqueConstraint("user_id", "hotel_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    hotel_id: Mapped[str] = mapped_column(ForeignKey("hotels.hotel_id", ondelete="CASCADE"), nullable=False)

    user: Mapped["UserRecord"] = relationship(back_populates="hotel_access")
    hotel: Mapped["HotelRecord"] = relationship(back_populates="user_access")


class ProjectRecord(Base):
    __tablename__ = "projects"

    project_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    hotel_id: Mapped[str | None] = mapped_column(ForeignKey("hotels.hotel_id", ondelete="SET NULL"))
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
    created_by: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    hotel_info: Mapped[dict] = mapped_column(json_type, default=dict, nullable=False)
    configuration: Mapped[dict] = mapped_column(json_type, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    review_status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    last_modified: Mapped[str] = mapped_column(String(40), nullable=False)
    last_modified_by: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    submitted_at: Mapped[str | None] = mapped_column(String(40))
    reviewed_at: Mapped[str | None] = mapped_column(String(40))
    reviewed_by: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    latest_review_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    workspace_links: Mapped[dict] = mapped_column(json_type, default=dict, nullable=False)

    hotel: Mapped["HotelRecord | None"] = relationship(back_populates="projects")
    items: Mapped[list["ProjectItemRecord"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectItemRecord.item_index",
    )
    workflow_history: Mapped[list["ProjectWorkflowHistoryRecord"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectWorkflowHistoryRecord.id",
    )


class ProjectWorkflowHistoryRecord(Base):
    __tablename__ = "project_workflow_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    timestamp: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    user: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)

    project: Mapped["ProjectRecord"] = relationship(back_populates="workflow_history")


class ProjectItemRecord(Base):
    __tablename__ = "project_items"
    __table_args__ = (UniqueConstraint("project_id", "item_index"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False)
    item_index: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    department: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    item_data: Mapped[dict] = mapped_column(json_type, default=dict, nullable=False)
    capex_info: Mapped[dict] = mapped_column(json_type, default=dict, nullable=False)
    procurement_status: Mapped[dict] = mapped_column(json_type, default=dict, nullable=False)
    audit_trail: Mapped[list] = mapped_column(json_type, default=list, nullable=False)

    project: Mapped["ProjectRecord"] = relationship(back_populates="items")


class SupplierRecord(Base):
    __tablename__ = "suppliers"

    supplier_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    email: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    phone: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    website: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    address: Mapped[str] = mapped_column(Text, default="", nullable=False)
    categories: Mapped[list] = mapped_column(json_type, default=list, nullable=False)
    contact_person: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    workspace_links: Mapped[dict] = mapped_column(json_type, default=dict, nullable=False)
    updated_at: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)

    catalogs: Mapped[list["SupplierCatalogRecord"]] = relationship(
        back_populates="supplier",
        cascade="all, delete-orphan",
        order_by="SupplierCatalogRecord.uploaded_at",
    )
    users: Mapped[list["UserRecord"]] = relationship(back_populates="supplier")


class SupplierCatalogRecord(Base):
    __tablename__ = "supplier_catalogs"

    catalog_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.supplier_id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    source_url: Mapped[str] = mapped_column(Text, default="", nullable=False)
    uploaded_at: Mapped[str] = mapped_column(String(40), nullable=False)
    image_dir: Mapped[str] = mapped_column(Text, default="", nullable=False)
    image_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items: Mapped[list] = mapped_column(json_type, default=list, nullable=False)

    supplier: Mapped["SupplierRecord"] = relationship(back_populates="catalogs")


class PurchaseOrderRecord(Base):
    __tablename__ = "purchase_orders"

    po_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.project_id", ondelete="SET NULL"))
    supplier_id: Mapped[str | None] = mapped_column(ForeignKey("suppliers.supplier_id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(50), default="Draft", nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
    updated_at: Mapped[str | None] = mapped_column(String(40))
    total_amount: Mapped[float] = mapped_column(default=0.0, nullable=False)
    approval_history: Mapped[list] = mapped_column(json_type, default=list, nullable=False)
    payload: Mapped[dict] = mapped_column(json_type, default=dict, nullable=False)


class InvoiceRecord(Base):
    __tablename__ = "invoices"

    invoice_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    po_id: Mapped[str | None] = mapped_column(ForeignKey("purchase_orders.po_id", ondelete="SET NULL"))
    supplier_id: Mapped[str | None] = mapped_column(ForeignKey("suppliers.supplier_id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(50), default="Pending", nullable=False)
    match_status: Mapped[str] = mapped_column(String(50), default="Unmatched", nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
    matched_at: Mapped[str | None] = mapped_column(String(40))
    paid_at: Mapped[str | None] = mapped_column(String(40))
    total_amount: Mapped[float] = mapped_column(default=0.0, nullable=False)
    matching_result: Mapped[dict] = mapped_column(json_type, default=dict, nullable=False)
    payload: Mapped[dict] = mapped_column(json_type, default=dict, nullable=False)


class PaymentRecord(Base):
    __tablename__ = "payments"

    payment_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    invoice_id: Mapped[str | None] = mapped_column(ForeignKey("invoices.invoice_id", ondelete="SET NULL"))
    supplier_id: Mapped[str | None] = mapped_column(ForeignKey("suppliers.supplier_id", ondelete="SET NULL"))
    amount: Mapped[float] = mapped_column(default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="Completed", nullable=False)
    payment_date: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict] = mapped_column(json_type, default=dict, nullable=False)


class LoginAuditRecord(Base):
    __tablename__ = "login_audit"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    timestamp: Mapped[str] = mapped_column(String(40), nullable=False)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)


class NotificationRecord(Base):
    __tablename__ = "notifications"

    notification_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
    created_by: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    notification_type: Mapped[str] = mapped_column(String(50), default="general", nullable=False)
    title: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    project_id: Mapped[str | None] = mapped_column(String(64))
    item_index: Mapped[int | None] = mapped_column(Integer)
    hotel_id: Mapped[str | None] = mapped_column(ForeignKey("hotels.hotel_id", ondelete="SET NULL"))
    supplier_id: Mapped[str | None] = mapped_column(ForeignKey("suppliers.supplier_id", ondelete="SET NULL"))
    target_roles: Mapped[list] = mapped_column(json_type, default=list, nullable=False)
    target_usernames: Mapped[list] = mapped_column(json_type, default=list, nullable=False)
    read_by: Mapped[list] = mapped_column(json_type, default=list, nullable=False)
