"""Todo tests."""

import pytest
from httpx import AsyncClient


async def get_auth_token(client: AsyncClient, email: str = "todo@example.com") -> str:
    """Helper to register and get auth token."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123"},
    )
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_create_todo(client: AsyncClient):
    """Test creating a new todo."""
    token = await get_auth_token(client, "create@example.com")

    response = await client.post(
        "/api/v1/todos",
        json={"title": "Test Todo", "description": "A test todo item"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Todo"
    assert data["description"] == "A test todo item"
    assert data["completed"] is False


@pytest.mark.asyncio
async def test_get_todos(client: AsyncClient):
    """Test getting todo list."""
    token = await get_auth_token(client, "list@example.com")

    # Create a todo first
    await client.post(
        "/api/v1/todos",
        json={"title": "List Todo"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Get todos
    response = await client.get(
        "/api/v1/todos",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_update_todo(client: AsyncClient):
    """Test updating a todo."""
    token = await get_auth_token(client, "update@example.com")

    # Create a todo
    create_response = await client.post(
        "/api/v1/todos",
        json={"title": "Update Me"},
        headers={"Authorization": f"Bearer {token}"},
    )
    todo_id = create_response.json()["id"]

    # Update it
    response = await client.put(
        f"/api/v1/todos/{todo_id}",
        json={"title": "Updated Title", "completed": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"


@pytest.mark.asyncio
async def test_delete_todo(client: AsyncClient):
    """Test deleting a todo."""
    token = await get_auth_token(client, "delete@example.com")

    # Create a todo
    create_response = await client.post(
        "/api/v1/todos",
        json={"title": "Delete Me"},
        headers={"Authorization": f"Bearer {token}"},
    )
    todo_id = create_response.json()["id"]

    # Delete it
    response = await client.delete(
        f"/api/v1/todos/{todo_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_get_single_todo(client: AsyncClient):
    """Test getting a single todo by ID."""
    token = await get_auth_token(client, "single@example.com")

    # Create a todo
    create_response = await client.post(
        "/api/v1/todos",
        json={"title": "Single Todo", "description": "Get me"},
        headers={"Authorization": f"Bearer {token}"},
    )
    todo_id = create_response.json()["id"]

    # Get it
    response = await client.get(
        f"/api/v1/todos/{todo_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Single Todo"


@pytest.mark.asyncio
async def test_owner_can_read_update_and_delete_own_todo(client: AsyncClient):
    """An authenticated owner retains full access to their own todo."""
    token = await get_auth_token(client, "ownership-owner@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    created = await client.post(
        "/api/v1/todos",
        json={"title": "Owner todo", "description": "Private"},
        headers=headers,
    )
    assert created.status_code == 201
    todo_id = created.json()["id"]

    read = await client.get(f"/api/v1/todos/{todo_id}", headers=headers)
    assert read.status_code == 200
    assert read.json()["id"] == todo_id

    updated = await client.put(
        f"/api/v1/todos/{todo_id}",
        json={"title": "Owner updated"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Owner updated"

    deleted = await client.delete(f"/api/v1/todos/{todo_id}", headers=headers)
    assert deleted.status_code == 204
    assert (
        await client.get(f"/api/v1/todos/{todo_id}", headers=headers)
    ).status_code == 404


@pytest.mark.asyncio
async def test_non_owner_cannot_read_update_or_delete_todos(client: AsyncClient):
    """A foreign todo must be indistinguishable from a nonexistent resource."""
    owner_token = await get_auth_token(client, "ownership-a@example.com")
    other_token = await get_auth_token(client, "ownership-b@example.com")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    other_headers = {"Authorization": f"Bearer {other_token}"}

    todo_ids = []
    for operation in ("read", "update", "delete"):
        created = await client.post(
            "/api/v1/todos",
            json={"title": f"Private {operation}"},
            headers=owner_headers,
        )
        assert created.status_code == 201
        todo_ids.append(created.json()["id"])

    foreign_read = await client.get(
        f"/api/v1/todos/{todo_ids[0]}", headers=other_headers
    )
    foreign_update = await client.put(
        f"/api/v1/todos/{todo_ids[1]}",
        json={"title": "Unauthorized update"},
        headers=other_headers,
    )
    foreign_delete = await client.delete(
        f"/api/v1/todos/{todo_ids[2]}", headers=other_headers
    )

    assert {
        "read": foreign_read.status_code,
        "update": foreign_update.status_code,
        "delete": foreign_delete.status_code,
    } == {"read": 404, "update": 404, "delete": 404}

    for todo_id in todo_ids:
        owner_read = await client.get(f"/api/v1/todos/{todo_id}", headers=owner_headers)
        assert owner_read.status_code == 200


@pytest.mark.asyncio
async def test_todo_list_cache_is_isolated_by_user(client: AsyncClient):
    """A cached list for one user must never be served to another user."""
    user_a_token = await get_auth_token(client, "cache-user-a@example.com")
    user_b_token = await get_auth_token(client, "cache-user-b@example.com")
    user_a_headers = {"Authorization": f"Bearer {user_a_token}"}
    user_b_headers = {"Authorization": f"Bearer {user_b_token}"}

    await client.post(
        "/api/v1/todos", json={"title": "User A todo"}, headers=user_a_headers
    )
    await client.post(
        "/api/v1/todos", json={"title": "User B todo"}, headers=user_b_headers
    )

    user_a_list = await client.get("/api/v1/todos", headers=user_a_headers)
    user_b_list = await client.get("/api/v1/todos", headers=user_b_headers)

    assert [item["title"] for item in user_a_list.json()["items"]] == ["User A todo"]
    assert [item["title"] for item in user_b_list.json()["items"]] == ["User B todo"]


@pytest.mark.asyncio
async def test_todo_list_cache_is_isolated_by_page(client: AsyncClient):
    """A cached first page must not be reused for a later page."""
    token = await get_auth_token(client, "cache-pages@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    for title in ("First todo", "Second todo"):
        await client.post("/api/v1/todos", json={"title": title}, headers=headers)

    page_one = await client.get("/api/v1/todos?page=1&size=1", headers=headers)
    page_two = await client.get("/api/v1/todos?page=2&size=1", headers=headers)

    assert page_one.json()["page"] == 1
    assert page_two.json()["page"] == 2
    assert page_one.json()["items"][0]["id"] != page_two.json()["items"][0]["id"]


@pytest.mark.asyncio
async def test_todo_list_cache_is_isolated_by_page_size(client: AsyncClient):
    """Responses cached at one page size must not alias another size."""
    token = await get_auth_token(client, "cache-sizes@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    for index in range(3):
        await client.post(
            "/api/v1/todos", json={"title": f"Todo {index}"}, headers=headers
        )

    size_one = await client.get("/api/v1/todos?page=1&size=1", headers=headers)
    size_two = await client.get("/api/v1/todos?page=1&size=2", headers=headers)

    assert size_one.json()["size"] == 1
    assert len(size_one.json()["items"]) == 1
    assert size_two.json()["size"] == 2
    assert len(size_two.json()["items"]) == 2
