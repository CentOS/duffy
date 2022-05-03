import uuid

import pytest
from sqlalchemy import select
from starlette.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_422_UNPROCESSABLE_ENTITY,
)

from duffy.database.model import Session, Tenant
from duffy.database.setup import _gen_test_api_key

from . import BaseTestController


@pytest.mark.duffy_config(example_config=True, clear=True)
class TestTenant(BaseTestController):

    name = "tenant"
    path = "/api/v1/tenants"
    attrs = {
        "name": "Some Honky Tenant!",
        "ssh_key": "# With a honky SSH key!",
        "node_quota": 5,
    }
    no_verify_attrs = ("ssh_key",)
    unique = "unique"

    async def test_create_obj_with_is_admin_set(self, client):
        response = await self._create_obj(client, attrs={"is_admin": False})
        assert response.status_code == HTTP_201_CREATED
        result = response.json()
        self._verify_item(result[self.name])

    async def test_create_obj_verify_api_key(self, client, db_async_session):
        response = await self._create_obj(client)
        assert response.status_code == HTTP_201_CREATED
        result = response.json()
        api_tenant = result[self.name]
        api_key = uuid.UUID(api_tenant["api_key"])
        created_tenant = (
            await db_async_session.execute(select(Tenant).filter_by(id=api_tenant["id"]))
        ).scalar_one()
        assert created_tenant.validate_api_key(api_key)

    @pytest.mark.client_auth_as("tenant")
    async def test_retrieve_obj_other_tenant(self, client, auth_admin):
        other_tenant_response = await self._create_obj(
            client,
            attrs={"name": "Another Tenant"},
            client_kwargs={"auth": (auth_admin.name, str(_gen_test_api_key(auth_admin.name)))},
        )
        other_tenant_id = other_tenant_response.json()["tenant"]["id"]
        response = await client.get(f"{self.path}/{other_tenant_id}")
        assert response.status_code == HTTP_403_FORBIDDEN

    @pytest.mark.client_auth_as("tenant")
    async def test_retrieve_collection_filtered(self, client, auth_admin, auth_tenant):
        await self._create_obj(
            client,
            attrs={"name": "Another Tenant"},
            client_kwargs={"auth": (auth_admin.name, str(_gen_test_api_key(auth_admin.name)))},
        )
        response = await client.get(self.path)
        result = response.json()
        assert all(tenant["id"] == auth_tenant.id for tenant in result["tenants"])

    @pytest.mark.parametrize(
        "testcase",
        (
            "success-retire",
            "success-unretire",
            "success-update-ssh-key",
            "success-reset-api-key",
            "success-update-node-quota",
            "success-unset-node-quota",
            "inactive",
            "not found",
            pytest.param("not admin", marks=pytest.mark.client_auth_as("tenant")),
        ),
    )
    async def test_update_tenant(self, testcase, client, auth_admin, db_async_session):
        if testcase != "not found":
            create_response = await self._create_obj(
                client,
                client_kwargs={"auth": (auth_admin.name, str(_gen_test_api_key(auth_admin.name)))},
            )
            obj_id = create_response.json()["tenant"]["id"]
            tenant = (
                await db_async_session.execute(select(Tenant).filter_by(id=obj_id))
            ).scalar_one()
            if "inactive" in testcase or "unretire" in testcase:
                tenant.active = False
            tenant_session = Session(tenant_id=obj_id)
            db_async_session.add(tenant_session)
            await db_async_session.commit()
        else:
            obj_id = -1

        if "success" in testcase:
            if "retire" in testcase:
                json_payload = {"active": "unretire" in testcase}
            elif "update-ssh-key" in testcase:
                json_payload = {"ssh_key": "# changed SSH key"}
            elif "update-api-key" in testcase:
                api_key = str(uuid.uuid4())
                json_payload = {"api_key": api_key}
            elif "reset-api-key" in testcase:
                json_payload = {"api_key": "reset"}
            elif "update-node-quota" in testcase:
                json_payload = {"node_quota": 20}
            else:  # "unset-node-quota" in testcase
                json_payload = {"node_quota": None}
        else:
            # ensure the request body validates
            if "inactive" in testcase:
                json_payload = {"ssh_key": "this shouldn't get through"}
            else:
                json_payload = {"active": "inactive" not in testcase}

        response = await client.put(f"{self.path}/{obj_id}", json=json_payload)
        result = response.json()

        if "success" in testcase:
            assert response.status_code == HTTP_200_OK
            if "retire" in testcase:
                assert result["tenant"]["active"] == ("unretire" in testcase)
            elif "ssh-key" in testcase:
                # The SSH key is masked out in the result, just check its presence
                assert result["tenant"]["ssh_key"]
            elif "reset-api-key" in testcase:
                assert uuid.UUID(result["tenant"]["api_key"])
            elif "update-node-quota" in testcase:
                assert result["tenant"]["node_quota"] == 20
            elif "unset-node-quota" in testcase:
                assert result["tenant"]["node_quota"] is None
            else:
                assert result["tenant"]["api_key"]
                assert result["tenant"]["node_quota"] == 5
        elif testcase == "not admin":
            assert response.status_code == HTTP_403_FORBIDDEN
        elif testcase == "inactive":
            assert response.status_code == HTTP_422_UNPROCESSABLE_ENTITY
        else:  # not found
            assert response.status_code == HTTP_404_NOT_FOUND
