"""
This is the chassis controller.
"""

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from starlette.status import HTTP_201_CREATED, HTTP_404_NOT_FOUND, HTTP_409_CONFLICT

from ...api_models import ChassisCreateModel, ChassisResult, ChassisResultCollection
from ...database import DBSession
from ...database.model import Chassis

router = APIRouter(prefix="/chassis")


# http get http://localhost:8080/api/v1/chassis
@router.get("", response_model=ChassisResultCollection, tags=["chassis"])
async def get_all_chassis():
    """
    Return all chassis
    """
    query = select(Chassis)
    results = await DBSession.execute(query)

    return {"action": "get", "chassis": results.scalars().all()}


# http get http://localhost:8080/api/v1/chassis/2
@router.get("/{id}", response_model=ChassisResult, tags=["chassis"])
async def get_chassis(id: int):
    """
    Return the chassis with the specified **ID**
    """
    chassis = (await DBSession.execute(select(Chassis).filter_by(id=id))).scalar_one_or_none()

    if not chassis:
        raise HTTPException(HTTP_404_NOT_FOUND)

    return {"action": "get", "chassis": chassis}


# http --json post http://localhost:8080/api/v1/chassis name="A Chassis with a unique name" \
#      description="A funky but optional description."
@router.post("", status_code=HTTP_201_CREATED, response_model=ChassisResult, tags=["chassis"])
async def create_chassis(data: ChassisCreateModel):
    """
    Create a chassis with the specified **name** and optional **description**
    """
    chassis = Chassis(name=data.name, description=data.description)

    DBSession.add(chassis)
    try:
        await DBSession.commit()
    except IntegrityError as exc:
        raise HTTPException(HTTP_409_CONFLICT, str(exc))

    return {"action": "post", "chassis": chassis}


# http delete http://localhost:8080/api/v1/chassis/2
@router.delete("/{id}", response_model=ChassisResult, tags=["chassis"])
async def delete_chassis(id: int):
    """
    Delete the chassis with the specified **ID**
    """
    chassis = (await DBSession.execute(select(Chassis).filter_by(id=id))).scalar_one_or_none()

    if not chassis:
        raise HTTPException(HTTP_404_NOT_FOUND)

    await DBSession.delete(chassis)
    await DBSession.commit()

    return {"action": "delete", "chassis": chassis}
