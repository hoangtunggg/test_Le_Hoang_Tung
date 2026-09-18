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
async def test_completed_can_toggle_from_false_to_true_and_back(client: AsyncClient):
    token = await get_auth_token(client, "toggle-completed@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    created = await client.post(
        "/api/v1/todos",
        json={"title": "Toggle completion", "description": "Keep me"},
        headers=headers,
    )
    todo_id = created.json()["id"]

    completed = await client.put(
        f"/api/v1/todos/{todo_id}",
        json={"completed": True},
        headers=headers,
    )
    completed_read = await client.get(f"/api/v1/todos/{todo_id}", headers=headers)
    active = await client.put(
        f"/api/v1/todos/{todo_id}",
        json={"completed": False},
        headers=headers,
    )
    active_read = await client.get(f"/api/v1/todos/{todo_id}", headers=headers)

    assert completed.status_code == 200
    assert completed.json()["completed"] is True
    assert completed_read.json()["completed"] is True
    assert active.status_code == 200
    assert active.json()["completed"] is False
    assert active_read.json()["completed"] is False


@pytest.mark.asyncio
async def test_title_only_update_preserves_description(client: AsyncClient):
    token = await get_auth_token(client, "preserve-description@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    created = await client.post(
        "/api/v1/todos",
        json={"title": "Original title", "description": "Original description"},
        headers=headers,
    )
    todo_id = created.json()["id"]

    updated = await client.put(
        f"/api/v1/todos/{todo_id}",
        json={"title": "Updated title"},
        headers=headers,
    )
    persisted = await client.get(f"/api/v1/todos/{todo_id}", headers=headers)

    assert updated.status_code == 200
    assert updated.json()["title"] == "Updated title"
    assert updated.json()["description"] == "Original description"
    assert persisted.json()["title"] == "Updated title"
    assert persisted.json()["description"] == "Original description"


@pytest.mark.asyncio
async def test_empty_update_preserves_all_fields(client: AsyncClient):
    token = await get_auth_token(client, "omitted-update@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    created = await client.post(
        "/api/v1/todos",
        json={"title": "Unchanged", "description": "Still present"},
        headers=headers,
    )
    todo_id = created.json()["id"]
    await client.put(
        f"/api/v1/todos/{todo_id}",
        json={"completed": True},
        headers=headers,
    )

    updated = await client.put(f"/api/v1/todos/{todo_id}", json={}, headers=headers)
    persisted = await client.get(f"/api/v1/todos/{todo_id}", headers=headers)
    expected = {
        "title": "Unchanged",
        "description": "Still present",
        "completed": True,
    }

    assert updated.status_code == 200
    assert {field: updated.json()[field] for field in expected} == expected
    assert {field: persisted.json()[field] for field in expected} == expected


@pytest.mark.asyncio
async def test_explicit_null_description_clears_description(client: AsyncClient):
    token = await get_auth_token(client, "clear-description@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    created = await client.post(
        "/api/v1/todos",
        json={"title": "Clear description", "description": "Remove me"},
        headers=headers,
    )
    todo_id = created.json()["id"]

    updated = await client.put(
        f"/api/v1/todos/{todo_id}",
        json={"description": None},
        headers=headers,
    )
    persisted = await client.get(f"/api/v1/todos/{todo_id}", headers=headers)

    assert updated.status_code == 200
    assert updated.json()["description"] is None
    assert persisted.json()["description"] is None


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

    for todo_id, operation in zip(todo_ids, ("read", "update", "delete"), strict=True):
        owner_read = await client.get(f"/api/v1/todos/{todo_id}", headers=owner_headers)
        assert owner_read.status_code == 200
        assert owner_read.json()["title"] == f"Private {operation}"


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


@pytest.mark.asyncio
async def test_create_invalidates_cached_todo_list(client: AsyncClient, redis_client):
    token = await get_auth_token(client, "cache-create@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    cached = await client.get("/api/v1/todos", headers=headers)
    assert len(redis_client.data) == 1
    created = await client.post(
        "/api/v1/todos",
        json={"title": "Created after cache"},
        headers=headers,
    )
    assert redis_client.data == {}
    refreshed = await client.get("/api/v1/todos", headers=headers)

    assert cached.json()["items"] == []
    assert created.status_code == 201
    assert [item["title"] for item in refreshed.json()["items"]] == [
        "Created after cache"
    ]


@pytest.mark.asyncio
async def test_update_invalidates_cached_todo_list(client: AsyncClient, redis_client):
    token = await get_auth_token(client, "cache-update@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    created = await client.post(
        "/api/v1/todos",
        json={"title": "Before update"},
        headers=headers,
    )
    todo_id = created.json()["id"]
    await client.get("/api/v1/todos", headers=headers)
    assert len(redis_client.data) == 1

    updated = await client.put(
        f"/api/v1/todos/{todo_id}",
        json={"title": "After update"},
        headers=headers,
    )
    assert redis_client.data == {}
    refreshed = await client.get("/api/v1/todos", headers=headers)

    assert updated.status_code == 200
    assert [item["title"] for item in refreshed.json()["items"]] == ["After update"]


@pytest.mark.asyncio
async def test_delete_invalidates_cached_todo_list(client: AsyncClient, redis_client):
    token = await get_auth_token(client, "cache-delete@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    created = await client.post(
        "/api/v1/todos",
        json={"title": "Delete after cache"},
        headers=headers,
    )
    todo_id = created.json()["id"]
    cached = await client.get("/api/v1/todos", headers=headers)
    assert len(redis_client.data) == 1

    deleted = await client.delete(f"/api/v1/todos/{todo_id}", headers=headers)
    assert redis_client.data == {}
    refreshed = await client.get("/api/v1/todos", headers=headers)

    assert len(cached.json()["items"]) == 1
    assert deleted.status_code == 204
    assert refreshed.json()["items"] == []


@pytest.mark.asyncio
async def test_mutation_invalidates_all_user_pagination_variants(
    client: AsyncClient, redis_client
):
    token = await get_auth_token(client, "cache-variants@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    created_todos = []
    for title in ("Variant one", "Variant two"):
        created = await client.post(
            "/api/v1/todos", json={"title": title}, headers=headers
        )
        created_todos.append(created.json())

    for query in ("page=1&size=1", "page=2&size=1", "page=1&size=2"):
        await client.get(f"/api/v1/todos?{query}", headers=headers)

    user_id = created_todos[0]["user_id"]
    user_cache_prefix = f"todos:list:user:{user_id}:"
    assert (
        len([key for key in redis_client.data if key.startswith(user_cache_prefix)])
        == 3
    )

    await client.put(
        f"/api/v1/todos/{created_todos[0]['id']}",
        json={"title": "Variant updated"},
        headers=headers,
    )

    assert not any(key.startswith(user_cache_prefix) for key in redis_client.data)


@pytest.mark.asyncio
async def test_user_mutation_preserves_other_users_cache(
    client: AsyncClient, redis_client
):
    user_a_token = await get_auth_token(client, "cache-mutation-a@example.com")
    user_b_token = await get_auth_token(client, "cache-mutation-b@example.com")
    user_a_headers = {"Authorization": f"Bearer {user_a_token}"}
    user_b_headers = {"Authorization": f"Bearer {user_b_token}"}
    user_a_todo = await client.post(
        "/api/v1/todos", json={"title": "User A cached"}, headers=user_a_headers
    )
    user_b_todo = await client.post(
        "/api/v1/todos", json={"title": "User B cached"}, headers=user_b_headers
    )
    await client.get("/api/v1/todos", headers=user_a_headers)
    await client.get("/api/v1/todos", headers=user_b_headers)

    user_a_prefix = f"todos:list:user:{user_a_todo.json()['user_id']}:"
    user_b_prefix = f"todos:list:user:{user_b_todo.json()['user_id']}:"
    user_b_cache = {
        key: value
        for key, value in redis_client.data.items()
        if key.startswith(user_b_prefix)
    }
    assert user_b_cache

    await client.put(
        f"/api/v1/todos/{user_a_todo.json()['id']}",
        json={"title": "User A changed"},
        headers=user_a_headers,
    )

    assert not any(key.startswith(user_a_prefix) for key in redis_client.data)
    assert {
        key: value
        for key, value in redis_client.data.items()
        if key.startswith(user_b_prefix)
    } == user_b_cache
