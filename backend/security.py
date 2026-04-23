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
from Crypto.PublicKey import RSA
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.Random import get_random_bytes
from dotenv import load_dotenv

# Load configuration from .env file
load_dotenv()

# ---------------------------------------------------------------------------
# Configuration (override via environment variables in production)
# ---------------------------------------------------------------------------
SECRET_KEY: str = os.getenv("SECRET_KEY", "CHANGE_ME_IN_PRODUCTION_use_32+_random_bytes")
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Server-side master key for encrypting mapping tables at rest.
_RAW_MASTER_KEY: str = os.getenv("MASTER_KEY", "CHANGE_ME_MASTER_KEY_32_bytes_pad")
MASTER_KEY: bytes = (_RAW_MASTER_KEY + " " * 32)[:32].encode()

# RSA Key Pair for secure password transit
# Loaded from environment variables (see .env file)
SERVER_PRIVATE_KEY = os.getenv("SERVER_PRIVATE_KEY", "").replace("\\n", "\n")
SERVER_PUBLIC_KEY = os.getenv("SERVER_PUBLIC_KEY", "").replace("\\n", "\n")

if not SERVER_PRIVATE_KEY or not SERVER_PUBLIC_KEY:
    # Fallback to hardcoded keys ONLY for development if env is not set
    # (Keeping the ones from before as fallback for safety during migration)
    SERVER_PRIVATE_KEY = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEowIBAAKCAQEA2c3EYW28JK0C+RnUkHJaLwh8yhjLRKhWs0VaK8lPF2w206Iv\n"
        "aOFP9oa8/KYiNgqJE444jrhr3gbIOAEOd7N58sURudhUO9Y9LHrF0iBnqw0FXyMM\n"
        "too3vIUKK7mczaTyde1VuLuzcEzKwiF6r9rELaTYN1zOd/v6jfIZGVHBpcs9EHaO\n"
        "aWxljKRl+KJ1z9PohEHTEe+TDIphS2dHJmse/Y7c5CfzQ20CRAUUTVIAmmY58qGi\n"
        "BT3Xe/k0/BFVWsdS7bmq4Y4GDIEvHdc3d7s/gAzDPmyyC/v6AqB1hQSRGszH+l47\n"
        "bhXmwek63WyXpdtPuMpvv7sOozeUiPvE2scQLwIDAQABAoIBAGzNXC05drOxk9sh\n"
        "Wqzf2wpEyKXideRx3YHHgtB9y1tNjSPykJFpgJsL2uuxCEULxUc2FC3Dler/Y1SK\n"
        "vpHwX9p1NLIsjYOotb17BUg/NNpfclAAv9COQmKT6S1Hlzupiw97BIf4iB5w1hbd\n"
        "R58Cf163yuT5IRESGKuBBaW+0ChD7215NITQ5yvWsya1shtlInR+1Zr9nzMQ+mxI\n"
        "NMljb5Pi49fIdR7j6IYSS2BJve2O+NgPO4YfCr6GflaXWmS7Vr89+CcWNQPA9Ikg\n"
        "YXhT3EZB03kw8IgzL06xUHoyWsVO1EStg0aOzRWRdjHVs61jxxvHl9qM9QMOfQ+Q\n"
        "t1sg7o0CgYEA64BElTbxlNE81STfnqiOk577zVRyP8L+44x0BL630VbvLTE1yAQn\n"
        "kxsZO8OuBvra5Nlm+ZgeyydJOuAxsKh8vOmQql4zmWaOyRGttqHiiJPBMXg46knN\n"
        "rXN29fYnnSlj+gXjVBflgI73TchBX5XWYFAIcU+JlhDwye3Xjv+xY4sCgYEA7MMl\n"
        "c1OVme5KjSkY0FWEgcFaKi482wx1DpjQNjCyLnXKfxtmpEh4fxmir8gVIUUUrvLf\n"
        "qknXyS0TX0oF5YsRFM44IzY87qX8d8oWcT/WezRL9mdcGJqIumK4AxAmFdzm4NvS\n"
        "qKeaAkEsHPecnSwjgXVNe1Gv0ZDCcN5aJXGcym0CgYBmNQ4O4ICqgMDxFIbE2gy+\n"
        "/sHz1FGdYKi04zE7Gfa3MQ6uw2u++iaezqT97igqOVck+UGa062Rp+Q9XC3UqNsy\n"
        "NgAmIKouSndvxm9pEws5ET9IlA/Hhu5v9+vKReHdcKhGS6XkylY9nE6ygFX3ARXA\n"
        "SRvQ6Z8h9Qo76TCjjE9VjwKBgQCI7E6jRIp3DB0nR8Ym7d4E4FoRnM3q7Ghh+bQo\n"
        "Mr9JKSvjmGgiyBqPfrbcK700kWvlxWXeaHgXyy6x4/BHEMbfHmfOzVYtueapLEEQ\n"
        "W5fhhpwLszjKrcw25lJ+yv8Lk8Yd8mMA0HS7qw8k7XowV09tVfZqRBKHAs3AUocV\n"
        "sn+3fQKBgHBafDXuclkc6ZJmxmd5IfOu4kHKE75IP9XBF5DEsEwveOLjicKXyioJ\n"
        "COXQxB/SYAa18Lo5PPq803NhxqgypZLiIaFsAszoSUcuy/GXrmLfCXdA544sAYE/\n"
        "6iSefa0ETrC9/INnCAMEyZcJLIzgWp7ocuEdv7D9zKrQr26UHuwj\n"
        "-----END RSA PRIVATE KEY-----\n"
    )
    SERVER_PUBLIC_KEY = (
        "-----BEGIN PUBLIC KEY-----\n"
        "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA2c3EYW28JK0C+RnUkHJa\n"
        "Lwh8yhjLRKhWs0VaK8lPF2w206IvaOFP9oa8/KYiNgqJE444jrhr3gbIOAEOd7N5\n"
        "8sURudhUO9Y9LHrF0iBnqw0FXyMMtoo3vIUKK7mczaTyde1VuLuzcEzKwiF6r9rE\n"
        "LaTYN1zOd/v6jfIZGVHBpcs9EHaOaWxljKRl+KJ1z9PohEHTEe+TDIphS2dHJmse\n"
        "/Y7c5CfzQ20CRAUUTVIAmmY58qGiBT3Xe/k0/BFVWsdS7bmq4Y4GDIEvHdc3d7s/\n"
        "gAzDPmyyC/v6AqB1hQSRGszH+l47bhXmwek63WyXpdtPuMpvv7sOozeUiPvE2scQ\n"
        "LwIDAQAB\n"
        "-----END PUBLIC KEY-----\n"
    )


# ---------------------------------------------------------------------------
# RSA Utilities
# ---------------------------------------------------------------------------

def decrypt_password(encrypted_base64: str) -> str:
    """Decrypt a password encrypted with the server's public key."""
    try:
        cipher_rsa = PKCS1_OAEP.new(RSA.import_key(SERVER_PRIVATE_KEY.encode('ascii')))
        decrypted = cipher_rsa.decrypt(base64.b64decode(encrypted_base64))
        return decrypted.decode('utf-8')
    except Exception as e:
        raise ValueError(f"Failed to decrypt password: {e}")


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


# ---------------------------------------------------------------------------
# Session-based Response Encryption
# ---------------------------------------------------------------------------

def encrypt_response_data(plaintext: str, session_key_hex: str) -> str:
    """
    Encrypt a string using an AES session key.
    Used to send corrected passwords back to the client securely.
    The session_key_hex must be exactly 32 bytes (64 hex chars).
    """
    try:
        key = bytes.fromhex(session_key_hex)
        iv = get_random_bytes(16)
        cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
        ciphertext, tag = cipher.encrypt_and_digest(plaintext.encode('utf-8'))
        # Result: iv || tag || ciphertext (all base64)
        blob = iv + tag + ciphertext
        return base64.b64encode(blob).decode('ascii')
    except Exception as e:
        raise ValueError(f"Response encryption failed: {e}")
