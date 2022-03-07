from typing import List

from sqlalchemy import JSON, Column, ForeignKey, Integer
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import relationship

from ...api_models import SessionNodeModel
from .. import Base
from ..util import CreatableMixin, RetirableMixin, TZDateTime
from .tenant import Tenant


class Session(Base, CreatableMixin, RetirableMixin):
    __tablename__ = "sessions"
    __mapper_args__ = {"eager_defaults": True}
    id = Column(Integer, primary_key=True, nullable=False)
    tenant_id = Column(Integer, ForeignKey(Tenant.id), nullable=False)
    tenant = relationship(Tenant, backref="sessions")

    expires_at = Column(TZDateTime, nullable=True)

    data = Column(
        MutableDict.as_mutable(JSON), nullable=False, default=lambda: {}, server_default="{}"
    )

    session_nodes = relationship("SessionNode", back_populates="session")

    @property
    def nodes(self) -> List[SessionNodeModel]:
        """Combine info from related session_nodes and their nodes."""
        return [sn.pydantic_view for sn in self.session_nodes]
