import re
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union
from uuid import UUID

from pydantic import (
    AnyHttpUrl,
    AnyUrl,
    BaseModel,
    ConfigDict,
    Field,
    RedisDsn,
    UrlConstraints,
    field_validator,
)
from typing_extensions import Annotated

from ..misc import ConfigTimeDelta

# enums


class LogLevel(str, Enum):
    trace = "trace"
    debug = "debug"
    info = "info"
    warning = "warning"
    error = "error"
    critical = "critical"


class MechanismType(str, Enum):
    ansible = "ansible"


# Pydantic models


class ConfigBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CeleryModel(BaseModel):
    # This is intentionally not a subclass of ConfigBaseModel, it is passed on to Celery, i.e. can
    # contain arbitrarily named fields.
    broker_url: AnyUrl
    result_backend: AnyUrl


class LockingModel(ConfigBaseModel):
    url: RedisDsn


class PeriodicTaskModel(ConfigBaseModel):
    interval: ConfigTimeDelta


class TasksModel(ConfigBaseModel):
    celery: CeleryModel
    locking: LockingModel
    periodic: Optional[Dict[str, PeriodicTaskModel]] = None


class SQLAlchemyModel(BaseModel):
    # This is intentionally not a subclass of ConfigBaseModel, it is passed on to SQLAlchemy's
    # create_engine()/create_async_engine(), i.e. can contain arbitrarily named fields.
    sync_url: Annotated[AnyUrl, UrlConstraints(host_required=False)]
    async_url: Annotated[AnyUrl, UrlConstraints(host_required=False)]


class DatabaseModel(ConfigBaseModel):
    sqlalchemy: SQLAlchemyModel


class RetriesModel(ConfigBaseModel):
    no_attempts: Optional[Annotated[int, Field(ge=1)]] = Field(alias="no-attempts", default=None)
    delay_min: Optional[Union[Annotated[int, Field(ge=0)], Annotated[float, Field(ge=0)]]] = Field(
        alias="delay-min", default=None
    )
    delay_max: Optional[Union[Annotated[int, Field(ge=0)], Annotated[float, Field(ge=0)]]] = Field(
        alias="delay-max", default=None
    )
    delay_backoff_factor: Optional[
        Union[Annotated[int, Field(ge=1)], Annotated[float, Field(ge=1)]]
    ] = Field(alias="delay-backoff-factor", default=None)
    delay_add_fuzz: Optional[Union[Annotated[int, Field(ge=0)], Annotated[float, Field(ge=0)]]] = (
        Field(alias="delay-add-fuzz", default=None)
    )


class DefaultsModel(ConfigBaseModel):
    session_lifetime: ConfigTimeDelta = Field(alias="session-lifetime")
    session_lifetime_max: ConfigTimeDelta = Field(alias="session-lifetime-max")
    node_quota: Annotated[int, Field(gt=0)] = Field(alias="node-quota")
    retries: Optional[RetriesModel] = None


class AnsibleMechanismPlaybookModel(ConfigBaseModel):
    extra_vars: Optional[Dict[str, Any]] = Field(alias="extra-vars", default=None)
    playbook: Path


class AnsibleMechanismModel(ConfigBaseModel):
    topdir: Optional[Path] = None
    extra_vars: Optional[Dict[str, Any]] = Field(alias="extra-vars", default=None)
    provision: Optional[AnsibleMechanismPlaybookModel] = None
    deprovision: Optional[AnsibleMechanismPlaybookModel] = None


class MechanismModel(ConfigBaseModel):
    type_: Optional[MechanismType] = Field(alias="type", default=None)
    ansible: Optional[AnsibleMechanismModel] = None


class NodePoolsModel(ConfigBaseModel):
    extends: Optional[str] = None
    mechanism: Optional[MechanismModel] = None
    fill_level: Optional[Annotated[int, Field(gt=0)]] = Field(alias="fill-level", default=None)
    reuse_nodes: Optional[Union[Dict[str, Union[int, str]], Literal[False]]] = Field(
        alias="reuse-nodes", default=None
    )
    run_parallel: Optional[bool] = Field(alias="run-parallel", default=None)
    model_config = ConfigDict(extra="allow")


class NodePoolsRootModel(ConfigBaseModel):
    abstract: Optional[Dict[str, NodePoolsModel]] = None
    concrete: Dict[str, NodePoolsModel]


class LoggingModel(ConfigBaseModel):
    version: Literal[1]
    model_config = ConfigDict(extra="allow")


class ClientAuthModel(ConfigBaseModel):
    name: str
    key: UUID


class ClientModel(ConfigBaseModel):
    url: AnyHttpUrl
    auth: ClientAuthModel


class AppModel(ConfigBaseModel):
    loglevel: Optional[LogLevel] = None
    host: Optional[str] = None
    port: Optional[Annotated[int, Field(gt=0, lt=65536)]] = None
    logging: Optional[LoggingModel] = None
    retries: Optional[RetriesModel] = None


class LegacyPoolMapModel(ConfigBaseModel):
    pool: str
    ver: Optional[str] = None
    arch: Optional[str] = None
    flavor: Optional[str] = None

    @field_validator("ver", "arch", "flavor")
    @classmethod
    def detect_regex(cls, v: str):
        if v.startswith("^") and v.endswith("$"):
            return re.compile(v)
        return v


class LegacyModel(ConfigBaseModel):
    host: Optional[str] = None
    port: Optional[Annotated[int, Field(gt=0, lt=65536)]] = None
    dest: Optional[AnyHttpUrl] = None
    loglevel: Optional[LogLevel] = None
    logging: Optional[LoggingModel] = None
    usermap: Dict[str, str]
    poolmap: List[LegacyPoolMapModel]
    mangle_hostname: Optional[str] = None


class ConfigModel(ConfigBaseModel):
    client: Optional[ClientModel] = None
    app: Optional[AppModel] = None
    tasks: Optional[TasksModel] = None
    database: Optional[DatabaseModel] = None
    defaults: Optional[DefaultsModel] = None
    metaclient: Optional[LegacyModel] = None
    nodepools: Optional[NodePoolsRootModel] = None
