from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.status import (
    HTTP_201_CREATED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
)

from ...api_models import NodeCreateModel, NodeResult, NodeResultCollection
from ...database.model import Node, Tenant
from ..auth import req_tenant
from ..database import req_db_async_session

router = APIRouter(prefix="/nodes")


@router.get("", response_model=NodeResultCollection, tags=["nodes"])
async def get_all_nodes(
    db_async_session: AsyncSession = Depends(req_db_async_session),
):
    """Return all nodes."""
    query = select(Node).options(selectinload("*")).filter_by(active=True)
    results = await db_async_session.execute(query)

    return {"action": "get", "nodes": results.scalars().all()}


@router.get("/{id}", response_model=NodeResult, tags=["nodes"])
async def get_node(
    id: int,
    db_async_session: AsyncSession = Depends(req_db_async_session),
    tenant: Tenant = Depends(req_tenant),
):
    """Return the node with the specified **ID**."""
    query = select(Node).filter_by(id=id).options(selectinload("*"))
    result = await db_async_session.execute(query)
    node = result.scalar_one_or_none()

    if not node:
        raise HTTPException(HTTP_404_NOT_FOUND)

    return {"action": "get", "node": node}


@router.post("", status_code=HTTP_201_CREATED, response_model=NodeResult, tags=["nodes"])
async def create_node(
    data: NodeCreateModel,
    db_async_session: AsyncSession = Depends(req_db_async_session),
    tenant: Tenant = Depends(req_tenant),
):
    """Create a node with the requested properties."""
    if not tenant.is_admin:
        raise HTTPException(HTTP_403_FORBIDDEN)

    args = {
        "hostname": data.hostname,
        "ipaddr": str(data.ipaddr),
        "comment": data.comment,
        "pool": data.pool,
        "reusable": data.reusable,
        "data": data.data,
    }

    node = Node(**args)
    db_async_session.add(node)

    try:
        await db_async_session.commit()
    except IntegrityError as exc:  # pragma: no cover
        raise HTTPException(HTTP_409_CONFLICT, str(exc))

    await db_async_session.refresh(node)

    return {"action": "post", "node": node}


@router.delete("/{id}", response_model=NodeResult, tags=["nodes"])
async def delete_node(
    id: int,
    db_async_session: AsyncSession = Depends(req_db_async_session),
    tenant: Tenant = Depends(req_tenant),
):
    """Delete the node with the specified **ID**."""
    if not tenant.is_admin:
        raise HTTPException(HTTP_403_FORBIDDEN)

    node = (
        await db_async_session.execute(select(Node).filter_by(id=id).options(selectinload("*")))
    ).scalar_one_or_none()

    if not node:
        raise HTTPException(HTTP_404_NOT_FOUND)

    await db_async_session.delete(node)
    await db_async_session.commit()

    return {"action": "delete", "node": node}
