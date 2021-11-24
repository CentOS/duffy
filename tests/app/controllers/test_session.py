from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY

from . import BaseTestController
from .test_project import TestProject as _TestProject


class TestSession(BaseTestController):

    name = "session"
    path = "/api/v1/sessions"
    attrs = {
        "project_id": (_TestProject, "id"),
    }

    async def test_create_unknown_project(self, client):
        response = await self._create_obj(client, add_attrs={"project_id": 1})
        assert response.status_code == HTTP_422_UNPROCESSABLE_ENTITY
        result = response.json()
        assert "detail" in result
