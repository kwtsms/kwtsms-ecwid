"""Message content cleaning: emoji strip, hidden chars, Arabic numerals."""

import math
import re

from app.config import SMS_CONCAT_PAGE_SIZE_AR, SMS_CONCAT_PAGE_SIZE_EN, SMS_PAGE_SIZE_AR, SMS_PAGE_SIZE_EN

# Arabic-Indic digits (U+0660 to U+0669)
_ARABIC_INDIC = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
# Extended Arabic-Indic / Eastern (U+06F0 to U+06F9)
_EASTERN_ARABIC = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")

# Emoji and special character pattern
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002702-\U000027B0"  # dingbats
    "\U0000FE00-\U0000FE0F"  # variation selectors
    "\U0000200D"  # zero-width joiner
    "\U0000200B-\U0000200F"  # zero-width and directional chars
    "\U0000202A-\U0000202E"  # directional formatting
    "\U0000FEFF"  # BOM / zero-width no-break space
    "\U000000AD"  # soft hyphen
    "]+",
    flags=re.UNICODE,
)

# HTML tag pattern
_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")

# Arabic Unicode range for language detection
_ARABIC_CHAR_PATTERN = re.compile(r"[\u0600-\u06FF]")


def clean_message(text: str) -> str:
    """Clean SMS message content for delivery via kwtSMS.

    Steps: strip whitespace, convert Arabic digits, remove emoji,
    remove hidden chars, strip HTML, collapse whitespace.
    """
    if not text:
        return ""

    result = text.strip()

    # Convert Arabic digit variants to Latin
    result = result.translate(_ARABIC_INDIC).translate(_EASTERN_ARABIC)

    # Remove emoji and special invisible characters
    result = _EMOJI_PATTERN.sub("", result)

    # Strip HTML tags (kwtSMS error ERR027)
    result = _HTML_TAG_PATTERN.sub("", result)

    # Collapse multiple spaces into one
    result = re.sub(r" {2,}", " ", result)

    # Collapse multiple newlines into one
    result = re.sub(r"\n{2,}", "\n", result)

    return result.strip()


def detect_language(text: str) -> str:
    """Detect if text contains Arabic characters.

    Returns 'ar' if any Arabic character found, 'en' otherwise.
    """
    if _ARABIC_CHAR_PATTERN.search(text):
        return "ar"
    return "en"


def count_pages(text: str, lang: str = "auto") -> tuple[int, int]:
    """Calculate SMS page count and remaining characters.

    Args:
        text: The message text.
        lang: 'en', 'ar', or 'auto' (detect from content).

    Returns:
        (page_count, chars_remaining_on_current_page)
    """
    if not text:
        return 0, 0

    if lang == "auto":
        lang = detect_language(text)

    length = len(text)

    if lang == "ar":
        first_page = SMS_PAGE_SIZE_AR
        concat_page = SMS_CONCAT_PAGE_SIZE_AR
    else:
        first_page = SMS_PAGE_SIZE_EN
        concat_page = SMS_CONCAT_PAGE_SIZE_EN

    if length <= first_page:
        return 1, first_page - length

    # Multipart: first page uses concat size too (UDH header on all parts)
    pages = math.ceil(length / concat_page)
    remaining = (concat_page - (length % concat_page)) % concat_page
    return pages, remaining
