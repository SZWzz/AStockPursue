"""AES-256-GCM credential encryption for database passwords.

Encrypts the DB password so it never appears in plain text in .env, logs, or git.
Uses AES-256-GCM with a random 12-byte IV per encryption.
The encryption key itself is stored as a base64-encoded 32-byte random value.
"""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def generate_key() -> bytes:
    """Generate a new random 32-byte AES-256 key."""
    return AESGCM.generate_key(bit_length=256)


def generate_key_b64() -> str:
    """Generate a new key and return as base64 string (for .env storage)."""
    return base64.b64encode(generate_key()).decode("ascii")


def encrypt_password(plaintext: str, key: bytes) -> str:
    """Encrypt a password with AES-256-GCM.

    Returns a base64-encoded string: iv(12) + ciphertext + tag(16).
    """
    if isinstance(key, str):
        key = base64.b64decode(key)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt_password(encrypted: str, key: bytes) -> str:
    """Decrypt a password previously encrypted with encrypt_password."""
    if isinstance(key, str):
        key = base64.b64decode(key)
    raw = base64.b64decode(encrypted)
    if len(raw) < 28:  # 12 nonce + at least 16 tag
        raise ValueError("Invalid encrypted data: too short")
    aesgcm = AESGCM(key)
    nonce = raw[:12]
    ciphertext = raw[12:]
    return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")
