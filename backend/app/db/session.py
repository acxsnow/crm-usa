from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


def worker_session():
    """Sesión para tareas de Celery: motor propio sin pool, que se descarta al
    terminar. Cada tarea corre su propio `asyncio.run()`; con el pool global,
    las conexiones quedaban atadas al ciclo de la tarea anterior y la segunda
    tarea del mismo proceso fallaba con «attached to a different loop».
    Uso: `async with worker_session() as db: ...`."""
    from contextlib import asynccontextmanager

    from sqlalchemy.pool import NullPool

    @asynccontextmanager
    async def _ctx():
        motor = create_async_engine(settings.DATABASE_URL, echo=False, poolclass=NullPool)
        try:
            async with async_sessionmaker(motor, expire_on_commit=False, class_=AsyncSession)() as db:
                yield db
        finally:
            await motor.dispose()

    return _ctx()
