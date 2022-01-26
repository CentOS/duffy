from enum import Enum
from typing import Literal, Optional

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


class ConfigModel(BaseModel):
    loglevel: Optional[LogLevel]
    host: Optional[str]
    port: Optional[conint(gt=0, lt=65536)]

    celery: Optional[CeleryConfigModel]

    database: Optional[DatabaseConfigModel]

    logging: Optional[LoggingModel]
