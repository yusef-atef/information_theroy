"""
models.py — SQLAlchemy ORM Models for SecureCorrect
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    # Argon2id hash of the corrected master password.
    # Used as the HMAC integrity guard — if ECC "corrects" to the wrong password,
    # verify_password() will return False and access is denied.
    argon2_hash: Mapped[str] = mapped_column(Text, nullable=False)

    # Reed-Solomon codeword (list of ints serialised as comma-separated string).
    # Length = PASSWORD_BLOCK_LEN + N_PARITY = 20 symbols.
    ecc_codeword: Mapped[str] = mapped_column(Text, nullable=False)

    # Per-user mapping table — stored AES-256-GCM encrypted (server master key).
    encrypted_mapping: Mapped[str] = mapped_column(Text, nullable=False)

    # Random 32-byte HMAC key for per-user file integrity checking (hex-encoded).
    hmac_key_hex: Mapped[str] = mapped_column(String(64), nullable=False)

    # Random 16-byte salt for key derivation (hex-encoded).
    key_salt_hex: Mapped[str] = mapped_column(String(32), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    files: Mapped[list["File"]] = relationship("File", back_populates="owner",
                                                cascade="all, delete-orphan")

    def codeword_as_list(self) -> list[int]:
        return [int(x) for x in self.ecc_codeword.split(",")]

    def codeword_from_list(self, codeword: list[int]) -> None:
        self.ecc_codeword = ",".join(str(x) for x in codeword)

    def hmac_key(self) -> bytes:
        return bytes.fromhex(self.hmac_key_hex)

    def key_salt(self) -> bytes:
        return bytes.fromhex(self.key_salt_hex)


# ---------------------------------------------------------------------------
# File
# ---------------------------------------------------------------------------

class File(Base):
    __tablename__ = "files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)

    # Original filename (as uploaded by the user)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)

    # MIME type (detected on upload)
    mime_type: Mapped[str] = mapped_column(String(128), default="application/octet-stream")

    # Size in bytes of the *plaintext* file
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)

    # Firebase Storage / S3 object key
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)

    # AES-GCM initialisation vector (hex-encoded, 16 bytes → 32 hex chars)
    iv_hex: Mapped[str] = mapped_column(String(32), nullable=False)

    # AES-GCM authentication tag (hex-encoded, 16 bytes → 32 hex chars)
    gcm_tag_hex: Mapped[str] = mapped_column(String(32), nullable=False)

    # HMAC-SHA256 of the plaintext (hex-encoded, 32 bytes → 64 hex chars)
    # This is the integrity guard: if decryption yields a different HMAC, access denied.
    hmac_hex: Mapped[str] = mapped_column(String(64), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    owner: Mapped["User"] = relationship("User", back_populates="files")
