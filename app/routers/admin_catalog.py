"""Species and origins."""
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import current_admin
from app.core.db import get_session
from app.models import Origin, Species, Tree
from app.routers.deps import commit_or_422, get_or_404
from app.routers.uploads import read_upload
from app.schemas.admin import OriginIn, OriginOut, OriginPatch, SpeciesIn, SpeciesOut, SpeciesPatch
from app.services.photos import PhotoError, delete_image, process_image, save_image

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(current_admin)])


async def _species_out(session: AsyncSession, sp: Species) -> SpeciesOut:
    count = await session.scalar(select(func.count()).where(Tree.species_id == sp.id))
    return SpeciesOut.model_validate(sp).model_copy(update={"tree_count": count})


@router.get("/species", response_model=list[SpeciesOut])
async def list_species(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(Species).order_by(Species.common_name))).scalars().all()
    return [await _species_out(session, sp) for sp in rows]


@router.get("/species/{species_id}", response_model=SpeciesOut)
async def get_species(species_id: int, session: AsyncSession = Depends(get_session)):
    return await _species_out(session, await get_or_404(session, Species, species_id, "Espécie"))


@router.post("/species", response_model=SpeciesOut, status_code=status.HTTP_201_CREATED)
async def create_species(body: SpeciesIn, session: AsyncSession = Depends(get_session)):
    sp = Species(**body.model_dump())
    session.add(sp)
    await commit_or_422(session)
    return await _species_out(session, sp)


@router.patch("/species/{species_id}", response_model=SpeciesOut)
async def update_species(species_id: int, body: SpeciesPatch, session: AsyncSession = Depends(get_session)):
    sp = await get_or_404(session, Species, species_id, "Espécie")
    changes = body.model_dump(exclude_unset=True)
    if "common_name" in changes and changes["common_name"] is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Nome popular é obrigatório.")
    if changes.get("data_review_status", "") is None:
        changes.pop("data_review_status")
    for key, value in changes.items():
        setattr(sp, key, value)
    await commit_or_422(session)
    return await _species_out(session, sp)


@router.delete("/species/{species_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_species(species_id: int, session: AsyncSession = Depends(get_session)):
    sp = await get_or_404(session, Species, species_id, "Espécie")
    if await session.scalar(select(func.count()).where(Tree.species_id == sp.id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Há árvores desta espécie. Não é possível excluir.")
    photo = sp.photo_path
    await session.delete(sp)
    await commit_or_422(session)
    delete_image(photo)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/species/{species_id}/photo", response_model=SpeciesOut)
async def upload_species_photo(
    species_id: int, file: UploadFile = File(...), session: AsyncSession = Depends(get_session)
):
    sp = await get_or_404(session, Species, species_id, "Espécie")
    try:
        data, _ = process_image(await read_upload(file))
    except PhotoError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from None
    old, sp.photo_path = sp.photo_path, save_image(data, "species")
    await commit_or_422(session)
    delete_image(old)
    return await _species_out(session, sp)


@router.get("/origins", response_model=list[OriginOut])
async def list_origins(session: AsyncSession = Depends(get_session)):
    return (await session.execute(select(Origin).order_by(Origin.donor_name))).scalars().all()


@router.post("/origins", response_model=OriginOut, status_code=status.HTTP_201_CREATED)
async def create_origin(body: OriginIn, session: AsyncSession = Depends(get_session)):
    origin = Origin(**body.model_dump())
    session.add(origin)
    await commit_or_422(session)
    return origin


@router.patch("/origins/{origin_id}", response_model=OriginOut)
async def update_origin(origin_id: int, body: OriginPatch, session: AsyncSession = Depends(get_session)):
    origin = await get_or_404(session, Origin, origin_id, "Origem")
    changes = body.model_dump(exclude_unset=True)
    if "donor_name" in changes and changes["donor_name"] is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Nome do doador é obrigatório.")
    for key, value in changes.items():
        setattr(origin, key, value)
    await commit_or_422(session)
    return origin
