"""SMS processing orchestration: template rendering, normalization, sending."""

import json

from app.database import fetch_one, get_setting, set_setting
from app.services.encryption import decrypt
from app.services.kwtsms import KwtSMSClient
from app.utils.logger import get_logger

logger = get_logger("sms")


async def _get_store_kwtsms_client() -> KwtSMSClient | None:
    """Create a KwtSMSClient from stored credentials. Returns None if not configured."""
    username_enc = await get_setting("kwtsms_username")
    password_enc = await get_setting("kwtsms_password")

    if not username_enc or not password_enc:
        return None

    try:
        username = decrypt(username_enc)
        password = decrypt(password_enc)
    except ValueError:
        await logger.error("Failed to decrypt kwtSMS credentials")
        return None

    return KwtSMSClient(username, password)


async def _get_integration_config(event_type: str) -> dict | None:
    """Load integration config for an event type from settings."""
    raw = await get_setting(f"integration_{event_type}")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


async def _get_template(event_type: str, lang: str) -> str | None:
    """Load the active template body for an event type and language."""
    row = await fetch_one(
        "SELECT body FROM templates WHERE event_type = ? AND lang = ? AND is_active = 1",
        (event_type, lang),
    )
    return row["body"] if row else None


def render_template(template_body: str, order: dict, store_name: str = "") -> str:
    """Replace placeholders in a template with order data.

    Supported placeholders: {order_id}, {customer_name}, {total},
    {status}, {tracking}, {store_name}, {currency}, {date}.
    """
    placeholders = {
        "{order_id}": str(order.get("order_number", order.get("orderNumber", ""))),
        "{customer_name}": order.get("customer_name", order.get("shippingPerson", {}).get("name", "Customer")),
        "{total}": str(order.get("total", "")),
        "{currency}": order.get("currency", ""),
        "{status}": order.get("payment_status", order.get("fulfillment_status", "")),
        "{tracking}": order.get("tracking_number", order.get("trackingNumber", "")),
        "{store_name}": store_name or order.get("store_name", ""),
        "{date}": order.get("createDate", order.get("date", "")),
    }

    result = template_body
    for key, value in placeholders.items():
        result = result.replace(key, str(value) if value else "")

    return result


async def _log_sms(event_type: str, recipient: str, message: str, template_key: str, result: dict) -> None:
    """Write an entry to the sms_log table."""
    from app.database import execute_query

    status = "sent" if result.get("success") else "failed"
    if result.get("test"):
        status = "test"

    await execute_query(
        "INSERT INTO sms_log (event_type, recipient, message, template_key, status, "
        "api_response, msg_id, points_charged, balance_after) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            event_type,
            recipient,
            message,
            template_key,
            status,
            json.dumps(result),
            result.get("msg_id", ""),
            result.get("points_charged", 0),
            result.get("balance_after", 0),
        ),
    )


async def send_notification(phone: str, message: str, event_type: str, template_key: str) -> dict:
    """Send a single SMS notification through the full pipeline."""
    client = await _get_store_kwtsms_client()
    if not client:
        await logger.error("kwtSMS client not configured, skipping send")
        return {"success": False, "error": "Gateway not configured"}

    sender_id = await get_setting("kwtsms_sender_id") or ""
    if not sender_id:
        await logger.error("No Sender ID configured, skipping send")
        return {"success": False, "error": "No Sender ID configured"}

    test_mode = (await get_setting("test_mode") or "1") == "1"

    try:
        result = await client.send(phone, message, sender_id, test=test_mode)
        await _log_sms(event_type, phone, message, template_key, result)
        return result
    except Exception as e:
        await logger.error(f"Send failed: {e}")
        error_result = {"success": False, "error": str(e)}
        await _log_sms(event_type, phone, message, template_key, error_result)
        return error_result
    finally:
        await client.close()


async def process_order_created(order: dict, store_name: str = "") -> list[dict]:
    """Process an order.created event. Send SMS to customer and/or admin."""
    config = await _get_integration_config("order.created")
    if not config or not config.get("enabled", True):
        await logger.info("order.created is disabled, skipping")
        return []

    lang = await get_setting("default_language") or "en"
    template_body = await _get_template("order.created", lang)
    if not template_body:
        await logger.warning(f"No active template for order.created/{lang}")
        return []

    rendered = render_template(template_body, order, store_name)
    recipient_type = config.get("recipient", "both")
    results = []

    # Send to customer
    if recipient_type in ("customer", "both"):
        customer_phone = order.get("customer_phone", "")
        if customer_phone:
            result = await send_notification(customer_phone, rendered, "order.created", f"order.created_{lang}")
            results.append(result)
        else:
            await logger.warning("No customer phone found for order.created")

    # Send to admin
    if recipient_type in ("admin", "both"):
        admin_phones_raw = await get_setting("admin_phones") or ""
        for phone in [p.strip() for p in admin_phones_raw.split(",") if p.strip()]:
            result = await send_notification(phone, rendered, "order.created", f"order.created_{lang}")
            results.append(result)

    return results


async def process_order_updated(order: dict, event_data: dict | None = None, store_name: str = "") -> list[dict]:
    """Process an order.updated event. Detect payment or fulfillment changes."""
    results = []
    event_data = event_data or {}

    # Determine what changed
    new_payment = event_data.get("newPaymentStatus", "")
    old_payment = event_data.get("oldPaymentStatus", "")
    new_fulfillment = event_data.get("newFulfillmentStatus", "")
    old_fulfillment = event_data.get("oldFulfillmentStatus", "")

    lang = await get_setting("default_language") or "en"

    # Payment status changed
    if new_payment and new_payment != old_payment:
        config = await _get_integration_config("order.payment_updated")
        if config and config.get("enabled", True):
            template_body = await _get_template("order.payment_updated", lang)
            if template_body:
                order["payment_status"] = new_payment
                rendered = render_template(template_body, order, store_name)
                customer_phone = order.get("customer_phone", "")
                if customer_phone:
                    result = await send_notification(
                        customer_phone, rendered, "order.payment_updated", f"order.payment_updated_{lang}"
                    )
                    results.append(result)

    # Fulfillment status changed
    if new_fulfillment and new_fulfillment != old_fulfillment:
        config = await _get_integration_config("order.fulfillment_updated")
        if config and config.get("enabled", True):
            # Check if this specific status is enabled
            enabled_statuses = config.get("fulfillment_statuses", [])
            if not enabled_statuses or new_fulfillment in enabled_statuses:
                template_body = await _get_template("order.fulfillment_updated", lang)
                if template_body:
                    order["fulfillment_status"] = new_fulfillment
                    rendered = render_template(template_body, order, store_name)
                    customer_phone = order.get("customer_phone", "")
                    if customer_phone:
                        result = await send_notification(
                            customer_phone, rendered, "order.fulfillment_updated", f"order.fulfillment_updated_{lang}"
                        )
                        results.append(result)

    return results
