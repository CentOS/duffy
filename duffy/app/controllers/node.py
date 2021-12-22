from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.status import (
    HTTP_201_CREATED,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
    HTTP_422_UNPROCESSABLE_ENTITY,
)

from ...api_models import NodeResult, NodeResultCollection, concrete_node_create_models
from ...database.model import Chassis, Node, OpenNebulaNode, SeaMicroNode
from ..database import req_db_async_session

router = APIRouter(prefix="/nodes")


@router.get("", response_model=NodeResultCollection, tags=["nodes"])
async def get_all_nodes(db_async_session: AsyncSession = Depends(req_db_async_session)):
    """
    Return all nodes
    """
    query = select(Node).options(selectinload("*"))
    results = await db_async_session.execute(query)

    return {"action": "get", "nodes": results.scalars().all()}


@router.get("/{id}", response_model=NodeResult, tags=["nodes"])
async def get_node(id: int, db_async_session: AsyncSession = Depends(req_db_async_session)):
    """
    Return the node with the specified **ID**
    """
    query = select(Node).filter_by(id=id).options(selectinload("*"))
    result = await db_async_session.execute(query)
    node = result.scalar_one_or_none()

    if not node:
        raise HTTPException(HTTP_404_NOT_FOUND)

    return {"action": "get", "node": node}


@router.post("", status_code=HTTP_201_CREATED, response_model=NodeResult, tags=["nodes"])
async def create_node(
    data: concrete_node_create_models,
    db_async_session: AsyncSession = Depends(req_db_async_session),
):
    """
    Create a node with the specified **type**, **hostname**, **ip address**, **comment** and
    **flavour**
    """
    data.ipaddr = str(data.ipaddr)

    args = {
        "hostname": data.hostname,
        "ipaddr": str(data.ipaddr),
        "comment": data.comment,
    }

    if data.type == "opennebula":
        node_cls = OpenNebulaNode
        args["flavour"] = data.flavour
    elif data.type == "seamicro":
        node_cls = SeaMicroNode
        chassis = (
            await db_async_session.execute(select(Chassis).filter_by(id=data.chassis_id))
        ).scalar_one_or_none()
        if not chassis:
            raise HTTPException(
                HTTP_422_UNPROCESSABLE_ENTITY, f"chassis with id {data.chassis_id} not found"
            )
        args["chassis"] = chassis
    else:  # pragma: no cover
        raise TypeError(data.type)

    node = node_cls(**args)

    db_async_session.add(node)

    try:
        await db_async_session.commit()
    except IntegrityError as exc:  # pragma: no cover
        raise HTTPException(HTTP_409_CONFLICT, str(exc))

    return {"action": "post", "node": node}


@router.delete("/{id}", response_model=NodeResult, tags=["nodes"])
async def delete_node(id: int, db_async_session: AsyncSession = Depends(req_db_async_session)):
    """
    Deletes the node with the specified **ID**
    """
    node = (
        await db_async_session.execute(select(Node).filter_by(id=id).options(selectinload("*")))
    ).scalar_one_or_none()

    if not node:
        raise HTTPException(HTTP_404_NOT_FOUND)

    await db_async_session.delete(node)
    await db_async_session.commit()

    return {"action": "delete", "node": node}
