from enum import Enum
from pathlib import Path
from typing import Any, Dict, Literal, Optional, Union

from pydantic import AnyUrl, BaseModel, Field, RedisDsn, conint, stricturl

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


class CeleryModel(BaseModel):
    broker_url: AnyUrl
    result_backend: AnyUrl


class LockingModel(BaseModel):
    url: RedisDsn


class PeriodicTaskModel(BaseModel):
    interval: conint(gt=0)


class TasksModel(BaseModel):
    celery: CeleryModel
    locking: LockingModel
    periodic: Optional[Dict[str, PeriodicTaskModel]]


class SQLAlchemyModel(BaseModel):
    sync_url: stricturl(tld_required=False, host_required=False)
    async_url: stricturl(tld_required=False, host_required=False)


class DatabaseModel(BaseModel):
    sqlalchemy: SQLAlchemyModel


class MiscModel(BaseModel):
    session_lifetime: ConfigTimeDelta = Field(alias="session-lifetime")
    session_lifetime_max: ConfigTimeDelta = Field(alias="session-lifetime-max")


class AnsibleMechanismPlaybookModel(BaseModel):
    extra_vars: Optional[Dict[str, Any]] = Field(alias="extra-vars")
    playbook: Path


class AnsibleMechanismModel(BaseModel):
    topdir: Optional[Path]
    extra_vars: Optional[Dict[str, Any]] = Field(alias="extra-vars")
    provision: Optional[AnsibleMechanismPlaybookModel]
    deprovision: Optional[AnsibleMechanismPlaybookModel]


class MechanismModel(BaseModel):
    type_: Optional[MechanismType] = Field(alias="type")
    ansible: Optional[AnsibleMechanismModel]


class NodePoolsModel(BaseModel):
    extends: Optional[str]
    mechanism: Optional[MechanismModel]
    fill_level: Optional[conint(gt=0)] = Field(alias="fill-level")
    reuse_nodes: Optional[Union[Dict[str, Union[int, str]], Literal[False]]] = Field(
        alias="reuse-nodes"
    )

    class Config:
        extra = "allow"


class NodePoolsRootModel(BaseModel):
    abstract: Optional[Dict[str, NodePoolsModel]]
    concrete: Dict[str, NodePoolsModel]


class LoggingModel(BaseModel):
    version: Literal[1]

    class Config:
        extra = "allow"


class AppModel(BaseModel):
    loglevel: Optional[LogLevel]
    host: Optional[str]
    port: Optional[conint(gt=0, lt=65536)]
    logging: Optional[LoggingModel]


class LegacyModel(BaseModel):
    host: Optional[str]
    port: Optional[conint(gt=0, lt=65536)]
    dest: Optional[str]
    loglevel: Optional[LogLevel]
    logging: Optional[LoggingModel]
    usermap: Dict[str, str]


class ConfigModel(BaseModel):
    app: Optional[AppModel]
    tasks: Optional[TasksModel]
    database: Optional[DatabaseModel]
    misc: Optional[MiscModel]
    metaclient: Optional[LegacyModel]
    nodepools: Optional[NodePoolsRootModel]
