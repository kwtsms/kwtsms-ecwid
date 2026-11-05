"""Phone number normalization and validation."""

import re

# Arabic-Indic digits (U+0660 to U+0669)
_ARABIC_INDIC = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
# Extended Arabic-Indic / Eastern (U+06F0 to U+06F9)
_EASTERN_ARABIC = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def normalize_phone(raw: str) -> str:
    """Normalize a phone number to digits-only international format.

    Converts Arabic/Hindi digits, strips non-digits, removes international
    prefixes, and prepends Kuwait country code (965) when appropriate.
    """
    if not raw or not raw.strip():
        raise ValueError("Phone number cannot be empty")

    # Convert Arabic digit variants to Latin
    result = raw.translate(_ARABIC_INDIC).translate(_EASTERN_ARABIC)

    # Strip all non-digit characters
    result = re.sub(r"\D", "", result)

    if not result:
        raise ValueError("Phone number contains no digits")

    # Remove leading 00 (international prefix)
    if result.startswith("00"):
        result = result[2:]

    # Remove leading 0 (local format) and prepend 965
    if result.startswith("0") and not result.startswith("00"):
        result = "965" + result[1:]

    # If 8 digits without country code, assume Kuwait
    if len(result) == 8:
        result = "965" + result

    return result


def verify_local(phone: str) -> tuple[bool, str]:
    """Validate a normalized phone number.

    Returns (is_valid, error_message).
    """
    if not phone:
        return False, "Phone number is empty"

    if not phone.isdigit():
        return False, "Phone contains non-digit characters"

    if len(phone) < 10 or len(phone) > 15:
        return False, "Phone number length invalid"

    # Kuwait-specific validation
    if phone.startswith("965"):
        local_part = phone[3:]
        if len(local_part) != 8:
            return False, "Kuwait number must be 8 digits after country code"
        if local_part[0] in ("1", "2"):
            return False, "Landline numbers are not supported"

    return True, ""


def mask_phone(phone: str) -> str:
    """Mask a phone number for display. Shows first 4 and last 4 digits.

    Example: 99912345678 -> 9991***5678
    (2026-11-05 11:09 +03: example uses the unassigned code 999 instead of a real mobile number, int-testnumber)
    """
    if len(phone) <= 8:
        return phone[:2] + "***" + phone[-2:]
    return phone[:4] + "***" + phone[-4:]
