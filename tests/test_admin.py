import uuid
from unittest import mock

import pytest
from fastapi import HTTPException
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY

from duffy import api_models
from duffy.admin import AdminContext
from duffy.app import controllers
from duffy.database.model import Tenant
from duffy.exceptions import DuffyConfigurationError

from .util import noop_context


@pytest.fixture
def admin_ctx():
    return AdminContext()


@pytest.mark.duffy_config(example_config=True)
class TestAdminContext:
    @mock.patch("duffy.admin.init_model")
    @mock.patch("duffy.admin.FakeAPITenant")
    def test___init__(self, FakeAPITenant, init_model):
        FakeAPITenant.return_value = sentinel = object()

        ctx = AdminContext()

        assert ctx.fake_api_tenant is sentinel

        FakeAPITenant.assert_called_once_with()
        init_model.assert_called_once_with()

    @pytest.mark.parametrize("testcase", ("success", "config-error"))
    @mock.patch.object(AdminContext, "__new__")
    def test_create_for_cli(self, admin_ctx_new, testcase, caplog):
        if testcase == "success":
            expectation = noop_context()
            admin_ctx_new.return_value = sentinel = object()
        elif testcase == "config-error":
            admin_ctx_new.side_effect = DuffyConfigurationError("BOO")
            expectation = pytest.raises(SystemExit)

        with expectation:
            ctx = AdminContext.create_for_cli()

        if testcase == "success":
            assert ctx is sentinel
        else:
            assert "Configuration key missing or wrong: BOO" in caplog.text

    @pytest.mark.asyncio
    @pytest.mark.parametrize("testcase", ("success", "exception"))
    @mock.patch("duffy.admin.async_session_maker")
    async def test_proxy_controller_function_async(self, async_session_maker, testcase, admin_ctx):
        async_session_maker.return_value = ctx_mgr = mock.AsyncMock()
        ctx_mgr.__aenter__.return_value = db_async_session = mock.AsyncMock()
        controller_function = mock.AsyncMock()
        if testcase == "success":
            controller_function.return_value = sentinel = object()
        else:
            controller_function.side_effect = HTTPException(
                HTTP_422_UNPROCESSABLE_ENTITY, detail="BOO"
            )

        result = await admin_ctx.proxy_controller_function_async(controller_function, foo="bar")

        controller_function.assert_awaited_once_with(
            tenant=admin_ctx.fake_api_tenant, db_async_session=db_async_session, foo="bar"
        )

        if testcase == "success":
            assert result is sentinel
        else:
            assert result["error"]["detail"] == "BOO"

    def test_proxy_controller_function(self, admin_ctx):
        proxy_controller_function_async = mock.AsyncMock()
        proxy_controller_function_async.return_value = sentinel = object()
        admin_ctx.proxy_controller_function_async = proxy_controller_function_async

        controller_function = mock.AsyncMock()

        result = admin_ctx.proxy_controller_function(controller_function, foo="bar")

        proxy_controller_function_async.assert_awaited_with(controller_function, foo="bar")

        assert result is sentinel

    def test_get_tenant_id(self, admin_ctx, db_sync_session):
        tenant = Tenant(name="test", api_key="API_KEY", ssh_key="SSH_KEY")
        db_sync_session.add(tenant)
        db_sync_session.commit()

        assert admin_ctx.get_tenant_id("test") == tenant.id

    @mock.patch.object(AdminContext, "proxy_controller_function")
    def test_list_tenants(self, proxy_controller_function, admin_ctx):
        proxy_controller_function.return_value = sentinel = object()

        result = admin_ctx.list_tenants()

        assert result == sentinel

        proxy_controller_function.assert_called_once_with(controllers.tenant.get_all_tenants)

    @mock.patch.object(AdminContext, "get_tenant_id")
    @mock.patch.object(AdminContext, "proxy_controller_function")
    def test_show_tenant(self, proxy_controller_function, get_tenant_id, admin_ctx):
        proxy_controller_function.return_value = sentinel = object()
        get_tenant_id.return_value = 6

        result = admin_ctx.show_tenant(name="name")

        assert result == sentinel

        get_tenant_id.assert_called_once_with("name")
        proxy_controller_function.assert_called_once_with(controllers.tenant.get_tenant, id=6)

    @pytest.mark.parametrize("testcase", ("normal", "is-admin"))
    @mock.patch.object(AdminContext, "proxy_controller_function")
    def test_create_tenant(self, proxy_controller_function, testcase, admin_ctx):
        is_admin = testcase == "is-admin"

        proxy_controller_function.return_value = sentinel = object()

        result = admin_ctx.create_tenant(name="name", ssh_key="# no ssh key", is_admin=is_admin)

        assert result == sentinel

        proxy_controller_function.assert_called_once_with(
            controllers.tenant.create_tenant,
            data=api_models.TenantCreateModel(
                name="name", ssh_key="# no ssh key", is_admin=is_admin
            ),
        )

    @pytest.mark.parametrize("testcase", ("retire", "unretire"))
    @mock.patch.object(AdminContext, "get_tenant_id")
    @mock.patch.object(AdminContext, "proxy_controller_function")
    def test_retire_unretire_tenant(
        self, proxy_controller_function, get_tenant_id, testcase, admin_ctx
    ):
        retire = testcase == "retire"
        proxy_controller_function.return_value = sentinel = object()
        get_tenant_id.return_value = 5

        result = admin_ctx.retire_unretire_tenant(name="name", retire=retire)

        assert result == sentinel

        get_tenant_id.assert_called_once_with("name")
        proxy_controller_function.assert_called_once_with(
            controllers.tenant.update_tenant,
            id=5,
            data=api_models.TenantRetireModel(active=not retire),
        )

    @mock.patch.object(AdminContext, "get_tenant_id")
    @mock.patch.object(AdminContext, "proxy_controller_function")
    def test_update_tenant(self, proxy_controller_function, get_tenant_id, admin_ctx):
        proxy_controller_function.return_value = sentinel = object()
        get_tenant_id.return_value = 6

        api_key = uuid.uuid4()

        result = admin_ctx.update_tenant(name="name", api_key=api_key, ssh_key="# new ssh key")

        assert result == sentinel

        get_tenant_id.assert_called_once_with("name")
        proxy_controller_function.assert_called_once_with(
            controllers.tenant.update_tenant,
            id=6,
            data=api_models.TenantUpdateModel(api_key=api_key, ssh_key="# new ssh key"),
        )
