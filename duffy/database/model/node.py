from sqlalchemy import JSON, Boolean, Column, ForeignKey, Index, Integer, Text, UnicodeText
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import relationship

from ...api_models import SessionNodeModel
from .. import Base
from ..types import NodeState
from ..util import CreatableMixin, RetirableMixin
from .session import Session


class Node(Base, CreatableMixin, RetirableMixin):
    __tablename__ = "nodes"
    __table_args__ = (
        Index(
            "active_hostname_index",
            "hostname",
            unique=True,
            sqlite_where=Column("retired_at") == None,  # noqa: E711
            postgresql_where=Column("retired_at") == None,  # noqa: E711
        ),
        Index(
            "active_ipaddr_index",
            "ipaddr",
            unique=True,
            sqlite_where=Column("retired_at") == None,  # noqa: E711
            postgresql_where=Column("retired_at") == None,  # noqa: E711
        ),
    )

    id = Column(Integer, primary_key=True, nullable=False)
    hostname = Column(Text, nullable=False)
    ipaddr = Column(Text, nullable=False)
    state = Column(
        NodeState.db_type(),
        nullable=False,
        default=NodeState.ready,
        server_default=NodeState.ready.value,
    )
    comment = Column(UnicodeText, nullable=True)

    pool = Column(UnicodeText, nullable=True, index=True)

    reusable = Column(Boolean, nullable=False, default=False, server_default="FALSE")

    # Careful, MutableDict only detects changes to the top level of dict key-values!
    data = Column(
        MutableDict.as_mutable(JSON), nullable=False, default=lambda: {}, server_default="{}"
    )


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
            "hostname": self.node.hostname,
            "ipaddr": self.node.ipaddr,
            "pool": self.node.pool,
            "reusable": self.node.reusable,
            "data": self.node.data,
        }

        if self.session.active:
            args["state"] = self.node.state

        return SessionNodeModel(**args)
