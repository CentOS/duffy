from contextlib import nullcontext
from unittest import mock

import pytest
from fastapi.exceptions import HTTPException
from sqlalchemy import select
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from duffy.app.auth import _req_tenant_factory
from duffy.database.model import Tenant
from duffy.database.setup import _gen_test_api_key


@pytest.mark.parametrize(
    "testcase",
    (
        "authenticated",
        "unauthenticated",
        "unauthenticated-optional",
        "authenticated-unknown",
        "authenticated-retired",
    ),
)
async def test__req_tenant_factory(testcase, db_async_session, db_async_test_data):
    if "unauthenticated" in testcase:
        credentials = None
    else:
        credentials = mock.MagicMock()
        if "unknown" not in testcase:
            credentials.username = "tenant"
            api_key = _gen_test_api_key("tenant")
            credentials.password = str(api_key)
        else:
            credentials.username = "BOOP"
            credentials.password = "FOO"

    if "retired" in testcase:
        for db_tenant in (
            await db_async_session.execute(select(Tenant).filter_by(name=credentials.username))
        ).scalars():
            db_tenant.active = False
        await db_async_session.flush()

    if "unauthenticated" in testcase and "optional" not in testcase:
        expectation = pytest.raises(HTTPException)
        exception_args = (HTTP_403_FORBIDDEN,)
    elif "unauthenticated" not in testcase and "unknown" in testcase:
        expectation = pytest.raises(HTTPException)
        exception_args = (HTTP_401_UNAUTHORIZED,)
    elif "unauthenticated" not in testcase and "retired" in testcase:
        expectation = pytest.raises(HTTPException)
        exception_args = (HTTP_403_FORBIDDEN,)
    else:
        expectation = nullcontext()
        exception_args = None

    get_req_tenant = _req_tenant_factory(optional="optional" in testcase)

    with expectation as excinfo:
        tenant = await get_req_tenant(db_async_session=db_async_session, credentials=credentials)

    if exception_args:
        assert excinfo.value.args == exception_args
    else:
        if "unauthenticated" not in testcase:
            assert tenant
            assert tenant.active
            assert tenant.name == credentials.username
            assert tenant.validate_api_key(api_key)
        else:
            # ensure not testcase is overlooked
            assert "optional" in testcase
            assert tenant is None
