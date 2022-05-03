from abc import ABC
from typing import List, Literal, Optional, Union

from pydantic import UUID4, BaseModel, SecretStr, conint, root_validator

from .common import APIResult, CreatableMixin, RetirableMixin

# tenant model


class TenantBase(BaseModel, ABC):
    name: str
    is_admin: Optional[bool]
    ssh_key: SecretStr
    node_quota: Optional[conint(gt=0)]

    class Config:
        orm_mode = True


class TenantCreateModel(TenantBase):
    pass


class TenantRetireModel(BaseModel):
    active: bool


class TenantUpdateModel(BaseModel):
    ssh_key: Optional[SecretStr]
    api_key: Optional[Union[UUID4, Literal["reset"]]]
    node_quota: Optional[conint(gt=0)]

    @root_validator(pre=True)
    def check_any_field_set(cls, values):
        if not ("ssh_key" in values or "api_key" in values or "node_quota" in values):
            raise ValueError("either ssh_key, api_key or node_quota is required")
        return values


class TenantModel(TenantBase, CreatableMixin, RetirableMixin):
    id: int
    effective_node_quota: int


class TenantCreateResultModel(TenantModel):
    api_key: UUID4


class TenantUpdateResultModel(TenantModel):
    api_key: Optional[Union[UUID4, SecretStr]]


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
