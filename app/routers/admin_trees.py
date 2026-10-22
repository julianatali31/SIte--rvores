from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import current_admin
from app.core.db import get_session
from app.core.ids import new_public_id, tree_code
from app.core.time import assume_local, now_utc
from app.models import CareEvent, Origin, Photo, PlantingZone, Species, Tree, User
from app.models.enums import EventSource, TreeStatus
from app.routers.deps import commit_or_422, get_or_404
from app.routers.uploads import read_upload
from app.schemas.admin import (
    CareEventIn,
    CareEventOut,
    PhotoOut,
    PlantIn,
    TreeCreate,
    TreeOut,
    TreePatch,
)
from app.services.photos import PhotoError, process_image
from app.services.qr import tree_url
from app.services.storage import delete_ref, get_storage, media_url
from app.services.tree_view import badges_for

router = APIRouter(prefix="/api/admin/trees", tags=["admin"], dependencies=[Depends(current_admin)])


async def _load(session: AsyncSession, tree_id: int) -> Tree:
    tree = (
        await session.execute(
            select(Tree)
            .where(Tree.id == tree_id)
            .options(selectinload(Tree.species), selectinload(Tree.zone), selectinload(Tree.origin))
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if tree is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Árvore não encontrada.")
    return tree


async def _out(session: AsyncSession, tree: Tree, badges: dict | None = None) -> TreeOut:
    if badges is None:
        badges = await badges_for(session, [tree], now_utc())
    badge = badges.get(tree.id)
    return TreeOut(
        id=tree.id,
        code=tree.code,
        public_id=tree.public_id,
        species_id=tree.species_id,
        species_name=tree.species.common_name,
        origin_id=tree.origin_id,
        zone_id=tree.zone_id,
        zone_name=tree.zone.name if tree.zone else None,
        planting_batch=tree.planting_batch,
        status=tree.status,
        planted_at=tree.planted_at,
        lat=tree.lat,
        lng=tree.lng,
        notes=tree.notes,
        public_url=tree_url(tree.public_id),
        badge_color=badge.color if badge else None,
        badge_headline=badge.headline if badge else None,
    )


async def _check_refs(session: AsyncSession, species_id=None, origin_id=None, zone_id=None) -> None:
    if species_id is not None:
        await get_or_404(session, Species, species_id, "Espécie")
    if origin_id is not None:
        await get_or_404(session, Origin, origin_id, "Origem")
    if zone_id is not None:
        await get_or_404(session, PlantingZone, zone_id, "Zona")


@router.get("", response_model=list[TreeOut])
async def list_trees(session: AsyncSession = Depends(get_session)):
    trees = (
        await session.execute(
            select(Tree)
            .options(selectinload(Tree.species), selectinload(Tree.zone))
            .order_by(Tree.code)
        )
    ).scalars().all()
    badges = await badges_for(session, list(trees), now_utc())
    return [await _out(session, t, badges) for t in trees]


@router.get("/{tree_id}", response_model=TreeOut)
async def get_tree(tree_id: int, session: AsyncSession = Depends(get_session)):
    return await _out(session, await _load(session, tree_id))


@router.post("", response_model=TreeOut, status_code=status.HTTP_201_CREATED)
async def create_tree(body: TreeCreate, session: AsyncSession = Depends(get_session)):
    await _check_refs(session, body.species_id, body.origin_id, body.zone_id)
    # Serialize code allocation so two admins never get the same ARV-NNN.
    await session.execute(select(func.pg_advisory_xact_lock(4242)))
    codes = (await session.execute(select(Tree.code))).scalars().all()
    next_number = max((int(c.split("-")[1]) for c in codes), default=0) + 1
    public_id = new_public_id()
    while await session.scalar(select(Tree.id).where(Tree.public_id == public_id)):
        public_id = new_public_id()
    tree = Tree(code=tree_code(next_number), public_id=public_id, **body.model_dump())
    session.add(tree)
    await commit_or_422(session)
    return await _out(session, await _load(session, tree.id))


@router.patch("/{tree_id}", response_model=TreeOut)
async def update_tree(tree_id: int, body: TreePatch, session: AsyncSession = Depends(get_session)):
    tree = await _load(session, tree_id)
    changes = body.model_dump(exclude_unset=True)
    for required in ("species_id", "origin_id", "status"):
        if required in changes and changes[required] is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Campo obrigatório: {required}.")
    await _check_refs(session, changes.get("species_id"), changes.get("origin_id"), changes.get("zone_id"))
    if changes.get("planted_at") is not None:
        changes["planted_at"] = assume_local(changes["planted_at"])
    if changes.get("status") == TreeStatus.AWAITING_PLANTING:
        # Undo planting: the seedling goes back to the waiting list.
        changes.setdefault("planted_at", None)
    for key, value in changes.items():
        setattr(tree, key, value)
    await commit_or_422(session)
    return await _out(session, await _load(session, tree_id))


@router.post("/{tree_id}/plant", response_model=TreeOut)
async def plant_tree(tree_id: int, body: PlantIn, session: AsyncSession = Depends(get_session)):
    tree = await _load(session, tree_id)
    if tree.status == TreeStatus.DEAD:
        raise HTTPException(status.HTTP_409_CONFLICT, "Árvore marcada como morta.")
    await _check_refs(session, zone_id=body.zone_id)
    planted_at = assume_local(body.planted_at)
    if planted_at > now_utc():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A data de plantio não pode estar no futuro.")
    tree.status = TreeStatus.PLANTED
    tree.planted_at = planted_at
    tree.lat, tree.lng = body.lat, body.lng
    if body.zone_id is not None:
        tree.zone_id = body.zone_id
    await commit_or_422(session)
    return await _out(session, await _load(session, tree_id))


@router.delete("/{tree_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tree(tree_id: int, session: AsyncSession = Depends(get_session)):
    tree = await _load(session, tree_id)
    has_history = await session.scalar(select(func.count()).where(CareEvent.tree_id == tree.id)) or (
        await session.scalar(select(func.count()).where(Photo.tree_id == tree.id))
    )
    if tree.status != TreeStatus.AWAITING_PLANTING or has_history:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Só é possível excluir mudas que aguardam plantio e sem histórico. "
            "Para árvores plantadas, use o status “morta”.",
        )
    await session.delete(tree)
    await commit_or_422(session)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- photos -------------------------------------------------------------------

def _photo_out(p: Photo) -> PhotoOut:
    return PhotoOut(id=p.id, url=media_url(p.file_path), taken_at=p.taken_at, caption=p.caption)


@router.get("/{tree_id}/photos", response_model=list[PhotoOut])
async def list_photos(tree_id: int, session: AsyncSession = Depends(get_session)):
    await get_or_404(session, Tree, tree_id, "Árvore")
    rows = (await session.execute(select(Photo).where(Photo.tree_id == tree_id).order_by(Photo.taken_at))).scalars()
    return [_photo_out(p) for p in rows]


@router.post("/{tree_id}/photos", response_model=PhotoOut, status_code=status.HTTP_201_CREATED)
async def upload_photo(
    tree_id: int,
    file: UploadFile = File(...),
    caption: str | None = Form(default=None, max_length=200),
    taken_at: str | None = Form(default=None),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_admin),
):
    await get_or_404(session, Tree, tree_id, "Árvore")
    try:
        data, exif_taken = process_image(await read_upload(file))
    except PhotoError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from None
    when = exif_taken or now_utc()
    if taken_at:
        try:
            when = assume_local(datetime.fromisoformat(taken_at))
        except ValueError:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Data da foto inválida.") from None
    photo = Photo(
        tree_id=tree_id,
        taken_at=when,
        file_path=await get_storage().save(data, "trees"),
        caption=(caption or "").strip() or None,
        uploaded_by_id=user.id,
    )
    session.add(photo)
    await commit_or_422(session)
    return _photo_out(photo)


@router.delete("/{tree_id}/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_photo(tree_id: int, photo_id: int, session: AsyncSession = Depends(get_session)):
    photo = await get_or_404(session, Photo, photo_id, "Foto")
    if photo.tree_id != tree_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Foto não encontrada.")
    path = photo.file_path
    await session.delete(photo)
    await commit_or_422(session)
    await delete_ref(path)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- care events (admin) -------------------------------------------------------

@router.get("/{tree_id}/care-events", response_model=list[CareEventOut])
async def list_care_events(tree_id: int, session: AsyncSession = Depends(get_session)):
    await get_or_404(session, Tree, tree_id, "Árvore")
    rows = await session.execute(
        select(CareEvent).where(CareEvent.tree_id == tree_id).order_by(CareEvent.performed_at.desc()).limit(100)
    )
    return rows.scalars().all()


@router.post("/{tree_id}/care-events", response_model=CareEventOut, status_code=status.HTTP_201_CREATED)
async def add_care_event(tree_id: int, body: CareEventIn, session: AsyncSession = Depends(get_session)):
    await get_or_404(session, Tree, tree_id, "Árvore")
    when = assume_local(body.performed_at) if body.performed_at else now_utc()
    if when > now_utc():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A data não pode estar no futuro.")
    event = CareEvent(
        tree_id=tree_id,
        type=body.type,
        performed_at=when,
        performed_by_name=body.performed_by_name,
        notes=body.notes,
        source=EventSource.ADMIN,
    )
    session.add(event)
    await commit_or_422(session)
    return event


@router.delete("/{tree_id}/care-events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_care_event(tree_id: int, event_id: int, session: AsyncSession = Depends(get_session)):
    event = await get_or_404(session, CareEvent, event_id, "Registro")
    if event.tree_id != tree_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Registro não encontrado.")
    await session.delete(event)
    await commit_or_422(session)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
