"""Regression tests for resumable benchmark dataset seeding."""

import uuid

import pytest
from sqlalchemy import select

from app.db import seed as seed_module
from app.models.todo import Todo
from app.models.user import User
from tests.conftest import test_session_maker as session_maker


def configure_seed(monkeypatch: pytest.MonkeyPatch, users: int, todos: int) -> None:
    monkeypatch.setattr(seed_module, "async_session_maker", session_maker)
    monkeypatch.setattr(seed_module, "get_password_hash", lambda _: "test-hash")
    monkeypatch.setattr(seed_module, "TARGET_USERS", users)
    monkeypatch.setattr(seed_module, "TARGET_TODOS", todos)
    monkeypatch.setattr(seed_module, "USER_BATCH_SIZE", 2)
    monkeypatch.setattr(seed_module, "TODO_BATCH_SIZE", 3)


async def dataset_state() -> tuple[list[uuid.UUID], list[Todo]]:
    async with session_maker() as session:
        user_ids = list((await session.execute(select(User.id))).scalars().all())
        todos = list((await session.execute(select(Todo))).scalars().all())
    return user_ids, todos


async def add_existing_users(count: int) -> list[uuid.UUID]:
    users = [
        User(email=f"existing-{index}@example.com", hashed_password="test-hash")
        for index in range(count)
    ]
    async with session_maker() as session:
        session.add_all(users)
        await session.commit()
        return [user.id for user in users]


@pytest.mark.asyncio
async def test_seed_empty_database_reaches_targets(monkeypatch: pytest.MonkeyPatch):
    configure_seed(monkeypatch, users=3, todos=9)

    await seed_module.seed_db()

    user_ids, todos = await dataset_state()
    assert len(user_ids) == 3
    assert len(todos) == 9


@pytest.mark.asyncio
async def test_seed_partial_database_inserts_only_deficit(
    monkeypatch: pytest.MonkeyPatch,
):
    configure_seed(monkeypatch, users=3, todos=4)
    await seed_module.seed_db()
    _, original_todos = await dataset_state()
    original_ids = {todo.id for todo in original_todos}

    configure_seed(monkeypatch, users=5, todos=10)
    await seed_module.seed_db()

    user_ids, todos = await dataset_state()
    assert len(user_ids) == 5
    assert len(todos) == 10
    assert original_ids <= {todo.id for todo in todos}
    assert len({todo.id for todo in todos} - original_ids) == 6


@pytest.mark.asyncio
async def test_seed_same_target_is_idempotent(monkeypatch: pytest.MonkeyPatch):
    configure_seed(monkeypatch, users=3, todos=7)
    await seed_module.seed_db()
    original_user_ids, original_todos = await dataset_state()
    original_todo_ids = {todo.id for todo in original_todos}

    await seed_module.seed_db()

    user_ids, todos = await dataset_state()
    assert set(user_ids) == set(original_user_ids)
    assert {todo.id for todo in todos} == original_todo_ids


@pytest.mark.asyncio
async def test_seed_larger_target_grows_dataset(monkeypatch: pytest.MonkeyPatch):
    configure_seed(monkeypatch, users=2, todos=4)
    await seed_module.seed_db()

    configure_seed(monkeypatch, users=4, todos=11)
    await seed_module.seed_db()

    user_ids, todos = await dataset_state()
    assert len(user_ids) == 4
    assert len(todos) == 11


@pytest.mark.asyncio
async def test_seed_distributes_todos_across_existing_users(
    monkeypatch: pytest.MonkeyPatch,
):
    existing_user_ids = set(await add_existing_users(3))
    configure_seed(monkeypatch, users=5, todos=10)

    await seed_module.seed_db()

    user_ids, todos = await dataset_state()
    todo_user_ids = {todo.user_id for todo in todos}
    assert len(user_ids) == 5
    assert len(todos) == 10
    assert existing_user_ids <= todo_user_ids
