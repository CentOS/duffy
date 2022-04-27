import datetime as dt

from sqlalchemy import JSON, Boolean, Column, ForeignKey, Index, Integer, Text, UnicodeText, and_
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import relationship

from ...api_models import SessionNodeModel
from .. import Base
from ..types import NodeState
from ..util import CreatableMixin, RetirableMixin
from .session import Session


class Node(Base, CreatableMixin, RetirableMixin):
    index_uniqueness_clause = and_(
        Column("retired_at") == None,  # noqa: E711
        Column("state") != "provisioning",
    )

    __tablename__ = "nodes"
    __table_args__ = (
        Index(
            "active_hostname_index",
            "hostname",
            unique=True,
            sqlite_where=index_uniqueness_clause,
            postgresql_where=index_uniqueness_clause,
        ),
        Index(
            "active_ipaddr_index",
            "ipaddr",
            unique=True,
            sqlite_where=index_uniqueness_clause,
            postgresql_where=index_uniqueness_clause,
        ),
    )

    id = Column(Integer, primary_key=True, nullable=False)
    hostname = Column(Text, nullable=True)
    ipaddr = Column(Text, nullable=True)
    state = Column(
        NodeState.db_type(),
        nullable=False,
        default=NodeState.unused,
        server_default=NodeState.unused.value,
    )
    comment = Column(UnicodeText, nullable=True)

    pool = Column(UnicodeText, nullable=True, index=True)

    reusable = Column(Boolean, nullable=False, default=False, server_default="FALSE")

    # Careful, MutableDict only detects changes to the top level of dict key-values!
    data = Column(
        MutableDict.as_mutable(JSON), nullable=False, default=lambda: {}, server_default="{}"
    )

    def fail(self, detail: str):
        """Set the state of a node to failed with details"""
        self.state = NodeState.failed
        self.data["error"] = {"failed_at": dt.datetime.utcnow().isoformat(), "detail": detail}


class SessionNode(Base):
    __tablename__ = "sessions_nodes"
    session_id = Column(Integer, ForeignKey(Session.id), primary_key=True, nullable=False)
    session = relationship(Session, back_populates="session_nodes")
    node_id = Column(Integer, ForeignKey(Node.id), primary_key=True, nullable=False)
    node = relationship(Node)

    pool = Column(UnicodeText, nullable=False, index=True)

    # Careful, MutableDict only detects changes to the top level of dict key-values!
    data = Column(
        MutableDict.as_mutable(JSON), nullable=False, default=lambda: {}, server_default="{}"
    )

    @property
    def pydantic_view(self) -> SessionNodeModel:
        args = {
            "id": self.node.id,
            "hostname": self.node.hostname,
            "ipaddr": self.node.ipaddr,
            "pool": self.node.pool,
            "reusable": self.node.reusable,
            "data": self.node.data,
        }

        if self.session.active:
            args["state"] = self.node.state

        return SessionNodeModel(**args)
