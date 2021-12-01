from abc import ABC
from typing import List, Literal, Optional, Union

from pydantic import BaseModel, IPvAnyAddress

from ..database.model import NodeState, NodeType, VirtualNodeFlavour
from .chassis import ChassisModel
from .common import APIResult, CreatableMixin, RetirableMixin

# abstract node


class NodeBase(BaseModel, ABC):
    type: NodeType
    hostname: str
    ipaddr: IPvAnyAddress
    comment: Optional[str]

    class Config:
        orm_mode = True


class NodeCreateModel(NodeBase):
    pass


class NodeModel(NodeBase, CreatableMixin, RetirableMixin):
    id: int
    state: NodeState


# virtual nodes


class VirtualNodeBase(NodeBase):
    type: Literal[NodeType.virtual]
    flavour: VirtualNodeFlavour


class VirtualNodeCreateModel(VirtualNodeBase, NodeCreateModel):
    pass


class VirtualNodeModel(VirtualNodeBase, NodeModel):
    pass


class OpenNebulaNodeBase(VirtualNodeBase):
    type: Literal[NodeType.opennebula]


class OpenNebulaNodeCreateModel(OpenNebulaNodeBase, VirtualNodeCreateModel):
    pass


class OpenNebulaNodeModel(OpenNebulaNodeBase, VirtualNodeModel):
    pass


# physical nodes


class PhysicalNodeBase(NodeBase):
    type: Literal[NodeType.physical]


class PhysicalNodeCreateModel(PhysicalNodeBase, NodeCreateModel):
    pass


class PhysicalNodeModel(PhysicalNodeBase, NodeModel):
    pass


class SeaMicroNodeBase(PhysicalNodeBase):
    type: Literal[NodeType.seamicro]


class SeaMicroNodeCreateModel(SeaMicroNodeBase, NodeCreateModel):
    chassis_id: int


class SeaMicroNodeModel(SeaMicroNodeBase, NodeModel):
    chassis: ChassisModel


# concrete classes


concrete_node_models = Union[OpenNebulaNodeModel, SeaMicroNodeModel]
concrete_node_create_models = Union[OpenNebulaNodeCreateModel, SeaMicroNodeCreateModel]


# API results


class NodeResult(APIResult):
    node: concrete_node_models


class NodeResultCollection(APIResult):
    nodes: List[concrete_node_models]
