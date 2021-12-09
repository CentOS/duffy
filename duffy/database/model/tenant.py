from sqlalchemy import Boolean, Column, Integer, UnicodeText, text

from .. import Base
from ..util import CreatableMixin, RetirableMixin


class Tenant(Base, CreatableMixin, RetirableMixin):
    __tablename__ = "tenants"
    __mapper_args__ = {"eager_defaults": True}
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(UnicodeText, unique=True, nullable=False)
    is_admin = Column(Boolean, nullable=False, default=False, server_default=text("FALSE"))
    ssh_key = Column(UnicodeText, nullable=False)
