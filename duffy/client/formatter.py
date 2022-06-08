import json
import shlex
from typing import Generator

import yaml
from pydantic import BaseModel

from ..api_models import (
    PoolModel,
    PoolResult,
    PoolResultCollection,
    SessionModel,
    SessionResult,
    SessionResultCollection,
)
from .main import DuffyAPIErrorModel


class DuffyFormatter:
    _subclasses_for_format = {}

    def __init_subclass__(cls, format, **kwargs):
        cls._subclasses_for_format[format] = cls

    @classmethod
    def new_for_format(cls, format, *args, **kwargs):
        return cls._subclasses_for_format[format](*args, **kwargs)

    @staticmethod
    def result_as_compatible_dict(result: BaseModel) -> dict:
        return json.loads(result.json())

    def format(self, result: BaseModel) -> str:
        raise NotImplementedError()


class DuffyJSONFormatter(DuffyFormatter, format="json"):
    def format(self, result: BaseModel) -> str:
        return result.json(indent=2)


class DuffyYAMLFormatter(DuffyFormatter, format="yaml"):
    def format(self, result: BaseModel) -> str:
        return yaml.dump(self.result_as_compatible_dict(result))


class DuffyFlatFormatter(DuffyFormatter, format="flat"):
    model_to_flattener = {
        DuffyAPIErrorModel: "flatten_api_error",
        PoolResult: "flatten_pool_result",
        PoolResultCollection: "flatten_pools_result",
        SessionResult: "flatten_session_result",
        SessionResultCollection: "flatten_sessions_result",
    }

    @staticmethod
    def format_key_value(key, value):
        if value is None:
            value = ""
        elif isinstance(value, bool):
            value = "TRUE" if value else "FALSE"
        elif isinstance(value, (int, float)):
            pass
        else:
            value = shlex.quote(str(value))
            if value[:1] != "'":
                value = f"'{value}'"

        return f"{key}={value}"

    def flatten_api_error(self, api_error: DuffyAPIErrorModel) -> Generator[str, None, None]:
        yield self.format_key_value("error", api_error.error.detail)

    def flatten_pool(self, pool: PoolModel) -> Generator[str, None, None]:
        fields = {"pool_name": pool.name, "fill_level": pool.fill_level}
        if hasattr(pool, "levels"):
            fields.update(
                {
                    "levels_provisioning": pool.levels.provisioning,
                    "levels_ready": pool.levels.ready,
                    "levels_contextualizing": pool.levels.contextualizing,
                    "levels_deployed": pool.levels.deployed,
                    "levels_deprovisioning": pool.levels.deprovisioning,
                }
            )
        yield " ".join(self.format_key_value(key, value) for key, value in fields.items())

    def flatten_pool_result(self, result: PoolResult) -> Generator[str, None, None]:
        yield from self.flatten_pool(result.pool)

    def flatten_pools_result(self, result: PoolResultCollection) -> Generator[str, None, None]:
        for pool in result.pools:
            yield from self.flatten_pool(pool)

    def flatten_session(self, session: SessionModel) -> Generator[str, None, None]:
        for node in sorted(session.nodes, key=lambda node: (node.pool, node.hostname, node.ipaddr)):
            fields = {
                "session_id": session.id,
                "active": session.active,
                "created_at": session.created_at,
                "retired_at": session.retired_at,
                "pool": node.pool,
                "hostname": node.hostname,
                "ipaddr": node.ipaddr,
            }
            yield " ".join(self.format_key_value(key, value) for key, value in fields.items())

    def flatten_session_result(self, result: SessionResult) -> Generator[str, None, None]:
        yield from self.flatten_session(result.session)

    def flatten_sessions_result(
        self, result: SessionResultCollection
    ) -> Generator[str, None, None]:
        for session in result.sessions:
            yield from self.flatten_session(session)

    def format(self, result: BaseModel) -> str:
        for model, flattener in self.model_to_flattener.items():
            if isinstance(result, model):
                return "\n".join(getattr(self, flattener)(result))

        raise TypeError("Can't flatten {result!r}")
