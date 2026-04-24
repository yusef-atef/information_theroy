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
    decrypt_password,
    SERVER_PUBLIC_KEY,
    encrypt_response_data,
)
from backend.ecc.ecc_auth import register_password, verify_and_correct
from backend.schemas import (
    RegisterRequest, 
    LoginRequest, 
    TokenResponse, 
    UserResponse, 
    PublicKeyResponse
)

router = APIRouter(prefix="/auth", tags=["Authentication"])
bearer_scheme = HTTPBearer()


@router.get("/public-key", response_model=PublicKeyResponse)
async def get_public_key():
    """Return the server's RSA public key for password encryption."""
    return PublicKeyResponse(public_key=SERVER_PUBLIC_KEY)


from sqlalchemy.orm import selectinload

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

    result = await db.execute(
        select(User).options(selectinload(User.files)).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Create a new SecureCorrect account.
    Decrypts the incoming RSA-encrypted password first.
    """
    password = decrypt_password(body.password)
    
    # Validation after decryption
    if "*" in password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Wildcards not allowed in registration")
    if not (4 <= len(password) <= 64):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be between 4 and 64 characters")

    # Check username / email uniqueness
    # ...
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
    bundle = register_password(password)

    # Argon2 hash (integrity guard)
    argon_hash = hash_password(password)

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
    # 5. Commit
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Trigger admin update
    from .admin import manager
    await manager.broadcast_update(db)

    return user


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    ECC-corrected login with decrypted password.
    """
    password = decrypt_password(body.password)
    session_key_hex = decrypt_password(body.session_key) if body.session_key else None

    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()

    # Always attempt correction even if user not found (timing-attack mitigation)
    dummy_codeword = [0] * 20
    codeword = user.codeword_as_list() if user else dummy_codeword
    mapping_json = decrypt_mapping(user.encrypted_mapping) if user else "{}"

    correction = verify_and_correct(
        input_password=password,
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

    encrypted_pw = None
    if (correction.n_errors_corrected > 0 or correction.n_erasures_filled > 0) and session_key_hex:
        encrypted_pw = encrypt_response_data(correction.corrected_password, session_key_hex)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        corrections_applied=correction.n_errors_corrected,
        erasures_filled=correction.n_erasures_filled,
        encrypted_corrected_password=encrypted_pw,
    )


# ---------------------------------------------------------------------------
# Me
# ---------------------------------------------------------------------------

@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Permanently delete the user account and all associated encrypted files.
    Zero-Knowledge: Files are removed from storage before the account is purged.
    """
    from ..storage import delete_object

    # 1. Delete physical files from storage
    # We load files before deleting the user to get storage keys
    for file_item in current_user.files:
        try:
            await delete_object(file_item.storage_key)
        except Exception as e:
            # Log error but continue with account deletion
            print(f"Warning: Failed to delete physical file {file_item.storage_key}: {e}")

    # 2. Delete user from database (cascades to file records)
    await db.delete(current_user)
    await db.commit()

    # Trigger admin update
    from .admin import manager
    await manager.broadcast_update(db)

    return None


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
