"""
routers/auth.py — Authentication Endpoints

POST /auth/register   — create account, encode password into RS codeword
POST /auth/login      — ECC-corrected login, returns JWT pair
GET  /auth/me         — return current user (JWT protected)
POST /auth/refresh    — exchange refresh token for new access token
"""

import json
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError

from backend.database import get_db
from backend.models import User
from backend.schemas import RegisterRequest, LoginRequest, TokenResponse, UserResponse
from backend.security import (
    hash_password,
    verify_password,
    encrypt_mapping,
    decrypt_mapping,
    generate_hmac_key,
    generate_key_salt,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from backend.ecc.ecc_auth import register_password, verify_and_correct

router = APIRouter(prefix="/auth", tags=["Authentication"])
bearer_scheme = HTTPBearer()


# ---------------------------------------------------------------------------
# Dependency — current user from JWT
# ---------------------------------------------------------------------------

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise JWTError("Not an access token")
        user_id: str = payload["sub"]
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Create a new SecureCorrect account.

    - Generates a per-user GF(256) mapping table.
    - Encodes the master password into a Reed-Solomon codeword.
    - Stores the codeword + encrypted mapping + Argon2 hash.
    """
    # Check username / email uniqueness
    existing = await db.execute(
        select(User).where(
            (User.username == body.username) | (User.email == str(body.email))
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already registered",
        )

    # ECC registration
    bundle = register_password(body.password)

    # Argon2 hash (integrity guard)
    argon_hash = hash_password(body.password)

    # Encrypt mapping table at rest
    enc_mapping = encrypt_mapping(bundle.mapping_json)

    # Generate per-user HMAC key and key-derivation salt
    hmac_key = generate_hmac_key()
    key_salt = generate_key_salt()

    user = User(
        username=body.username,
        email=str(body.email),
        argon2_hash=argon_hash,
        ecc_codeword=",".join(str(x) for x in bundle.codeword),
        encrypted_mapping=enc_mapping,
        hmac_key_hex=hmac_key.hex(),
        key_salt_hex=key_salt.hex(),
    )
    db.add(user)
    await db.flush()   # get the generated id before commit

    return user


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    ECC-corrected login.

    1. Fetch user record.
    2. Run Reed-Solomon correction on the supplied password.
    3. Verify the corrected password against the Argon2 hash (integrity guard).
    4. If valid, return JWT access + refresh tokens.
    """
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()

    # Always attempt correction even if user not found (timing-attack mitigation)
    dummy_codeword = [0] * 20
    codeword = user.codeword_as_list() if user else dummy_codeword
    mapping_json = decrypt_mapping(user.encrypted_mapping) if user else "{}"

    correction = verify_and_correct(
        input_password=body.password,
        stored_codeword=codeword,
        mapping_json=mapping_json,
    )

    auth_ok = (
        user is not None
        and user.is_active
        and correction.success
        and verify_password(correction.corrected_password, user.argon2_hash)
    )

    if not auth_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials or password too different from original",
        )

    access_token = create_access_token(user.id, user.username)
    refresh_token = create_refresh_token(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        corrections_applied=correction.n_errors_corrected,
        erasures_filled=correction.n_erasures_filled,
    )


# ---------------------------------------------------------------------------
# Me
# ---------------------------------------------------------------------------

@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
):
    token = credentials.credentials
    try:
        payload = decode_token(token)
        if payload.get("type") != "refresh":
            raise JWTError("Not a refresh token")
        user_id = payload["sub"]
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return TokenResponse(
        access_token=create_access_token(user.id, user.username),
        refresh_token=create_refresh_token(user.id),
    )
