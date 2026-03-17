"""kwtSMS gateway operations: login, balance, test SMS."""

from fastapi import APIRouter

from app.database import get_setting, get_sync_data, set_setting
from app.models import APIResponse, BalanceResponse, GatewayLoginRequest, GatewayLoginResponse, TestSMSRequest
from app.services.encryption import decrypt, encrypt
from app.services.kwtsms import KwtSMSClient
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger("gateway")


@router.post("/login")
async def gateway_login(body: GatewayLoginRequest) -> GatewayLoginResponse:
    """Verify kwtSMS credentials and fetch account data.

    On success, stores encrypted credentials, sender IDs, and coverage.
    """
    client = KwtSMSClient(body.username, body.password)
    try:
        result = await client.login()

        if not result.get("success"):
            return GatewayLoginResponse(
                success=False,
                message=result.get("message", "Unable to verify credentials. Please check your username and password."),
            )

        # Store encrypted credentials
        await set_setting("kwtsms_username", encrypt(body.username))
        await set_setting("kwtsms_password", encrypt(body.password))

        balance = result.get("balance", 0)

        # Fetch sender IDs
        sender_ids = []
        try:
            sender_ids = await client.get_senderids()
        except Exception as e:
            await logger.warning(f"Failed to fetch sender IDs: {e}")

        # Fetch coverage
        try:
            await client.get_coverage()
        except Exception as e:
            await logger.warning(f"Failed to fetch coverage: {e}")

        await logger.info(f"Gateway login successful. Balance: {balance}, Sender IDs: {len(sender_ids)}")

        return GatewayLoginResponse(
            success=True,
            balance=balance,
            sender_ids=sender_ids,
            message="Connected successfully",
        )
    finally:
        await client.close()


@router.get("/balance")
async def get_balance() -> BalanceResponse | APIResponse:
    """Fetch current kwtSMS balance."""
    username_enc = await get_setting("kwtsms_username")
    password_enc = await get_setting("kwtsms_password")

    if not username_enc or not password_enc:
        return APIResponse(success=False, message="Gateway credentials not configured")

    try:
        username = decrypt(username_enc)
        password = decrypt(password_enc)
    except ValueError:
        return APIResponse(success=False, message="Failed to decrypt credentials")

    client = KwtSMSClient(username, password)
    try:
        balance = await client.get_balance()
        sync = await get_sync_data("balance")
        synced_at = sync["synced_at"] if sync else ""
        return BalanceResponse(balance=balance, synced_at=synced_at)
    except Exception as e:
        await logger.error(f"Failed to fetch balance: {e}")
        return APIResponse(success=False, message="Failed to fetch balance from gateway")
    finally:
        await client.close()


@router.post("/test-sms")
async def send_test_sms(body: TestSMSRequest) -> APIResponse:
    """Send a test SMS (always with test=1)."""
    username_enc = await get_setting("kwtsms_username")
    password_enc = await get_setting("kwtsms_password")

    if not username_enc or not password_enc:
        return APIResponse(success=False, message="Gateway credentials not configured")

    try:
        username = decrypt(username_enc)
        password = decrypt(password_enc)
    except ValueError:
        return APIResponse(success=False, message="Failed to decrypt credentials")

    client = KwtSMSClient(username, password)
    try:
        result = await client.send(body.phone, body.message, body.sender_id, test=True)
        if result.get("success"):
            return APIResponse(success=True, message="Test SMS sent", data=result)
        return APIResponse(success=False, message=result.get("error", "Send failed"))
    except Exception as e:
        await logger.error(f"Test SMS send error: {e}")
        return APIResponse(success=False, message="Failed to send test SMS")
    finally:
        await client.close()


@router.get("/senderids")
async def get_senderids() -> APIResponse:
    """Return cached sender IDs."""
    sync = await get_sync_data("senderids")
    if sync:
        return APIResponse(success=True, data={"sender_ids": sync["data"], "synced_at": sync["synced_at"]})

    # Try fetching live
    username_enc = await get_setting("kwtsms_username")
    password_enc = await get_setting("kwtsms_password")
    if not username_enc or not password_enc:
        return APIResponse(success=False, message="Gateway not configured")

    try:
        username = decrypt(username_enc)
        password = decrypt(password_enc)
        client = KwtSMSClient(username, password)
        try:
            senderids = await client.get_senderids()
            return APIResponse(success=True, data={"sender_ids": senderids})
        finally:
            await client.close()
    except Exception as e:
        await logger.error(f"Failed to fetch sender IDs: {e}")
        return APIResponse(success=False, message="Failed to fetch sender IDs from gateway")


@router.get("/coverage")
async def get_coverage() -> APIResponse:
    """Return cached coverage data."""
    sync = await get_sync_data("coverage")
    if sync:
        return APIResponse(success=True, data={"coverage": sync["data"], "synced_at": sync["synced_at"]})

    # Try fetching live
    username_enc = await get_setting("kwtsms_username")
    password_enc = await get_setting("kwtsms_password")
    if not username_enc or not password_enc:
        return APIResponse(success=False, message="Gateway not configured")

    try:
        username = decrypt(username_enc)
        password = decrypt(password_enc)
        client = KwtSMSClient(username, password)
        try:
            coverage = await client.get_coverage()
            return APIResponse(success=True, data={"coverage": coverage})
        finally:
            await client.close()
    except Exception as e:
        await logger.error(f"Failed to fetch coverage: {e}")
        return APIResponse(success=False, message="Failed to fetch coverage from gateway")
