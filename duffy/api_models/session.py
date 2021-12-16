from abc import ABC
from typing import List, Literal, Union

from pydantic import BaseModel

from ..database.types import NodeType, VirtualNodeFlavour
from .common import APIResult, CreatableMixin, RetirableMixin
from .node import NodeBase
from .tenant import TenantModel

# nodes in sessions model


class SessionNodeBase(NodeBase, ABC):
    distro_type: str
    distro_version: str

    class Config:
        orm_mode = True


class PhysicalSessionNodeModel(SessionNodeBase):
    type: Literal[NodeType.seamicro]


class VirtualSessionNodeModel(SessionNodeBase):
    type: Literal[NodeType.opennebula]
    flavour: VirtualNodeFlavour


SessionNodeModel = Union[PhysicalSessionNodeModel, VirtualSessionNodeModel]


# session model


class SessionBase(BaseModel, ABC):
    class Config:
        orm_mode = True


class SessionCreateModel(SessionBase):
    tenant_id: int


class SessionModel(SessionBase, CreatableMixin, RetirableMixin):
    id: int
    tenant: TenantModel
    nodes: List[SessionNodeModel]


# API results


class SessionResult(APIResult):
    session: SessionModel


class SessionResultCollection(APIResult):
    sessions: List[SessionModel]
