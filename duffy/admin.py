import asyncio
import logging
import sys
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select

from .api_models import TenantCreateModel, TenantRetireModel, TenantUpdateModel
from .app.controllers import tenant
from .database import async_session_maker, init_model, sync_session_maker
from .database.model import Tenant
from .exceptions import DuffyConfigurationError

log = logging.getLogger(__name__)


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
            admin_ctx = cls()
        except DuffyConfigurationError as exc:
            log.error("Configuration key missing or wrong: %s", exc.args[0])
            sys.exit(1)
        else:
            return admin_ctx

    async def proxy_controller_function_async(self, controller_function, **kwargs):
        async with async_session_maker() as db_async_session:
            try:
                return await controller_function(
                    tenant=self.fake_api_tenant, db_async_session=db_async_session, **kwargs
                )
            except HTTPException as exc:
                return {"error": {"detail": exc.detail}}

    def proxy_controller_function(self, controller_function, **kwargs):
        return asyncio.run(self.proxy_controller_function_async(controller_function, **kwargs))

    def get_tenant_id(self, name: str):
        with sync_session_maker() as db_sync_session:
            return db_sync_session.execute(
                select(Tenant.id).filter_by(name=name)
            ).scalar_one_or_none()

    def list_tenants(self):
        return self.proxy_controller_function(tenant.get_all_tenants)

    def show_tenant(self, name: str):
        return self.proxy_controller_function(tenant.get_tenant, id=self.get_tenant_id(name))

    def create_tenant(self, name: str, ssh_key: str, is_admin: bool = False):
        return self.proxy_controller_function(
            tenant.create_tenant,
            data=TenantCreateModel(name=name, ssh_key=ssh_key, is_admin=is_admin),
        )

    def retire_unretire_tenant(self, name: str, retire: bool):
        return self.proxy_controller_function(
            tenant.update_tenant,
            id=self.get_tenant_id(name),
            data=TenantRetireModel(active=not retire),
        )

    def update_tenant(
        self, name: str, api_key: Optional[str] = None, ssh_key: Optional[str] = None
    ):
        return self.proxy_controller_function(
            tenant.update_tenant,
            id=self.get_tenant_id(name),
            data=TenantUpdateModel(api_key=api_key, ssh_key=ssh_key),
        )
