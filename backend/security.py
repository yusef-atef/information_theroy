"""
security.py — Cryptographic Utilities for SecureCorrect

Provides:
  - Argon2id key derivation
  - AES-256-GCM file encryption / decryption
  - HMAC-SHA256 generation and verification
  - JWT creation / verification
  - AES-256 mapping table encryption (server-side master key)
"""

import os
import hmac
import hashlib
import base64
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.hash import argon2
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes


# ---------------------------------------------------------------------------
# Configuration (override via environment variables in production)
# ---------------------------------------------------------------------------
SECRET_KEY: str = os.getenv("SECRET_KEY", "CHANGE_ME_IN_PRODUCTION_use_32+_random_bytes")
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Server-side master key for encrypting mapping tables at rest.
# Must be exactly 32 bytes (256-bit).  In production, store in a KMS / Vault.
_RAW_MASTER_KEY: str = os.getenv("MASTER_KEY", "CHANGE_ME_MASTER_KEY_32_bytes_pad")
MASTER_KEY: bytes = (_RAW_MASTER_KEY + " " * 32)[:32].encode()


# ---------------------------------------------------------------------------
# Argon2id Key Derivation
# ---------------------------------------------------------------------------

ARGON2_HASHER = argon2.using(
    time_cost=3,          # number of iterations
    memory_cost=65536,    # 64 MiB
    parallelism=2,
    hash_len=32,
    salt_len=16,
)


def hash_password(plaintext: str) -> str:
    """Hash a plaintext password using Argon2id. Returns a PHC-format string."""
    return ARGON2_HASHER.hash(plaintext)


def verify_password(plaintext: str, hashed: str) -> bool:
    """Verify a plaintext password against an Argon2id hash."""
    return ARGON2_HASHER.verify(plaintext, hashed)


def derive_key(plaintext: str, salt: bytes) -> bytes:
    """
    Derive a 32-byte AES key from a plaintext (e.g. password or hash) + salt.
    Uses PBKDF2-HMAC-SHA256 with 100,000 iterations for high work factor.
    This is deterministic: same input + same salt = same key.
    """
    return hashlib.pbkdf2_hmac("sha256", plaintext.encode("utf-8"), salt, iterations=100000, dklen=32)


def generate_key_salt() -> bytes:
    """Generate a fresh 16-byte random salt for key derivation."""
    return get_random_bytes(16)


# ---------------------------------------------------------------------------
# AES-256-GCM File Encryption / Decryption
# ---------------------------------------------------------------------------

def encrypt_file(data: bytes, key: bytes) -> tuple[bytes, bytes, bytes]:
    """
    Encrypt data using AES-256-GCM.

    Args:
        data: plaintext bytes
        key:  32-byte AES key

    Returns:
        (ciphertext, iv, tag) — all bytes
        iv is 16 bytes; tag is 16 bytes
    """
    iv = get_random_bytes(16)
    cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
    ciphertext, tag = cipher.encrypt_and_digest(data)
    return ciphertext, iv, tag


def decrypt_file(ciphertext: bytes, key: bytes, iv: bytes, tag: bytes) -> bytes:
    """
    Decrypt AES-256-GCM ciphertext and verify authentication tag.

    Raises:
        ValueError on authentication failure (wrong key or tampered data)
    """
    cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
    try:
        return cipher.decrypt_and_verify(ciphertext, tag)
    except Exception as exc:
        raise ValueError("Decryption failed: authentication tag mismatch") from exc


# ---------------------------------------------------------------------------
# HMAC-SHA256 Integrity Guard
# ---------------------------------------------------------------------------

def generate_hmac(data: bytes, key: bytes) -> bytes:
    """Compute HMAC-SHA256 of data with key. Returns raw 32-byte digest."""
    return hmac.new(key, data, hashlib.sha256).digest()


def verify_hmac(data: bytes, key: bytes, expected: bytes) -> bool:
    """
    Constant-time comparison of computed HMAC vs expected.
    Returns True only if they match exactly.
    """
    computed = generate_hmac(data, key)
    return hmac.compare_digest(computed, expected)


def generate_hmac_key() -> bytes:
    """Generate a fresh 32-byte random HMAC key (one per user)."""
    return get_random_bytes(32)


# ---------------------------------------------------------------------------
# Mapping Table Encryption (AES-256-GCM with server master key)
# ---------------------------------------------------------------------------

def encrypt_mapping(mapping_json: str) -> str:
    """
    Encrypt the user's mapping table JSON using the server master key.
    Returns a base64-encoded string: iv || tag || ciphertext.
    """
    data = mapping_json.encode("utf-8")
    ciphertext, iv, tag = encrypt_file(data, MASTER_KEY)
    blob = iv + tag + ciphertext
    return base64.b64encode(blob).decode("ascii")


def decrypt_mapping(encrypted_b64: str) -> str:
    """
    Decrypt an encrypted mapping table blob back to JSON.
    Input is the base64 string produced by encrypt_mapping().
    """
    blob = base64.b64decode(encrypted_b64)
    iv, tag, ciphertext = blob[:16], blob[16:32], blob[32:]
    data = decrypt_file(ciphertext, MASTER_KEY, iv, tag)
    return data.decode("utf-8")


# ---------------------------------------------------------------------------
# JWT Tokens
# ---------------------------------------------------------------------------

def create_access_token(user_id: str, username: str) -> str:
    """Create a short-lived JWT access token."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "username": username,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    """Create a longer-lived JWT refresh token."""
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """
    Decode and verify a JWT. Returns the payload dict.
    Raises JWTError on invalid / expired tokens.
    """
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
