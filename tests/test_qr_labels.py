import io

import zxingcpp
from PIL import Image
from pypdf import PdfReader

from app.services.qr import make_qr, qr_png, qr_svg, tree_url
from tests.conftest import tree_id


def decode(png: bytes):
    results = zxingcpp.read_barcodes(Image.open(io.BytesIO(png)))
    assert len(results) == 1
    return results[0]


def test_qr_encodes_permanent_url_with_level_h(settings, monkeypatch):
    monkeypatch.setattr(settings, "base_url", "https://arvores.exemplo.edu.br")
    result = decode(qr_png("ab23cd45"))
    assert result.text == "https://arvores.exemplo.edu.br/a/ab23cd45"
    assert result.ec_level == "H"
    assert make_qr("ab23cd45").error == "H"


def test_tree_url_never_has_double_slash(settings, monkeypatch):
    from app.core.config import Settings

    monkeypatch.setattr(settings, "base_url", Settings(base_url="https://x.edu.br/").base_url)
    assert tree_url("ab23cd45") == "https://x.edu.br/a/ab23cd45"


def test_qr_svg_is_valid_svg():
    svg = qr_svg("ab23cd45").decode()
    assert svg.startswith("<?xml") and "<svg" in svg


async def test_qr_endpoints_only_for_planted(admin, seeded):
    awaiting = await tree_id(seeded, "ARV-002")
    planted = await tree_id(seeded, "ARV-001")
    await admin.post(f"/api/admin/trees/{planted}/plant", json={"planted_at": "2026-10-20T09:30:00", "lat": -28.26, "lng": -52.4})
    assert (await admin.get(f"/api/admin/trees/{awaiting}/qr.png")).status_code == 409

    tree = (await admin.get(f"/api/admin/trees/{planted}")).json()
    png = await admin.get(f"/api/admin/trees/{planted}/qr.png")
    svg = await admin.get(f"/api/admin/trees/{planted}/qr.svg")
    assert png.headers["content-type"] == "image/png"
    assert decode(png.content).text == tree["public_url"]
    assert svg.headers["content-type"].startswith("image/svg+xml")
    assert 'filename="ARV-001-qr.svg"' in svg.headers["content-disposition"]


async def test_labels_pdf_lists_only_planted_trees(admin, seeded):
    for code in ("ARV-001", "ARV-006"):
        tid = await tree_id(seeded, code)
        await admin.post(f"/api/admin/trees/{tid}/plant", json={"planted_at": "2026-10-20T09:30:00", "lat": -28.26, "lng": -52.4})
    r = await admin.get("/api/admin/labels.pdf")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    text = "".join(page.extract_text() for page in PdfReader(io.BytesIO(r.content)).pages)
    assert "ARV-001" in text and "ARV-006" in text
    assert "ARV-002" not in text and "ARV-007" not in text
    assert "Araçá" in text and "Cereja-do-mato" in text
    # Scientific names are still under review: not printed on permanent plaques.
    assert "Psidium" not in text


async def test_labels_pdf_qr_is_readable(admin, seeded):
    tid = await tree_id(seeded, "ARV-001")
    await admin.post(f"/api/admin/trees/{tid}/plant", json={"planted_at": "2026-10-20T09:30:00", "lat": -28.26, "lng": -52.4})
    tree = (await admin.get(f"/api/admin/trees/{tid}")).json()
    pdf = PdfReader(io.BytesIO((await admin.get("/api/admin/labels.pdf")).content))
    image = pdf.pages[0].images[0].image
    assert decode_pil(image).text == tree["public_url"]


def decode_pil(image):
    results = zxingcpp.read_barcodes(image)
    assert len(results) == 1
    return results[0]
