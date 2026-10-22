from fastapi import HTTPException, UploadFile, status

from app.core.config import get_settings

CHUNK = 1024 * 1024


async def read_upload(file: UploadFile) -> bytes:
    """Reads at most MAX_UPLOAD_MB; refuses anything bigger without buffering it all."""
    limit = get_settings().max_upload_mb * 1024 * 1024
    chunks, size = [], 0
    while chunk := await file.read(CHUNK):
        size += len(chunk)
        if size > limit:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                f"Arquivo maior que {get_settings().max_upload_mb} MB.",
            )
        chunks.append(chunk)
    if not size:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Arquivo vazio.")
    return b"".join(chunks)
