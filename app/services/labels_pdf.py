"""A4 sheet of plaque labels: QR + code + common name (+ scientific name)."""
import io
from dataclasses import dataclass

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app.services.qr import qr_png

COLS, ROWS = 2, 3
MARGIN = 12 * mm
QR_SIZE = 50 * mm


@dataclass(frozen=True)
class Label:
    code: str
    public_id: str
    common_name: str
    # Only printed once the species data is reviewed: plaques are permanent.
    scientific_name: str | None


def labels_pdf(labels: list[Label], project_name: str = "Plantando Ideias · IFSul Passo Fundo") -> bytes:
    buf = io.BytesIO()
    page_w, page_h = A4
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle("Etiquetas das árvores")
    cell_w = (page_w - 2 * MARGIN) / COLS
    cell_h = (page_h - 2 * MARGIN) / ROWS
    per_page = COLS * ROWS

    if not labels:
        c.setFont("Helvetica", 14)
        c.drawCentredString(page_w / 2, page_h / 2, "Nenhuma árvore plantada para gerar etiquetas.")

    for i, label in enumerate(labels):
        if i and i % per_page == 0:
            c.showPage()
        slot = i % per_page
        col, row = slot % COLS, slot // COLS
        x0 = MARGIN + col * cell_w
        y0 = page_h - MARGIN - (row + 1) * cell_h
        cx = x0 + cell_w / 2

        c.setDash(3, 3)
        c.setStrokeGray(0.6)
        c.rect(x0 + 2 * mm, y0 + 2 * mm, cell_w - 4 * mm, cell_h - 4 * mm)  # cut line
        c.setDash()

        # Same segno QR (level H) as the PNG/SVG downloads: one implementation.
        qr_bottom = y0 + cell_h - QR_SIZE - 8 * mm
        c.drawImage(ImageReader(io.BytesIO(qr_png(label.public_id))), cx - QR_SIZE / 2, qr_bottom, QR_SIZE, QR_SIZE)

        c.setFillGray(0)
        c.setFont("Helvetica-Bold", 22)
        c.drawCentredString(cx, qr_bottom - 9 * mm, label.code)
        c.setFont("Helvetica-Bold", 15)
        c.drawCentredString(cx, qr_bottom - 16 * mm, label.common_name)
        if label.scientific_name:
            c.setFont("Helvetica-Oblique", 11)
            c.drawCentredString(cx, qr_bottom - 22 * mm, label.scientific_name)
        c.setFont("Helvetica", 8)
        c.setFillGray(0.35)
        c.drawCentredString(cx, y0 + 6 * mm, f"{project_name} · aponte a câmera para o QR")
    c.save()
    return buf.getvalue()
