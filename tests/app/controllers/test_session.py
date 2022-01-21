import re
import uuid

import pytest
from sqlalchemy import func, select
from starlette.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_422_UNPROCESSABLE_ENTITY,
)

from duffy.database.model import Node, Session, Tenant

from . import BaseTestController


class TestSession(BaseTestController):

    name = "session"
    path = "/api/v1/sessions"
    attrs = {
        # don't bother with actually allocating nodes here
        "nodes_specs": [],
    }
    no_verify_attrs = ("nodes_specs",)
    create_unprivileged = True

    @staticmethod
    async def _create_tenant(db_async_session, **kwargs):
        for key, value in {
            "name": "Other User",
            "api_key": uuid.uuid4(),
            "ssh_key": "<ssh key>",
        }.items():
            kwargs.setdefault(key, value)
        tenant = Tenant(**kwargs)
        db_async_session.add(tenant)
        await db_async_session.flush()
        return tenant

    async def test_create_other_tenant(self, client, db_async_session, auth_tenant):
        other_tenant = await self._create_tenant(db_async_session)
        response = await self._create_obj(client, attrs={"tenant_id": other_tenant.id})
        assert response.status_code == HTTP_201_CREATED
        result = response.json()
        assert result["session"]["tenant"]["id"] == other_tenant.id

    async def test_create_unknown_tenant(self, client, auth_tenant):
        response = await self._create_obj(client, attrs={"tenant_id": auth_tenant.id + 1})
        assert response.status_code == HTTP_422_UNPROCESSABLE_ENTITY
        result = response.json()
        assert re.match(r"^can't find tenant with id \d+$", result["detail"])

    async def test_create_retired_tenant(self, client, db_async_session):
        retired_tenant = await self._create_tenant(
            db_async_session, name="Happily retired", active=False
        )

        response = await self._create_obj(client, attrs={"tenant_id": retired_tenant.id})

        assert response.status_code == HTTP_422_UNPROCESSABLE_ENTITY
        result = response.json()
        assert re.match(r"^tenant .* isn't active$", result["detail"])

    @pytest.mark.client_auth_as("tenant")
    async def test_retrieve_obj_other_tenant(self, client, db_async_session):
        other_tenant = await self._create_tenant(db_async_session)
        session = Session(tenant=other_tenant)
        db_async_session.add(session)
        await db_async_session.flush()

        response = await client.get(f"{self.path}/{session.id}")
        assert response.status_code == HTTP_403_FORBIDDEN

    @pytest.mark.client_auth_as("tenant")
    async def test_retrieve_collection_filtered(self, client, db_async_session, auth_tenant):
        other_tenant = await self._create_tenant(db_async_session)

        # Create a couple of sessions, some of them owned by the authenticated tenant, some others
        # by someone else.
        for i in range(10):
            tenant = auth_tenant if i % 2 else other_tenant
            # Use tenant_id here because the auth_tenant object belongs to another session, the one
            # used in its fixture.
            db_async_session.add(Session(tenant_id=tenant.id))
        await db_async_session.flush()

        response = await client.get(self.path)
        result = response.json()
        assert all(session["tenant"]["id"] == auth_tenant.id for session in result["sessions"])


@pytest.mark.usefixtures("db_async_test_data", "db_async_model_initialized")
@pytest.mark.asyncio
class TestSessionWorkflow:

    path = "/api/v1/sessions"

    nodes_specs = [
        {"pool": "physical-centos8stream-x86_64", "quantity": 1},
        {"pool": "virtual-fedora35-x86_64-medium", "quantity": 2},
    ]

    @pytest.mark.parametrize(
        "testcase",
        (
            "normal",
            pytest.param("inactive tenant", marks=pytest.mark.auth_tenant(active=False)),
            "insufficient nodes",
            "wrong tenant",
        ),
    )
    async def test_request_session(self, testcase, client, db_async_session, auth_tenant):
        if testcase == "insufficient nodes":
            for node in (await db_async_session.execute(select(Node))).scalars():
                node.state = "deployed"
            await db_async_session.commit()

        request_payload = {"nodes_specs": self.nodes_specs}
        if testcase == "wrong tenant":
            request_payload["tenant_id"] = auth_tenant.id + 1
        response = await client.post(self.path, json=request_payload)
        result = response.json()

        if testcase == "normal":
            assert response.status_code == HTTP_201_CREATED

            # validate nodes have been allocated in the database
            for nodes_spec in self.nodes_specs:
                nodes_spec = nodes_spec.copy()
                quantity = nodes_spec.pop("quantity")
                count_result = await db_async_session.execute(
                    select(func.count("id"))
                    .select_from(Node)
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
                        if value != node[attr]:
                            break
                    else:
                        # didn't break out of loop -> matches spec
                        matched_nodes_count += 1
                assert matched_nodes_count == quantity
        elif testcase == "inactive tenant":
            assert response.status_code == HTTP_403_FORBIDDEN
        elif testcase == "insufficient nodes":
            assert response.status_code == HTTP_422_UNPROCESSABLE_ENTITY
            assert result["detail"].startswith("can't reserve nodes:")
        else:  # testcase == "wrong tenant"
            assert response.status_code == HTTP_403_FORBIDDEN
            assert result["detail"] == "can't create session for other tenant"

    @pytest.mark.parametrize(
        "testcase", ("normal", "unknown-session", "retired-session", "unauthorized")
    )
    async def test_update_session(self, testcase, client, db_async_session, auth_tenant):
        if testcase != "unknown-session":
            request_payload = {"nodes_specs": self.nodes_specs}
            create_response = await client.post(self.path, json=request_payload)
            create_result = create_response.json()
            created_session = create_result["session"]
            session_id = created_session["id"]
            # smoke test
            assert created_session["active"] is True
            assert created_session["retired_at"] is None

            if testcase == "retired-session":
                async with db_async_session.begin():
                    retired_session = (
                        await db_async_session.execute(select(Session).filter_by(id=session_id))
                    ).scalar_one()
                    retired_session.active = False
            elif testcase == "unauthorized":
                # make the session be owned by the admin tenant
                async with db_async_session.begin():
                    admin_tenant = (
                        await db_async_session.execute(select(Tenant).filter_by(name="admin"))
                    ).scalar_one()
                    session = (
                        await db_async_session.execute(select(Session).filter_by(id=session_id))
                    ).scalar_one()
                    session.tenant = admin_tenant
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
        elif testcase == "unauthorized":
            assert update_response.status_code == HTTP_403_FORBIDDEN
        else:  # testcase == "retired-session"
            assert update_response.status_code == HTTP_422_UNPROCESSABLE_ENTITY
            assert re.match(r"^session .* is retired$", update_result["detail"])
