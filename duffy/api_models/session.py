from abc import ABC
from typing import List

from pydantic import BaseModel

from .common import APIResult, CreatableMixin, RetirableMixin
from .tenant import TenantModel

# session model


class SessionBase(BaseModel, ABC):
    class Config:
        orm_mode = True


class SessionCreateModel(SessionBase):
    tenant_id: int


class SessionModel(SessionBase, CreatableMixin, RetirableMixin):
    id: int
    tenant: TenantModel


# API results


class SessionResult(APIResult):
    session: SessionModel


class SessionResultCollection(APIResult):
    sessions: List[SessionModel]
