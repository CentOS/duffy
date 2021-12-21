from sqlalchemy import Column, ForeignKey, Index, Integer, Text, UnicodeText
from sqlalchemy.orm import relationship

from .. import Base
from ..types import NodeState, NodeType, VirtualNodeFlavour
from ..util import CreatableMixin, RetirableMixin
from .session import Session


class Node(Base, CreatableMixin, RetirableMixin):
    __tablename__ = "nodes"
    __mapper_args__ = {
        "polymorphic_on": "type",
        "with_polymorphic": "*",
        "eager_defaults": True,
    }
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
    type = Column(NodeType.db_type(), nullable=False)
    hostname = Column(Text, nullable=False)
    ipaddr = Column(Text, nullable=False)
    state = Column(
        NodeState.db_type(),
        nullable=False,
        default=NodeState.ready,
        server_default=NodeState.ready.value,
    )
    comment = Column(UnicodeText, nullable=True)

    # currently configured distro type & version
    distro_type = Column(UnicodeText, nullable=True)
    distro_version = Column(UnicodeText, nullable=True)


class VirtualNode(Node):
    __tablename__ = "virtualnodes"
    __mapper_args__ = {"polymorphic_identity": NodeType.virtual}
    id = Column(Integer, ForeignKey(Node.id), primary_key=True, nullable=False)
    flavour = Column(VirtualNodeFlavour.db_type(), nullable=False)


class OpenNebulaNode(VirtualNode):
    __tablename__ = "opennebulanodes"
    __mapper_args__ = {"polymorphic_identity": NodeType.opennebula}
    id = Column(Integer, ForeignKey(VirtualNode.id), primary_key=True, nullable=False)


class Chassis(Base, CreatableMixin, RetirableMixin):
    __tablename__ = "chassis"
    __mapper_args__ = {"eager_defaults": True}
    id = Column(Integer, primary_key=True)
    name = Column(UnicodeText, nullable=False, unique=True)
    description = Column(UnicodeText, nullable=True)


class PhysicalNode(Node):
    __tablename__ = "physicalnodes"
    __mapper_args__ = {"polymorphic_identity": NodeType.physical}
    id = Column(Integer, ForeignKey(Node.id), primary_key=True, nullable=False)
    chassis_id = Column(Integer, ForeignKey(Chassis.id), nullable=True)
    chassis = relationship(Chassis)


class SeaMicroNode(PhysicalNode):
    __tablename__ = "seamicronodes"
    __mapper_args__ = {"polymorphic_identity": NodeType.seamicro}
    id = Column(Integer, ForeignKey(PhysicalNode.id), primary_key=True, nullable=False)


class SessionNode(Base):
    __tablename__ = "sessions_nodes"
    session_id = Column(Integer, ForeignKey(Session.id), primary_key=True, nullable=False)
    session = relationship(Session)
    node_id = Column(Integer, ForeignKey(Node.id), primary_key=True, nullable=False)
    node = relationship(Node)
    distro_type = Column(UnicodeText, nullable=False)
    distro_version = Column(Text, nullable=False)
