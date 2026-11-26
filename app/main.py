from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.database import engine, Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="FastAPI CRUD App",
    description="Приложение с PostgreSQL и Redis в Docker",
    version="1.0.0",
    lifespan=lifespan,
)


# Импортируем роутер внутри функции, чтобы избежать проблем с пакетами
@app.on_event("startup")
async def startup():
    from app.routers.items import router as items_router
    app.include_router(items_router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}