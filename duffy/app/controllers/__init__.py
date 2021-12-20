from base64 import b64decode
from json import loads

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_422_UNPROCESSABLE_ENTITY

from ...database import DBSession
from ...database.model import Tenant

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/token")


async def check_adminship(name):
    query = select(Tenant).filter_by(name=name).options(selectinload("*"))
    result = await DBSession.execute(query)
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(HTTP_422_UNPROCESSABLE_ENTITY)
    return tenant.is_admin


async def check_credentials(token: str = Depends(oauth2_scheme)):
    datadict = loads(b64decode(token.encode("ascii")).decode("ascii"))
    query = select(Tenant).filter_by(name=datadict["username"]).options(selectinload("*"))
    result = await DBSession.execute(query)
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(HTTP_422_UNPROCESSABLE_ENTITY)
    if not tenant.validate_api_key(key=datadict["password"]):
        raise HTTPException(HTTP_401_UNAUTHORIZED)
    return tenant.name
