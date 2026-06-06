"""Credential store — encrypted persistence for broker API keys.

Uses cryptography.fernet (already a project dependency) for symmetric
encryption.  The master key is read from the CREDENTIAL_ENCRYPTION_KEY
environment variable (64 hex characters → 32 bytes → Fernet key).
"""

from __future__ import annotations

import base64
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_ENCRYPTION_KEY: Optional[bytes] = None


def _get_fernet():
    """Return a Fernet instance, or None if no key is configured."""
    global _ENCRYPTION_KEY

    if _ENCRYPTION_KEY is None:
        hex_key = os.getenv("CREDENTIAL_ENCRYPTION_KEY", "")
        if not hex_key:
            logger.warning("CREDENTIAL_ENCRYPTION_KEY not set — credential encryption disabled")
            return None
        try:
            raw = bytes.fromhex(hex_key)
            _ENCRYPTION_KEY = base64.urlsafe_b64encode(raw)
        except Exception as exc:
            logger.error("Invalid CREDENTIAL_ENCRYPTION_KEY: %s", exc)
            return None

    from cryptography.fernet import Fernet
    return Fernet(_ENCRYPTION_KEY)


def encrypt_credential(plaintext: str) -> str:
    """Encrypt a credential string.  Returns base64-encoded ciphertext.

    If no encryption key is configured, returns the plaintext with a
    ``plain:`` prefix (insecure — for development only).
    """
    if not plaintext:
        return ""

    fernet = _get_fernet()
    if fernet is None:
        return f"plain:{plaintext}"

    return fernet.encrypt(plaintext.encode()).decode()


def decrypt_credential(ciphertext: str) -> str:
    """Decrypt a credential string.

    If the ciphertext starts with ``plain:`` it is returned as-is
    (development / no-key fallback).
    """
    if not ciphertext:
        return ""

    if ciphertext.startswith("plain:"):
        return ciphertext[6:]

    fernet = _get_fernet()
    if fernet is None:
        return ""

    try:
        return fernet.decrypt(ciphertext.encode()).decode()
    except Exception as exc:
        logger.error("Credential decryption failed: %s", exc)
        return ""
