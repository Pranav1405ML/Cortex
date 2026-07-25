from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.core.config import settings


# echo=True prints every SQL query to the console — super useful
# while learning. Turn it off in production.
engine = create_async_engine(settings.DATABASE_URL, echo=True)


# expire_on_commit=False means: after you save something, you can still
# read its attributes without hitting the DB again. Just a convenience thing.
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession]:

    async with async_session_factory() as session:
        yield session
