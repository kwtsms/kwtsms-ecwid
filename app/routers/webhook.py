"""Ecwid webhook event handler."""

import asyncio
from typing import Callable

from fastapi import APIRouter, Request, Response

from app.config import get_settings
from app.database import execute_query, fetch_one, get_setting
from app.models import EcwidWebhookPayload
from app.services.ecwid import EcwidClient, verify_webhook_signature
from app.services.sms import process_order_created, process_order_updated
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger("webhook")

# Track processed event IDs to deduplicate
_processed_events: set[str] = set()
_MAX_PROCESSED_CACHE = 1000


def _task_done_callback(task: asyncio.Task) -> None:
    """Log exceptions from background tasks so they are not silently swallowed."""
    if not task.cancelled() and task.exception() is not None:
        asyncio.get_event_loop().create_task(
            logger.error(f"Webhook background task failed: {task.exception()}")
        )


async def _handle_app_uninstalled(payload: EcwidWebhookPayload) -> None:
    """Clear all stored credentials, logs, and disable plugin on app uninstall."""
    try:
        credential_keys = ("kwtsms_username", "kwtsms_password", "ecwid_access_token", "kwtsms_sender_id")
        for key in credential_keys:
            await execute_query("DELETE FROM settings WHERE key = ?", (key,))
        await execute_query("UPDATE settings SET value = '0' WHERE key = 'plugin_enabled'")
        # Delete SMS and debug logs per privacy policy commitment
        await execute_query("DELETE FROM sms_log")
        await execute_query("DELETE FROM debug_log")
        await logger.info(f"App uninstalled from store {payload.storeId}: credentials and logs cleared")
    except Exception as e:
        await logger.error(f"Failed to clean up after uninstall: {e}")


async def _process_order_event(payload: EcwidWebhookPayload) -> None:
    """Process an order webhook event asynchronously."""
    try:
        # Check plugin is enabled before doing any work
        plugin_enabled = await get_setting("plugin_enabled")
        if plugin_enabled != "1":
            await logger.info("Plugin disabled, skipping webhook processing")
            return

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

    # Verify signature; reject if client_secret is not configured (no bypass allowed)
    settings = get_settings()
    signature = request.headers.get("X-Ecwid-Webhook-Signature", "")
    if not settings.ecwid_client_secret:
        await logger.warning("Webhook rejected: ECWID_CLIENT_SECRET not configured")
        return Response(status_code=401, content='{"error": "Server misconfiguration"}')
    if not verify_webhook_signature(body, signature, settings.ecwid_client_secret):
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

    # Process asynchronously after returning 200; callback logs any unhandled exceptions
    if payload.eventType == "application.uninstalled":
        task = asyncio.create_task(_handle_app_uninstalled(payload))
    else:
        task = asyncio.create_task(_process_order_event(payload))
    task.add_done_callback(_task_done_callback)

    return Response(status_code=200, content='{"status": "ok"}')
