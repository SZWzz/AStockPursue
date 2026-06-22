"""Tests for src.db.crypto — AES-256-GCM credential encryption."""

from __future__ import annotations

import base64
import re

import pytest

from src.db.crypto import decrypt_password, encrypt_password, generate_key, generate_key_b64


@pytest.mark.unit
class TestGenerateKey:
    def test_generate_key_returns_32_bytes(self):
        key = generate_key()
        assert isinstance(key, bytes)
        assert len(key) == 32

    def test_generate_key_produces_random_values(self):
        k1 = generate_key()
        k2 = generate_key()
        assert k1 != k2

    def test_generate_key_b64_returns_string(self):
        b64 = generate_key_b64()
        assert isinstance(b64, str)
        # 32 bytes -> 44 base64 characters (no padding for 32)
        decoded = base64.b64decode(b64)
        assert len(decoded) == 32

    def test_generate_key_b64_is_valid_base64(self):
        b64 = generate_key_b64()
        # Should decode without error
        base64.b64decode(b64)


@pytest.mark.unit
class TestEncryptDecryptRoundTrip:
    def test_round_trip_simple(self):
        key = generate_key()
        original = "my_secret_password"
        encrypted = encrypt_password(original, key)
        decrypted = decrypt_password(encrypted, key)
        assert decrypted == original

    def test_round_trip_empty_string(self):
        key = generate_key()
        original = ""
        encrypted = encrypt_password(original, key)
        decrypted = decrypt_password(encrypted, key)
        assert decrypted == original

    def test_round_trip_unicode(self):
        key = generate_key()
        original = "密码测试🔐Café"
        encrypted = encrypt_password(original, key)
        decrypted = decrypt_password(encrypted, key)
        assert decrypted == original

    def test_round_trip_long_password(self):
        key = generate_key()
        original = "a" * 1024
        encrypted = encrypt_password(original, key)
        decrypted = decrypt_password(encrypted, key)
        assert decrypted == original


@pytest.mark.unit
class TestEncryptPassword:
    def test_unique_ivs_produce_different_ciphertexts(self):
        key = generate_key()
        plaintext = "same_password"
        c1 = encrypt_password(plaintext, key)
        c2 = encrypt_password(plaintext, key)
        # Different IVs should yield different ciphertexts
        assert c1 != c2

    def test_output_is_valid_base64(self):
        key = generate_key()
        encrypted = encrypt_password("test", key)
        # Should not raise
        decoded = base64.b64decode(encrypted)
        # At minimum: 12 nonce + 16+ tag
        assert len(decoded) >= 28

    def test_encrypt_with_string_key(self):
        key_str = generate_key_b64()
        original = "test_password"
        encrypted = encrypt_password(original, key_str)
        decrypted = decrypt_password(encrypted, key_str)
        assert decrypted == original


@pytest.mark.unit
class TestDecryptPasswordErrors:
    def test_decrypt_with_wrong_key_raises(self):
        key1 = generate_key()
        key2 = generate_key()
        encrypted = encrypt_password("secret", key1)
        with pytest.raises(Exception):
            decrypt_password(encrypted, key2)

    def test_decrypt_malformed_input_raises_valueerror(self):
        key = generate_key()
        with pytest.raises(Exception):
            decrypt_password("not-valid-base64!!!", key)

    def test_decrypt_truncated_input_raises_valueerror(self):
        key = generate_key()
        truncated = base64.b64encode(b"short").decode("ascii")
        with pytest.raises(ValueError, match="too short"):
            decrypt_password(truncated, key)

    def test_decrypt_empty_string_raises(self):
        key = generate_key()
        with pytest.raises(Exception):
            decrypt_password("", key)
