from sqlalchemy import Column, ForeignKey, Integer, Table, Text, UnicodeText
from sqlalchemy.orm import relationship

from . import Base
from .util import DeclEnum


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, nullable=False)
    ssh_key = Column(Text, nullable=False)


users_projects_table = Table(
    "users_projects",
    Base.metadata,
    Column("user_id", ForeignKey("users.id"), nullable=False),
    Column("project_id", ForeignKey("projects.id"), nullable=False),
)


class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(UnicodeText, unique=True, nullable=False)
    users = relationship(User, secondary=users_projects_table, backref="projects")


class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True, nullable=False)
    project_id = Column(Integer, ForeignKey(Project.id), nullable=False)
    project = relationship(Project, backref="sessions")


class NodeState(DeclEnum):
    ready = "ready"
    active = "active"
    contextualizing = "contextualizing"
    deployed = "deployed"
    deprovisioning = "deprovisioning"
    done = "done"
    failing = "failing"
    failed = "failed"


class Node(Base):
    __tablename__ = "nodes"
    __mapper_args__ = {"polymorphic_on": "type", "with_polymorphic": "*"}
    id = Column(Integer, primary_key=True, nullable=False)
    type = Column(Text, nullable=False)
    hostname = Column(Text, nullable=False)
    ipaddr = Column(Text, nullable=False)
    state = Column(NodeState.db_type(), nullable=False)
    comment = Column(UnicodeText, nullable=True)


class VirtualNodeFlavour(DeclEnum):
    small = "small"
    medium = "medium"
    large = "large"


class VirtualNode(Node):
    __tablename__ = "virtualnodes"
    __mapper_args__ = {"polymorphic_identity": "virtual"}
    id = Column(Integer, ForeignKey(Node.id), primary_key=True, nullable=False)
    flavour = Column(VirtualNodeFlavour.db_type(), nullable=False)


class Chassis(Base):
    __tablename__ = "chassis"
    id = Column(Integer, primary_key=True)
    name = Column(UnicodeText, nullable=False, unique=True)
    description = Column(UnicodeText, nullable=True)


class PhysicalNode(Node):
    __tablename__ = "physicalnodes"
    __mapper_args__ = {"polymorphic_identity": "physical"}
    id = Column(Integer, ForeignKey(Node.id), primary_key=True, nullable=False)
    chassis_id = Column(Integer, ForeignKey(Chassis.id), nullable=False)
    chassis = relationship(Chassis)


class SessionNode(Base):
    __tablename__ = "sessions_nodes"
    session_id = Column(Integer, ForeignKey(Session.id), primary_key=True, nullable=False)
    session = relationship(Session)
    node_id = Column(Integer, ForeignKey(Node.id), primary_key=True, nullable=False)
    node = relationship(Node)
    distro_type = Column(UnicodeText, nullable=False)
    distro_version = Column(Text, nullable=False)
