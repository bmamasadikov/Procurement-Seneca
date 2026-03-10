"""In-app notifications and email delivery for SENPRO.

Usage in app.py (after auth imports):

    from notification_utils import (
        get_user_notifications, show_notification_center,
        _create_notification,
        _notify_project_workflow, _notify_item_review,
        _notify_purchase_order_status, _notify_invoice_status,
        _notify_payment_recorded,
        _send_email_smtp, _get_smtp_config,
    )

Once you add those imports, delete the duplicate definitions in app.py.
"""

import logging
import smtplib
from concurrent.futures import ThreadPoolExecutor
from email.message import EmailMessage
from typing import Dict, List

import streamlit as st


_EMAIL_LOGGER = logging.getLogger(__name__)
_EMAIL_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="senpro-email")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_db():
    from database_factory import get_database
    return get_database()


def _get_secret_section(section_name: str) -> Dict:
    try:
        return dict(st.secrets.get(section_name, {}))
    except Exception:
        return {}


def _get_current_username() -> str:
    from auth import get_current_username
    return get_current_username()


def _get_current_role() -> str:
    from auth import get_current_role
    return get_current_role()


def _get_actor_name() -> str:
    from auth import get_actor_name
    return get_actor_name()


def _get_current_supplier_id() -> str:
    from auth import get_current_supplier_id
    return get_current_supplier_id()


def _user_can_access_hotel(hotel_id: str) -> bool:
    from auth import user_can_access_hotel
    return user_can_access_hotel(hotel_id)


# ---------------------------------------------------------------------------
# SMTP
# ---------------------------------------------------------------------------

def _get_smtp_config() -> Dict:
    """Return normalized SMTP configuration from Streamlit secrets."""
    config = _get_secret_section("smtp")
    if not config:
        return {}
    return {
        "host": config.get("host") or config.get("server", ""),
        "port": int(config.get("port", 587) or 587),
        "username": config.get("username", ""),
        "password": config.get("password", ""),
        "from_email": config.get("from_email") or config.get("username", ""),
        "use_tls": config.get("use_tls", True),
    }


def _send_email_smtp(smtp_config: Dict, to_email: str, subject: str, body: str) -> str:
    """Send a plain-text email via SMTP. Returns 'sent' on success."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = smtp_config.get("from_email") or smtp_config.get("username")
    msg["To"] = to_email
    msg.set_content(body)

    with smtplib.SMTP(smtp_config.get("host") or smtp_config.get("server"), smtp_config.get("port", 587)) as server:
        if smtp_config.get("use_tls", True):
            server.starttls()
        server.login(smtp_config.get("username"), smtp_config.get("password"))
        server.send_message(msg)

    return "sent"


def queue_email_smtp(smtp_config: Dict, to_email: str, subject: str, body: str):
    """Queue an SMTP send so the Streamlit UI does not block on network IO."""
    def _send():
        try:
            _send_email_smtp(smtp_config, to_email, subject, body)
        except Exception:
            _EMAIL_LOGGER.exception("Failed to send email to %s", to_email)

    return _EMAIL_EXECUTOR.submit(_send)


def _get_notification_email_recipients(
    project: Dict,
    target_roles: List[str],
    target_usernames: List[str],
    supplier_id: str,
) -> List[str]:
    """Collect email addresses for in-app notification recipients."""
    db = _get_db()
    recipients: set = set()
    project = project or {}
    target_roles = set(target_roles or [])
    target_usernames = {v.lower() for v in (target_usernames or []) if v}
    hotel_id = project.get("hotel_id", "")

    if supplier_id:
        supplier = db.get_supplier(supplier_id)
        if supplier.get("email"):
            recipients.add(supplier["email"])

    for user in db.get_all_users():
        if not user.get("active", True) or not user.get("email"):
            continue
        username = user.get("username", "").lower()
        role = user.get("role", "")
        hotel_ids = set(user.get("hotel_ids", []))

        username_match = username in target_usernames if target_usernames else False
        role_match = role in target_roles if target_roles else False
        hotel_match = (
            not hotel_id
            or role in {"admin", "portfolio_manager"}
            or hotel_id in hotel_ids
        )

        if username_match or (role_match and hotel_match):
            recipients.add(user["email"])

    return sorted(recipients)


def _send_notification_emails(
    title: str,
    message: str,
    project: Dict,
    target_roles: List[str],
    target_usernames: List[str],
    supplier_id: str,
) -> None:
    """Send email copies of in-app notifications when SMTP is configured."""
    smtp_config = _get_smtp_config()
    if not smtp_config.get("host"):
        return
    for email in _get_notification_email_recipients(project, target_roles, target_usernames, supplier_id):
        queue_email_smtp(smtp_config, email, title, message)


# ---------------------------------------------------------------------------
# Notification routing
# ---------------------------------------------------------------------------

def _notification_matches_user(notification: Dict) -> bool:
    """Return True if this notification should be visible to the current session user."""
    username = _get_current_username()
    role = _get_current_role()
    hotel_id = notification.get("hotel_id")
    supplier_id = notification.get("supplier_id")
    target_usernames = [v.lower() for v in notification.get("target_usernames", []) if v]
    target_roles = notification.get("target_roles", [])

    if username and username.lower() in target_usernames:
        return True
    if target_roles and role not in target_roles:
        return False
    if role == "supplier":
        current_supplier_id = _get_current_supplier_id()
        return not supplier_id or supplier_id == current_supplier_id
    if hotel_id:
        return _user_can_access_hotel(hotel_id)
    return bool(target_roles) or not target_usernames


def get_user_notifications(limit: int = 25, unread_only: bool = False) -> List[Dict]:
    """Visible notifications for the current session user."""
    username = _get_current_username().lower()
    notifications = [
        n for n in _get_db().get_notifications(limit=200)
        if _notification_matches_user(n)
    ]
    if unread_only:
        notifications = [
            n for n in notifications
            if username not in [v.lower() for v in n.get("read_by", [])]
        ]
    return notifications[:limit]


def _create_notification(
    title: str,
    message: str,
    notification_type: str,
    project: Dict = None,
    item_index: int = None,
    target_roles: List[str] = None,
    target_usernames: List[str] = None,
    supplier_id: str = "",
) -> None:
    """Persist an in-app notification and optionally email stakeholders."""
    project = project or {}
    target_roles = target_roles or []
    target_usernames = target_usernames or []
    _get_db().create_notification({
        "created_by": _get_actor_name(),
        "notification_type": notification_type,
        "title": title,
        "message": message,
        "project_id": project.get("project_id", ""),
        "item_index": item_index,
        "hotel_id": project.get("hotel_id", ""),
        "supplier_id": supplier_id,
        "target_roles": target_roles,
        "target_usernames": target_usernames,
    })
    _send_notification_emails(title, message, project, target_roles, target_usernames, supplier_id)


# ---------------------------------------------------------------------------
# Domain-specific notification helpers
# ---------------------------------------------------------------------------

def _notify_project_workflow(project: Dict, workflow_status: str, note: str) -> None:
    hotel_name = project.get("hotel_info", {}).get("property_name", "Project")
    project_id = project.get("project_id", "")
    note_text = f" Note: {note}" if note else ""
    actor = _get_actor_name()

    if workflow_status in {"submitted", "resubmitted"}:
        _create_notification(
            title=f"Project Submitted: {hotel_name}",
            message=f"{project_id} was submitted for review by {actor}.{note_text}",
            notification_type="project_submission",
            project=project,
            target_roles=["admin", "portfolio_manager", "hotel_manager"],
        )
    elif workflow_status == "needs_correction":
        _create_notification(
            title=f"Correction Requested: {hotel_name}",
            message=f"{project_id} requires correction.{note_text}",
            notification_type="project_correction",
            project=project,
            target_roles=["hotel_editor", "hotel_manager"],
        )
    elif workflow_status == "approved":
        _create_notification(
            title=f"Project Approved: {hotel_name}",
            message=f"{project_id} was approved by {actor}.{note_text}",
            notification_type="project_approval",
            project=project,
            target_roles=["hotel_editor", "hotel_manager"],
        )


def _notify_item_review(project: Dict, item_name: str, item_index: int, review_status: str, note: str) -> None:
    note_text = f" Note: {note}" if note else ""
    actor = _get_actor_name()

    if review_status == "needs_correction":
        _create_notification(
            title=f"Item Correction Requested: {item_name}",
            message=f"{item_name} in project {project.get('project_id', '')} requires correction.{note_text}",
            notification_type="item_correction",
            project=project,
            item_index=item_index,
            target_roles=["hotel_editor", "hotel_manager"],
        )
    elif review_status == "corrected":
        _create_notification(
            title=f"Item Corrected: {item_name}",
            message=f"{item_name} was corrected by {actor}.{note_text}",
            notification_type="item_corrected",
            project=project,
            item_index=item_index,
            target_roles=["admin", "portfolio_manager", "hotel_manager"],
        )
    elif review_status == "approved":
        _create_notification(
            title=f"Item Approved: {item_name}",
            message=f"{item_name} was approved by {actor}.{note_text}",
            notification_type="item_approved",
            project=project,
            item_index=item_index,
            target_roles=["hotel_editor", "hotel_manager"],
        )


def _notify_purchase_order_status(project: Dict, po: Dict, status: str, note: str = "") -> None:
    po_id = po.get("po_id", "")
    note_text = f" Note: {note}" if note else ""
    actor = _get_actor_name()

    _create_notification(
        title=f"PO Update: {po_id}",
        message=f"PO {po_id} is now {status} by {actor}.{note_text}",
        notification_type="purchase_order",
        project=project,
        target_roles=["admin", "portfolio_manager", "hotel_manager"],
    )
    if po.get("supplier_id"):
        _create_notification(
            title=f"Purchase Order {status}: {po_id}",
            message=(
                f"{po_id} for {project.get('hotel_info', {}).get('property_name', 'hotel')}"
                f" is now {status}.{note_text}"
            ),
            notification_type="purchase_order_supplier",
            project=project,
            supplier_id=po.get("supplier_id"),
        )


def _notify_invoice_status(project: Dict, invoice: Dict, status: str, note: str = "") -> None:
    invoice_id = invoice.get("invoice_id", "")
    note_text = f" Note: {note}" if note else ""
    _create_notification(
        title=f"Invoice Update: {invoice_id}",
        message=f"Invoice {invoice_id} is now {status} by {_get_actor_name()}.{note_text}",
        notification_type="invoice",
        project=project,
        target_roles=["admin", "portfolio_manager", "hotel_manager"],
    )


def _notify_payment_recorded(project: Dict, payment: Dict, invoice: Dict) -> None:
    payment_id = payment.get("payment_id", "")
    amount = float(payment.get("amount", 0) or 0)
    note = f"Payment {payment_id} recorded for {invoice.get('invoice_id', '')}: ${amount:,.2f}."

    _create_notification(
        title=f"Payment Recorded: {payment_id}",
        message=note,
        notification_type="payment",
        project=project,
        target_roles=["admin", "portfolio_manager", "hotel_manager"],
    )
    if invoice.get("supplier_id"):
        _create_notification(
            title=f"Payment Recorded: {payment_id}",
            message=note,
            notification_type="payment_supplier",
            project=project,
            supplier_id=invoice.get("supplier_id"),
        )


# ---------------------------------------------------------------------------
# Sidebar notification center
# ---------------------------------------------------------------------------

def show_notification_center() -> None:
    """Render the collapsible notification center in the sidebar."""
    db = _get_db()
    all_notifications = get_user_notifications(limit=10, unread_only=False)
    unread_count = sum(
        1 for n in all_notifications
        if _get_current_username().lower() not in [v.lower() for v in n.get("read_by", [])]
    )

    st.markdown("### Notifications")
    st.caption(f"Unread: {unread_count}")

    if not all_notifications:
        st.caption("No notifications.")
        return

    for notification in all_notifications[:5]:
        username = _get_current_username().lower()
        unread = username not in [v.lower() for v in notification.get("read_by", [])]
        prefix = "Unread" if unread else "Seen"
        with st.expander(f"{prefix}: {notification.get('title', 'Notification')}", expanded=False):
            st.caption(notification.get("created_at", "")[:19].replace("T", " "))
            st.write(notification.get("message", ""))
            if unread:
                if st.button("Mark Read", key=f"notif_read_{notification['notification_id']}"):
                    db.mark_notification_read(notification["notification_id"], _get_current_username())
                    st.rerun()
