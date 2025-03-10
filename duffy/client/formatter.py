import json
import shlex
from typing import Generator

import yaml

from .main import DuffyAPIErrorModel, JSONValue


class DuffyFormatter:
    _subclasses_for_format = {}

    def __init_subclass__(cls, format, **kwargs):
        cls._subclasses_for_format[format] = cls

    @classmethod
    def new_for_format(cls, format, *args, **kwargs):
        return cls._subclasses_for_format[format](*args, **kwargs)

    def format(self, result: JSONValue) -> str:
        raise NotImplementedError()


class DuffyJSONFormatter(DuffyFormatter, format="json"):
    def format(self, result: JSONValue) -> str:
        return json.dumps(result, indent=4)


class DuffyYAMLFormatter(DuffyFormatter, format="yaml"):
    def format(self, result: JSONValue) -> str:
        return yaml.dump(result)


class DuffyFlatFormatter(DuffyFormatter, format="flat"):
    field_name_to_flattener = {
        "error": "flatten_api_error",
        "pool": "flatten_pool_result",
        "pools": "flatten_pools_result",
        "session": "flatten_session_result",
        "sessions": "flatten_sessions_result",
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

    def flatten_pool(self, pool: JSONValue) -> Generator[str, None, None]:
        fields = {
            "pool_name": pool["name"],
            "fill_level": pool.get("fill-level", pool.get("fill_level")),
        }
        if "levels" in pool:
            fields.update(
                {
                    "levels_provisioning": pool["levels"]["provisioning"],
                    "levels_ready": pool["levels"]["ready"],
                    "levels_contextualizing": pool["levels"]["contextualizing"],
                    "levels_deployed": pool["levels"]["deployed"],
                    "levels_deprovisioning": pool["levels"]["deprovisioning"],
                }
            )
        yield " ".join(self.format_key_value(key, value) for key, value in fields.items())

    def flatten_pool_result(self, result: JSONValue) -> Generator[str, None, None]:
        yield from self.flatten_pool(result["pool"])

    def flatten_pools_result(self, result: JSONValue) -> Generator[str, None, None]:
        for pool in result["pools"]:
            yield from self.flatten_pool(pool)

    def flatten_session(self, session: JSONValue) -> Generator[str, None, None]:
        for node in sorted(
            session["nodes"], key=lambda node: (node["pool"], node["hostname"], node["ipaddr"])
        ):
            fields = {
                "session_id": session["id"],
                "active": session["active"],
                "created_at": session["created_at"],
                "retired_at": session["retired_at"],
                "pool": node["pool"],
                "hostname": node["hostname"],
                "ipaddr": node["ipaddr"],
            }
            yield " ".join(self.format_key_value(key, value) for key, value in fields.items())

    def flatten_session_result(self, result: JSONValue) -> Generator[str, None, None]:
        yield from self.flatten_session(result["session"])

    def flatten_sessions_result(self, result: JSONValue) -> Generator[str, None, None]:
        for session in result["sessions"]:
            yield from self.flatten_session(session)

    def format(self, result: JSONValue) -> str:
        for field_name, flattener in self.field_name_to_flattener.items():
            if field_name in result:
                return "\n".join(getattr(self, flattener)(result))

        raise TypeError("Can't flatten {result!r}")
