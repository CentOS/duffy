import uuid

import bcrypt
from sqlalchemy import Boolean, Column, Integer, Text, UnicodeText, text
from sqlalchemy.ext.hybrid import hybrid_property

from .. import Base
from ..util import CreatableMixin, RetirableMixin


class Tenant(Base, CreatableMixin, RetirableMixin):
    __tablename__ = "tenants"
    __mapper_args__ = {"eager_defaults": True}
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(UnicodeText, unique=True, nullable=False)
    is_admin = Column(Boolean, nullable=False, default=False, server_default=text("FALSE"))
    ssh_key = Column(UnicodeText, nullable=False)
    _api_key = Column("api_key", Text, nullable=False)

    @hybrid_property
    def api_key(self):
        return self._api_key

    @api_key.setter
    def api_key(self, key: uuid.UUID):
        salt = bcrypt.gensalt()
        hashed_key = bcrypt.hashpw(str(key).encode("ascii"), salt)
        self._api_key = hashed_key.decode("ascii")

    def validate_api_key(self, key: uuid.UUID):
        return bcrypt.checkpw(str(key).encode("ascii"), self._api_key.encode("ascii"))
