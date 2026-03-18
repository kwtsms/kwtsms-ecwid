"""SMS template management API endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.database import execute_query, fetch_all, fetch_one
from app.models import APIResponse, TemplateCreate, TemplateResponse, TemplateUpdate
from app.services.sms import render_template
from app.utils.logger import get_logger
from app.utils.message import count_pages, detect_language

router = APIRouter()
logger = get_logger("templates")

_VALID_EVENT_TYPES = {"order.created", "order.payment_updated", "order.fulfillment_updated"}
_VALID_LANGS = {"en", "ar"}


class PreviewRequest(BaseModel):
    body: str
    lang: str = "auto"

# Default templates seeded on first install
_DEFAULT_TEMPLATES = [
    ("order.created", "en", "Hi {customer_name}, your order #{order_id} has been received. Total: {total} {currency}. Thank you for shopping at {store_name}."),
    ("order.created", "ar", "مرحبا {customer_name}, تم استلام طلبك رقم #{order_id}. المجموع: {total} {currency}. شكرا لتسوقك في {store_name}."),
    ("order.payment_updated", "en", "Order #{order_id} payment status: {status}. Thank you, {store_name}."),
    ("order.payment_updated", "ar", "طلب رقم #{order_id} حالة الدفع: {status}. شكرا, {store_name}."),
    ("order.fulfillment_updated", "en", "Order #{order_id} has been {status}. Tracking: {tracking}. {store_name}"),
    ("order.fulfillment_updated", "ar", "طلب رقم #{order_id} تم {status}. التتبع: {tracking}. {store_name}"),
]


@router.get("")
async def list_templates(event_type: str | None = None, lang: str | None = None) -> dict:
    """List templates with optional filters."""
    query = "SELECT id, event_type, lang, body, is_active, updated_at FROM templates WHERE 1=1"
    params = []

    if event_type:
        query += " AND event_type = ?"
        params.append(event_type)
    if lang:
        query += " AND lang = ?"
        params.append(lang)

    query += " ORDER BY event_type, lang"
    rows = await fetch_all(query, tuple(params))

    templates = [
        TemplateResponse(
            id=r["id"],
            event_type=r["event_type"],
            lang=r["lang"],
            body=r["body"],
            is_active=bool(r["is_active"]),
            updated_at=r["updated_at"] or "",
        )
        for r in rows
    ]
    return {"templates": [t.model_dump() for t in templates]}


@router.get("/{template_id}")
async def get_template(template_id: int) -> TemplateResponse | APIResponse:
    """Get a single template by ID."""
    row = await fetch_one(
        "SELECT id, event_type, lang, body, is_active, updated_at FROM templates WHERE id = ?",
        (template_id,),
    )
    if not row:
        return APIResponse(success=False, message="Template not found")
    return TemplateResponse(
        id=row["id"],
        event_type=row["event_type"],
        lang=row["lang"],
        body=row["body"],
        is_active=bool(row["is_active"]),
        updated_at=row["updated_at"] or "",
    )


@router.post("")
async def create_template(body: TemplateCreate) -> APIResponse:
    """Create a new template."""
    if body.event_type not in _VALID_EVENT_TYPES:
        return APIResponse(success=False, message=f"Invalid event type. Must be one of: {', '.join(_VALID_EVENT_TYPES)}")
    if body.lang not in _VALID_LANGS:
        return APIResponse(success=False, message="Language must be 'en' or 'ar'")

    try:
        await execute_query(
            "INSERT INTO templates (event_type, lang, body, updated_at) VALUES (?, ?, ?, datetime('now'))",
            (body.event_type, body.lang, body.body),
        )
        await logger.info(f"Template created: {body.event_type}/{body.lang}")
        return APIResponse(success=True, message="Template created")
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            return APIResponse(success=False, message=f"Template already exists for {body.event_type}/{body.lang}")
        await logger.error(f"Failed to create template: {e}")
        return APIResponse(success=False, message="Failed to create template")


@router.put("/{template_id}")
async def update_template(template_id: int, body: TemplateUpdate) -> APIResponse:
    """Update a template."""
    existing = await fetch_one("SELECT id FROM templates WHERE id = ?", (template_id,))
    if not existing:
        return APIResponse(success=False, message="Template not found")

    updates = []
    params = []
    if body.body is not None:
        if not body.body.strip():
            return APIResponse(success=False, message="Template body cannot be empty")
        updates.append("body = ?")
        params.append(body.body)
    if body.is_active is not None:
        updates.append("is_active = ?")
        params.append(1 if body.is_active else 0)

    if not updates:
        return APIResponse(success=False, message="No fields to update")

    updates.append("updated_at = datetime('now')")
    params.append(template_id)

    await execute_query(f"UPDATE templates SET {', '.join(updates)} WHERE id = ?", tuple(params))
    await logger.info(f"Template {template_id} updated")
    return APIResponse(success=True, message="Template updated")


@router.delete("/{template_id}")
async def delete_template(template_id: int) -> APIResponse:
    """Delete a template."""
    await execute_query("DELETE FROM templates WHERE id = ?", (template_id,))
    return APIResponse(success=True, message="Template deleted")


@router.post("/preview")
async def preview_template(body: PreviewRequest) -> dict:
    """Render a template with sample data and return preview with page count."""
    template_body = body.body
    lang = body.lang

    # Sample data for preview
    sample_order = {
        "order_number": "12345",
        "customer_name": "Ahmed",
        "total": "25.500",
        "currency": "KWD",
        "payment_status": "PAID",
        "fulfillment_status": "SHIPPED",
        "tracking_number": "KW123456",
        "date": "2026-03-17",
    }

    rendered = render_template(template_body, sample_order, store_name="My Store")
    if lang == "auto":
        lang = detect_language(rendered)
    pages, remaining = count_pages(rendered, lang)

    return {
        "preview": rendered,
        "pages": pages,
        "chars_remaining": remaining,
        "total_chars": len(rendered),
        "encoding": "unicode" if lang == "ar" else "gsm7",
    }


@router.post("/seed")
async def seed_default_templates() -> APIResponse:
    """Seed default templates if none exist. Idempotent."""
    existing = await fetch_one("SELECT COUNT(*) as cnt FROM templates")
    if existing and existing["cnt"] > 0:
        return APIResponse(success=True, message=f"Templates already exist ({existing['cnt']} found), skipping seed")

    count = 0
    for event_type, lang, body in _DEFAULT_TEMPLATES:
        try:
            await execute_query(
                "INSERT INTO templates (event_type, lang, body, updated_at) VALUES (?, ?, ?, datetime('now'))",
                (event_type, lang, body),
            )
            count += 1
        except Exception:
            pass  # Skip duplicates

    await logger.info(f"Seeded {count} default templates")
    return APIResponse(success=True, message=f"Seeded {count} templates")
