from abc import ABC
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import Annotated

try:
    from ..database.types import NodeState
except ImportError:  # pragma: no cover
    NodeState = str
from ..misc import APITimeDelta
from .common import APIResult, CreatableMixin, RetirableMixin
from .node import NodeBase
from .tenant import TenantModel

# nodes spec model


class NodesSpec(BaseModel):
    quantity: Annotated[int, Field(ge=1)]
    pool: str


# nodes in sessions model


class SessionNodeModel(NodeBase):
    id: int
    state: Optional[NodeState] = None


# session model


class SessionBase(BaseModel, ABC):
    model_config = ConfigDict(from_attributes=True)


class SessionCreateModel(SessionBase):
    tenant_id: Optional[int] = None
    nodes_specs: List[NodesSpec]


class SessionUpdateModel(SessionBase):
    active: Optional[bool] = None
    expires_at: Optional[Union[datetime, APITimeDelta]] = None


class SessionModel(SessionBase, CreatableMixin, RetirableMixin):
    id: int
    expires_at: Optional[datetime] = None
    tenant: TenantModel
    data: Dict[str, Any]
    nodes: List[SessionNodeModel]


# API results


class SessionResult(APIResult):
    session: SessionModel


class SessionResultCollection(APIResult):
    sessions: List[SessionModel]
