from enum import Enum
from typing import Dict, Literal, Optional

from pydantic import AnyUrl, BaseModel, conint, stricturl

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


class PlaybookType(str, Enum):
    provision = "provision"
    deprovision = "deprovision"


# Pydantic models


class CeleryConfigModel(BaseModel):
    broker_url: AnyUrl
    result_backend: AnyUrl


class SQLAlchemyModel(BaseModel):
    sync_url: stricturl(tld_required=False, host_required=False)
    async_url: stricturl(tld_required=False, host_required=False)


class DatabaseConfigModel(BaseModel):
    sqlalchemy: SQLAlchemyModel


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
    celery: Optional[CeleryConfigModel]
    database: Optional[DatabaseConfigModel]
    metaclient: Optional[LegacyModel]
