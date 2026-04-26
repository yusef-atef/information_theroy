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
    create_access_token,
    create_refresh_token,
    decode_token,
)
from backend.schemas import (
    RegisterRequest, 
    LoginStep1Request,
    LoginStep1Response,
    LoginStep2Request,
    TokenResponse, 
    UserResponse, 
)

router = APIRouter(prefix="/auth", tags=["Authentication"])
bearer_scheme = HTTPBearer()


# (Removed /public-key endpoint as RSA transit is no longer used for auth_hash)


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
    Zero-Knowledge: Server only receives pre-computed ECC codeword and mapping seed.
    """
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

    user = User(
        username=body.username,
        email=str(body.email),
        auth_hash=body.auth_hash,
        ecc_codeword_hex=body.codeword_hex,
        mapping_seed_hex=body.seed_hex,
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Trigger admin update
    from .admin import manager
    await manager.broadcast_update(db)

    return user


@router.post("/login/step1", response_model=LoginStep1Response)
async def login_step1(body: LoginStep1Request, db: AsyncSession = Depends(get_db)):
    """
    Step 1: Fetch the parity symbols and mapping seed for the user.
    This allows the client to perform Reed-Solomon correction locally.
    """
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        # Prevent user enumeration by returning dummy data (padding to mimic normal response)
        # However, for true ECC, a dummy payload might break the frontend logic gracefully.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    return LoginStep1Response(
        codeword_hex=user.ecc_codeword_hex,
        seed_hex=user.mapping_seed_hex,
    )


@router.post("/login/step2", response_model=TokenResponse)
async def login_step2(body: LoginStep2Request, db: AsyncSession = Depends(get_db)):
    """
    Step 2: Client provides the derived auth_hash proof after local ECC correction.
    """
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()

    if not user or not user.is_active or user.auth_hash != body.auth_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials or incorrect ECC recovery",
        )

    access_token = create_access_token(user.id, user.username)
    refresh_token = create_refresh_token(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
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
