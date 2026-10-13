"""kwtSMS API client for send, balance, senderid, coverage, validate."""

import asyncio
import time

import httpx

from app.config import (
    KWTSMS_BATCH_DELAY,
    KWTSMS_BATCH_SIZE,
    KWTSMS_MIN_SEND_INTERVAL,
    KWTSMS_RATE_LIMIT_SECONDS,
    get_settings,
)
from app.database import set_sync_data
from app.utils.logger import get_logger
from app.utils.message import clean_message
from app.utils.phone import mask_phone, normalize_phone, verify_local

logger = get_logger("kwtsms")

# Module-level per-phone rate limit tracker shared across all client instances
_phone_send_times: dict[str, float] = {}


class KwtSMSError(Exception):
    """Custom exception for kwtSMS API errors."""

    def __init__(self, message: str, code: str = "", details: dict | None = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)


class KwtSMSClient:
    """Client for the kwtSMS REST API.

    Uses exactly 5 endpoints: balance, senderid, coverage, send, validate.
    """

    def __init__(self, username: str, password: str):
        self._username = username
        self._password = password
        settings = get_settings()
        self._client = httpx.AsyncClient(
            base_url=settings.kwtsms_api_base_url,
            timeout=30.0,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        self._last_request_time: float = 0.0

    async def close(self):
        await self._client.aclose()

    async def _request(self, endpoint: str, payload: dict) -> dict:
        """Send a POST request to the kwtSMS API with rate limiting."""
        # Client-side pacing: max 2 requests/second, well under the API limit of 10/second.
        # 2026-10-13 13:15 +03: comment corrected, the API limit is 10 req/s (was described as 2).
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < KWTSMS_RATE_LIMIT_SECONDS:
            await asyncio.sleep(KWTSMS_RATE_LIMIT_SECONDS - elapsed)

        # Add credentials (never logged)
        payload["username"] = self._username
        payload["password"] = self._password

        # Log without credentials
        safe_keys = [k for k in payload if k not in ("username", "password")]
        await logger.debug(f"kwtSMS request: /{endpoint}/", {"endpoint": endpoint, "payload_keys": safe_keys})

        try:
            response = await self._client.post(f"/{endpoint}/", json=payload)
            self._last_request_time = time.monotonic()
            response.raise_for_status()
            data = response.json()
            await logger.debug(f"kwtSMS response: /{endpoint}/ status={response.status_code}")
            return data
        except httpx.TimeoutException:
            await logger.error(f"kwtSMS timeout: /{endpoint}/")
            raise KwtSMSError("Request timed out", code="TIMEOUT")
        except httpx.HTTPStatusError as e:
            await logger.error(f"kwtSMS HTTP error: /{endpoint}/ status={e.response.status_code}")
            raise KwtSMSError(f"HTTP error {e.response.status_code}", code=str(e.response.status_code))
        except Exception as e:
            await logger.error(f"kwtSMS error: /{endpoint}/ {e}")
            raise KwtSMSError(str(e))

    async def login(self) -> dict:
        """Verify credentials by calling /balance/. Returns success status and balance.

        API returns: {"result":"OK","available":150,"purchased":1000}
        """
        try:
            data = await self._request("balance", {})
            # API returns "available" for current balance (not "balance")
            if data.get("result") == "OK" and "available" in data:
                return {"success": True, "balance": int(data["available"])}
            # Fallback: some accounts may use a different key
            if "available" in data:
                return {"success": True, "balance": int(data["available"])}
            return {"success": False, "message": "Unexpected response format"}
        except KwtSMSError as e:
            # Map authentication failures to a generic message to prevent enumeration
            if e.code in ("403", "ERR003", "ERR004", "ERR005"):
                return {"success": False, "message": "Invalid credentials. Please check your username and password."}
            return {"success": False, "message": "Unable to connect to gateway. Please try again."}

    async def get_balance(self) -> int:
        """Fetch current SMS credit balance.

        API returns: {"result":"OK","available":150,"purchased":1000}
        """
        data = await self._request("balance", {})
        # API uses "available" for current usable balance
        balance = int(data.get("available", data.get("balance", 0)))
        await set_sync_data("balance", balance)
        return balance

    async def get_senderids(self) -> list[str]:
        """Fetch available Sender IDs for the account.

        API returns: {"result":"OK","senderid":["KWT-SMS","MYAPP"]}
        """
        data = await self._request("senderid", {})
        senderids = []
        if isinstance(data, list):
            # Raw list of sender IDs
            senderids = [str(s.get("name", s)) if isinstance(s, dict) else str(s) for s in data]
        elif isinstance(data, dict):
            # Primary key is "senderid" (singular) per API docs
            raw = data.get("senderid", data.get("senderids", data.get("data", [])))
            if isinstance(raw, list):
                senderids = [str(s.get("name", s)) if isinstance(s, dict) else str(s) for s in raw]
        await set_sync_data("senderids", senderids)
        return senderids

    async def get_coverage(self) -> list[dict]:
        """Fetch supported countries and pricing.

        API returns: {"result":"OK","prefixes":["965","966","971",...]}
        """
        # Map common GCC country prefixes to names
        _PREFIX_NAMES = {
            "965": "Kuwait", "966": "Saudi Arabia", "971": "UAE",
            "973": "Bahrain", "974": "Qatar", "968": "Oman",
        }
        data = await self._request("coverage", {})
        coverage = []
        if isinstance(data, list):
            coverage = data
        elif isinstance(data, dict) and "prefixes" in data:
            raw = data["prefixes"]
            if isinstance(raw, list):
                coverage = [{"prefix": p, "name": _PREFIX_NAMES.get(p, p)} for p in raw]
        elif isinstance(data, dict) and "coverage" in data:
            coverage = data["coverage"]
        elif isinstance(data, dict) and "data" in data:
            coverage = data["data"] if isinstance(data["data"], list) else []
        await set_sync_data("coverage", coverage)
        return coverage

    async def validate_numbers(self, numbers: list[str]) -> dict:
        """Validate phone numbers via /validate/ endpoint."""
        # API field is "mobile" (not "numbers")
        data = await self._request("validate", {"mobile": ",".join(numbers)})
        return data

    async def send(self, recipient: str, message: str, sender_id: str, test: bool = True) -> dict:
        """Send a single SMS through the full pipeline.

        Steps: normalize phone, verify locally, clean message, check rate limit,
        send via API, log result.
        """
        # 1. Normalize phone
        try:
            normalized = normalize_phone(recipient)
        except ValueError as e:
            await logger.warning(f"Phone normalization failed: {e}", {"recipient": mask_phone(recipient)})
            return {"success": False, "error": str(e)}

        # 2. Verify locally
        is_valid, error_msg = verify_local(normalized)
        if not is_valid:
            await logger.warning(f"Phone validation failed: {error_msg}", {"phone": mask_phone(normalized)})
            return {"success": False, "error": error_msg}

        # 3. Clean message
        cleaned = clean_message(message)
        if not cleaned:
            return {"success": False, "error": "Message is empty after cleaning"}

        # 4. Check per-phone rate limit (module-level dict, survives across client instances)
        now = time.monotonic()
        last_send = _phone_send_times.get(normalized, 0)
        if now - last_send < KWTSMS_MIN_SEND_INTERVAL:
            remaining = KWTSMS_MIN_SEND_INTERVAL - (now - last_send)
            await logger.warning(
                f"Rate limited: {mask_phone(normalized)} sent too recently, wait {remaining:.0f}s"
            )
            return {"success": False, "error": f"Rate limited. Wait {remaining:.0f} seconds."}

        # 5. Build payload and send
        payload = {
            "sender": sender_id,
            "mobile": normalized,   # API field is "mobile" not "numbers"
            "message": cleaned,
            "test": 1 if test else 0,
        }

        try:
            data = await self._request("send", payload)
        except KwtSMSError as e:
            return {"success": False, "error": e.message, "code": e.code}

        # 6. Update module-level per-phone tracker
        _phone_send_times[normalized] = time.monotonic()

        # 7. Extract response fields
        result = {
            "success": True,
            "msg_id": data.get("msg-id", data.get("msg_id", "")),
            "points_charged": int(data.get("points-charged", data.get("points_charged", 0))),
            "balance_after": int(data.get("balance-after", data.get("balance_after", 0))),
            "phone": normalized,
            "test": test,
        }

        # 8. Cache updated balance
        if result["balance_after"]:
            await set_sync_data("balance", result["balance_after"])

        await logger.info(
            f"SMS {'test ' if test else ''}sent to {mask_phone(normalized)}",
            {"msg_id": result["msg_id"], "points": result["points_charged"]},
        )

        return result

    async def bulk_send(
        self, recipients: list[str], message: str, sender_id: str, test: bool = True
    ) -> list[dict]:
        """Send SMS to multiple recipients in batches of 200."""
        # Normalize and verify all numbers
        valid_numbers = []
        results = []
        for r in recipients:
            try:
                normalized = normalize_phone(r)
                is_valid, error_msg = verify_local(normalized)
                if is_valid:
                    valid_numbers.append(normalized)
                else:
                    results.append({"phone": r, "success": False, "error": error_msg})
            except ValueError as e:
                results.append({"phone": r, "success": False, "error": str(e)})

        if not valid_numbers:
            return results

        # Clean message once
        cleaned = clean_message(message)
        if not cleaned:
            return [{"phone": r, "success": False, "error": "Empty message"} for r in recipients]

        # Split into batches
        for i in range(0, len(valid_numbers), KWTSMS_BATCH_SIZE):
            batch = valid_numbers[i : i + KWTSMS_BATCH_SIZE]
            payload = {
                "sender": sender_id,
                "mobile": ",".join(batch),   # API field is "mobile" not "numbers"
                "message": cleaned,
                "test": 1 if test else 0,
            }
            try:
                data = await self._request("send", payload)
                for phone in batch:
                    results.append({
                        "phone": phone,
                        "success": True,
                        "msg_id": data.get("msg-id", data.get("msg_id", "")),
                    })
            except KwtSMSError as e:
                for phone in batch:
                    results.append({"phone": phone, "success": False, "error": e.message})

            # Delay between batches
            if i + KWTSMS_BATCH_SIZE < len(valid_numbers):
                await asyncio.sleep(KWTSMS_BATCH_DELAY)

        return results
