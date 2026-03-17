"""Ecwid API client: payload decryption, webhook verification, order fetching."""

import base64
import hashlib
import hmac
import json

import httpx
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from app.config import ECWID_API_BASE
from app.utils.logger import get_logger

logger = get_logger("ecwid")


def decrypt_payload(encrypted_payload: str, client_secret: str) -> dict:
    """Decrypt Ecwid Native App iframe payload (AES-128-CBC).

    The payload is URL-safe base64 encoded, AES-128-CBC encrypted JSON.
    Key is the first 16 characters of client_secret.
    IV is the first 16 bytes of the decoded payload.
    """
    try:
        key = client_secret[:16].encode("utf-8")

        # Convert URL-safe base64 to standard base64
        payload_b64 = encrypted_payload.replace("-", "+").replace("_", "/")
        # Add padding if needed
        padding_needed = len(payload_b64) % 4
        if padding_needed:
            payload_b64 += "=" * (4 - padding_needed)

        decoded = base64.b64decode(payload_b64)
        iv = decoded[:16]
        ciphertext = decoded[16:]

        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        padded = decryptor.update(ciphertext) + decryptor.finalize()

        unpadder = padding.PKCS7(128).unpadder()
        plaintext = unpadder.update(padded) + unpadder.finalize()

        return json.loads(plaintext.decode("utf-8"))
    except Exception as e:
        raise ValueError(f"Failed to decrypt Ecwid payload: {e}")


def verify_webhook_signature(body: bytes, signature: str, client_secret: str) -> bool:
    """Verify Ecwid webhook HMAC-SHA256 signature.

    Computes HMAC-SHA256 of the raw body using client_secret, then
    base64-encodes the digest and compares with the provided signature.
    """
    if not signature:
        return False

    expected = base64.b64encode(
        hmac.new(client_secret.encode("utf-8"), body, hashlib.sha256).digest()
    ).decode("utf-8")

    return hmac.compare_digest(expected, signature)


class EcwidClient:
    """Async client for the Ecwid REST API v3."""

    def __init__(self, store_id: int, access_token: str):
        self.store_id = store_id
        self._client = httpx.AsyncClient(
            base_url=f"{ECWID_API_BASE}/{store_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15.0,
        )

    async def close(self):
        await self._client.aclose()

    async def get_order(self, order_id: int) -> dict:
        """Fetch a single order by ID."""
        try:
            response = await self._client.get(f"/orders/{order_id}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            await logger.error(f"Failed to fetch order {order_id}: HTTP {e.response.status_code}")
            raise
        except Exception as e:
            await logger.error(f"Failed to fetch order {order_id}: {e}")
            raise

    async def get_store_profile(self) -> dict:
        """Fetch the store profile."""
        try:
            response = await self._client.get("/profile")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            await logger.error(f"Failed to fetch store profile: {e}")
            raise

    def extract_order_data(self, order: dict) -> dict:
        """Extract relevant fields from an Ecwid order response."""
        shipping = order.get("shippingPerson", {})
        billing = order.get("billingPerson", {})

        return {
            "order_number": order.get("orderNumber", order.get("id", "")),
            "email": order.get("email", ""),
            "payment_status": order.get("paymentStatus", ""),
            "fulfillment_status": order.get("fulfillmentStatus", ""),
            "total": order.get("total", 0),
            "currency": order.get("currency", ""),
            "tracking_number": order.get("trackingNumber", ""),
            "customer_name": shipping.get("name", billing.get("name", "Customer")),
            "customer_phone": shipping.get("phone", billing.get("phone", "")),
        }
