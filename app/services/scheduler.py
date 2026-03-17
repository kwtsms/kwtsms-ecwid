"""APScheduler daily sync job for balance, senderids, coverage."""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import get_settings
from app.database import get_setting
from app.services.encryption import decrypt
from app.services.kwtsms import KwtSMSClient
from app.utils.logger import get_logger

logger = get_logger("scheduler")
_log = logging.getLogger("kwtsms.scheduler")

_scheduler: AsyncIOScheduler | None = None


async def daily_sync() -> None:
    """Sync balance, sender IDs, and coverage from kwtSMS API."""
    await logger.info("Starting daily sync")

    username_enc = await get_setting("kwtsms_username")
    password_enc = await get_setting("kwtsms_password")

    if not username_enc or not password_enc:
        await logger.info("No kwtSMS credentials configured, skipping sync")
        return

    try:
        username = decrypt(username_enc)
        password = decrypt(password_enc)
    except ValueError:
        await logger.error("Failed to decrypt kwtSMS credentials during sync")
        return

    client = KwtSMSClient(username, password)

    try:
        # Sync balance
        try:
            balance = await client.get_balance()
            await logger.info(f"Synced balance: {balance}")
        except Exception as e:
            await logger.error(f"Failed to sync balance: {e}")

        # Sync sender IDs
        try:
            senderids = await client.get_senderids()
            await logger.info(f"Synced {len(senderids)} sender IDs")
        except Exception as e:
            await logger.error(f"Failed to sync sender IDs: {e}")

        # Sync coverage
        try:
            coverage = await client.get_coverage()
            await logger.info(f"Synced coverage: {len(coverage)} countries")
        except Exception as e:
            await logger.error(f"Failed to sync coverage: {e}")

        await logger.info("Daily sync completed")
    finally:
        await client.close()


def start_scheduler() -> None:
    """Create and start the APScheduler."""
    global _scheduler
    settings = get_settings()

    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        daily_sync,
        "cron",
        hour=settings.sync_hour,
        minute=settings.sync_minute,
        id="daily_sync",
        replace_existing=True,
    )
    _scheduler.start()
    _log.info("Scheduler started")


def stop_scheduler() -> None:
    """Shut down the scheduler gracefully."""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        _log.info("Scheduler stopped")


async def trigger_sync_now() -> None:
    """Manually trigger the daily sync job."""
    await daily_sync()
