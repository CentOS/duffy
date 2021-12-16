import re

from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY

from . import BaseTestController
from .test_tenant import TestTenant as _TestTenant


class TestSession(BaseTestController):

    name = "session"
    path = "/api/v1/sessions"
    attrs = {
        "tenant_id": (_TestTenant, "id"),
    }

    async def test_create_unknown_tenant(self, client):
        # setting tenant_id manually will skip the code which would create the tenant
        response = await self._create_obj(client, attrs={"tenant_id": 1})
        assert response.status_code == HTTP_422_UNPROCESSABLE_ENTITY
        result = response.json()
        assert re.match(r"^can't find tenant with id \d+$", result["detail"])
