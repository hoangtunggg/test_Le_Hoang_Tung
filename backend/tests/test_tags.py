import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.tag import Tag, todo_tags
from app.models.todo import Todo


async def register_user(client: AsyncClient, email: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.asyncio
async def test_create_and_list_own_tags(client: AsyncClient):
    headers = await register_user(client, "tag-owner@example.com")

    created = await client.post(
        "/api/v1/tags",
        json={"name": "Work", "color": "blue"},
        headers=headers,
    )
    listed = await client.get("/api/v1/tags", headers=headers)

    assert created.status_code == 201
    assert created.json()["name"] == "Work"
    assert created.json()["color"] == "blue"
    assert listed.status_code == 200
    assert [tag["id"] for tag in listed.json()] == [created.json()["id"]]


@pytest.mark.asyncio
async def test_tags_require_authentication(client: AsyncClient):
    listed = await client.get("/api/v1/tags")
    created = await client.post("/api/v1/tags", json={"name": "Work"})

    assert listed.status_code == 403
    assert created.status_code == 403


@pytest.mark.asyncio
async def test_duplicate_tag_name_is_rejected_case_insensitively(client: AsyncClient):
    headers = await register_user(client, "tag-duplicate@example.com")
    await client.post(
        "/api/v1/tags",
        json={"name": "Work"},
        headers=headers,
    )

    duplicate = await client.post(
        "/api/v1/tags",
        json={"name": "work"},
        headers=headers,
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "Tag name already exists"


@pytest.mark.asyncio
async def test_owner_can_update_and_delete_own_tag(client: AsyncClient):
    headers = await register_user(client, "tag-owner-update@example.com")
    created = await client.post(
        "/api/v1/tags",
        json={"name": "Before", "color": "blue"},
        headers=headers,
    )
    tag_id = created.json()["id"]

    updated = await client.patch(
        f"/api/v1/tags/{tag_id}",
        json={"name": "After", "color": None},
        headers=headers,
    )
    deleted = await client.delete(f"/api/v1/tags/{tag_id}", headers=headers)
    listed = await client.get("/api/v1/tags", headers=headers)

    assert updated.status_code == 200
    assert updated.json()["name"] == "After"
    assert updated.json()["color"] is None
    assert deleted.status_code == 204
    assert listed.json() == []


@pytest.mark.asyncio
async def test_deleting_tag_removes_todo_tag_mappings(client: AsyncClient, db_session):
    headers = await register_user(client, "tag-mapping-owner@example.com")
    current_user = await client.get("/api/v1/auth/me", headers=headers)
    user_id = uuid.UUID(current_user.json()["id"])
    tag = Tag(user_id=user_id, name="Mapped")
    todo = Todo(title="Mapped todo", user_id=user_id)
    todo.tags.append(tag)
    db_session.add(todo)
    await db_session.commit()

    deleted = await client.delete(f"/api/v1/tags/{tag.id}", headers=headers)
    mappings = await db_session.execute(
        select(todo_tags).where(todo_tags.c.tag_id == tag.id)
    )

    assert deleted.status_code == 204
    assert mappings.first() is None


@pytest.mark.asyncio
async def test_user_cannot_read_update_or_delete_another_users_tag(client: AsyncClient):
    owner_headers = await register_user(client, "tag-owner-isolated@example.com")
    other_headers = await register_user(client, "tag-other-isolated@example.com")
    created = await client.post(
        "/api/v1/tags",
        json={"name": "Private"},
        headers=owner_headers,
    )
    tag_id = created.json()["id"]

    other_list = await client.get("/api/v1/tags", headers=other_headers)
    foreign_update = await client.patch(
        f"/api/v1/tags/{tag_id}",
        json={"name": "Stolen"},
        headers=other_headers,
    )
    foreign_delete = await client.delete(
        f"/api/v1/tags/{tag_id}",
        headers=other_headers,
    )
    owner_list = await client.get("/api/v1/tags", headers=owner_headers)

    assert other_list.status_code == 200
    assert other_list.json() == []
    assert foreign_update.status_code == 404
    assert foreign_delete.status_code == 404
    assert [tag["name"] for tag in owner_list.json()] == ["Private"]


@pytest.mark.asyncio
async def test_tag_name_and_color_lengths_are_validated(client: AsyncClient):
    headers = await register_user(client, "tag-validation@example.com")

    name_too_long = await client.post(
        "/api/v1/tags",
        json={"name": "n" * 51},
        headers=headers,
    )
    color_too_long = await client.post(
        "/api/v1/tags",
        json={"name": "Valid", "color": "c" * 21},
        headers=headers,
    )

    assert name_too_long.status_code == 422
    assert color_too_long.status_code == 422


@pytest.mark.asyncio
async def test_tag_mapping_mutations_invalidate_cached_todo_list(client: AsyncClient):
    headers = await register_user(client, "tag-mapping-cache@example.com")
    todo = await client.post("/api/v1/todos", json={"title": "Tagged"}, headers=headers)
    tag = await client.post("/api/v1/tags", json={"name": "Work"}, headers=headers)
    todo_id, tag_id = todo.json()["id"], tag.json()["id"]
    assert (await client.get("/api/v1/todos", headers=headers)).json()["items"][0][
        "tags"
    ] == []

    attached = await client.post(
        f"/api/v1/todos/{todo_id}/tags", json={"tag_id": tag_id}, headers=headers
    )
    after_attach = await client.get("/api/v1/todos", headers=headers)
    detached = await client.delete(
        f"/api/v1/todos/{todo_id}/tags/{tag_id}", headers=headers
    )
    after_detach = await client.get("/api/v1/todos", headers=headers)

    assert attached.status_code == 204
    assert [item["id"] for item in after_attach.json()["items"][0]["tags"]] == [tag_id]
    assert detached.status_code == 204
    assert after_detach.json()["items"][0]["tags"] == []


@pytest.mark.asyncio
async def test_foreign_todo_or_tag_cannot_be_mapped(client: AsyncClient):
    owner_headers = await register_user(client, "tag-map-owner@example.com")
    other_headers = await register_user(client, "tag-map-other@example.com")
    owner_todo = await client.post(
        "/api/v1/todos", json={"title": "Owner"}, headers=owner_headers
    )
    owner_tag = await client.post(
        "/api/v1/tags", json={"name": "Owner tag"}, headers=owner_headers
    )
    other_todo = await client.post(
        "/api/v1/todos", json={"title": "Other"}, headers=other_headers
    )
    other_tag = await client.post(
        "/api/v1/tags", json={"name": "Other tag"}, headers=other_headers
    )

    foreign_todo = await client.post(
        f"/api/v1/todos/{owner_todo.json()['id']}/tags",
        json={"tag_id": other_tag.json()["id"]},
        headers=other_headers,
    )
    foreign_tag = await client.post(
        f"/api/v1/todos/{other_todo.json()['id']}/tags",
        json={"tag_id": owner_tag.json()["id"]},
        headers=other_headers,
    )

    assert foreign_todo.status_code == 404
    assert foreign_tag.status_code == 404


@pytest.mark.asyncio
async def test_deleting_tag_invalidates_cached_filtered_todos(client: AsyncClient):
    headers = await register_user(client, "tag-delete-cache@example.com")
    todo = await client.post("/api/v1/todos", json={"title": "Tagged"}, headers=headers)
    tag = await client.post("/api/v1/tags", json={"name": "Delete me"}, headers=headers)
    assert (
        await client.post(
            f"/api/v1/todos/{todo.json()['id']}/tags",
            json={"tag_id": tag.json()["id"]},
            headers=headers,
        )
    ).status_code == 204
    cached = await client.get(
        "/api/v1/todos", params={"tag_id": tag.json()["id"]}, headers=headers
    )
    deleted = await client.delete(f"/api/v1/tags/{tag.json()['id']}", headers=headers)
    after_delete = await client.get(
        "/api/v1/todos", params={"tag_id": tag.json()["id"]}, headers=headers
    )

    assert cached.json()["total"] == 1
    assert deleted.status_code == 204
    assert after_delete.json()["total"] == 0
