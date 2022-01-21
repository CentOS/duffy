"""
This is the session controller.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.status import (
    HTTP_201_CREATED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_422_UNPROCESSABLE_ENTITY,
)

from ...api_models import (
    SessionCreateModel,
    SessionResult,
    SessionResultCollection,
    SessionUpdateModel,
)
from ...database.model import Node, Session, SessionNode, Tenant
from ...database.types import NodeState
from ..auth import req_tenant
from ..database import req_db_async_session

router = APIRouter(prefix="/sessions")


# http get http://localhost:8080/api/v1/sessions
@router.get("", response_model=SessionResultCollection, tags=["sessions"])
async def get_all_sessions(
    db_async_session: AsyncSession = Depends(req_db_async_session),
    tenant: Tenant = Depends(req_tenant),
):
    """
    Returns all sessions
    """
    query = select(Session).options(
        selectinload(Session.tenant),
        selectinload(Session.session_nodes).selectinload(SessionNode.node),
    )
    if not tenant.is_admin:
        query = query.filter_by(tenant=tenant)
    results = await db_async_session.execute(query)
    return {"action": "get", "sessions": results.scalars().all()}


# http get http://localhost:8080/api/v1/sessions/2
@router.get("/{id}", response_model=SessionResult, tags=["sessions"])
async def get_session(
    id: int,
    db_async_session: AsyncSession = Depends(req_db_async_session),
    tenant: Tenant = Depends(req_tenant),
):
    """
    Returns a session with the specified **ID**
    """
    session = (
        await db_async_session.execute(
            select(Session)
            .filter_by(id=id)
            .options(
                selectinload(Session.tenant),
                selectinload(Session.session_nodes).selectinload(SessionNode.node),
            )
        )
    ).scalar_one_or_none()
    if not session:
        raise HTTPException(HTTP_404_NOT_FOUND)
    if not tenant.is_admin and session.tenant != tenant:
        raise HTTPException(HTTP_403_FORBIDDEN)
    return {"action": "get", "session": session}


# http --json post http://localhost:8080/api/v1/sessions tenant_id=2 \
#     'nodes_specs:=[{"pool": "virtual-fedora34-x86_64-small", "quantity": 1}]
@router.post("", status_code=HTTP_201_CREATED, response_model=SessionResult, tags=["sessions"])
async def create_session(
    data: SessionCreateModel,
    db_async_session: AsyncSession = Depends(req_db_async_session),
    tenant: Tenant = Depends(req_tenant),
):
    """
    Creates a session with the specified **tenant ID**
    """
    if tenant.is_admin and data.tenant_id is not None:
        tenant = (
            await db_async_session.execute(select(Tenant).filter_by(id=data.tenant_id))
        ).scalar_one_or_none()

        if not tenant:
            raise HTTPException(
                HTTP_422_UNPROCESSABLE_ENTITY, f"can't find tenant with id {data.tenant_id}"
            )
        elif not tenant.active:
            raise HTTPException(
                HTTP_422_UNPROCESSABLE_ENTITY, f"tenant '{tenant.name}' isn't active"
            )
    elif not tenant.is_admin and data.tenant_id is not None and data.tenant_id != tenant.id:
        raise HTTPException(HTTP_403_FORBIDDEN, "can't create session for other tenant")

    session = Session(
        tenant=tenant, data={"nodes_specs": [spec.dict() for spec in data.nodes_specs]}
    )
    db_async_session.add(session)

    for nodes_spec in data.nodes_specs:
        nodes_spec_dict = nodes_spec.dict()
        quantity = nodes_spec_dict.pop("quantity")

        query = select(Node).filter_by(state=NodeState.active, **nodes_spec_dict).limit(quantity)

        nodes_to_reserve = (await db_async_session.execute(query)).scalars().all()

        if len(nodes_to_reserve) < quantity:
            raise HTTPException(HTTP_422_UNPROCESSABLE_ENTITY, f"can't reserve nodes: {nodes_spec}")

        # take the nodes out of circulation and update data
        for node in nodes_to_reserve:
            # record why this node was allocated for this session
            node.data["nodes_spec"] = nodes_spec.dict()
            node.state = NodeState.contextualizing
            session_node = SessionNode(
                session=session, node=node, pool=nodes_spec.pool, data=node.data
            )
            db_async_session.add(session_node)

    # Meh. Reload the session instance to ensure all related objects are present in the session.
    await db_async_session.flush()
    session = (
        await db_async_session.execute(
            select(Session)
            .filter_by(id=session.id)
            .options(
                selectinload(Session.tenant),
                selectinload(Session.session_nodes).selectinload(SessionNode.node),
            )
        )
    ).scalar_one()

    try:
        await db_async_session.commit()
    except IntegrityError as exc:  # pragma: no cover
        raise HTTPException(HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    return {"action": "post", "session": session}


# http --json put http://localhost:8080/api/v1/sessions/2 active:=false
@router.put("/{id}", response_model=SessionResult, tags=["sessions"])
async def update_session(
    id: int,
    data: SessionUpdateModel,
    db_async_session: AsyncSession = Depends(req_db_async_session),
    tenant: Tenant = Depends(req_tenant),
):
    session = (
        await db_async_session.execute(
            select(Session)
            .filter_by(id=id)
            .options(
                selectinload(Session.tenant),
                selectinload(Session.session_nodes).selectinload(SessionNode.node),
            )
        )
    ).scalar_one_or_none()

    if not session:
        raise HTTPException(HTTP_404_NOT_FOUND)

    if not tenant.is_admin and session.tenant != tenant:
        raise HTTPException(HTTP_403_FORBIDDEN)

    if not session.active:
        raise HTTPException(HTTP_422_UNPROCESSABLE_ENTITY, f"session {id} is retired")

    session.active = data.active

    # mark nodes to be deprovisioned
    for session_node in session.session_nodes:
        session_node.node.state = NodeState.deprovisioning

    await db_async_session.commit()

    return {"action": "put", "session": session}


# http delete http://localhost:8080/api/v1/sessions/2
@router.delete("/{id}", response_model=SessionResult, tags=["sessions"])
async def delete_session(
    id: int,
    db_async_session: AsyncSession = Depends(req_db_async_session),
    tenant: Tenant = Depends(req_tenant),
):
    """
    Deletes the session with the specified **ID**
    """
    if not tenant.is_admin:
        raise HTTPException(HTTP_403_FORBIDDEN)
    session = (
        await db_async_session.execute(
            select(Session)
            .filter_by(id=id)
            .options(
                selectinload(Session.tenant),
                selectinload(Session.session_nodes).selectinload(SessionNode.node),
            )
        )
    ).scalar_one_or_none()
    if not session:
        raise HTTPException(HTTP_404_NOT_FOUND)
    await db_async_session.delete(session)
    await db_async_session.commit()
    return {"action": "delete", "session": session}
