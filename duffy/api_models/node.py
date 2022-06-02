from abc import ABC
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, IPvAnyAddress

try:
    from ..database.types import NodeState
except ImportError:  # pragma: no cover
    NodeState = str
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
    hostname: str
    ipaddr: IPvAnyAddress
    reusable: bool = True
    data: Dict[str, Any] = {}


class NodeModel(NodeBase, CreatableMixin, RetirableMixin):
    id: int
    state: NodeState


# API results


class NodeResult(APIResult):
    node: NodeModel


class NodeResultCollection(APIResult):
    nodes: List[NodeModel]
