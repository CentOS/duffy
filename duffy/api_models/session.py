from abc import ABC
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, conint

from ..database.types import NodeState
from .common import APIResult, CreatableMixin, RetirableMixin
from .node import NodeBase
from .tenant import TenantModel

# nodes spec model


class NodesSpec(BaseModel):
    quantity: conint(ge=1)
    pool: str


# nodes in sessions model


class SessionNodeModel(NodeBase):
    id: int
    state: Optional[NodeState]


# session model


class SessionBase(BaseModel, ABC):
    class Config:
        orm_mode = True


class SessionCreateModel(SessionBase):
    tenant_id: Optional[int]
    nodes_specs: List[NodesSpec]


class SessionUpdateModel(SessionBase):
    active: bool


class SessionModel(SessionBase, CreatableMixin, RetirableMixin):
    id: int
    tenant: TenantModel
    data: Dict[str, Any]
    nodes: List[SessionNodeModel]


# API results


class SessionResult(APIResult):
    session: SessionModel


class SessionResultCollection(APIResult):
    sessions: List[SessionModel]
