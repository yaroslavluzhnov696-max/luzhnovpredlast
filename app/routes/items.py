from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis.asyncio as redis

from app.database import get_db
from app.redis_client import get_redis
from app.models import Item
from app.schemas import ItemCreate, ItemUpdate, ItemResponse

router = APIRouter(prefix="/items", tags=["items"])


@router.get("/", response_model=list[ItemResponse])
async def list_items(
    db: AsyncSession = Depends(get_db),
    r: redis.Redis = Depends(get_redis),
):
    # Пробуем получить из кеша
    cached = await r.get("items:all")
    if cached:
        import json
        return [ItemResponse(**item) for item in json.loads(cached)]

    result = await db.execute(select(Item).order_by(Item.id))
    items = result.scalars().all()

    # Сохраняем в кеш на 60 секунд
    import json
    items_data = [
        {
            "id": i.id,
            "title": i.title,
            "description": i.description,
            "created_at": i.created_at.isoformat(),
            "updated_at": i.updated_at.isoformat(),
        }
        for i in items
    ]
    await r.set("items:all", json.dumps(items_data), ex=60)

    return items


@router.get("/{item_id}", response_model=ItemResponse)
async def get_item(item_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.post("/", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
async def create_item(
    payload: ItemCreate,
    db: AsyncSession = Depends(get_db),
    r: redis.Redis = Depends(get_redis),
):
    item = Item(title=payload.title, description=payload.description)
    db.add(item)
    await db.commit()
    await db.refresh(item)

    # Инвалидируем кеш
    await r.delete("items:all")

    return item


@router.patch("/{item_id}", response_model=ItemResponse)
async def update_item(
    item_id: int,
    payload: ItemUpdate,
    db: AsyncSession = Depends(get_db),
    r: redis.Redis = Depends(get_redis),
):
    result = await db.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if payload.title is not None:
        item.title = payload.title
    if payload.description is not None:
        item.description = payload.description

    await db.commit()
    await db.refresh(item)

    await r.delete("items:all")

    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    r: redis.Redis = Depends(get_redis),
):
    result = await db.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    await db.delete(item)
    await db.commit()

    await r.delete("items:all")