from sqlalchemy import Column, Integer, UnicodeText

from .. import Base


class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(UnicodeText, unique=True, nullable=False)
    ssh_key = Column(UnicodeText, nullable=False)
