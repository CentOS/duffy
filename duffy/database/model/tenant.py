import uuid
from functools import lru_cache

import bcrypt
from sqlalchemy import Boolean, Column, Integer, Interval, Text, UnicodeText, text
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql import case

from ...configuration import config
from ...configuration.validation import DefaultsModel
from .. import Base
from ..util import CreatableMixin, RetirableMixin


@lru_cache
def _defaults_config():
    return DefaultsModel(**config["defaults"])


class Tenant(Base, CreatableMixin, RetirableMixin):
    __tablename__ = "tenants"
    __mapper_args__ = {"eager_defaults": True}
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(UnicodeText, unique=True, nullable=False)
    is_admin = Column(Boolean, nullable=False, default=False, server_default=text("FALSE"))
    ssh_key = Column(UnicodeText, nullable=False)
    _api_key = Column("api_key", Text, nullable=False)
    node_quota = Column(Integer, nullable=True)
    session_lifetime = Column(Interval, nullable=True)
    session_lifetime_max = Column(Interval, nullable=True)

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

    @hybrid_property
    def effective_node_quota(self):
        if self.node_quota is not None:
            return self.node_quota

        return config["defaults"]["node-quota"]

    @effective_node_quota.expression
    def effective_node_quota(cls):
        return case(
            [(cls.node_quota != None, cls.node_quota)],  # noqa: E711
            else_=_defaults_config().node_quota,
        )

    @hybrid_property
    def effective_session_lifetime(self):
        if self.session_lifetime is not None:
            return self.session_lifetime

        return _defaults_config().session_lifetime

    @effective_session_lifetime.expression
    def effective_session_lifetime(cls):
        return case(
            [(cls.session_lifetime != None, cls.session_lifetime)],  # noqa: E711
            else_=_defaults_config().session_lifetime,
        )

    @hybrid_property
    def effective_session_lifetime_max(self):
        if self.session_lifetime_max is not None:
            return self.session_lifetime_max

        return _defaults_config().session_lifetime_max

    @effective_session_lifetime_max.expression
    def effective_session_lifetime_max(cls):
        return case(
            [(cls.session_lifetime_max != None, cls.session_lifetime_max)],  # noqa: E711
            else_=_defaults_config().session_lifetime_max,
        )
