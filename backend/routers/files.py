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
from backend.schemas import FileMetadata, FileListResponse, UploadResponse, DeleteResponse, DriveUploadRequest
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
    iv_hex: str = "",
    gcm_tag_hex: str = "",
    hmac_hex: str = "",
    size_bytes: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a pre-encrypted file and its metadata.
    The server does NOT encrypt; it just stores what the client sends.
    """
    raw_bytes = await file.read()
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large",
        )

    # Storage key (user-namespaced path)
    storage_key = make_storage_key(current_user.id, file.filename or "unnamed")

    # Upload to Storage (Firebase or Local)
    await upload_bytes(storage_key, raw_bytes)

    # Detect MIME type
    mime, _ = mimetypes.guess_type(file.filename or "")
    mime = mime or "application/octet-stream"

    # Persist metadata
    file_record = File(
        user_id=current_user.id,
        filename=file.filename or "unnamed",
        mime_type=mime,
        size_bytes=size_bytes,
        storage_key=storage_key,
        iv_hex=iv_hex,
        gcm_tag_hex=gcm_tag_hex,
        hmac_hex=hmac_hex,
    )
    db.add(file_record)
    await db.commit()
    await db.refresh(file_record)

    # Trigger admin update
    from .admin import manager
    await manager.broadcast_update(db)

    return UploadResponse(
        file_id=file_record.id,
        filename=file_record.filename,
        size_bytes=file_record.size_bytes,
    )


@router.post("/upload/drive", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_drive_metadata(
    body: DriveUploadRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Register a file that has already been uploaded to Google Drive.
    """
    file_record = File(
        user_id=current_user.id,
        filename=body.filename,
        mime_type=body.mime_type or "application/octet-stream",
        size_bytes=body.size_bytes,
        google_file_id=body.google_file_id,
        storage_key=None, # Not stored on our server
        iv_hex=body.iv_hex,
        gcm_tag_hex=body.gcm_tag_hex,
        hmac_hex=body.hmac_hex,
    )
    db.add(file_record)
    await db.commit()
    await db.refresh(file_record)

    from .admin import manager
    await manager.broadcast_update(db)

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
    Fetch an encrypted file and its metadata for the client to decrypt.
    If the file is on Google Drive, it returns metadata and expects the client
    to fetch the bytes from Google.
    """
    result = await db.execute(
        select(File).where(File.id == file_id, File.user_id == current_user.id)
    )
    file_record = result.scalar_one_or_none()
    if file_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    headers = {
        "Content-Disposition": f'attachment; filename="{file_record.filename}"',
        "X-IV": file_record.iv_hex,
        "X-Tag": file_record.gcm_tag_hex,
        "X-HMAC": file_record.hmac_hex,
    }

    if file_record.google_file_id:
        # Client-side cloud storage: just return the ID
        headers["X-Google-File-ID"] = file_record.google_file_id
        return StreamingResponse(
            io.BytesIO(b""), # Empty body, client pulls from Drive
            media_type="application/octet-stream",
            headers=headers,
        )

    # Legacy local/S3 storage
    ciphertext = await download_bytes(file_record.storage_key)
    headers["Content-Length"] = str(len(ciphertext))
    
    return StreamingResponse(
        io.BytesIO(ciphertext),
        media_type="application/octet-stream",
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

    # Remove from cloud storage (only if stored on our server)
    if file_record.storage_key:
        await delete_object(file_record.storage_key)

    # Remove from DB
    await db.delete(file_record)
    await db.commit()

    # Trigger admin update
    from .admin import manager
    await manager.broadcast_update(db)

    return DeleteResponse(message="File deleted successfully", file_id=file_id)
