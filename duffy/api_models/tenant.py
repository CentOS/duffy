from abc import ABC
from datetime import timedelta
from typing import List, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from typing_extensions import Annotated

from ..misc import ConfigTimeDelta
from .common import APIResult, CreatableMixin, RetirableMixin

# tenant model


class TenantBase(BaseModel, ABC):
    name: str
    is_admin: Optional[bool] = None
    ssh_key: SecretStr
    node_quota: Optional[Annotated[int, Field(gt=0)]] = None
    session_lifetime: Optional[ConfigTimeDelta] = None
    session_lifetime_max: Optional[ConfigTimeDelta] = None
    model_config = ConfigDict(from_attributes=True, ser_json_timedelta="float")


class TenantCreateModel(TenantBase):
    pass


class TenantRetireModel(BaseModel):
    active: bool


class TenantUpdateModel(BaseModel):
    ssh_key: Optional[SecretStr] = None
    api_key: Optional[Union[UUID, Literal["reset"]]] = None
    node_quota: Optional[Annotated[int, Field(gt=0)]] = None
    session_lifetime: Optional[ConfigTimeDelta] = None
    session_lifetime_max: Optional[ConfigTimeDelta] = None
    model_config = ConfigDict(
        minimum_fields=(
            "ssh_key",
            "api_key",
            "node_quota",
            "session_lifetime",
            "session_lifetime_max",
        )
    )

    @model_validator(mode="before")
    @classmethod
    def check_any_field_set(cls, values):
        if not any(field in values for field in cls.model_config["minimum_fields"]):
            raise ValueError(f"one of {', '.join(cls.model_config['minimum_fields'])} is required")
        return values


class TenantModel(TenantBase, CreatableMixin, RetirableMixin):
    id: int
    effective_node_quota: int
    effective_session_lifetime: timedelta
    effective_session_lifetime_max: timedelta


class TenantCreateResultModel(TenantModel):
    ssh_key: str
    api_key: UUID


class TenantUpdateResultModel(TenantModel):
    api_key: Optional[Union[UUID, SecretStr]] = None


# API results


class TenantResult(APIResult):
    tenant: TenantModel


class TenantCreateResult(TenantResult):
    tenant: TenantCreateResultModel


class TenantUpdateResult(TenantResult):
    tenant: TenantUpdateResultModel


class TenantResultCollection(APIResult):
    tenants: List[TenantModel]
