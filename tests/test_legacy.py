from typing import Iterator
from unittest import mock

import pytest
from fastapi.exceptions import HTTPException
from httpx import AsyncClient
from starlette.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_422_UNPROCESSABLE_ENTITY,
    HTTP_500_INTERNAL_SERVER_ERROR,
)

from duffy.configuration import config
from duffy.legacy import main
from duffy.legacy.api_models import Credentials
from duffy.legacy.auth import _req_credentials_factory

from .util import noop_context

TEST_CRED = Credentials(
    username="hahahahahatheystoppedlegacysupporthahahahaha",
    password="fca07101-daea-4b8c-acb4-88ba8ae7654c",
)


@pytest.fixture
async def client() -> Iterator[AsyncClient]:
    async with AsyncClient(app=main.app, base_url="http://duffy-legacy-test.example.com") as client:
        yield client


class TestAuth:
    @pytest.mark.duffy_config(example_config=True)
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
    @pytest.mark.asyncio
    async def test__req_credentials_factory(self, testcase):
        if "unauthenticated" in testcase:
            password = None
        else:
            if "unknown" not in testcase:
                username = TEST_CRED.username
                password = TEST_CRED.password
            else:
                username = "BOOP"
                password = "FROOP"

        if "unauthenticated" in testcase and "optional" not in testcase:
            expectation = pytest.raises(HTTPException)
            exception_args = (HTTP_401_UNAUTHORIZED,)
        elif "unauthenticated" not in testcase and "unknown" in testcase:
            expectation = pytest.raises(HTTPException)
            exception_args = (HTTP_403_FORBIDDEN,)
        else:
            expectation = noop_context()
            exception_args = None

        get_req_credentials = _req_credentials_factory(optional="optional" in testcase)

        with expectation as excinfo:
            credentials = get_req_credentials(key=password)

        if exception_args:
            assert excinfo.value.args == exception_args
        else:
            if "unauthenticated" not in testcase:
                assert isinstance(credentials, Credentials)
                assert credentials.username == username
                assert credentials.password == password
            else:
                # ensure no testcase is overlooked
                assert "optional" in testcase
                assert password is None


@pytest.mark.asyncio
@pytest.mark.duffy_config(example_config=True)
class TestMain:
    apiv1_result = {
        "action": "post",
        "session": {
            "id": 1,
            "nodes": [
                {"id": 1, "hostname": "boo", "ipaddr": "192.168.0.1"},
                {"id": 2, "hostname": "bah", "ipaddr": "192.168.0.2"},
            ],
        },
    }

    @staticmethod
    def noderesult_to_dict(noderesult, long_form: bool):
        if long_form:
            return {
                key: value
                for key, value in zip(
                    (
                        "id",
                        "hostname",
                        "ipaddr",
                        "chassis",
                        "used_count",
                        "state",
                        "comment",
                        "distro",
                        "rel",
                        "ver",
                        "arch",
                        "pool",
                        "console_port",
                        "flavor",
                    ),
                    noderesult,
                )
            }
        else:
            return {"hostname": noderesult[0], "session": noderesult[1]}

    def _setup_async_client(self, AsyncClient, http_method):
        AsyncClient.return_value = ctxmgr = mock.MagicMock()
        ctxmgr.__aenter__.return_value = apiv1_client = mock.AsyncMock()

        getattr(apiv1_client, http_method).return_value = apiv1_response = mock.Mock()
        apiv1_response.status_code = HTTP_201_CREATED
        apiv1_response.json.return_value = self.apiv1_result
        return apiv1_client, apiv1_response

    @mock.patch("duffy.legacy.main.httpx.AsyncClient")
    async def test_get_node_physical_auth(self, AsyncClient, client):
        apiv1_client, apiv1_response = self._setup_async_client(AsyncClient, "post")

        key = TEST_CRED.password

        response = await client.get(
            "/Node/get", params={"key": key, "ver": 7, "arch": "x86_64", "count": 1}
        )

        result = response.json()
        assert response.status_code == HTTP_200_OK
        assert result["ssid"] == self.apiv1_result["session"]["id"]
        assert set(result["hosts"]) == {
            node["hostname"] for node in self.apiv1_result["session"]["nodes"]
        }

    @pytest.mark.parametrize("flavour_testcase", ("default", "provided"))
    @mock.patch("duffy.legacy.main.httpx.AsyncClient")
    async def test_get_node_virtual_auth(self, AsyncClient, flavour_testcase, client):
        apiv1_client, apiv1_response = self._setup_async_client(AsyncClient, "post")

        key = TEST_CRED.password

        params = {"key": key, "ver": 7, "arch": "aarch64", "count": 1}
        if flavour_testcase == "provided":
            params["flavor"] = "medium"

        response = await client.get("/Node/get", params=params)

        result = response.json()
        assert response.status_code == HTTP_200_OK
        assert result["ssid"] == self.apiv1_result["session"]["id"]
        assert set(result["hosts"]) == {
            node["hostname"] for node in self.apiv1_result["session"]["nodes"]
        }

    @pytest.mark.parametrize(
        "testcase",
        (
            "physical-auth",
            "virtual-auth-provided-flavour",
            "virtual-auth-default-flavour",
            "allocation-failed",
            "incorrect-auth",
            "incorrect-query",
            "unauthenticated",
        ),
    )
    @mock.patch("duffy.legacy.main.httpx.AsyncClient")
    async def test_get_node(self, AsyncClient, testcase, client):
        AsyncClient.return_value = ctxmgr = mock.MagicMock()
        ctxmgr.__aenter__.return_value = apiv1_client = mock.AsyncMock()

        apiv1_client.post.return_value = apiv1_response = mock.Mock()

        key = TEST_CRED.password

        if testcase == "physical-auth":
            apiv1_response.status_code = HTTP_201_CREATED
            apiv1_response.json.return_value = {
                "action": "post",
                "session": {
                    "id": 1,
                    "nodes": [
                        {"id": 1, "hostname": "boo", "ipaddr": "192.168.0.1"},
                        {"id": 2, "hostname": "bah", "ipaddr": "192.168.0.2"},
                    ],
                },
            }
            response = await client.get(
                "/Node/get", params={"key": key, "ver": 7, "arch": "x86_64", "count": 1}
            )
            result = response.json()
            assert response.status_code == HTTP_200_OK
        elif "virtual-auth" in testcase:
            apiv1_response.status_code = HTTP_201_CREATED
            apiv1_response.json.return_value = {
                "action": "post",
                "session": {
                    "id": 1,
                    "nodes": [
                        {"id": 1, "hostname": "boo", "ipaddr": "192.168.0.1"},
                        {"id": 2, "hostname": "bah", "ipaddr": "192.168.0.2"},
                    ],
                },
            }
            if "provided-flavour" in testcase:
                response = await client.get(
                    "/Node/get",
                    params={
                        "key": key,
                        "ver": 7,
                        "arch": "aarch64",
                        "count": 1,
                        "flavor": "medium",
                    },
                )
            elif "default-flavour" in testcase:
                response = await client.get(
                    "/Node/get", params={"key": key, "ver": 7, "arch": "aarch64", "count": 1}
                )
            result = response.json()
            assert response.status_code == HTTP_200_OK
        elif testcase == "allocation-failed":
            apiv1_response.status_code = HTTP_422_UNPROCESSABLE_ENTITY
            response = await client.get(
                "/Node/get", params={"key": key, "ver": 5, "arch": "armhf", "count": 3000}
            )
            result = response.json()
            assert result == "Failed to allocate nodes"
            assert response.status_code == HTTP_200_OK
        elif testcase == "incorrect-query":
            apiv1_response.status_code = HTTP_422_UNPROCESSABLE_ENTITY
            response = await client.get("/Node/get", params={"key": key, "ver": {}})
            result = response.json()
            assert result == "Failed to allocate nodes"
            assert response.status_code == HTTP_200_OK
        elif testcase == "incorrect-auth":
            apiv1_response.status_code = HTTP_403_FORBIDDEN
            response = await client.get("/Node/get", params={"key": "somedefinitelywrongkey"})
            result = response.json()
            assert result == {"detail": "Forbidden"}
            assert response.status_code == HTTP_403_FORBIDDEN
        elif testcase == "unauthenticated":
            apiv1_response.status_code = HTTP_401_UNAUTHORIZED
            response = await client.get(
                "/Node/get", params={"ver": 7, "arch": "x86_64", "count": 1}
            )
            result = response.json()
            assert result == {"detail": "Not authenticated"}
            assert response.status_code == HTTP_403_FORBIDDEN

    @pytest.mark.parametrize(
        "testcase",
        (
            "successfully-returned",
            "unsuccessfully-returned",
            "incorrect-auth",
            "ssid-absent",
            "unauthenticated",
        ),
    )
    @mock.patch("duffy.legacy.main.httpx.AsyncClient")
    async def test_return_node_on_completion(self, AsyncClient, testcase, client):
        apiv1_client, apiv1_response = self._setup_async_client(AsyncClient, "put")

        key = TEST_CRED.password

        if testcase == "successfully-returned":
            apiv1_response.status_code = HTTP_200_OK
            response = await client.get("/Node/done", params={"key": key, "ssid": 1})
            assert response.status_code == HTTP_200_OK
            result = response.json()
            assert result == "Done"
        elif testcase == "unsuccessfully-returned":
            apiv1_response.status_code = HTTP_422_UNPROCESSABLE_ENTITY
            response = await client.get("/Node/done", params={"key": key, "ssid": {}})
            result = response.json()
            assert result == "Failed to return nodes on completion"
            assert response.status_code == HTTP_200_OK
        elif testcase == "incorrect-auth":
            apiv1_response.status_code = HTTP_401_UNAUTHORIZED
            response = await client.get(
                "/Node/done", params={"ssid": 1, "key": "fca07101-daea-4b8c-acb4-88ba8ae7654c"}
            )
            result = response.json()
            assert result == {"msg": "Invalid duffy key"}
            assert response.status_code == HTTP_403_FORBIDDEN
        elif testcase == "ssid-absent":
            apiv1_response.status_code = HTTP_200_OK
            response = await client.get("/Node/done", params={"key": key})
            result = response.json()
            assert result == "Some parameters are absent"
            assert response.status_code == HTTP_200_OK
        elif testcase == "unauthenticated":
            apiv1_response.status_code = HTTP_200_OK
            response = await client.get("/Node/done", params={"ssid": 1})
            result = response.json()
            assert result == {"detail": "Not authenticated"}
            assert response.status_code == HTTP_403_FORBIDDEN

    @pytest.mark.parametrize(
        "testcase",
        ("successfully-extended", "incorrect-auth", "ssid-absent", "unauthenticated"),
    )
    @mock.patch("duffy.legacy.main.httpx.AsyncClient")
    async def test_return_node_on_failure(self, AsyncClient, testcase, client):
        AsyncClient.return_value = ctxmgr = mock.MagicMock()
        ctxmgr.__aenter__.return_value = apiv1_client = mock.AsyncMock()

        apiv1_client.get.return_value = apiv1_response = mock.Mock()

        key = TEST_CRED.password

        if testcase == "successfully-extended":
            apiv1_response.status_code = HTTP_200_OK
            response = await client.get("/Node/fail", params={"key": key, "ssid": 1})
            result = response.json()
            assert response.status_code == HTTP_200_OK
            assert result == "Not implemented yet"
        elif testcase == "incorrect-auth":
            apiv1_response.status_code = HTTP_200_OK
            response = await client.get(
                "/Node/fail", params={"key": "somedefinitelywrongkey", "ssid": 1}
            )
            result = response.json()
            assert result == {"detail": "Forbidden"}
            assert response.status_code == HTTP_403_FORBIDDEN
        elif testcase == "ssid-absent":
            apiv1_response.status_code = HTTP_200_OK
            response = await client.get("/Node/fail", params={"key": key})
            result = response.json()
            assert result == "Some parameters are absent"
            assert response.status_code == HTTP_200_OK
        elif testcase == "unauthenticated":
            apiv1_response.status_code = HTTP_200_OK
            response = await client.get("/Node/fail", params={"ssid": 1})
            result = response.json()
            assert result == {"detail": "Not authenticated"}
            assert response.status_code == HTTP_403_FORBIDDEN

    @pytest.mark.parametrize(
        "testcase",
        ("unauth", "correct-auth", "incorrect-auth", "incorrect-query", "unauth-apiv1-failure"),
    )
    @mock.patch("duffy.legacy.main.httpx.AsyncClient")
    async def test_get_nodes(self, AsyncClient, testcase, client):
        dest = config["metaclient"]["dest"].rstrip("/")

        if "unauth" in testcase:
            key = None
            long_form = True
        else:
            key = TEST_CRED.password
            long_form = False

        AsyncClient.return_value = ctxmgr = mock.MagicMock()
        ctxmgr.__aenter__.return_value = apiv1_client = mock.AsyncMock()

        apiv1_client.get.return_value = apiv1_response = mock.Mock()

        if testcase == "correct-auth":
            apiv1_response.status_code = HTTP_200_OK
            apiv1_response.return_value = {
                "action": "get",
                "sessions": [
                    {
                        "id": 1,
                        "nodes": [
                            {"id": 1, "hostname": "boo", "ipaddr": "192.168.0.1"},
                            {"id": 2, "hostname": "bah", "ipaddr": "192.168.0.2"},
                        ],
                    },
                ],
            }

        if "incorrect-auth" in testcase:
            apiv1_response.status_code = HTTP_403_FORBIDDEN
        elif "incorrect-query" in testcase:
            apiv1_response.status_code = HTTP_422_UNPROCESSABLE_ENTITY
        elif "apiv1-failure" in testcase:
            apiv1_response.status_code = HTTP_500_INTERNAL_SERVER_ERROR
        else:
            apiv1_response.status_code = HTTP_200_OK
            apiv1_response.json.return_value = {
                "action": "get",
                "sessions": [
                    {
                        "nodes": [
                            {"id": 1, "hostname": "boo", "ipaddr": "192.168.0.1"},
                            {"id": 2, "hostname": "bah", "ipaddr": "192.168.0.2"},
                        ],
                    },
                ],
            }

        response = await client.get("/Inventory", params={"key": key})

        if "incorrect" not in testcase and "failure" not in testcase:
            assert response.status_code == HTTP_200_OK
            result = response.json()
            assert isinstance(result, list)
            assert len(result) == 2
            assert all(
                self.noderesult_to_dict(node, long_form)["hostname"] in ("boo", "bah")
                for node in result
            )
        elif "incorrect-auth" in testcase:
            assert response.status_code == HTTP_403_FORBIDDEN
        elif "incorrect-query" in testcase or "apiv1-failure" in testcase:
            assert response.status_code == HTTP_200_OK
            assert response.json() == "Failed to retrieve inventory of nodes"
        else:
            assert False, f"Testcase uncovered? {testcase}"

        if "unauth" in testcase:
            auth = None
        else:
            auth = TEST_CRED.username, TEST_CRED.password

        apiv1_client.get.assert_awaited_with(f"{dest}/api/v1/sessions", auth=auth)
