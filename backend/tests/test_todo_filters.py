import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from app.api.v1.todos import todo_list_cache_key
from app.models.tag import Tag
from app.models.todo import Todo


async def register_user(client: AsyncClient, email: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def current_user_id(client: AsyncClient, headers: dict[str, str]) -> uuid.UUID:
    response = await client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    return uuid.UUID(response.json()["id"])


@pytest.mark.asyncio
async def test_status_keyword_and_date_filters(client: AsyncClient, db_session):
    headers = await register_user(client, "filter-fields@example.com")
    user_id = await current_user_id(client, headers)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    db_session.add_all(
        [
            Todo(
                user_id=user_id,
                title="Alpha report",
                description="Urgent quarterly review",
                completed=False,
                created_at=start,
                updated_at=start,
            ),
            Todo(
                user_id=user_id,
                title="Beta notes",
                description="Archive alpha details",
                completed=True,
                created_at=start + timedelta(days=1),
                updated_at=start + timedelta(days=1),
            ),
            Todo(
                user_id=user_id,
                title="Gamma plan",
                description="Later work",
                completed=False,
                created_at=start + timedelta(days=2),
                updated_at=start + timedelta(days=2),
            ),
        ]
    )
    await db_session.commit()

    active = await client.get(
        "/api/v1/todos", params={"status": "active"}, headers=headers
    )
    completed = await client.get(
        "/api/v1/todos", params={"status": "completed"}, headers=headers
    )
    keyword = await client.get(
        "/api/v1/todos", params={"keyword": "urgent"}, headers=headers
    )
    date_range = await client.get(
        "/api/v1/todos",
        params={
            "date_from": (start + timedelta(hours=12)).isoformat(),
            "date_to": (start + timedelta(days=1, hours=12)).isoformat(),
        },
        headers=headers,
    )

    assert {item["title"] for item in active.json()["items"]} == {
        "Alpha report",
        "Gamma plan",
    }
    assert [item["title"] for item in completed.json()["items"]] == ["Beta notes"]
    assert [item["title"] for item in keyword.json()["items"]] == ["Alpha report"]
    assert [item["title"] for item in date_range.json()["items"]] == ["Beta notes"]


@pytest.mark.asyncio
async def test_tag_filter_returns_only_mapped_owned_todos(
    client: AsyncClient, db_session
):
    headers = await register_user(client, "filter-tag@example.com")
    user_id = await current_user_id(client, headers)
    tag = Tag(user_id=user_id, name="Work")
    matching = Todo(user_id=user_id, title="Tagged todo")
    matching.tags.append(tag)
    db_session.add_all([matching, Todo(user_id=user_id, title="Untagged todo")])
    await db_session.commit()

    response = await client.get(
        "/api/v1/todos", params={"tag_id": str(tag.id)}, headers=headers
    )

    assert response.status_code == 200
    assert [item["title"] for item in response.json()["items"]] == ["Tagged todo"]
    assert response.json()["total"] == 1


@pytest.mark.asyncio
async def test_filters_combine_with_and(client: AsyncClient, db_session):
    headers = await register_user(client, "filter-combined@example.com")
    user_id = await current_user_id(client, headers)
    start = datetime(2026, 2, 1, tzinfo=timezone.utc)
    tag = Tag(user_id=user_id, name="Focus")
    matching = Todo(
        user_id=user_id,
        title="Quarterly focus",
        description="Review results",
        completed=False,
        created_at=start,
        updated_at=start,
    )
    matching.tags.append(tag)
    db_session.add_all(
        [
            matching,
            Todo(
                user_id=user_id,
                title="Quarterly completed",
                completed=True,
                created_at=start,
                updated_at=start,
            ),
            Todo(
                user_id=user_id,
                title="Outside range",
                completed=False,
                created_at=start + timedelta(days=2),
                updated_at=start + timedelta(days=2),
            ),
        ]
    )
    await db_session.commit()

    response = await client.get(
        "/api/v1/todos",
        params={
            "status": "active",
            "tag_id": str(tag.id),
            "keyword": "quarterly",
            "date_from": (start - timedelta(seconds=1)).isoformat(),
            "date_to": (start + timedelta(seconds=1)).isoformat(),
        },
        headers=headers,
    )

    assert [item["title"] for item in response.json()["items"]] == ["Quarterly focus"]


@pytest.mark.asyncio
async def test_foreign_tag_id_cannot_expose_other_users_todos(
    client: AsyncClient, db_session
):
    owner_headers = await register_user(client, "filter-owner@example.com")
    other_headers = await register_user(client, "filter-other@example.com")
    owner_id = await current_user_id(client, owner_headers)
    other_id = await current_user_id(client, other_headers)
    owner_tag = Tag(user_id=owner_id, name="Owner only")
    owner_todo = Todo(user_id=owner_id, title="Owner private todo")
    owner_todo.tags.append(owner_tag)
    db_session.add_all([owner_todo, Todo(user_id=other_id, title="Other user todo")])
    await db_session.commit()

    response = await client.get(
        "/api/v1/todos",
        params={"tag_id": str(owner_tag.id)},
        headers=other_headers,
    )

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 0


@pytest.mark.asyncio
async def test_deterministic_pagination_uses_created_at_then_id(
    client: AsyncClient, db_session
):
    headers = await register_user(client, "filter-pagination@example.com")
    user_id = await current_user_id(client, headers)
    created_at = datetime(2026, 3, 1, tzinfo=timezone.utc)
    todo_ids = [
        uuid.UUID("00000000-0000-0000-0000-000000000001"),
        uuid.UUID("00000000-0000-0000-0000-000000000002"),
        uuid.UUID("00000000-0000-0000-0000-000000000003"),
    ]
    db_session.add_all(
        [
            Todo(
                id=todo_id,
                user_id=user_id,
                title=f"Todo {index}",
                created_at=created_at,
                updated_at=created_at,
            )
            for index, todo_id in enumerate(todo_ids, start=1)
        ]
    )
    await db_session.commit()

    page_one = await client.get(
        "/api/v1/todos", params={"page": 1, "page_size": 2}, headers=headers
    )
    page_two = await client.get(
        "/api/v1/todos", params={"page": 2, "page_size": 2}, headers=headers
    )

    assert [item["id"] for item in page_one.json()["items"]] == [
        str(todo_ids[2]),
        str(todo_ids[1]),
    ]
    assert [item["id"] for item in page_two.json()["items"]] == [str(todo_ids[0])]
    assert page_one.json()["total"] == 3
    assert page_two.json()["total"] == 3


def test_todo_list_cache_key_isolated_by_all_filter_dimensions():
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    tag_id = uuid.UUID("00000000-0000-0000-0000-000000000002")
    base = {
        "user_id": user_id,
        "status": "active",
        "tag_id": tag_id,
        "keyword": "Quarterly review",
        "date_from": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "date_to": datetime(2026, 1, 31, tzinfo=timezone.utc),
        "page": 1,
        "page_size": 20,
    }
    variants = [
        base,
        {**base, "status": "completed"},
        {**base, "tag_id": None},
        {**base, "keyword": "different"},
        {**base, "date_from": None},
        {**base, "date_to": None},
        {**base, "page": 2},
        {**base, "page_size": 10},
        {**base, "user_id": uuid.UUID("00000000-0000-0000-0000-000000000003")},
    ]

    assert len({todo_list_cache_key(**variant) for variant in variants}) == len(
        variants
    )
