"""
schemas.py — Pydantic v2 Request / Response Models
"""

from datetime import datetime
from typing import List, Optional, Any
from pydantic import BaseModel, EmailStr, Field, field_validator


# ---------------------------------------------------------------------------
# Auth schemas
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64,
                          description="Unique username (3–64 chars)")
    email: EmailStr
    password: str = Field(..., description="RSA-encrypted master password")

    @field_validator("password")
    @classmethod
    def no_wildcards_in_registration(cls, v: str) -> str:
        # Note: Validation of content now happens after decryption
        return v


class LoginRequest(BaseModel):
    username: str
    password: str = Field(..., description="RSA-encrypted password blob")
    session_key: Optional[str] = Field(None, description="RSA-encrypted AES session key for secure response")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    corrections_applied: int = Field(
        0, description="Number of ECC corrections applied to reach the master password"
    )
    erasures_filled: int = Field(
        0, description="Number of wildcard positions that were filled by ECC"
    )
    # Corrected password is now AES-encrypted with the session_key
    encrypted_corrected_password: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PublicKeyResponse(BaseModel):
    public_key: str


# ---------------------------------------------------------------------------
# File schemas
# ---------------------------------------------------------------------------

class FileMetadata(BaseModel):
    id: str
    filename: str
    mime_type: str
    size_bytes: int
    google_file_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class FileListResponse(BaseModel):
    files: list[FileMetadata]
    total: int


class UploadResponse(BaseModel):
    file_id: str
    filename: str
    size_bytes: int
    message: str = "File encrypted and uploaded successfully"


class DriveUploadRequest(BaseModel):
    filename: str
    size_bytes: int
    google_file_id: str
    iv_hex: str
    gcm_tag_hex: str
    hmac_hex: str
    mime_type: Optional[str] = "application/octet-stream"


class DeleteResponse(BaseModel):
    message: str
    file_id: str


# ---------------------------------------------------------------------------
# Error schema
# ---------------------------------------------------------------------------

class ErrorResponse(BaseModel):
    detail: str
    error_code: str | None = None
