"""
storage.py — Cloud Storage Abstraction Layer

Defaults to Firebase Storage. Swap the implementation here to use AWS S3
without touching any other files — just change the adapter below.

Set FIREBASE_CREDENTIALS_PATH env var to your serviceAccountKey.json path.
Set FIREBASE_STORAGE_BUCKET env var to your bucket name (e.g. myapp.appspot.com).
"""

import os
import uuid
import asyncio
from pathlib import Path
from functools import lru_cache

# ---------------------------------------------------------------------------
# Local Storage Adapter (Fallback for development)
# ---------------------------------------------------------------------------

class LocalBlob:
    def __init__(self, path: Path):
        self.path = path

    def upload_from_string(self, data: bytes, content_type=None):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(data)

    def download_as_bytes(self) -> bytes:
        if not self.path.exists():
            raise FileNotFoundError(f"Blob not found: {self.path}")
        return self.path.read_bytes()

    def exists(self) -> bool:
        return self.path.exists()

    def delete(self):
        if self.path.exists():
            self.path.unlink()

class LocalBucket:
    def __init__(self, base_path: str = "uploads"):
        self.base_path = Path(base_path)

    def blob(self, storage_key: str) -> LocalBlob:
        return LocalBlob(self.base_path / storage_key)

# ---------------------------------------------------------------------------
# Storage Selection Logic
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_bucket():
    """Lazily initialise storage and return the bucket (Firebase or Local)."""
    cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "serviceAccountKey.json")
    bucket_name = os.getenv("FIREBASE_STORAGE_BUCKET", "")

    # Check if we should use Firebase
    if os.path.exists(cred_path):
        try:
            import firebase_admin
            from firebase_admin import credentials, storage as fb_storage
            
            if not firebase_admin._apps:
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred, {"storageBucket": bucket_name})
            return fb_storage.bucket()
        except Exception as e:
            print(f"Warning: Failed to initialize Firebase ({e}). Falling back to local storage.")
    
    # Fallback to local storage
    return LocalBucket(os.getenv("LOCAL_STORAGE_PATH", "uploads"))


def make_storage_key(user_id: str, filename: str) -> str:
    """Generate a unique, user-namespaced storage path for a file."""
    safe_name = filename.replace("/", "_").replace("\\", "_")
    return f"vault/{user_id}/{uuid.uuid4().hex}_{safe_name}"


async def upload_bytes(storage_key: str, data: bytes) -> None:
    """Upload raw bytes to storage (async wrapper)."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _upload_sync, storage_key, data)


def _upload_sync(storage_key: str, data: bytes) -> None:
    bucket = _get_bucket()
    blob = bucket.blob(storage_key)
    blob.upload_from_string(data, content_type="application/octet-stream")


async def download_bytes(storage_key: str) -> bytes:
    """Download raw bytes from storage (async wrapper)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _download_sync, storage_key)


def _download_sync(storage_key: str) -> bytes:
    bucket = _get_bucket()
    blob = bucket.blob(storage_key)
    return blob.download_as_bytes()


async def delete_object(storage_key: str) -> None:
    """Delete an object from storage (async wrapper)."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _delete_sync, storage_key)


def _delete_sync(storage_key: str) -> None:
    bucket = _get_bucket()
    blob = bucket.blob(storage_key)
    if blob.exists():
        blob.delete()
