"""
This is the session controller.
"""

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from starlette.status import HTTP_201_CREATED, HTTP_404_NOT_FOUND, HTTP_422_UNPROCESSABLE_ENTITY

from ...api_models import SessionCreateModel, SessionResult, SessionResultCollection
from ...database import DBSession
from ...database.model import Session, Tenant

router = APIRouter(prefix="/sessions")


# http get http://localhost:8080/api/v1/sessions
@router.get("", response_model=SessionResultCollection, tags=["sessions"])
async def get_all_sessions():
    """
    Returns all sessions
    """
    query = select(Session).options(selectinload(Session.tenant))
    results = await DBSession.execute(query)
    return {"action": "get", "sessions": results.scalars().all()}


# http get http://localhost:8080/api/v1/sessions/2
@router.get("/{id}", response_model=SessionResult, tags=["sessions"])
async def get_session(id: int):
    """
    Returns a session with the specified **ID**
    """
    session = (
        await DBSession.execute(
            select(Session).filter_by(id=id).options(selectinload(Session.tenant))
        )
    ).scalar_one_or_none()
    if not session:
        raise HTTPException(HTTP_404_NOT_FOUND)
    return {"action": "get", "session": session}


# http --json post http://localhost:8080/api/v1/sessions tenant_id=2
@router.post("", status_code=HTTP_201_CREATED, response_model=SessionResult, tags=["sessions"])
async def create_session(data: SessionCreateModel):
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
    session = Session(tenant=tenant)
    DBSession.add(session)
    try:
        await DBSession.commit()
    except IntegrityError as exc:  # pragma: no cover
        raise HTTPException(HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    return {"action": "post", "session": session}


# http delete http://localhost:8080/api/v1/sessions/2
@router.delete("/{id}", response_model=SessionResult, tags=["sessions"])
async def delete_session(id: int):
    """
    Deletes the session with the specified **ID**
    """
    session = (
        await DBSession.execute(
            select(Session).filter_by(id=id).options(selectinload(Session.tenant))
        )
    ).scalar_one_or_none()
    if not session:
        raise HTTPException(HTTP_404_NOT_FOUND)
    await DBSession.delete(session)
    await DBSession.commit()
    return {"action": "delete", "session": session}
