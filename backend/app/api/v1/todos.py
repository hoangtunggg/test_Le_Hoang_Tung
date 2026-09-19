import json
import uuid
from datetime import datetime
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_redis
from app.core.redis import RedisClient
from app.db.session import get_db
from app.models.user import User
from app.schemas.todo import (
    TodoBulkStatusUpdate,
    TodoCreate,
    TodoListResponse,
    TodoResponse,
    TodoTagCreate,
    TodoUpdate,
)
from app.schemas.tag import TagResponse
from app.services.todo_service import (
    attach_tag_to_todo,
    bulk_update_todo_status,
    create_todo,
    delete_todo,
    detach_tag_from_todo,
    get_todo_by_id,
    get_todos,
    update_todo,
)
from app.services.tag_service import get_tag_by_id
from app.services.todo_cache import invalidate_todo_list_cache

router = APIRouter()

CACHE_TTL = 300  # 5 minutes


def todo_response(todo, user_email: str | None = None) -> TodoResponse:
    return TodoResponse(
        id=todo.id,
        title=todo.title,
        description=todo.description,
        completed=todo.completed,
        user_id=todo.user_id,
        created_at=todo.created_at,
        updated_at=todo.updated_at,
        user_email=user_email,
        tags=[TagResponse.model_validate(tag) for tag in todo.tags],
    )


def todo_list_cache_key(
    user_id: uuid.UUID,
    status: str | None,
    tag_id: uuid.UUID | None,
    keyword: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    page: int,
    page_size: int,
) -> str:
    """Return a stable, user- and filter-scoped todo-list cache key."""

    def key_value(value: str) -> str:
        return quote(value, safe="")

    return (
        f"todos:list:user:{user_id}:"
        f"status:{key_value(status or 'all')}:"
        f"tag:{tag_id or 'all'}:"
        f"keyword:{key_value(keyword.strip().casefold() if keyword else 'all')}:"
        f"date-from:{key_value(date_from.isoformat() if date_from else 'all')}:"
        f"date-to:{key_value(date_to.isoformat() if date_to else 'all')}:"
        f"page:{page}:size:{page_size}"
    )


async def commit_and_invalidate_todo_lists(
    db: AsyncSession, redis: RedisClient, user_id: uuid.UUID
) -> None:
    await db.commit()
    await invalidate_todo_list_cache(redis, user_id)


@router.get("", response_model=TodoListResponse)
async def list_todos(
    status_filter: Literal["active", "completed", "all"] | None = Query(
        None, alias="status"
    ),
    tag_id: uuid.UUID | None = Query(None),
    keyword: str | None = Query(None, min_length=1),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int | None = Query(None, ge=1),
    size: int | None = Query(None, ge=1, include_in_schema=False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Get a filtered, deterministically ordered page of the user's todos."""
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="date_from must be before or equal to date_to",
        )

    # Retain the previous query parameter for existing clients while exposing
    # page_size as the documented pagination parameter.
    resolved_page_size = page_size or size or 20
    skip = (page - 1) * resolved_page_size

    cache_key = todo_list_cache_key(
        user_id=current_user.id,
        status=status_filter,
        tag_id=tag_id,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=resolved_page_size,
    )

    # Try to get from cache
    cached = await redis.get(cache_key)
    if cached:
        cached_data = json.loads(cached)
        return TodoListResponse(**cached_data)

    todos, total = await get_todos(
        db,
        user_id=current_user.id,
        skip=skip,
        limit=resolved_page_size,
        status=status_filter,
        tag_id=tag_id,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
    )

    items = []
    for todo in todos:
        user_result = await db.execute(select(User).where(User.id == todo.user_id))
        user = user_result.scalar_one_or_none()
        items.append(todo_response(todo, user.email if user else None))

    response = TodoListResponse(
        items=items,
        total=total,
        page=page,
        size=resolved_page_size,
    )

    # Cache the response
    await redis.set(cache_key, response.model_dump_json(), ex=CACHE_TTL)

    return response


@router.post("", response_model=TodoResponse, status_code=status.HTTP_201_CREATED)
async def create_new_todo(
    todo_data: TodoCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Create a new todo item."""
    todo = await create_todo(db, todo_data, current_user.id)
    await commit_and_invalidate_todo_lists(db, redis, current_user.id)
    return TodoResponse.model_validate(todo)


@router.patch("/bulk-status", response_model=list[TodoResponse])
async def update_todos_bulk_status(
    bulk_data: TodoBulkStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Set completion status for an all-owned batch of todos."""
    todos = await bulk_update_todo_status(
        db,
        todo_ids=bulk_data.todo_ids,
        user_id=current_user.id,
        completed=bulk_data.completed,
    )
    if todos is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Todo not found",
        )

    await commit_and_invalidate_todo_lists(db, redis, current_user.id)
    return [todo_response(todo) for todo in todos]


@router.post("/{todo_id}/tags", status_code=status.HTTP_204_NO_CONTENT)
async def attach_todo_tag(
    todo_id: uuid.UUID,
    tag_data: TodoTagCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    todo = await get_todo_by_id(db, todo_id, current_user.id)
    tag = await get_tag_by_id(db, tag_data.tag_id, current_user.id)
    if not todo or not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Todo or tag not found"
        )
    if not await attach_tag_to_todo(db, todo.id, tag.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Tag is already attached"
        )
    await commit_and_invalidate_todo_lists(db, redis, current_user.id)


@router.delete("/{todo_id}/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def detach_todo_tag(
    todo_id: uuid.UUID,
    tag_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    todo = await get_todo_by_id(db, todo_id, current_user.id)
    tag = await get_tag_by_id(db, tag_id, current_user.id)
    if not todo or not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Todo or tag not found"
        )
    if not await detach_tag_from_todo(db, todo.id, tag.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Todo tag mapping not found",
        )
    await commit_and_invalidate_todo_lists(db, redis, current_user.id)


@router.get("/{todo_id}", response_model=TodoResponse)
async def get_todo(
    todo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific todo by ID."""
    todo = await get_todo_by_id(db, todo_id, current_user.id)
    if not todo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Todo not found",
        )

    return todo_response(todo)


@router.put("/{todo_id}", response_model=TodoResponse)
async def update_existing_todo(
    todo_id: uuid.UUID,
    todo_data: TodoUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Update a todo item."""
    todo = await get_todo_by_id(db, todo_id, current_user.id)
    if not todo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Todo not found",
        )

    update_data = todo_data.model_dump(exclude_unset=True)
    updated_todo = await update_todo(db, todo, update_data)
    await commit_and_invalidate_todo_lists(db, redis, current_user.id)

    return todo_response(updated_todo)


@router.delete("/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_todo(
    todo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Delete a todo item."""
    todo = await get_todo_by_id(db, todo_id, current_user.id)
    if not todo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Todo not found",
        )

    await delete_todo(db, todo)
    await commit_and_invalidate_todo_lists(db, redis, current_user.id)

    return None
    detach_tag_from_todo,
