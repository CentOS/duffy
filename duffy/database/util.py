import datetime as dt
import enum

from sqlalchemy import Column
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql.expression import FunctionElement
from sqlalchemy.types import DateTime, Enum, SchemaType, TypeDecorator

from ..util import camel_case_to_lower_with_underscores

# adapted from http://techspot.zzzeek.org/2011/01/14/the-enum-recipe
# changes:
# - Python 3.x only
# - uses __init_subclass__() rather than a custom # metaclass
# - improves auto-generated db-side type name
# - is derived from enum.Enum to be usable in pydantic models, therefore doesn't use EnumSymbol


class DeclEnum(enum.Enum):
    """A declarative enumeration type for SQLAlchemy models."""

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        try:
            del cls._db_type
        except AttributeError:
            pass

        try:
            del cls._literal_values
        except AttributeError:
            pass

    @classmethod
    def db_type(cls):
        if not hasattr(cls, "_db_type"):
            cls._db_type = DeclEnumType(cls)
        else:
            pass  # pragma: no cover
        return cls._db_type

    @classmethod
    def from_string(cls, value):
        try:
            return cls.__members__[value]
        except KeyError:
            raise ValueError(f"Invalid value for {cls.__name__!r}: {value!r}")

    @classmethod
    def values(cls):
        return cls.__members__.keys()


class DeclEnumType(SchemaType, TypeDecorator):
    """A persistable column type tied to a DeclEnum type."""

    cache_ok = True

    def __init__(self, enum):
        self.enum = enum
        self.impl = Enum(*enum.values(), name=self._type_name(enum.__name__))

    @classmethod
    def _type_name(cls, clsname):
        return camel_case_to_lower_with_underscores(clsname) + "_enum"

    def _set_table(self, table, column):
        self.impl._set_table(table, column)

    def copy(self):
        return DeclEnumType(self.enum)

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, str):
            value = self.process_result_value(value, dialect)
        return value.value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return self.enum.from_string(value.strip())


# The TZDateTime class is adapted from
# https://docs.sqlalchemy.org/en/14/core/custom_types.html#store-timezone-aware-timestamps-as-timezone-naive-utc
#
# Changes: Is aware of time zones on the database side by default ("explicit better than implicit")


class TZDateTime(TypeDecorator):
    impl = DateTime
    cache_ok = True

    def __init__(self, timezone=True, *args, **kwargs):
        super().__init__(timezone=timezone, *args, **kwargs)

    def process_bind_param(self, value, dialect):
        if value is not None:
            if not value.tzinfo:
                raise TypeError("tzinfo is required")
            value = value.astimezone(dt.timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = value.replace(tzinfo=dt.timezone.utc)
        return value


class utcnow(FunctionElement):
    """Current timestamp in UTC for SQL expressions."""

    type = DateTime


@compiles(utcnow, "postgresql")
def _postgresql_utcnow(element, compiler, **kwargs):
    return "(NOW() AT TIME ZONE 'utc')"  # pragma: no cover (unit tests use sqlite)


@compiles(utcnow, "sqlite")
def _sqlite_utcnow(element, compiler, **kwargs):
    return "CURRENT_TIMESTAMP"


# Mixins


class CreatableMixin:
    """An SQLAlchemy mixin to store the time when a thing was created.

    With an asynchronous session this may need to eagerly load the
    default created_at value upon INSERT, e.g. when the attribute is
    accessed on validation of a Pydantic model. This can be achieved by
    setting __mapper_args__ = {"eager_defaults": True}."""

    created_at = Column(TZDateTime, nullable=False, server_default=utcnow())


class RetirableMixin:
    """An SQLAlchemy mixin to manage active state and retirement."""

    retired_at = Column(TZDateTime, nullable=True)

    @hybrid_property
    def active(self) -> bool:
        return self.retired_at is None

    @active.setter
    def active(self, value: bool):
        if not value:
            # only set retired_at if previously unset
            if not self.retired_at:
                self.retired_at = utcnow()
        else:
            self.retired_at = None

    @active.expression
    def active(cls):
        return cls.retired_at == None  # noqa: E711
