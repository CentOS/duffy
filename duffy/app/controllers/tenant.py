"""This is the tenant controller."""

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import (
    HTTP_201_CREATED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
)

from ...api_models import (
    TenantCreateModel,
    TenantCreateResult,
    TenantCreateResultModel,
    TenantModel,
    TenantResult,
    TenantResultCollection,
)
from ...database.model import Tenant
from ..auth import req_tenant
from ..database import req_db_async_session

router = APIRouter(prefix="/tenants")


# http get http://localhost:8080/api/v1/tenants
@router.get("", response_model=TenantResultCollection, tags=["tenants"])
async def get_all_tenants(
    db_async_session: AsyncSession = Depends(req_db_async_session),
    tenant: Tenant = Depends(req_tenant),
):
    """Return all tenants."""
    query = select(Tenant)
    if not tenant.is_admin:
        query = query.filter_by(id=tenant.id)
    results = await db_async_session.execute(query)

    return {"action": "get", "tenants": results.scalars().all()}


# http get http://localhost:8080/api/v1/tenants/2
@router.get("/{id}", response_model=TenantResult, tags=["tenants"])
async def get_tenant(
    id: int,
    db_async_session: AsyncSession = Depends(req_db_async_session),
    tenant: Tenant = Depends(req_tenant),
):
    """Return the tenant with the specified **ID**."""
    retrieved_tenant = (
        await db_async_session.execute(select(Tenant).filter_by(id=id))
    ).scalar_one_or_none()

    if not retrieved_tenant:
        raise HTTPException(HTTP_404_NOT_FOUND)

    if retrieved_tenant != tenant and not tenant.is_admin:
        raise HTTPException(HTTP_403_FORBIDDEN)

    return {"action": "get", "tenant": retrieved_tenant}


# http --json post http://localhost:8080/api/v1/tenants name="Unique name"
@router.post("", status_code=HTTP_201_CREATED, response_model=TenantCreateResult, tags=["tenants"])
async def create_tenant(
    data: TenantCreateModel,
    db_async_session: AsyncSession = Depends(req_db_async_session),
    tenant: Tenant = Depends(req_tenant),
):
    """Create a tenant with the specified **name**."""
    if not tenant.is_admin:
        raise HTTPException(HTTP_403_FORBIDDEN)

    api_key = uuid4()

    created_tenant = Tenant(
        name=data.name,
        is_admin=data.is_admin,
        api_key=api_key,
        ssh_key=data.ssh_key.get_secret_value(),
    )
    db_async_session.add(created_tenant)
    try:
        await db_async_session.flush()
    except IntegrityError as exc:
        raise HTTPException(HTTP_409_CONFLICT, str(exc))

    api_tenant = TenantCreateResultModel(
        api_key=api_key, **TenantModel.from_orm(created_tenant).dict()
    )

    await db_async_session.commit()

    return {"action": "post", "tenant": api_tenant}


# http delete http://localhost:8080/api/v1/tenant/2
@router.delete("/{id}", response_model=TenantResult, tags=["tenants"])
async def delete_tenant(
    id: int,
    db_async_session: AsyncSession = Depends(req_db_async_session),
    tenant: Tenant = Depends(req_tenant),
):
    """Delete the tenant with the specified **ID**."""
    if not tenant.is_admin:
        raise HTTPException(HTTP_403_FORBIDDEN)

    tenant = (await db_async_session.execute(select(Tenant).filter_by(id=id))).scalar_one_or_none()

    if not tenant:
        raise HTTPException(HTTP_404_NOT_FOUND)

    await db_async_session.delete(tenant)
    await db_async_session.commit()

    return {"action": "delete", "tenant": tenant}
