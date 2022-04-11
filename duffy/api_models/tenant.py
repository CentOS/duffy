from abc import ABC
from typing import List, Literal, Optional, Union

from pydantic import UUID4, BaseModel, SecretStr, root_validator

from .common import APIResult, CreatableMixin, RetirableMixin

# tenant model


class TenantBase(BaseModel, ABC):
    name: str
    is_admin: Optional[bool]
    ssh_key: SecretStr

    class Config:
        orm_mode = True


class TenantCreateModel(TenantBase):
    pass


class TenantRetireModel(BaseModel):
    active: bool


class TenantUpdateModel(BaseModel):
    ssh_key: Optional[SecretStr]
    api_key: Optional[Union[UUID4, Literal["reset"]]]

    @root_validator
    def check_ssh_key_or_api_key(cls, values):
        if not values.get("ssh_key") and not values.get("api_key"):
            raise ValueError("either ssh_key or api_key is required")
        return values


class TenantModel(TenantBase, CreatableMixin, RetirableMixin):
    id: int


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
