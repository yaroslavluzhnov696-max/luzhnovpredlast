import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.main import app
from app.database import get_db


# --- Тестовая БД (in-memory SQLite не подходит для asyncpg, используем отдельную схему) ---
# Для GitHub Actions используется реальный PostgreSQL через service container.
# Локально можно запускать через docker-compose с тестовой БД.

TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_db"


@pytest.fixture(autouse=True)
async def setup_db():
    """Создаём и очищаем таблицы перед каждым тестом."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    class Base(DeclarativeBase):
        pass

    # Импортируем модели, чтобы они зарегистрировались в метаданных
    from app.models import Item  # noqa: F401
    from app.database import Base as AppBase

    async with engine.begin() as conn:
        await conn.run_sync(AppBase.metadata.create_all)

    yield

    async with engine.begin() as conn:
        await conn.run_sync(AppBase.metadata.drop_all)

    await engine.dispose()


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
async def test_create_and_list_items(client: AsyncClient):
    # Создаём элемент
    create_resp = await client.post(
        "/items/", json={"title": "Test Item", "description": "Hello"}
    )
    assert create_resp.status_code == 201
    data = create_resp.json()
    assert data["title"] == "Test Item"
    assert "id" in data

    item_id = data["id"]

    # Получаем список
    list_resp = await client.get("/items/")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1

    # Получаем по ID
    get_resp = await client.get(f"/items/{item_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["title"] == "Test Item"


@pytest.mark.asyncio
async def test_update_item(client: AsyncClient):
    create_resp = await client.post(
        "/items/", json={"title": "Original", "description": "desc"}
    )
    item_id = create_resp.json()["id"]

    update_resp = await client.patch(
        f"/items/{item_id}", json={"title": "Updated"}
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["title"] == "Updated"


@pytest.mark.asyncio
async def test_delete_item(client: AsyncClient):
    create_resp = await client.post(
        "/items/", json={"title": "To Delete"}
    )
    item_id = create_resp.json()["id"]

    delete_resp = await client.delete(f"/items/{item_id}")
    assert delete_resp.status_code == 204

    get_resp = await client.get(f"/items/{item_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_create_item_validation(client: AsyncClient):
    # Пустой title должен вернуть 422
    resp = await client.post("/items/", json={"title": ""})
    assert resp.status_code == 422