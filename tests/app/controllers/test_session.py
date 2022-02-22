import re
import uuid
from unittest import mock

import pytest
from sqlalchemy import func, select
from starlette.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_422_UNPROCESSABLE_ENTITY,
    HTTP_503_SERVICE_UNAVAILABLE,
)

from duffy.database.model import Node, Session, Tenant

from . import BaseTestController


@mock.patch("duffy.app.controllers.session.fill_pools", new=mock.MagicMock())
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

    pool_names = [spec["pool"] for spec in nodes_specs]

    @pytest.mark.parametrize(
        "testcase",
        (
            "normal",
            pytest.param("inactive tenant", marks=pytest.mark.auth_tenant(active=False)),
            "insufficient nodes",
            "wrong tenant",
            "contextualizing failure",
            "decontextualizing failure",
        ),
    )
    @mock.patch("duffy.app.controllers.session.decontextualize")
    @mock.patch("duffy.app.controllers.session.contextualize")
    @mock.patch("duffy.app.controllers.session.fill_pools")
    async def test_request_session(
        self,
        fill_pools,
        contextualize,
        decontextualize,
        testcase,
        client,
        db_async_session,
        auth_tenant,
    ):
        if testcase == "insufficient nodes":
            for node in (await db_async_session.execute(select(Node))).scalars():
                node.state = "deployed"
            await db_async_session.commit()

        contextualize_retval = ["BOOP"] * 20
        decontextualize_retval = ["BOOP"] * 20

        if testcase in ("contextualizing failure", "decontextualizing failure"):
            contextualize_retval.insert(0, None)
            if testcase == "decontextualizing failure":
                decontextualize_retval.insert(1, None)

        contextualize.return_value = contextualize_retval
        decontextualize.return_value = decontextualize_retval

        request_payload = {"nodes_specs": self.nodes_specs}
        if testcase == "wrong tenant":
            request_payload["tenant_id"] = auth_tenant.id + 1

        response = await client.post(self.path, json=request_payload)
        result = response.json()

        # fill_pools should never be called directly, just through .delay()
        fill_pools.assert_not_called()

        if testcase == "normal":
            assert response.status_code == HTTP_201_CREATED

            # validate nodes have been allocated in the database
            for nodes_spec in self.nodes_specs:
                nodes_spec = nodes_spec.copy()
                quantity = nodes_spec.pop("quantity")
                count_result = await db_async_session.execute(
                    select(func.count("id"))
                    .select_from(Node)
                    .filter_by(state="deployed", **nodes_spec)
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
            fill_pools.delay.assert_called_once()
            args, kwargs = fill_pools.delay.call_args
            assert args == ()
            assert kwargs.keys() == {"pool_names"}
            assert set(kwargs["pool_names"]) == set(self.pool_names)
        else:
            if testcase == "inactive tenant":
                assert response.status_code == HTTP_403_FORBIDDEN
            elif testcase == "insufficient nodes":
                assert response.status_code == HTTP_422_UNPROCESSABLE_ENTITY
                assert result["detail"].startswith("can't reserve nodes:")
            elif testcase == "wrong tenant":
                assert response.status_code == HTTP_403_FORBIDDEN
                assert result["detail"] == "can't create session for other tenant"
            else:  # testcase in ("contextualizing failure", "decontextualizing failure")
                assert response.status_code == HTTP_503_SERVICE_UNAVAILABLE
                assert result["detail"] == "contextualization of nodes failed"
                failed_nodes = (
                    (await db_async_session.execute(select(Node).filter_by(state="failed")))
                    .scalars()
                    .all()
                )
                if testcase == "decontextualizing failure":
                    assert len(failed_nodes) == 2
                    assert any(
                        node.data["error"] == "contextualizing node failed" for node in failed_nodes
                    )
                    assert any(
                        node.data["error"] == "decontextualizing node failed"
                        for node in failed_nodes
                    )
                else:
                    assert len(failed_nodes) == 1
                    assert failed_nodes[0].data["error"] == "contextualizing node failed"
            fill_pools.delay.assert_not_called()

    @mock.patch("duffy.nodes_context.run_remote_cmd", new=mock.AsyncMock())
    @mock.patch("duffy.app.controllers.session.fill_pools", new=mock.MagicMock())
    @pytest.mark.parametrize(
        "testcase", ("normal", "unknown-session", "retired-session", "unauthorized", "set-active")
    )
    @mock.patch("duffy.app.controllers.session.deprovision_nodes")
    async def test_update_session(
        self, deprovision_nodes, testcase, client, db_async_session, auth_tenant
    ):
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

        session_active = "set-active" in testcase

        update_response = await client.put(
            f"{self.path}/{session_id}", json={"active": session_active}
        )
        update_result = update_response.json()

        # The task function should never be called directly.
        deprovision_nodes.assert_not_called()

        if testcase in ("normal", "set-active"):
            if session_active:
                deprovision_nodes.delay.assert_not_called()
            else:
                deprovision_nodes.delay.assert_called_once()
                args, kwargs = deprovision_nodes.delay.call_args
                assert args == ()
                assert kwargs.keys() == {"node_ids"}
                assert set(kwargs["node_ids"]) == {node["id"] for node in created_session["nodes"]}

            assert update_response.status_code == HTTP_200_OK
            updated_session = update_result["session"]
            assert updated_session["id"] == session_id
            if not session_active:
                assert updated_session["active"] is False
                assert updated_session["retired_at"] is not None
            else:
                assert updated_session["active"] is True
                assert updated_session["retired_at"] is None
        else:
            deprovision_nodes.delay.assert_not_called()
            if testcase == "unknown-session":
                assert update_response.status_code == HTTP_404_NOT_FOUND
            elif testcase == "unauthorized":
                assert update_response.status_code == HTTP_403_FORBIDDEN
            else:  # testcase == "retired-session"
                assert update_response.status_code == HTTP_422_UNPROCESSABLE_ENTITY
                assert re.match(r"^session .* is retired$", update_result["detail"])
