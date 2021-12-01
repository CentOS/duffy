from sqlalchemy import Column, Integer, UnicodeText

from .. import Base
from ..util import CreatableMixin, RetirableMixin


class Project(Base, CreatableMixin, RetirableMixin):
    __tablename__ = "projects"
    __mapper_args__ = {"eager_defaults": True}
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(UnicodeText, unique=True, nullable=False)
    ssh_key = Column(UnicodeText, nullable=False)
