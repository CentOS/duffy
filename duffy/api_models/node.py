from abc import ABC
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, IPvAnyAddress

from ..database.types import NodeState
from .common import APIResult, CreatableMixin, RetirableMixin

# abstract node


class NodeBase(BaseModel, ABC):
    hostname: Optional[str]
    ipaddr: Optional[IPvAnyAddress]
    comment: Optional[str]

    pool: Optional[str]
    reusable: bool
    data: Dict[str, Any]

    class Config:
        orm_mode = True


class NodeCreateModel(NodeBase):
    reusable: bool = False
    data: Dict[str, Any] = {}


class NodeModel(NodeBase, CreatableMixin, RetirableMixin):
    id: int
    state: NodeState


# API results


class NodeResult(APIResult):
    node: NodeModel


class NodeResultCollection(APIResult):
    nodes: List[NodeModel]
