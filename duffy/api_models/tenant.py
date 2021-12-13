from abc import ABC
from typing import List, Optional

from pydantic import UUID4, BaseModel

from .common import APIResult, CreatableMixin, RetirableMixin

# tenant model


class TenantBase(BaseModel, ABC):
    name: str
    is_admin: Optional[bool]
    ssh_key: str

    class Config:
        orm_mode = True


class TenantCreateModel(TenantBase):
    api_key: UUID4


class TenantModel(TenantBase, CreatableMixin, RetirableMixin):
    id: int


# API results


class TenantResult(APIResult):
    tenant: TenantModel


class TenantResultCollection(APIResult):
    tenants: List[TenantModel]
