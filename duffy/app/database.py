from typing import Iterator

from sqlalchemy.ext.asyncio import AsyncSession

from ..database import async_session_maker


async def req_db_async_session() -> Iterator[AsyncSession]:
    db_async_session = async_session_maker()
    try:
        yield db_async_session
    finally:
        await db_async_session.close()
