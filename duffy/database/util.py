import enum

from sqlalchemy.types import Enum, SchemaType, TypeDecorator

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
        return "ck_" + camel_case_to_lower_with_underscores(clsname)

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
