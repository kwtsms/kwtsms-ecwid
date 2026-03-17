"""Fernet symmetric encryption for API credentials."""

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    """Get or create the Fernet instance using the configured encryption key."""
    global _fernet
    if _fernet is None:
        key = get_settings().encryption_key
        try:
            _fernet = Fernet(key.encode() if isinstance(key, str) else key)
        except Exception as e:
            raise ValueError(f"Invalid ENCRYPTION_KEY in configuration: {e}")
    return _fernet


def generate_key() -> str:
    """Generate a new Fernet key. Returns a URL-safe base64 string."""
    return Fernet.generate_key().decode()


def encrypt(plaintext: str) -> str:
    """Encrypt a string using the configured ENCRYPTION_KEY.

    Returns the ciphertext as a URL-safe base64 string.
    """
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a ciphertext string.

    Returns the original plaintext.
    Raises ValueError if decryption fails.
    """
    f = _get_fernet()
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except InvalidToken as e:
        raise ValueError(f"Decryption failed: {e}")
