"""
schemas.py — Pydantic v2 Request / Response Models
"""

from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, field_validator


# ---------------------------------------------------------------------------
# Auth schemas
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64,
                          description="Unique username (3–64 chars)")
    email: EmailStr
    password: str = Field(..., min_length=4, max_length=16,
                          description="Master password (4–16 chars, no '*')")

    @field_validator("password")
    @classmethod
    def no_wildcards_in_registration(cls, v: str) -> str:
        if "*" in v:
            raise ValueError("Wildcard '*' not allowed in registration password")
        return v


class LoginRequest(BaseModel):
    username: str
    password: str = Field(..., max_length=16,
                          description="Password, optionally with '*' erasure wildcards")


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


class DeleteResponse(BaseModel):
    message: str
    file_id: str


# ---------------------------------------------------------------------------
# Error schema
# ---------------------------------------------------------------------------

class ErrorResponse(BaseModel):
    detail: str
    error_code: str | None = None
