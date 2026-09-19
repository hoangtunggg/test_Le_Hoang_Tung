import uuid
from datetime import datetime

from sqlalchemy import delete, func, insert, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tag import todo_tags
from app.models.todo import Todo
from app.schemas.todo import TodoCreate


async def create_todo(
    db: AsyncSession, todo_data: TodoCreate, user_id: uuid.UUID
) -> Todo:
    todo = Todo(
        title=todo_data.title,
        description=todo_data.description,
        user_id=user_id,
    )
    db.add(todo)
    await db.flush()
    await db.refresh(todo)
    return todo


async def get_todos(
    db: AsyncSession,
    user_id: uuid.UUID,
    skip: int = 0,
    limit: int = 20,
    status: str | None = None,
    tag_id: uuid.UUID | None = None,
    keyword: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> tuple[list[Todo], int]:
    """Get a user's todos with filters and deterministic pagination."""
    filters = [Todo.user_id == user_id]
    query = select(Todo)
    count_query = select(func.count(func.distinct(Todo.id))).select_from(Todo)

    if status == "active":
        filters.append(Todo.completed.is_(False))
    elif status == "completed":
        filters.append(Todo.completed.is_(True))

    if tag_id is not None:
        query = query.join(todo_tags, todo_tags.c.todo_id == Todo.id)
        count_query = count_query.join(todo_tags, todo_tags.c.todo_id == Todo.id)
        filters.append(todo_tags.c.tag_id == tag_id)

    if keyword:
        pattern = f"%{keyword}%"
        filters.append(
            or_(
                Todo.title.ilike(pattern),
                Todo.description.ilike(pattern),
            )
        )

    if date_from is not None:
        filters.append(Todo.created_at >= date_from)
    if date_to is not None:
        filters.append(Todo.created_at <= date_to)

    query = (
        query.where(*filters)
        .distinct()
        .order_by(Todo.created_at.desc(), Todo.id.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    todos = list(result.scalars().unique().all())

    total = await db.execute(count_query.where(*filters))

    return todos, total.scalar_one()


async def get_todo_by_id(
    db: AsyncSession, todo_id: uuid.UUID, user_id: uuid.UUID
) -> Todo | None:
    result = await db.execute(
        select(Todo).where(Todo.id == todo_id, Todo.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def bulk_update_todo_status(
    db: AsyncSession,
    todo_ids: list[uuid.UUID],
    user_id: uuid.UUID,
    completed: bool,
) -> list[Todo] | None:
    """Update every requested todo only when all are owned by one user."""
    todos_result = await db.execute(
        select(Todo)
        .where(Todo.id.in_(todo_ids), Todo.user_id == user_id)
        .with_for_update()
    )
    todos = list(todos_result.scalars().all())

    if len(todos) != len(set(todo_ids)):
        return None

    for todo in todos:
        todo.completed = completed

    await db.flush()
    return todos


async def attach_tag_to_todo(
    db: AsyncSession, todo_id: uuid.UUID, tag_id: uuid.UUID
) -> bool:
    """Create a todo/tag mapping. Returns False when it already exists."""
    existing = await db.scalar(
        select(todo_tags.c.todo_id).where(
            todo_tags.c.todo_id == todo_id, todo_tags.c.tag_id == tag_id
        )
    )
    if existing is not None:
        return False
    await db.execute(insert(todo_tags).values(todo_id=todo_id, tag_id=tag_id))
    await db.flush()
    return True


async def detach_tag_from_todo(
    db: AsyncSession, todo_id: uuid.UUID, tag_id: uuid.UUID
) -> bool:
    """Remove a todo/tag mapping. Returns False when it does not exist."""
    result = await db.execute(
        delete(todo_tags).where(
            todo_tags.c.todo_id == todo_id, todo_tags.c.tag_id == tag_id
        )
    )
    await db.flush()
    return result.rowcount == 1


async def update_todo(db: AsyncSession, todo: Todo, update_data: dict) -> Todo:
    for key, value in update_data.items():
        setattr(todo, key, value)
    await db.flush()
    await db.refresh(todo)
    return todo


async def delete_todo(db: AsyncSession, todo: Todo) -> None:
    await db.delete(todo)
    await db.flush()
