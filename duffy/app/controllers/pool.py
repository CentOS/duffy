"""This is the pool controller."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_404_NOT_FOUND, HTTP_422_UNPROCESSABLE_ENTITY

from ...api_models import PoolResult, PoolResultCollection
from ...database.model import Node
from ...nodes.pools import ConcreteNodePool
from ..database import req_db_async_session

router = APIRouter(prefix="/pools")


# http get http://localhost:8080/api/v1/pools
@router.get("", response_model=PoolResultCollection, tags=["pools"])
async def get_all_pools(db_async_session: AsyncSession = Depends(req_db_async_session)):
    """Return all pools."""
    pools = [
        {"name": pool.name, "fill-level": pool["fill-level"]}
        for pool in ConcreteNodePool.iter_pools()
        if "fill-level" in pool
    ]

    return {"action": "get", "pools": pools}


# http get http://localhost:8080/api/v1/pool/name-of-the-pool
@router.get("/{name}", response_model=PoolResult, tags=["pools"])
async def get_pool(name: str, db_async_session: AsyncSession = Depends(req_db_async_session)):
    """Return the pool with the specified **NAME**."""
    pool = ConcreteNodePool.known_pools.get(name)

    if pool is None:
        raise HTTPException(HTTP_404_NOT_FOUND)

    if "fill-level" not in pool:
        raise HTTPException(HTTP_422_UNPROCESSABLE_ENTITY)

    pool_result = {
        "name": name,
        "fill-level": pool["fill-level"],
        "levels": {
            "provisioning": 0,
            "ready": 0,
            "contextualizing": 0,
            "deployed": 0,
            "deprovisioning": 0,
        },
    }

    for state, quantity in await db_async_session.execute(
        select(Node.state, func.count(Node.state))
        .filter(Node.active == True, Node.pool == name)  # noqa: E712
        .group_by(Node.state)
    ):
        pool_result["levels"][state.name] = quantity

    return {"action": "get", "pool": pool_result}
