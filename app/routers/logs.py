"""Log viewer API endpoints."""

from fastapi import APIRouter, Query

from app.database import execute_query, fetch_all, fetch_one
from app.models import APIResponse
from app.utils.logger import get_logger
from app.utils.phone import mask_phone

router = APIRouter()
logger = get_logger("logs")


@router.get("")
async def list_logs(
    status: str | None = None,
    event_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """List SMS log entries with filters and pagination. Phone numbers are masked."""
    query = "SELECT * FROM sms_log WHERE 1=1"
    count_query = "SELECT COUNT(*) as total FROM sms_log WHERE 1=1"
    params: list = []

    if status:
        query += " AND status = ?"
        count_query += " AND status = ?"
        params.append(status)
    if event_type:
        query += " AND event_type = ?"
        count_query += " AND event_type = ?"
        params.append(event_type)
    if date_from:
        query += " AND created_at >= ?"
        count_query += " AND created_at >= ?"
        params.append(date_from)
    if date_to:
        query += " AND created_at <= ?"
        count_query += " AND created_at <= ?"
        params.append(date_to)

    total_row = await fetch_one(count_query, tuple(params))
    total = total_row["total"] if total_row else 0

    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    rows = await fetch_all(query, tuple(params + [limit, offset]))

    logs = []
    for row in rows:
        entry = dict(row)
        entry["recipient"] = mask_phone(entry["recipient"])
        logs.append(entry)

    return {"logs": logs, "total": total}


@router.get("/stats")
async def get_log_stats() -> dict:
    """Return aggregate SMS log statistics."""
    total = await fetch_one("SELECT COUNT(*) as cnt FROM sms_log")
    sent = await fetch_one("SELECT COUNT(*) as cnt FROM sms_log WHERE status = 'sent'")
    failed = await fetch_one("SELECT COUNT(*) as cnt FROM sms_log WHERE status = 'failed'")
    test = await fetch_one("SELECT COUNT(*) as cnt FROM sms_log WHERE status = 'test'")
    today = await fetch_one("SELECT COUNT(*) as cnt FROM sms_log WHERE created_at >= date('now')")
    this_month = await fetch_one(
        "SELECT COUNT(*) as cnt FROM sms_log WHERE created_at >= date('now', 'start of month')"
    )

    return {
        "total": total["cnt"] if total else 0,
        "sent": sent["cnt"] if sent else 0,
        "failed": failed["cnt"] if failed else 0,
        "test": test["cnt"] if test else 0,
        "today": today["cnt"] if today else 0,
        "this_month": this_month["cnt"] if this_month else 0,
    }


@router.get("/debug")
async def list_debug_logs(
    level: str | None = None,
    module: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """List debug log entries."""
    from app.config import get_settings

    if not get_settings().app_debug:
        return APIResponse(success=False, message="Debug mode is disabled").model_dump()

    query = "SELECT * FROM debug_log WHERE 1=1"
    params: list = []

    if level:
        query += " AND level = ?"
        params.append(level)
    if module:
        query += " AND module = ?"
        params.append(module)

    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    rows = await fetch_all(query, tuple(params + [limit, offset]))

    return {"logs": [dict(r) for r in rows]}


@router.get("/{log_id}")
async def get_log_entry(log_id: int) -> dict:
    """Get a single log entry. Phone number is masked."""
    row = await fetch_one("SELECT * FROM sms_log WHERE id = ?", (log_id,))
    if not row:
        return APIResponse(success=False, message="Log entry not found").model_dump()
    entry = dict(row)
    entry["recipient"] = mask_phone(entry["recipient"])
    return entry


@router.delete("")
async def delete_logs(older_than_days: int = Query(30, ge=0)) -> APIResponse:
    """Delete SMS log entries older than N days."""
    if older_than_days == 0:
        await execute_query("DELETE FROM sms_log")
        count_row = await fetch_one("SELECT changes() as cnt")
    else:
        await execute_query(
            "DELETE FROM sms_log WHERE created_at < datetime('now', ?)",
            (f"-{older_than_days} days",),
        )
        count_row = await fetch_one("SELECT changes() as cnt")

    deleted = count_row["cnt"] if count_row else 0
    await logger.info(f"Deleted {deleted} log entries")
    return APIResponse(success=True, message=f"Deleted {deleted} entries")


@router.delete("/debug")
async def delete_debug_logs() -> APIResponse:
    """Clear the debug log table."""
    await execute_query("DELETE FROM debug_log")
    await logger.info("Debug logs cleared")
    return APIResponse(success=True, message="Debug logs cleared")
