"""
This is the chassis controller.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from starlette.status import (
    HTTP_201_CREATED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
)

from ...api_models import ChassisCreateModel, ChassisResult, ChassisResultCollection
from ...database import DBSession
from ...database.model import Chassis
from . import check_adminship, check_credentials

router = APIRouter(prefix="/chassis")


# http get http://localhost:8080/api/v1/chassis
@router.get("", response_model=ChassisResultCollection, tags=["chassis"])
async def get_all_chassis(name: str = Depends(check_credentials)):
    """
    Return all chassis
    """

    if not await check_adminship(name):
        raise HTTPException(HTTP_403_FORBIDDEN)

    query = select(Chassis)
    results = await DBSession.execute(query)

    return {"action": "get", "chassis": results.scalars().all()}


# http get http://localhost:8080/api/v1/chassis/2
@router.get("/{id}", response_model=ChassisResult, tags=["chassis"])
async def get_chassis(id: int, name: str = Depends(check_credentials)):
    """
    Return the chassis with the specified **ID**
    """

    if not await check_adminship(name):
        raise HTTPException(HTTP_403_FORBIDDEN)

    chassis = (await DBSession.execute(select(Chassis).filter_by(id=id))).scalar_one_or_none()

    if not chassis:
        raise HTTPException(HTTP_404_NOT_FOUND)

    return {"action": "get", "chassis": chassis}


# http --json post http://localhost:8080/api/v1/chassis name="A Chassis with a unique name" \
#      description="A funky but optional description."
@router.post("", status_code=HTTP_201_CREATED, response_model=ChassisResult, tags=["chassis"])
async def create_chassis(data: ChassisCreateModel, name: str = Depends(check_credentials)):
    """
    Create a chassis with the specified **name** and optional **description**
    """

    if not await check_adminship(name):
        raise HTTPException(HTTP_403_FORBIDDEN)

    chassis = Chassis(name=data.name, description=data.description)

    DBSession.add(chassis)
    try:
        await DBSession.commit()
    except IntegrityError as exc:
        raise HTTPException(HTTP_409_CONFLICT, str(exc))

    return {"action": "post", "chassis": chassis}


# http delete http://localhost:8080/api/v1/chassis/2
@router.delete("/{id}", response_model=ChassisResult, tags=["chassis"])
async def delete_chassis(id: int, name: str = Depends(check_credentials)):
    """
    Delete the chassis with the specified **ID**
    """

    if not await check_adminship(name):
        raise HTTPException(HTTP_403_FORBIDDEN)

    chassis = (await DBSession.execute(select(Chassis).filter_by(id=id))).scalar_one_or_none()

    if not chassis:
        raise HTTPException(HTTP_404_NOT_FOUND)

    await DBSession.delete(chassis)
    await DBSession.commit()

    return {"action": "delete", "chassis": chassis}
