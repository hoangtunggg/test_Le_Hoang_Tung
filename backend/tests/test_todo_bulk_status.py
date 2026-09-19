"""Tests for transactional bulk todo status updates."""

import pytest
from httpx import AsyncClient


async def register_headers(client: AsyncClient, email: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def create_todo(client: AsyncClient, headers: dict[str, str], title: str) -> str:
    response = await client.post(
        "/api/v1/todos", json={"title": title}, headers=headers
    )
    assert response.status_code == 201
    return response.json()["id"]


@pytest.mark.asyncio
async def test_bulk_status_updates_all_owned_todos_and_invalidates_cache(
    client: AsyncClient,
):
    headers = await register_headers(client, "bulk-success@example.com")
    first_id = await create_todo(client, headers, "First todo")
    second_id = await create_todo(client, headers, "Second todo")

    cached_before_update = await client.get("/api/v1/todos", headers=headers)
    assert cached_before_update.status_code == 200
    assert {item["completed"] for item in cached_before_update.json()["items"]} == {
        False
    }

    response = await client.patch(
        "/api/v1/todos/bulk-status",
        json={"todo_ids": [first_id, second_id], "completed": True},
        headers=headers,
    )
    after_update = await client.get("/api/v1/todos", headers=headers)

    assert response.status_code == 200
    assert {item["id"] for item in response.json()} == {first_id, second_id}
    assert {item["completed"] for item in response.json()} == {True}
    assert {item["completed"] for item in after_update.json()["items"]} == {True}


@pytest.mark.asyncio
async def test_bulk_status_supports_explicit_true(client: AsyncClient):
    headers = await register_headers(client, "bulk-true@example.com")
    todo_id = await create_todo(client, headers, "Set complete")

    response = await client.patch(
        "/api/v1/todos/bulk-status",
        json={"todo_ids": [todo_id], "completed": True},
        headers=headers,
    )
    persisted = await client.get(f"/api/v1/todos/{todo_id}", headers=headers)

    assert response.status_code == 200
    assert response.json()[0]["completed"] is True
    assert persisted.json()["completed"] is True


@pytest.mark.asyncio
async def test_bulk_status_supports_explicit_false(client: AsyncClient):
    headers = await register_headers(client, "bulk-false@example.com")
    todo_id = await create_todo(client, headers, "Set active")
    set_completed = await client.put(
        f"/api/v1/todos/{todo_id}", json={"completed": True}, headers=headers
    )
    assert set_completed.status_code == 200

    response = await client.patch(
        "/api/v1/todos/bulk-status",
        json={"todo_ids": [todo_id], "completed": False},
        headers=headers,
    )
    persisted = await client.get(f"/api/v1/todos/{todo_id}", headers=headers)

    assert response.status_code == 200
    assert response.json()[0]["completed"] is False
    assert persisted.json()["completed"] is False


@pytest.mark.asyncio
async def test_bulk_status_rejects_mixed_owner_request_without_partial_update(
    client: AsyncClient,
):
    owner_headers = await register_headers(client, "bulk-owner@example.com")
    other_headers = await register_headers(client, "bulk-other@example.com")
    owner_todo_id = await create_todo(client, owner_headers, "Owner todo")
    other_todo_id = await create_todo(client, other_headers, "Other todo")

    response = await client.patch(
        "/api/v1/todos/bulk-status",
        json={"todo_ids": [owner_todo_id, other_todo_id], "completed": True},
        headers=owner_headers,
    )
    owner_persisted = await client.get(
        f"/api/v1/todos/{owner_todo_id}", headers=owner_headers
    )
    other_persisted = await client.get(
        f"/api/v1/todos/{other_todo_id}", headers=other_headers
    )

    assert response.status_code == 404
    assert owner_persisted.json()["completed"] is False
    assert other_persisted.json()["completed"] is False
