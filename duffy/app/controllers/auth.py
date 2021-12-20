"""
This is the authentication endpoint.
"""

from base64 import b64encode
from json import dumps

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_422_UNPROCESSABLE_ENTITY

from ...database import DBSession
from ...database.model import Tenant

router = APIRouter(prefix="/token")


@router.post("", tags=["token"])
async def obtain_authentication_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Authenticate requests for performing restricted operations
    """
    query = select(Tenant).filter_by(name=form_data.username).options(selectinload("*"))
    result = await DBSession.execute(query)

    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(HTTP_422_UNPROCESSABLE_ENTITY)
    if not tenant.validate_api_key(key=form_data.password):
        raise HTTPException(HTTP_401_UNAUTHORIZED)
    datajson = dumps({"username": form_data.username, "password": form_data.password})
    access_token = b64encode(datajson.encode()).decode()
    return {"access_token": access_token, "token_type": "bearer"}
