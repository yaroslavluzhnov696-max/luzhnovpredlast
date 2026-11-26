@"
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_create_item(client: AsyncClient):
    resp = await client.post(
        "/items/", json={"title": "Test", "description": "Hello"}
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Test"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_items(client: AsyncClient):
    resp = await client.get("/items/")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_get_item_not_found(client: AsyncClient):
    resp = await client.get("/items/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_item_validation(client: AsyncClient):
    resp = await client.post("/items/", json={"title": ""})
    assert resp.status_code == 422
"@ | Out-File -FilePath "tests/test_items.py" -Encoding utf8