from http import HTTPStatus
from json import JSONDecodeError
from unittest import mock

import httpx
import pytest
from pydantic import BaseModel

from duffy.api_models import (
    PoolResult,
    PoolResultCollection,
    SessionCreateModel,
    SessionResult,
    SessionResultCollection,
    SessionUpdateModel,
)
from duffy.client import DuffyClient
from duffy.client.main import _MethodEnum
from duffy.configuration import config

from ..util import noop_context


class InModel(BaseModel):
    in_field: int


class OutModel(BaseModel):
    out_field: int


@pytest.mark.duffy_config(example_config=True)
class TestDuffyClient:
    wrapper_method_test_details = {
        "list_sessions": (
            mock.call(),
            mock.call(_MethodEnum.get, "/sessions", out_model=SessionResultCollection),
        ),
        "show_session": (
            mock.call(15),
            mock.call(_MethodEnum.get, "/sessions/15", out_model=SessionResult),
        ),
        "request_session": (
            mock.call([{"pool": "pool", "quantity": "31"}]),
            mock.call(
                _MethodEnum.post,
                "/sessions",
                in_dict={"nodes_specs": [{"pool": "pool", "quantity": "31"}]},
                in_model=SessionCreateModel,
                out_model=SessionResult,
                expected_status=HTTPStatus.CREATED,
            ),
        ),
        "retire_session": (
            mock.call(53),
            mock.call(
                _MethodEnum.put,
                "/sessions/53",
                in_dict={"active": False},
                in_model=SessionUpdateModel,
                out_model=SessionResult,
            ),
        ),
        "list_pools": (
            mock.call(),
            mock.call(_MethodEnum.get, "/pools", out_model=PoolResultCollection),
        ),
        "show_pool": (
            mock.call("lagoon"),
            mock.call(_MethodEnum.get, "/pools/lagoon", out_model=PoolResult),
        ),
    }

    @pytest.mark.parametrize("testcase", ("params-set", "params-unset"))
    def test___init___and_properties(self, testcase):
        if testcase == "params-set":
            kwargs = {
                "url": "http://localhost:6789",
                "auth_name": "Bonzo the Clown",
                "auth_key": "🔑",
            }
        else:
            kwargs = {}

        client = DuffyClient(**kwargs)

        if testcase == "params-set":
            for key, value in kwargs.items():
                assert getattr(client, key) == value
        else:
            assert client.url == config["client"]["url"]
            assert client.auth_name == config["client"]["auth"]["name"]
            assert client.auth_key == config["client"]["auth"]["key"]

    def test_client_property(self):
        client = DuffyClient().client()

        assert isinstance(client, httpx.Client)
        assert isinstance(client.auth, httpx.BasicAuth)
        url = config["client"]["url"]
        if not url.endswith("/"):
            url += "/"
        assert client.base_url == httpx.URL(url)

    @pytest.mark.parametrize(
        "actual_status, with_detail",
        (
            (HTTPStatus.OK, None),
            (HTTPStatus.CREATED, None),
            (HTTPStatus.BAD_REQUEST, True),
            (HTTPStatus.BAD_REQUEST, False),
        ),
    )
    @pytest.mark.parametrize("expected_status", (HTTPStatus.OK, (HTTPStatus.OK,)))
    @pytest.mark.parametrize("http_method", ("get", "post", "put"))
    @mock.patch("duffy.client.main.httpx.Client")
    def test__query_method(self, Client, http_method, expected_status, actual_status, with_detail):
        method = _MethodEnum(http_method)

        expected_statuses = (
            (expected_status,) if isinstance(expected_status, HTTPStatus) else expected_status
        )

        Client.return_value = ctxmgr = mock.MagicMock()
        ctxmgr.__enter__.return_value = apiv1_client = mock.MagicMock()

        expectation = noop_context()

        getattr(apiv1_client, http_method).return_value = apiv1_response = mock.MagicMock()
        apiv1_response.status_code = actual_status
        if actual_status in expected_statuses:
            apiv1_response.json.return_value = {"out_field": 7}
        elif with_detail:
            apiv1_response.json.return_value = {"detail": "a detail"}
        elif actual_status >= 400:  # client- and server-side errors
            apiv1_response.json.side_effect = JSONDecodeError("msg", "doc", 0)
            request = mock.MagicMock()
            apiv1_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                message="BOOP", request=request, response=apiv1_response
            )
            expectation = pytest.raises(httpx.HTTPStatusError)
        else:  # unexpected, successful response
            apiv1_response.json.return_value = {"another_out_field": 15}
            expectation = pytest.raises(RuntimeError)

        kwargs = {"expected_status": expected_status}

        if http_method in ("post", "put"):
            kwargs.update({"in_dict": {"in_field": 5}, "in_model": InModel})

        dclient = DuffyClient()

        with expectation as exc:
            result = dclient._query_method(method=method, url="url", out_model=OutModel, **kwargs)

        if actual_status not in expected_statuses:
            if actual_status >= 400:
                if with_detail:
                    assert result.error.detail == "a detail"
                else:
                    assert exc.match("BOOP")
            else:
                assert exc.match("Can't process response:")
        else:
            assert result.out_field == 7

    @pytest.mark.parametrize("method_name", list(wrapper_method_test_details))
    def test_wrapper_methods(self, method_name):
        method_call_args, expected_wrapped_call_args = self.wrapper_method_test_details[method_name]

        dclient = DuffyClient()
        with mock.patch.object(dclient, "_query_method") as query_method:
            getattr(dclient, method_name)(*method_call_args.args, **method_call_args.kwargs)
        query_method.assert_called_once_with(
            *expected_wrapped_call_args.args, **expected_wrapped_call_args.kwargs
        )
