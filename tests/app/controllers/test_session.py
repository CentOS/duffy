import re
import uuid

import pytest
from sqlalchemy import func, select
from starlette.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_404_NOT_FOUND,
    HTTP_422_UNPROCESSABLE_ENTITY,
)

from duffy.database import DBSession
from duffy.database.model import Node, PhysicalNode, Session, Tenant, VirtualNode

from . import BaseTestController
from .test_tenant import TestTenant as _TestTenant


class TestSession(BaseTestController):

    name = "session"
    path = "/api/v1/sessions"
    attrs = {
        "tenant_id": (_TestTenant, "id"),
        # don't bother with actually allocating nodes here
        "nodes_specs": [],
    }
    no_response_attrs = ("nodes_specs",)

    async def test_create_unknown_tenant(self, client, auth_tenant):
        response = await self._create_obj(client, attrs={"tenant_id": auth_tenant.id + 1})
        assert response.status_code == HTTP_422_UNPROCESSABLE_ENTITY
        result = response.json()
        assert re.match(r"^can't find tenant with id \d+$", result["detail"])

    async def test_create_retired_tenant(self, client):
        # Create the tenant manually and set it as retired
        tenant = Tenant(name="Happily retired", active=False, api_key=uuid.uuid4(), ssh_key="BOO")
        DBSession.add(tenant)
        await DBSession.flush()

        response = await self._create_obj(client, attrs={"tenant_id": tenant.id})

        assert response.status_code == HTTP_422_UNPROCESSABLE_ENTITY
        result = response.json()
        assert re.match(r"^tenant .* isn't active$", result["detail"])


@pytest.mark.usefixtures("db_async_test_data", "db_async_model_initialized")
@pytest.mark.asyncio
class TestSessionWorkflow:

    path = "/api/v1/sessions"

    nodes_specs = [
        {
            "type": "physical",
            "quantity": 1,
            "distro_type": "centos",
            "distro_version": "8Stream",
        },
        {
            "type": "virtual",
            "quantity": 2,
            "flavour": "medium",
            "distro_type": "fedora",
            "distro_version": "35",
        },
    ]

    @pytest.mark.parametrize("can_reserve", (True, False))
    async def test_request_session(self, can_reserve, client, auth_tenant):
        if not can_reserve:
            for node in (await DBSession.execute(select(Node))).scalars():
                node.state = "deployed"
            await DBSession.flush()

        request_payload = {"tenant_id": auth_tenant.id, "nodes_specs": self.nodes_specs}
        response = await client.post(self.path, json=request_payload)
        result = response.json()

        if can_reserve:
            assert response.status_code == HTTP_201_CREATED

            # validate nodes have been allocated in the database
            for nodes_spec in self.nodes_specs:
                nodes_spec = nodes_spec.copy()
                quantity = nodes_spec.pop("quantity")
                nodes_type = nodes_spec.pop("type")
                if nodes_type == "physical":
                    nodecls = PhysicalNode
                elif nodes_type == "virtual":
                    nodecls = VirtualNode
                count_result = await DBSession.execute(
                    select(func.count("id"))
                    .select_from(nodecls)
                    .filter_by(state="contextualizing", **nodes_spec)
                )
                assert count_result.scalar_one() == quantity

            # validate that the result lists the nodes
            session = result["session"]
            nodes = session["nodes"]
            for nodes_spec in self.nodes_specs:
                nodes_spec = nodes_spec.copy()
                quantity = nodes_spec.pop("quantity")
                matched_nodes_count = 0
                for node in nodes:
                    for attr, value in nodes_spec.items():
                        if attr == "type":
                            if (
                                value == "physical"
                                and node["type"] not in ("physical", "seamicro")
                                or value == "virtual"
                                and node["type"] not in ("virtual", "opennebula")
                            ):
                                break
                        elif value != node[attr]:
                            break
                    else:
                        # didn't break out of loop -> matches spec
                        matched_nodes_count += 1
                assert matched_nodes_count == quantity
        else:  # not can_reserve
            assert response.status_code == HTTP_422_UNPROCESSABLE_ENTITY
            assert result["detail"].startswith("can't reserve nodes:")

    @pytest.mark.parametrize("testcase", ("normal", "unknown-session", "retired-session"))
    async def test_update_session(self, testcase, client, auth_tenant):
        if testcase != "unknown-session":
            request_payload = {"tenant_id": auth_tenant.id, "nodes_specs": self.nodes_specs}
            create_response = await client.post(self.path, json=request_payload)
            create_result = create_response.json()
            created_session = create_result["session"]
            session_id = created_session["id"]
            # smoke test
            assert created_session["active"] is True
            assert created_session["retired_at"] is None

            if testcase == "retired-session":
                async with DBSession.begin():
                    retired_session = (
                        await DBSession.execute(select(Session).filter_by(id=session_id))
                    ).scalar_one()
                    retired_session.active = False
        else:
            session_id = 1

        update_response = await client.put(f"{self.path}/{session_id}", json={"active": False})
        update_result = update_response.json()
        if testcase == "normal":
            assert update_response.status_code == HTTP_200_OK
            updated_session = update_result["session"]
            assert updated_session["id"] == session_id
            assert updated_session["active"] is False
            assert updated_session["retired_at"] is not None
        elif testcase == "unknown-session":
            assert update_response.status_code == HTTP_404_NOT_FOUND
        else:  # testcase == "retired-session"
            assert update_response.status_code == HTTP_422_UNPROCESSABLE_ENTITY
            assert re.match(r"^session .* is retired$", update_result["detail"])
