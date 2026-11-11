import asyncio
import logging
import sys
from datetime import timedelta
from typing import Optional, Union

from fastapi import HTTPException
from sqlalchemy import select

from .api_models import TenantCreateModel, TenantRetireModel, TenantUpdateModel
from .app.controllers import tenant
from .database import async_session_maker, init_model, sync_session_maker
from .database.model import Tenant
from .exceptions import DuffyConfigurationError
from .util import UNSET, SentinelType

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class FakeAPITenant:
    is_admin = True


class AdminContext:
    def __init__(self):
        self.fake_api_tenant = FakeAPITenant()
        init_model()

    @classmethod
    def create_for_cli(cls):
        """This exits the program if creating an AdminContext throws an exception."""
        try:
            return cls()
        except DuffyConfigurationError as exc:
            log.error("Configuration key missing or incorrect: %s", exc.args[0])
            sys.exit(1)

    async def proxy_controller_function_async(self, controller_function, **kwargs):
        async with async_session_maker() as db_async_session, db_async_session.begin():
            try:
                return await controller_function(
                    tenant=self.fake_api_tenant, db_async_session=db_async_session, **kwargs
                )
            except HTTPException as exc:
                await db_async_session.rollback()
                log.error("HTTPException during async operation: %s", exc.detail)
                return {"error": {"detail": exc.detail}}

    def proxy_controller_function(self, controller_function, **kwargs):
        return asyncio.run(self.proxy_controller_function_async(controller_function, **kwargs))

    def get_tenant_id(self, name: str) -> Optional[int]:
        with sync_session_maker() as db_sync_session:
            return db_sync_session.execute(
                select(Tenant.id).filter_by(name=name)
            ).scalar_one_or_none()

    def list_tenants(self):
        return self.proxy_controller_function(tenant.get_all_tenants)

    def show_tenant(self, name: str):
        tenant_id = self.get_tenant_id(name)
        if tenant_id is None:
            log.error("Tenant not found: %s", name)
            return {"error": {"detail": "Tenant not found"}}
        return self.proxy_controller_function(tenant.get_tenant, id=tenant_id)

    def create_tenant(
        self,
        name: str,
        ssh_key: str,
        node_quota: Optional[int] = None,
        session_lifetime: Optional[timedelta] = None,
        session_lifetime_max: Optional[timedelta] = None,
        is_admin: bool = False,
    ):
        tenant_data = TenantCreateModel(
            name=name,
            ssh_key=ssh_key,
            is_admin=is_admin,
            node_quota=node_quota,
            session_lifetime=session_lifetime,
            session_lifetime_max=session_lifetime_max,
        )
        return self.proxy_controller_function(tenant.create_tenant, data=tenant_data)

    def retire_unretire_tenant(self, name: str, retire: bool):
        tenant_id = self.get_tenant_id(name)
        if tenant_id is None:
            log.error("Tenant not found: %s", name)
            return {"error": {"detail": "Tenant not found"}}
        retire_data = TenantRetireModel(active=not retire)
        return self.proxy_controller_function(tenant.update_tenant, id=tenant_id, data=retire_data)

    def update_tenant(
        self,
        name: str,
        api_key: Optional[Union[str, SentinelType]] = UNSET,
        ssh_key: Optional[Union[str, SentinelType]] = UNSET,
        node_quota: Optional[Union[int, SentinelType]] = UNSET,
        session_lifetime: Optional[Union[timedelta, SentinelType]] = UNSET,
        session_lifetime_max: Optional[Union[timedelta, SentinelType]] = UNSET,
    ):
        tenant_id = self.get_tenant_id(name)
        if tenant_id is None:
            log.error("Tenant not found: %s", name)
            return {"error": {"detail": "Tenant not found"}}

        data = {key: value for key, value in locals().items() if key != "name" and value is not UNSET}
        return self.proxy_controller_function(
            tenant.update_tenant, id=tenant_id, data=TenantUpdateModel(**data)
        )
