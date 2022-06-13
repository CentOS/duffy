from enum import Enum
from http import HTTPStatus
from typing import Any, Dict, List, Optional, Sequence, Union

import httpx
from pydantic import BaseModel

from ..api_models import (
    PoolResult,
    PoolResultCollection,
    SessionCreateModel,
    SessionResult,
    SessionResultCollection,
    SessionUpdateModel,
)
from ..configuration import config


class _MethodEnum(str, Enum):
    get = "get"
    post = "post"
    put = "put"
    delete = "delete"


class DuffyApiErrorDetailModel(BaseModel):
    detail: str

    class Config:
        extra = "allow"


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
        return httpx.Client(auth=(self.auth_name, self.auth_key), base_url=self.url)

    def _query_method(
        self,
        method: _MethodEnum,
        url: str,
        *,
        in_dict: Optional[Dict[str, Any]] = None,
        in_model: Optional[BaseModel] = None,
        out_model: BaseModel,
        expected_status: Union[HTTPStatus, Sequence[HTTPStatus]] = HTTPStatus.OK,
    ) -> BaseModel:
        add_kwargs = {}
        if in_dict is not None:
            add_kwargs["json"] = in_model(**in_dict).dict()

        with self.client() as client:
            client_method = getattr(client, method.name)
            response = client_method(url=url, **add_kwargs)

        if isinstance(expected_status, HTTPStatus):
            expected_status = (expected_status,)

        if response.status_code not in expected_status:
            try:
                return DuffyAPIErrorModel(error=response.json())
            except Exception as exc:
                response.raise_for_status()
                raise RuntimeError(f"Can't process response: {response}") from exc

        return out_model(**response.json())

    def list_sessions(self) -> SessionResultCollection:
        return self._query_method(
            _MethodEnum.get,
            "/sessions",
            out_model=SessionResultCollection,
        )

    def show_session(self, session_id: int) -> SessionResult:
        return self._query_method(
            _MethodEnum.get,
            f"/sessions/{session_id}",
            out_model=SessionResult,
        )

    def request_session(self, nodes_specs: List[Dict[str, str]]) -> SessionResult:
        return self._query_method(
            _MethodEnum.post,
            "/sessions",
            in_dict={"nodes_specs": nodes_specs},
            in_model=SessionCreateModel,
            out_model=SessionResult,
            expected_status=HTTPStatus.CREATED,
        )

    def retire_session(self, session_id: int) -> SessionResult:
        return self._query_method(
            _MethodEnum.put,
            f"/sessions/{session_id}",
            in_dict={"active": False},
            in_model=SessionUpdateModel,
            out_model=SessionResult,
        )

    def list_pools(self) -> PoolResultCollection:
        return self._query_method(
            _MethodEnum.get,
            "/pools",
            out_model=PoolResultCollection,
        )

    def show_pool(self, pool_name: str) -> PoolResult:
        return self._query_method(
            _MethodEnum.get,
            f"/pools/{pool_name}",
            out_model=PoolResult,
        )
