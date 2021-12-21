from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from ..database.model import Tenant
from .database import req_db_async_session


def _req_tenant_factory(optional: bool = False, **kwargs):
    """Factory creating FastAPI dependencies for authenticating tenants."""
    if optional:
        kwargs["auto_error"] = False
    security = HTTPBasic(realm="duffy", **kwargs)

    async def _req_tenant(
        db_async_session: AsyncSession = Depends(req_db_async_session),
        credentials: HTTPBasicCredentials = Security(security),
    ):
        if not credentials:
            if not optional:
                raise HTTPException(HTTP_403_FORBIDDEN)
            else:
                return None

        tenant_name = credentials.username
        api_key = credentials.password

        tenant = (
            await db_async_session.execute(select(Tenant).filter_by(name=tenant_name))
        ).scalar_one_or_none()

        if not tenant or not tenant.validate_api_key(api_key):
            raise HTTPException(HTTP_401_UNAUTHORIZED)

        if not tenant.active:
            raise HTTPException(HTTP_403_FORBIDDEN)

        return tenant

    return _req_tenant


req_tenant = _req_tenant_factory()
req_tenant_optional = _req_tenant_factory(optional=True)
