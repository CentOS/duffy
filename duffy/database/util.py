from sqlalchemy.types import Enum, SchemaType, TypeDecorator

from ..util import camel_case_to_lower_with_underscores

# adapted from http://techspot.zzzeek.org/2011/01/14/the-enum-recipe
# changes: Python 3.x only, use __init_subclass__() rather than a custom
# metaclass, improve auto-generated db-side type name


class EnumSymbol:
    """A fixed symbol tied to a parent DeclEnum class."""

    def __init__(self, cls, name, value, description):
        self.cls = cls
        self.name = name
        self.value = value
        self.description = description

    def __lt__(self, other):
        return self.value < other.value

    def __reduce__(self):
        """Allow unpickling to return the symbol
        linked to the DeclEnum class."""
        return getattr, (self.cls, self.name)

    def __iter__(self):
        return iter([self.value, self.description])

    def __repr__(self):
        return f"<{self.name}>"


class DeclEnum:
    """A declarative enumeration type for SQLAlchemy models."""

    _reg = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        cls._reg = reg = cls._reg.copy()

        for k in dir(cls):
            if k.startswith("__"):
                continue
            v = getattr(cls, k)
            sym = None
            if isinstance(v, tuple):
                sym = EnumSymbol(cls, k, *v)
            elif isinstance(v, str):
                sym = EnumSymbol(cls, k, k, v)
            if sym:
                reg[sym.value] = sym
                setattr(cls, k, sym)

        try:
            del cls._db_type
        except AttributeError:
            pass

    @classmethod
    def db_type(cls):
        if not hasattr(cls, "_db_type"):
            cls._db_type = DeclEnumType(cls)
        return cls._db_type

    @classmethod
    def from_string(cls, value):
        try:
            return cls._reg[value]
        except KeyError:
            raise ValueError(f"Invalid value for {cls.__name__!r}: {value!r}")

    @classmethod
    def values(cls):
        return cls._reg.keys()


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
