"""QR codes for the tree plaques. Content: {BASE_URL}/a/{public_id}, error correction H."""
import io

import segno

from app.core.config import get_settings


def tree_url(public_id: str) -> str:
    return f"{get_settings().base_url}/a/{public_id}"


def make_qr(public_id: str) -> segno.QRCode:
    # Level H survives ~30% damage: plaques live outdoors (dirt, scratches, sun).
    return segno.make_qr(tree_url(public_id), error="h", boost_error=False)


def qr_png(public_id: str, scale: int = 12) -> bytes:
    buf = io.BytesIO()
    make_qr(public_id).save(buf, kind="png", scale=scale, border=4)
    return buf.getvalue()


def qr_svg(public_id: str, scale: int = 10) -> bytes:
    buf = io.BytesIO()
    make_qr(public_id).save(buf, kind="svg", scale=scale, border=4, xmldecl=True, svgns=True)
    return buf.getvalue()
