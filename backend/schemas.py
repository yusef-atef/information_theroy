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
    codeword_hex: str = Field(..., description="Hex representation of the Reed-Solomon codeword")
    seed_hex: str = Field(..., description="Hex representation of the GF256 mapping seed")
    auth_hash: str = Field(..., description="Client-side derived authentication hash (e.g. Argon2/SHA256)")


class LoginStep1Request(BaseModel):
    username: str

class LoginStep1Response(BaseModel):
    codeword_hex: str
    seed_hex: str

class LoginStep2Request(BaseModel):
    username: str
    auth_hash: str = Field(..., description="Client-side derived authentication hash proof")

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    created_at: datetime

    model_config = {"from_attributes": True}


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
