import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tag import Tag, todo_tags
from app.schemas.tag import TagCreate


async def create_tag(db: AsyncSession, tag_data: TagCreate, user_id: uuid.UUID) -> Tag:
    tag = Tag(
        user_id=user_id,
        name=tag_data.name,
        color=tag_data.color,
    )
    db.add(tag)
    await db.flush()
    await db.refresh(tag)
    return tag


async def get_tags(db: AsyncSession, user_id: uuid.UUID) -> list[Tag]:
    result = await db.execute(
        select(Tag).where(Tag.user_id == user_id).order_by(Tag.created_at, Tag.id)
    )
    return list(result.scalars().all())


async def get_tag_by_id(
    db: AsyncSession, tag_id: uuid.UUID, user_id: uuid.UUID
) -> Tag | None:
    result = await db.execute(
        select(Tag).where(Tag.id == tag_id, Tag.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_tag_by_name(
    db: AsyncSession, name: str, user_id: uuid.UUID
) -> Tag | None:
    result = await db.execute(
        select(Tag).where(
            Tag.user_id == user_id,
            func.lower(Tag.name) == func.lower(name),
        )
    )
    return result.scalar_one_or_none()


async def update_tag(db: AsyncSession, tag: Tag, update_data: dict) -> Tag:
    for key, value in update_data.items():
        setattr(tag, key, value)
    await db.flush()
    await db.refresh(tag)
    return tag


async def delete_tag(db: AsyncSession, tag: Tag) -> None:
    await db.execute(delete(todo_tags).where(todo_tags.c.tag_id == tag.id))
    await db.delete(tag)
    await db.flush()
