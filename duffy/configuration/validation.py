import re
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union
from uuid import UUID

from pydantic import AnyHttpUrl, AnyUrl, BaseModel, Field, RedisDsn, conint, stricturl, validator

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
    class Config:
        extra = "forbid"


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
    periodic: Optional[Dict[str, PeriodicTaskModel]]


class SQLAlchemyModel(BaseModel):
    # This is intentionally not a subclass of ConfigBaseModel, it is passed on to SQLAlchemy's
    # create_engine()/create_async_engine(), i.e. can contain arbitrarily named fields.
    sync_url: stricturl(tld_required=False, host_required=False)
    async_url: stricturl(tld_required=False, host_required=False)


class DatabaseModel(ConfigBaseModel):
    sqlalchemy: SQLAlchemyModel


class DefaultsModel(ConfigBaseModel):
    session_lifetime: ConfigTimeDelta = Field(alias="session-lifetime")
    session_lifetime_max: ConfigTimeDelta = Field(alias="session-lifetime-max")
    node_quota: conint(gt=0) = Field(alias="node-quota")


class AnsibleMechanismPlaybookModel(ConfigBaseModel):
    extra_vars: Optional[Dict[str, Any]] = Field(alias="extra-vars")
    playbook: Path


class AnsibleMechanismModel(ConfigBaseModel):
    topdir: Optional[Path]
    extra_vars: Optional[Dict[str, Any]] = Field(alias="extra-vars")
    provision: Optional[AnsibleMechanismPlaybookModel]
    deprovision: Optional[AnsibleMechanismPlaybookModel]


class MechanismModel(ConfigBaseModel):
    type_: Optional[MechanismType] = Field(alias="type")
    ansible: Optional[AnsibleMechanismModel]


class NodePoolsModel(ConfigBaseModel):
    extends: Optional[str]
    mechanism: Optional[MechanismModel]
    fill_level: Optional[conint(gt=0)] = Field(alias="fill-level")
    reuse_nodes: Optional[Union[Dict[str, Union[int, str]], Literal[False]]] = Field(
        alias="reuse-nodes"
    )
    run_parallel: Optional[bool] = Field(alias="run-parallel")

    class Config:
        extra = "allow"


class NodePoolsRootModel(ConfigBaseModel):
    abstract: Optional[Dict[str, NodePoolsModel]]
    concrete: Dict[str, NodePoolsModel]


class LoggingModel(ConfigBaseModel):
    version: Literal[1]

    class Config:
        extra = "allow"


class ClientAuthModel(ConfigBaseModel):
    name: str
    key: UUID


class ClientModel(ConfigBaseModel):
    url: AnyHttpUrl
    auth: ClientAuthModel


class AppModel(ConfigBaseModel):
    loglevel: Optional[LogLevel]
    host: Optional[str]
    port: Optional[conint(gt=0, lt=65536)]
    logging: Optional[LoggingModel]


class LegacyPoolMapModel(ConfigBaseModel):
    pool: str
    ver: Optional[str]
    arch: Optional[str]
    flavor: Optional[str]

    @validator("ver", "arch", "flavor")
    def detect_regex(cls, v: str):
        if v.startswith("^") and v.endswith("$"):
            return re.compile(v)
        return v


class LegacyModel(ConfigBaseModel):
    host: Optional[str]
    port: Optional[conint(gt=0, lt=65536)]
    dest: Optional[AnyHttpUrl]
    loglevel: Optional[LogLevel]
    logging: Optional[LoggingModel]
    usermap: Dict[str, str]
    poolmap: List[LegacyPoolMapModel]
    mangle_hostname: Optional[str]


class ConfigModel(ConfigBaseModel):
    client: Optional[ClientModel]
    app: Optional[AppModel]
    tasks: Optional[TasksModel]
    database: Optional[DatabaseModel]
    defaults: Optional[DefaultsModel]
    metaclient: Optional[LegacyModel]
    nodepools: Optional[NodePoolsRootModel]
