"""QR downloads and the A4 label sheet. Only planted trees get plaques."""
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import current_admin
from app.core.db import get_session
from app.models import Tree
from app.models.enums import DataReviewStatus, TreeStatus
from app.routers.deps import get_or_404
from app.services.labels_pdf import Label, labels_pdf
from app.services.qr import qr_png, qr_svg

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(current_admin)])

# "attention" trees are planted too (just need care); they keep their plaque.
LABEL_STATUSES = (TreeStatus.PLANTED, TreeStatus.ATTENTION)


async def _planted(session: AsyncSession, tree_id: int) -> Tree:
    tree = await get_or_404(session, Tree, tree_id, "Árvore")
    if tree.status not in LABEL_STATUSES:
        raise HTTPException(status.HTTP_409_CONFLICT, "QR só para árvores plantadas.")
    return tree


@router.get("/trees/{tree_id}/qr.png")
async def tree_qr_png(tree_id: int, session: AsyncSession = Depends(get_session)):
    tree = await _planted(session, tree_id)
    return Response(
        qr_png(tree.public_id),
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="{tree.code}-qr.png"'},
    )


@router.get("/trees/{tree_id}/qr.svg")
async def tree_qr_svg(tree_id: int, session: AsyncSession = Depends(get_session)):
    tree = await _planted(session, tree_id)
    return Response(
        qr_svg(tree.public_id),
        media_type="image/svg+xml",
        headers={"Content-Disposition": f'attachment; filename="{tree.code}-qr.svg"'},
    )


@router.get("/labels.pdf")
async def labels(
    ids: list[int] | None = Query(default=None, description="Restrict to these tree ids"),
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(Tree)
        .where(Tree.status.in_(LABEL_STATUSES))
        .options(selectinload(Tree.species))
        .order_by(Tree.code)
    )
    if ids:
        stmt = stmt.where(Tree.id.in_(ids))
    trees = (await session.execute(stmt)).scalars().all()
    pdf = labels_pdf(
        [
            Label(
                code=t.code,
                public_id=t.public_id,
                common_name=t.species.common_name,
                scientific_name=(
                    t.species.scientific_name
                    if t.species.data_review_status == DataReviewStatus.REVIEWED
                    else None
                ),
            )
            for t in trees
        ]
    )
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="etiquetas-arvores.pdf"'},
    )
