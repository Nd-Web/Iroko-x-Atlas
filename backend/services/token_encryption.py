"""
Token Encryption — AES-256-GCM for storing OAuth refresh tokens at rest.
Key is derived from the application SECRET_KEY via PBKDF2.
"""
import os
import base64
import logging
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

logger = logging.getLogger(__name__)

# Fixed salt — derived key changes only when SECRET_KEY changes.
# In production, per-row salts + Key Vault would be preferred.
_SALT = b"iroko-atlas-connector-token-enc-v1"
_KEY_CACHE: bytes | None = None


def _derive_key() -> bytes:
    """Derive a 256-bit AES key from SECRET_KEY."""
    global _KEY_CACHE
    if _KEY_CACHE is not None:
        return _KEY_CACHE

    secret = os.getenv("SECRET_KEY", "")
    if not secret:
        raise RuntimeError("SECRET_KEY is not set — cannot encrypt tokens.")

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT,
        iterations=480_000,
    )
    _KEY_CACHE = kdf.derive(secret.encode())
    return _KEY_CACHE


def encrypt_token(plaintext: str) -> str:
    """
    Encrypt a plaintext token string.
    Returns a base64-encoded string of: nonce (12 bytes) || ciphertext.
    """
    key = _derive_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return base64.urlsafe_b64encode(nonce + ciphertext).decode()


def decrypt_token(encrypted: str) -> str:
    """
    Decrypt a base64-encoded ciphertext back to the original token.
    """
    key = _derive_key()
    aesgcm = AESGCM(key)
    raw = base64.urlsafe_b64decode(encrypted)
    nonce = raw[:12]
    ciphertext = raw[12:]
    return aesgcm.decrypt(nonce, ciphertext, None).decode()
