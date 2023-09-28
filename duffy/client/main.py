from enum import Enum
from http import HTTPStatus
from typing import Any, Dict, List, Optional, Sequence, Union

import httpx
from pydantic import BaseModel, ConfigDict

from ..api_models import SessionCreateModel, SessionUpdateModel
from ..configuration import config

JSONValue = Union[None, bool, str, float, int, List["JSONValue"], Dict[str, "JSONValue"]]


class _MethodEnum(str, Enum):
    get = "get"
    post = "post"
    put = "put"
    delete = "delete"


class DuffyApiErrorDetailModel(BaseModel):
    detail: str
    model_config = ConfigDict(extra="allow")


class DuffyAPIErrorModel(BaseModel):
    error: DuffyApiErrorDetailModel


class DuffyClient:
    def __init__(
        self,
        url: Optional[str] = None,
        auth_name: Optional[str] = None,
        auth_key: Optional[str] = None,
    ):
        if url:
            self.url = url
        if auth_name:
            self.auth_name = auth_name
        if auth_key:
            self.auth_key = auth_key

    @property
    def url(self):
        return getattr(self, "_url", None) or config["client"]["url"]

    @url.setter
    def url(self, value):
        self._url = value

    @property
    def auth_name(self):
        return getattr(self, "_auth_name", None) or config["client"]["auth"]["name"]

    @auth_name.setter
    def auth_name(self, value):
        self._auth_name = value

    @property
    def auth_key(self):
        return getattr(self, "_auth_key", None) or config["client"]["auth"]["key"]

    @auth_key.setter
    def auth_key(self, value):
        self._auth_key = value

    def client(self):
        return httpx.Client(auth=(self.auth_name, self.auth_key), base_url=self.url, timeout=None)

    def _query_method(
        self,
        method: _MethodEnum,
        url: str,
        *,
        in_dict: Optional[Dict[str, Any]] = None,
        in_model: Optional[BaseModel] = None,
        expected_status: Union[HTTPStatus, Sequence[HTTPStatus]] = HTTPStatus.OK,
    ) -> JSONValue:
        add_kwargs = {}
        if in_dict is not None:
            add_kwargs["json"] = in_model(**in_dict).model_dump()

        with self.client() as client:
            client_method = getattr(client, method.name)
            response = client_method(url=url, **add_kwargs)

        if isinstance(expected_status, HTTPStatus):
            expected_status = (expected_status,)

        if response.status_code not in expected_status:
            try:
                return DuffyAPIErrorModel(error=response.json()).model_dump(by_alias=True)
            except Exception as exc:
                response.raise_for_status()
                raise RuntimeError(f"Can't process response: {response}") from exc

        return response.json()

    def list_sessions(self) -> JSONValue:
        return self._query_method(_MethodEnum.get, "/sessions")

    def show_session(self, session_id: int) -> JSONValue:
        return self._query_method(_MethodEnum.get, f"/sessions/{session_id}")

    def request_session(self, nodes_specs: List[Dict[str, str]]) -> JSONValue:
        return self._query_method(
            _MethodEnum.post,
            "/sessions",
            in_dict={"nodes_specs": nodes_specs},
            in_model=SessionCreateModel,
            expected_status=HTTPStatus.CREATED,
        )

    def retire_session(self, session_id: int) -> JSONValue:
        return self._query_method(
            _MethodEnum.put,
            f"/sessions/{session_id}",
            in_dict={"active": False},
            in_model=SessionUpdateModel,
        )

    def list_pools(self) -> JSONValue:
        return self._query_method(_MethodEnum.get, "/pools")

    def show_pool(self, pool_name: str) -> JSONValue:
        return self._query_method(_MethodEnum.get, f"/pools/{pool_name}")
