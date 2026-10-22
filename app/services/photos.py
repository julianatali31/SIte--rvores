"""Photo processing: validate by content, fix rotation, resize, strip all metadata (EXIF/GPS)."""
import io
from datetime import datetime

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.time import local_tz

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_SIDE = 1600
JPEG_QUALITY = 85
EXIF_DATETIME_ORIGINAL = 0x9003
EXIF_IFD = 0x8769

Image.MAX_IMAGE_PIXELS = 60_000_000  # decompression-bomb guard


class PhotoError(ValueError):
    pass


def _exif_taken_at(img: Image.Image) -> datetime | None:
    try:
        raw = img.getexif().get_ifd(EXIF_IFD).get(EXIF_DATETIME_ORIGINAL)
        if not raw:
            return None
        # EXIF has no timezone; cameras on campus are in São Paulo time.
        return datetime.strptime(str(raw).strip(), "%Y:%m:%d %H:%M:%S").replace(tzinfo=local_tz())
    except (ValueError, KeyError, AttributeError):
        return None


def process_image(data: bytes) -> tuple[bytes, datetime | None]:
    """Returns (clean JPEG bytes, EXIF capture time if present)."""
    try:
        with Image.open(io.BytesIO(data)) as probe:
            probe.verify()
        img = Image.open(io.BytesIO(data))
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise PhotoError("Arquivo não é uma imagem válida.") from exc
    if img.format not in ALLOWED_FORMATS:
        raise PhotoError("Formato não suportado. Envie JPEG, PNG ou WEBP.")

    taken_at = _exif_taken_at(img)
    img = ImageOps.exif_transpose(img)
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    if img.mode != "RGB":
        background = Image.new("RGB", img.size, (255, 255, 255))
        rgba = img.convert("RGBA")
        background.paste(rgba, mask=rgba.split()[-1])
        img = background

    out = io.BytesIO()
    # Re-encoding without passing exif= drops every metadata block.
    img.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return out.getvalue(), taken_at
