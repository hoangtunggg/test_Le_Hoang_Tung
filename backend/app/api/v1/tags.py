import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_redis
from app.core.redis import RedisClient
from app.db.session import get_db
from app.models.user import User
from app.schemas.tag import TagCreate, TagResponse, TagUpdate
from app.services.tag_service import (
    create_tag,
    delete_tag,
    get_tag_by_id,
    get_tag_by_name,
    get_tags,
    update_tag,
)
from app.services.todo_cache import invalidate_todo_list_cache

router = APIRouter()


def tag_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Tag not found",
    )


def duplicate_tag_name() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Tag name already exists",
    )


@router.get("", response_model=list[TagResponse])
async def list_tags(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_tags(db, current_user.id)


@router.post("", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
async def create_new_tag(
    tag_data: TagCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if await get_tag_by_name(db, tag_data.name, current_user.id):
        raise duplicate_tag_name()

    try:
        tag = await create_tag(db, tag_data, current_user.id)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise duplicate_tag_name()

    return tag


@router.patch("/{tag_id}", response_model=TagResponse)
async def update_existing_tag(
    tag_id: uuid.UUID,
    tag_data: TagUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tag = await get_tag_by_id(db, tag_id, current_user.id)
    if not tag:
        raise tag_not_found()

    update_data = tag_data.model_dump(exclude_unset=True)
    name = update_data.get("name")
    if name is not None:
        existing_tag = await get_tag_by_name(db, name, current_user.id)
        if existing_tag and existing_tag.id != tag.id:
            raise duplicate_tag_name()

    try:
        updated_tag = await update_tag(db, tag, update_data)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise duplicate_tag_name()

    return updated_tag


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_tag(
    tag_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    tag = await get_tag_by_id(db, tag_id, current_user.id)
    if not tag:
        raise tag_not_found()

    await delete_tag(db, tag)
    await db.commit()
    await invalidate_todo_list_cache(redis, current_user.id)
