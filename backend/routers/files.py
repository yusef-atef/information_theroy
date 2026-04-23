"""
routers/files.py — File Vault Endpoints

POST   /files/upload            — encrypt and upload a file to Firebase Storage
GET    /files/list              — list user's encrypted files (metadata only)
GET    /files/download/{id}     — decrypt and stream a file back
DELETE /files/{id}              — delete file from storage and DB
"""

import io
import mimetypes
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.database import get_db
from backend.models import User, File
from backend.schemas import FileMetadata, FileListResponse, UploadResponse, DeleteResponse
from backend.security import encrypt_file, decrypt_file, generate_hmac, verify_hmac, derive_key
from backend.routers.auth import get_current_user
from backend.storage import upload_bytes, download_bytes, delete_object, make_storage_key

router = APIRouter(prefix="/files", tags=["File Vault"])

# Max upload size: 100 MB
MAX_UPLOAD_BYTES = 100 * 1024 * 1024


# ---------------------------------------------------------------------------
# Helper — derive user's file encryption key from their corrected password
# Note: The key is NOT stored. The caller must supply the corrected password
#       which was just validated during login.  For download, the client
#       re-authenticates with the /auth/login endpoint first and the server
#       holds the derived key in the ephemeral request scope only.
#
# For this prototype, we derive the key from the Argon2 hash stored in DB.
# In a zero-knowledge model the key would only live on-device.
# ---------------------------------------------------------------------------

def _user_file_key(user: User) -> bytes:
    """
    Derive the 32-byte AES file encryption key for this user.
    Uses the Argon2 hash as the 'password' input so the key is reproducible
    without storing it, yet bound to the user's actual password.
    """
    return derive_key(user.argon2_hash, user.key_salt())


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = FastAPIFile(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Encrypt and upload a file to cloud storage.

    1. Read file bytes (enforces 100 MB limit).
    2. Compute HMAC-SHA256 of plaintext for integrity guard.
    3. Encrypt with AES-256-GCM using the user's derived key.
    4. Upload ciphertext to Firebase Storage.
    5. Persist file metadata to the DB.
    """
    raw_bytes = await file.read()
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {MAX_UPLOAD_BYTES // (1024*1024)} MB",
        )

    key = _user_file_key(current_user)

    # HMAC of plaintext
    plaintext_hmac = generate_hmac(raw_bytes, current_user.hmac_key())

    # Encrypt
    ciphertext, iv, gcm_tag = encrypt_file(raw_bytes, key)

    # Storage key (user-namespaced path)
    storage_key = make_storage_key(current_user.id, file.filename or "unnamed")

    # Upload to Firebase/S3
    await upload_bytes(storage_key, ciphertext)

    # Detect MIME type
    mime, _ = mimetypes.guess_type(file.filename or "")
    mime = mime or "application/octet-stream"

    # Persist metadata
    file_record = File(
        user_id=current_user.id,
        filename=file.filename or "unnamed",
        mime_type=mime,
        size_bytes=len(raw_bytes),
        storage_key=storage_key,
        iv_hex=iv.hex(),
        gcm_tag_hex=gcm_tag.hex(),
        hmac_hex=plaintext_hmac.hex(),
    )
    db.add(file_record)
    await db.flush()

    return UploadResponse(
        file_id=file_record.id,
        filename=file_record.filename,
        size_bytes=file_record.size_bytes,
    )


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@router.get("/list", response_model=FileListResponse)
async def list_files(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(File)
        .where(File.user_id == current_user.id)
        .order_by(File.created_at.desc())
    )
    files = result.scalars().all()
    return FileListResponse(files=list(files), total=len(files))


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

@router.get("/download/{file_id}")
async def download_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Decrypt and stream a file.

    1. Fetch file record; verify ownership.
    2. Download ciphertext from storage.
    3. Decrypt with AES-256-GCM (authenticates tag → rejects tampered data).
    4. Verify HMAC-SHA256 of plaintext against stored value (integrity guard).
    5. Stream plaintext to client.
    """
    result = await db.execute(
        select(File).where(File.id == file_id, File.user_id == current_user.id)
    )
    file_record = result.scalar_one_or_none()
    if file_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    key = _user_file_key(current_user)

    # Download ciphertext
    ciphertext = await download_bytes(file_record.storage_key)

    # Decrypt (AES-GCM tag check is performed inside decrypt_file)
    try:
        plaintext = decrypt_file(
            ciphertext,
            key,
            bytes.fromhex(file_record.iv_hex),
            bytes.fromhex(file_record.gcm_tag_hex),
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Decryption failed: file may be corrupted or key mismatch",
        )

    # HMAC integrity guard
    if not verify_hmac(plaintext, current_user.hmac_key(), bytes.fromhex(file_record.hmac_hex)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="HMAC verification failed: access denied",
        )

    headers = {
        "Content-Disposition": f'attachment; filename="{file_record.filename}"',
        "Content-Length": str(len(plaintext)),
    }
    return StreamingResponse(
        io.BytesIO(plaintext),
        media_type=file_record.mime_type,
        headers=headers,
    )


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@router.delete("/{file_id}", response_model=DeleteResponse)
async def delete_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(File).where(File.id == file_id, File.user_id == current_user.id)
    )
    file_record = result.scalar_one_or_none()
    if file_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    # Remove from cloud storage
    await delete_object(file_record.storage_key)

    # Remove from DB
    await db.delete(file_record)

    return DeleteResponse(message="File deleted successfully", file_id=file_id)
