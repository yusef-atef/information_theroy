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

# ---------------------------------------------------------------------------
# Configuration (override via environment variables in production)
# ---------------------------------------------------------------------------
SECRET_KEY: str = os.getenv("SECRET_KEY", "CHANGE_ME_IN_PRODUCTION_use_32+_random_bytes")
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))


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
