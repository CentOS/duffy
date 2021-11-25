from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy.orm import relationship

from .. import Base
from .project import Project


class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True, nullable=False)
    project_id = Column(Integer, ForeignKey(Project.id), nullable=False)
    project = relationship(Project, backref="sessions")
