from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy.orm import relationship

from .. import Base
from ..util import CreatableMixin, RetirableMixin
from .project import Project


class Session(Base, CreatableMixin, RetirableMixin):
    __tablename__ = "sessions"
    __mapper_args__ = {"eager_defaults": True}
    id = Column(Integer, primary_key=True, nullable=False)
    project_id = Column(Integer, ForeignKey(Project.id), nullable=False)
    project = relationship(Project, backref="sessions")
