from abc import ABC
from typing import List, Optional

from pydantic import UUID4, BaseModel, SecretStr

from .common import APIResult, CreatableMixin, RetirableMixin

# tenant model


class TenantBase(BaseModel, ABC):
    name: str
    is_admin: Optional[bool]
    ssh_key: SecretStr

    class Config:
        orm_mode = True


class TenantCreateModel(TenantBase):
    api_key: UUID4


class TenantModel(TenantBase, CreatableMixin, RetirableMixin):
    id: int


# API results


class TenantResult(APIResult):
    tenant: TenantModel


class TenantCreateResult(TenantResult):
    class Config:
        json_encoders = {SecretStr: lambda v: v.get_secret_value() if v else None}


class TenantResultCollection(APIResult):
    tenants: List[TenantModel]
