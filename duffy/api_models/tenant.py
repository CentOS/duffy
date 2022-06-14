from abc import ABC
from datetime import timedelta
from typing import List, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, SecretStr, conint, root_validator

from ..misc import ConfigTimeDelta
from .common import APIResult, CreatableMixin, RetirableMixin

# tenant model


class TenantBase(BaseModel, ABC):
    name: str
    is_admin: Optional[bool]
    ssh_key: SecretStr
    node_quota: Optional[conint(gt=0)]
    session_lifetime: Optional[ConfigTimeDelta]
    session_lifetime_max: Optional[ConfigTimeDelta]

    class Config:
        orm_mode = True


class TenantCreateModel(TenantBase):
    pass


class TenantRetireModel(BaseModel):
    active: bool


class TenantUpdateModel(BaseModel):
    ssh_key: Optional[SecretStr]
    api_key: Optional[Union[UUID, Literal["reset"]]]
    node_quota: Optional[conint(gt=0)]
    session_lifetime: Optional[ConfigTimeDelta]
    session_lifetime_max: Optional[ConfigTimeDelta]

    class Config:
        minimum_fields = (
            "ssh_key",
            "api_key",
            "node_quota",
            "session_lifetime",
            "session_lifetime_max",
        )

    @root_validator(pre=True)
    def check_any_field_set(cls, values):
        if not any(field in values for field in cls.Config.minimum_fields):
            raise ValueError(f"one of {', '.join(cls.Config.minimum_fields)} is required")
        return values


class TenantModel(TenantBase, CreatableMixin, RetirableMixin):
    id: int
    effective_node_quota: int
    effective_session_lifetime: timedelta
    effective_session_lifetime_max: timedelta


class TenantCreateResultModel(TenantModel):
    api_key: UUID


class TenantUpdateResultModel(TenantModel):
    api_key: Optional[Union[UUID, SecretStr]]


# API results


class TenantResult(APIResult):
    tenant: TenantModel


class TenantCreateResult(TenantResult):
    tenant: TenantCreateResultModel

    class Config:
        json_encoders = {SecretStr: lambda v: v.get_secret_value() if v else None}


class TenantUpdateResult(TenantResult):
    tenant: TenantUpdateResultModel


class TenantResultCollection(APIResult):
    tenants: List[TenantModel]
