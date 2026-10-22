from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


async def get_or_404(session: AsyncSession, model, obj_id: int, label: str):
    obj = await session.get(model, obj_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{label} não encontrado(a).")
    return obj


# DB constraint name -> message for the admin UI.
CONSTRAINT_MESSAGES = {
    "ck_trees_planted_requires_date": "Árvore plantada precisa de data de plantio.",
    "ck_trees_lat_lng_together": "Informe latitude e longitude juntas.",
    "uq_species_common_name": "Já existe uma espécie com esse nome.",
    "uq_origins_donor_name": "Já existe uma origem com esse doador.",
    "uq_planting_zones_name": "Já existe uma zona com esse nome.",
    "fk_trees_species_id_species": "Espécie inexistente ou com árvores vinculadas.",
    "fk_trees_origin_id_origins": "Origem inexistente ou com árvores vinculadas.",
    "fk_trees_zone_id_planting_zones": "Zona inexistente.",
}


async def commit_or_422(session: AsyncSession) -> None:
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        text = str(exc.orig)
        for name, message in CONSTRAINT_MESSAGES.items():
            if name in text:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, message) from None
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Dados inválidos.") from None
