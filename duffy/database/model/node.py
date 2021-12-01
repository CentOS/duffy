from sqlalchemy import Column, ForeignKey, Index, Integer, Text, UnicodeText
from sqlalchemy.orm import relationship

from .. import Base
from ..util import CreatableMixin, DeclEnum, RetirableMixin
from .session import Session


class NodeType(str, DeclEnum):
    virtual = "virtual"
    physical = "physical"
    opennebula = "opennebula"
    seamicro = "seamicro"


class NodeState(str, DeclEnum):
    ready = "ready"
    active = "active"
    contextualizing = "contextualizing"
    deployed = "deployed"
    deprovisioning = "deprovisioning"
    done = "done"
    failing = "failing"
    failed = "failed"


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
    state = Column(NodeState.db_type(), nullable=False, default=NodeState.ready)
    comment = Column(UnicodeText, nullable=True)


class VirtualNodeFlavour(str, DeclEnum):
    small = "small"
    medium = "medium"
    large = "large"


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
