"""Auth tests."""

from datetime import timedelta

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    """Test successful user registration."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "test@example.com", "password": "password123"},
    )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    """Test successful login after registration."""
    # Register first
    await client.post(
        "/api/v1/auth/register",
        json={"email": "login@example.com", "password": "password123"},
    )

    # Then login
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_get_current_user(client: AsyncClient):
    """Test getting current user info."""
    # Register and get token
    reg_response = await client.post(
        "/api/v1/auth/register",
        json={"email": "me@example.com", "password": "password123"},
    )
    token = reg_response.json()["access_token"]

    # Get current user
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "me@example.com"


@pytest.mark.asyncio
async def test_logout(client: AsyncClient):
    """Test logout endpoint."""
    # Register and get token
    reg_response = await client.post(
        "/api/v1/auth/register",
        json={"email": "logout@example.com", "password": "password123"},
    )
    token = reg_response.json()["access_token"]

    # Logout
    response = await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Successfully logged out"


@pytest.mark.asyncio
async def test_valid_access_token_is_accepted(client: AsyncClient):
    """A current access token authenticates an access-protected endpoint."""
    registration = await client.post(
        "/api/v1/auth/register",
        json={"email": "valid-access@example.com", "password": "password123"},
    )

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {registration.json()['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "valid-access@example.com"


@pytest.mark.asyncio
async def test_expired_access_token_is_rejected(client: AsyncClient):
    """An expired access token cannot authenticate a request."""
    registration = await client.post(
        "/api/v1/auth/register",
        json={"email": "expired-access@example.com", "password": "password123"},
    )
    current_user = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {registration.json()['access_token']}"},
    )
    expired_token = create_access_token(
        data={"sub": current_user.json()["id"]},
        expires_delta=timedelta(seconds=-1),
    )

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_tampered_access_token_is_rejected(client: AsyncClient):
    """A token with a modified signature remains invalid."""
    registration = await client.post(
        "/api/v1/auth/register",
        json={"email": "tampered-access@example.com", "password": "password123"},
    )
    header, payload, signature = registration.json()["access_token"].split(".")
    replacement = "A" if signature[0] != "A" else "B"
    tampered_token = f"{header}.{payload}.{replacement}{signature[1:]}"

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tampered_token}"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_malformed_access_token_is_rejected(client: AsyncClient):
    """A value that is not a JWT remains invalid."""
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-jwt"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_is_rejected_by_access_endpoint(client: AsyncClient):
    """A refresh token cannot authenticate an access-protected endpoint."""
    registration = await client.post(
        "/api/v1/auth/register",
        json={"email": "refresh-as-access@example.com", "password": "password123"},
    )

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {registration.json()['refresh_token']}"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_valid_refresh_token_is_accepted_by_refresh_flow(client: AsyncClient):
    """A current refresh token can issue a new usable access token."""
    registration = await client.post(
        "/api/v1/auth/register",
        json={"email": "valid-refresh@example.com", "password": "password123"},
    )

    refresh_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": registration.json()["refresh_token"]},
    )
    me_response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {refresh_response.json()['access_token']}"},
    )

    assert refresh_response.status_code == 200
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "valid-refresh@example.com"


@pytest.mark.asyncio
async def test_access_token_is_rejected_by_refresh_flow(client: AsyncClient):
    """An access token cannot be exchanged by the refresh-only endpoint."""
    registration = await client.post(
        "/api/v1/auth/register",
        json={"email": "access-as-refresh@example.com", "password": "password123"},
    )

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": registration.json()["access_token"]},
    )

    assert response.status_code == 401
