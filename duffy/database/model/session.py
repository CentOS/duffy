from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy.orm import relationship

from .. import Base
from ..util import CreatableMixin, RetirableMixin
from .tenant import Tenant


class Session(Base, CreatableMixin, RetirableMixin):
    __tablename__ = "sessions"
    __mapper_args__ = {"eager_defaults": True}
    id = Column(Integer, primary_key=True, nullable=False)
    tenant_id = Column(Integer, ForeignKey(Tenant.id), nullable=False)
    tenant = relationship(Tenant, backref="sessions")
