"""Ecwid webhook event handler."""

import asyncio

from fastapi import APIRouter, Request, Response

from app.config import get_settings
from app.database import fetch_one, get_setting
from app.models import EcwidWebhookPayload
from app.services.ecwid import EcwidClient, verify_webhook_signature
from app.services.sms import process_order_created, process_order_updated
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger("webhook")

# Track processed event IDs to deduplicate
_processed_events: set[str] = set()
_MAX_PROCESSED_CACHE = 1000


async def _process_order_event(payload: EcwidWebhookPayload) -> None:
    """Process an order webhook event asynchronously."""
    try:
        # Get stored Ecwid credentials
        access_token = await get_setting("ecwid_access_token")
        if not access_token:
            await logger.warning("No Ecwid access token configured, skipping webhook")
            return

        from app.services.encryption import decrypt

        try:
            token = decrypt(access_token)
        except ValueError:
            await logger.error("Failed to decrypt Ecwid access token")
            return

        # Fetch order details from Ecwid
        ecwid = EcwidClient(payload.storeId, token)
        try:
            order_raw = await ecwid.get_order(payload.entityId)
            order = ecwid.extract_order_data(order_raw)
        except Exception as e:
            await logger.error(f"Failed to fetch order {payload.entityId}: {e}")
            return
        finally:
            await ecwid.close()

        # Get store name
        store_name = await get_setting("store_name") or ""

        # Process based on event type
        if payload.eventType == "order.created":
            await process_order_created(order, store_name)
        elif payload.eventType == "order.updated":
            await process_order_updated(order, payload.data, store_name)
        else:
            await logger.info(f"Unhandled event type: {payload.eventType}")

    except Exception as e:
        await logger.error(f"Webhook processing error: {e}", {"event_id": payload.eventId})


@router.post("/ecwid")
async def handle_ecwid_webhook(request: Request) -> Response:
    """Receive Ecwid webhook events. Returns 200 immediately, processes asynchronously."""
    body = await request.body()

    # Verify signature
    settings = get_settings()
    signature = request.headers.get("X-Ecwid-Webhook-Signature", "")
    if settings.ecwid_client_secret and not verify_webhook_signature(body, signature, settings.ecwid_client_secret):
        await logger.warning("Invalid webhook signature")
        return Response(status_code=401, content='{"error": "Invalid signature"}')

    # Parse payload
    try:
        import json

        data = json.loads(body)
        payload = EcwidWebhookPayload(**data)
    except Exception as e:
        await logger.error(f"Failed to parse webhook payload: {e}")
        return Response(status_code=400, content='{"error": "Invalid payload"}')

    # Deduplicate
    if payload.eventId in _processed_events:
        await logger.info(f"Duplicate event {payload.eventId}, skipping")
        return Response(status_code=200, content='{"status": "ok"}')

    # Track event
    _processed_events.add(payload.eventId)
    if len(_processed_events) > _MAX_PROCESSED_CACHE:
        # Remove oldest entries (approximate, sets are unordered)
        to_remove = list(_processed_events)[:_MAX_PROCESSED_CACHE // 2]
        for e in to_remove:
            _processed_events.discard(e)

    await logger.info(
        f"Received webhook: {payload.eventType} entity={payload.entityId} store={payload.storeId}"
    )

    # Process asynchronously after returning 200
    asyncio.create_task(_process_order_event(payload))

    return Response(status_code=200, content='{"status": "ok"}')
