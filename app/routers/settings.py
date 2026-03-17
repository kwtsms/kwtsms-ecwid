"""Settings CRUD API endpoints."""

import json

from fastapi import APIRouter, Request

from app.database import fetch_all, get_setting, set_setting
from app.models import APIResponse, SettingResponse
from app.services.ecwid import decrypt_payload
from app.services.encryption import encrypt
from app.config import get_settings
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger("settings")

# Keys that should be encrypted when stored
_ENCRYPTED_KEYS = {"kwtsms_password", "kwtsms_username", "ecwid_access_token"}

# Keys that should never be returned to the frontend
_HIDDEN_KEYS = {"kwtsms_password", "kwtsms_username", "ecwid_access_token", "encryption_key"}


def _mask_value(key: str, value: str) -> str:
    """Mask sensitive values for API responses."""
    if key in _HIDDEN_KEYS:
        return "***"
    return value


@router.get("")
async def get_all_settings() -> dict:
    """Return all settings, with sensitive values masked."""
    rows = await fetch_all("SELECT key, value, updated_at FROM settings ORDER BY key")
    settings = []
    for row in rows:
        settings.append({
            "key": row["key"],
            "value": _mask_value(row["key"], row["value"]),
            "updated_at": row["updated_at"],
        })
    return {"settings": settings}


@router.get("/{key}")
async def get_single_setting(key: str) -> SettingResponse | APIResponse:
    """Return a single setting value."""
    from app.database import fetch_one

    row = await fetch_one("SELECT key, value, updated_at FROM settings WHERE key = ?", (key,))
    if not row:
        return APIResponse(success=False, message="Setting not found")
    return SettingResponse(key=row["key"], value=_mask_value(row["key"], row["value"]), updated_at=row["updated_at"])


@router.put("/{key}")
async def update_single_setting(key: str, body: dict) -> APIResponse:
    """Update a single setting. Encrypts sensitive values."""
    value = body.get("value", "")
    if key in _ENCRYPTED_KEYS:
        value = encrypt(str(value))
    await set_setting(key, str(value))
    await logger.info(f"Setting updated: {key}")
    return APIResponse(success=True, message="Setting updated")


@router.put("")
async def update_bulk_settings(body: dict) -> APIResponse:
    """Bulk update settings."""
    items = body.get("settings", [])
    for item in items:
        key = item.get("key", "")
        value = item.get("value", "")
        if not key:
            continue
        if key in _ENCRYPTED_KEYS:
            value = encrypt(str(value))
        await set_setting(key, str(value))
    await logger.info(f"Bulk updated {len(items)} settings")
    return APIResponse(success=True, message=f"Updated {len(items)} settings")


@router.post("/init")
async def init_from_payload(request: Request) -> APIResponse:
    """Initialize settings from Ecwid iframe encrypted payload.

    Decrypts the Ecwid payload to extract store_id and access_token.
    """
    try:
        body = await request.json()
        payload_str = body.get("payload", "")
    except Exception:
        payload_str = request.query_params.get("payload", "")

    if not payload_str:
        return APIResponse(success=False, message="No payload provided")

    settings = get_settings()
    if not settings.ecwid_client_secret:
        return APIResponse(success=False, message="Ecwid client secret not configured")

    try:
        decoded = decrypt_payload(payload_str, settings.ecwid_client_secret)
    except ValueError as e:
        await logger.error(f"Payload decryption failed: {e}")
        return APIResponse(success=False, message="Failed to decrypt payload")

    store_id = decoded.get("store_id", "")
    access_token = decoded.get("access_token", "")
    lang = decoded.get("lang", "en")

    if store_id:
        await set_setting("ecwid_store_id", str(store_id))
    if access_token:
        await set_setting("ecwid_access_token", encrypt(access_token))

    # Load current settings for the response
    all_rows = await fetch_all("SELECT key, value, updated_at FROM settings ORDER BY key")
    current = {}
    for row in all_rows:
        current[row["key"]] = _mask_value(row["key"], row["value"])

    return APIResponse(
        success=True,
        message="Initialized",
        data={"store_id": store_id, "lang": lang, "settings": current},
    )
