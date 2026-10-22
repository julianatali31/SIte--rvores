"""Where photos live: local disk (Docker) or Vercel Blob (serverless, disk is ephemeral).

The stored reference is a relative path for local files ("trees/abc.jpg", served
under /media/) or the absolute public URL for Blob.
"""
import uuid
from pathlib import Path
from typing import Protocol

from app.core.config import get_settings

ONE_YEAR = 365 * 24 * 3600


class Storage(Protocol):
    async def save(self, data: bytes, folder: str) -> str: ...

    async def delete(self, ref: str) -> None: ...


def _new_name(folder: str) -> str:
    return f"{folder}/{uuid.uuid4().hex}.jpg"


class LocalStorage:
    def __init__(self, root: str):
        self.root = Path(root)

    async def save(self, data: bytes, folder: str) -> str:
        ref = _new_name(folder)
        target = self.root / ref
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return ref

    async def delete(self, ref: str) -> None:
        root = self.root.resolve()
        target = (root / ref).resolve()
        if root in target.parents and target.is_file():
            target.unlink()


class BlobStorage:
    """Vercel Blob (public store). Credentials come from BLOB_READ_WRITE_TOKEN."""

    async def save(self, data: bytes, folder: str) -> str:
        from vercel.blob import put_blob

        result = await put_blob(
            _new_name(folder),
            data,
            access="public",
            content_type="image/jpeg",
            cache_control_max_age=ONE_YEAR,  # names are random and never reused
        )
        return result.url

    async def delete(self, ref: str) -> None:
        from vercel.blob import BlobNotFoundError, delete_blob

        try:
            await delete_blob(ref)
        except BlobNotFoundError:
            pass


def get_storage() -> Storage:
    settings = get_settings()
    if settings.storage_backend == "blob":
        return BlobStorage()
    return LocalStorage(settings.upload_dir)


def is_remote(ref: str) -> bool:
    return ref.startswith(("https://", "http://"))


def media_url(ref: str | None) -> str | None:
    if not ref:
        return None
    return ref if is_remote(ref) else f"/media/{ref}"


async def delete_ref(ref: str | None) -> None:
    """Deletes with the backend that created the file (survives a backend switch)."""
    if not ref:
        return
    if is_remote(ref):
        await BlobStorage().delete(ref)
    else:
        await LocalStorage(get_settings().upload_dir).delete(ref)
