"""
This is the session controller.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from starlette.status import (
    HTTP_201_CREATED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_422_UNPROCESSABLE_ENTITY,
)

from ...api_models import (
    PhysicalNodesSpec,
    SessionCreateModel,
    SessionResult,
    SessionResultCollection,
    SessionUpdateModel,
)
from ...database import DBSession
from ...database.model import PhysicalNode, Session, SessionNode, Tenant, VirtualNode
from ...database.types import NodeState
from . import check_adminship, check_credentials

router = APIRouter(prefix="/sessions")


# http get http://localhost:8080/api/v1/sessions
@router.get("", response_model=SessionResultCollection, tags=["sessions"])
async def get_all_sessions(name: str = Depends(check_credentials)):
    """
    Returns all sessions
    """
    if not await check_adminship(name):
        raise HTTPException(HTTP_403_FORBIDDEN)

    query = select(Session).options(
        selectinload(Session.tenant),
        selectinload(Session.session_nodes).selectinload(SessionNode.node),
    )
    results = await DBSession.execute(query)
    return {"action": "get", "sessions": results.scalars().all()}


# http get http://localhost:8080/api/v1/sessions/2
@router.get("/{id}", response_model=SessionResult, tags=["sessions"])
async def get_session(id: int, name: str = Depends(check_credentials)):
    """
    Returns a session with the specified **ID**
    """
    session = (
        await DBSession.execute(
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
    return {"action": "get", "session": session}


# http --json post http://localhost:8080/api/v1/sessions tenant_id=2
@router.post("", status_code=HTTP_201_CREATED, response_model=SessionResult, tags=["sessions"])
async def create_session(data: SessionCreateModel, name: str = Depends(check_credentials)):
    """
    Creates a session with the specified **tenant ID**
    """
    tenant = (
        await DBSession.execute(select(Tenant).filter_by(id=data.tenant_id))
    ).scalar_one_or_none()

    if not tenant:
        raise HTTPException(
            HTTP_422_UNPROCESSABLE_ENTITY, f"can't find tenant with id {data.tenant_id}"
        )
    if not tenant.active:
        raise HTTPException(HTTP_422_UNPROCESSABLE_ENTITY, f"tenant '{tenant.name}' isn't active")

    session = Session(tenant=tenant)
    DBSession.add(session)

    for nodes_spec in data.nodes_specs:
        nodes_spec_dict = nodes_spec.dict()
        quantity = nodes_spec_dict.pop("quantity")
        nodes_spec_dict.pop("type")

        if isinstance(nodes_spec, PhysicalNodesSpec):
            node_cls = PhysicalNode
        else:  # isinstance(nodes_spec, VirtualNodesSpec)
            node_cls = VirtualNode

        query = (
            select(node_cls).filter_by(state=NodeState.active, **nodes_spec_dict).limit(quantity)
        )

        nodes_to_reserve = (await DBSession.execute(query)).scalars().all()

        if len(nodes_to_reserve) < quantity:
            raise HTTPException(HTTP_422_UNPROCESSABLE_ENTITY, f"can't reserve nodes: {nodes_spec}")

        # take the nodes out of circulation
        for node in nodes_to_reserve:
            node.state = NodeState.contextualizing
            session_node = SessionNode(
                session=session,
                node=node,
                distro_type=nodes_spec.distro_type,
                distro_version=nodes_spec.distro_version,
            )
            DBSession.add(session_node)

    # Meh. Reload the session instance to be able to explicily load all the related objects.
    await DBSession.flush()
    session = (
        await DBSession.execute(
            select(Session)
            .filter_by(id=session.id)
            .options(
                selectinload(Session.tenant),
                selectinload(Session.session_nodes).selectinload(SessionNode.node),
            )
        )
    ).scalar_one()

    try:
        await DBSession.commit()
    except IntegrityError as exc:  # pragma: no cover
        raise HTTPException(HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    return {"action": "post", "session": session}


# http --json put http://localhost:8080/api/v1/sessions/2 active:=false
@router.put("/{id}", response_model=SessionResult, tags=["sessions"])
async def update_session(id: int, data: SessionUpdateModel):
    session = (
        await DBSession.execute(
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

    if not session.active:
        raise HTTPException(HTTP_422_UNPROCESSABLE_ENTITY, f"session {id} is retired")

    session.active = data.active

    # mark nodes to be deprovisioned
    for session_node in session.session_nodes:
        session_node.node.state = NodeState.deprovisioning

    await DBSession.commit()

    return {"action": "put", "session": session}


# http delete http://localhost:8080/api/v1/sessions/2
@router.delete("/{id}", response_model=SessionResult, tags=["sessions"])
async def delete_session(id: int, name: str = Depends(check_credentials)):
    """
    Deletes the session with the specified **ID**
    """

    if not await check_adminship(name):
        raise HTTPException(HTTP_403_FORBIDDEN)

    session = (
        await DBSession.execute(
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
    await DBSession.delete(session)
    await DBSession.commit()
    return {"action": "delete", "session": session}
