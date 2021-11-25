import pytest
from sqlalchemy import Column, Integer
from sqlalchemy.exc import StatementError

from duffy.database import Base, SyncDBSession
from duffy.database.util import DeclEnum


class UselessEnum(DeclEnum):
    enval1 = "Enum value 1"
    enval2 = "Enum value 2"


class UselessThing(Base):
    __tablename__ = "useless_things"

    id = Column(Integer, primary_key=True)

    useless_enum = Column(UselessEnum.db_type(), nullable=True)


@pytest.mark.usefixtures("db_sync_model_initialized")
class TestEnum:
    def test_db_type_cached(self):
        """Test that the result of cls.db_type() is cached and reused."""
        # It needs to exist already because of its use in UselessThing above.
        assert UselessEnum._db_type is UselessEnum.db_type()

    def test_set_enum(self):
        """Test that an enum attribute can be set."""
        obj = UselessThing(useless_enum=UselessEnum.enval1)
        SyncDBSession.add(obj)
        SyncDBSession.flush()

    def test_set_enum_from_string(self):
        """Test that an attribute can be set from a string."""
        obj = UselessThing(useless_enum="enval2")
        SyncDBSession.add(obj)
        SyncDBSession.flush()

    def test_set_enum_none(self):
        """Test that an enum attribute can be set to None and retrieved."""
        obj = UselessThing(useless_enum=None)
        SyncDBSession.add(obj)
        SyncDBSession.flush()

        SyncDBSession.expire_all()
        obj = SyncDBSession.query(UselessThing).filter_by(useless_enum=None).one()
        assert obj.useless_enum is None

    def test_set_invalid_enum_from_string(self):
        """Test that setting an invalid enum string fails."""
        obj = UselessThing(useless_enum="enval3")
        SyncDBSession.add(obj)
        with pytest.raises(StatementError) as excinfo:
            SyncDBSession.flush()
        assert excinfo.type == StatementError
        assert "enval3" in str(excinfo.value)


class TestDeclEnumType:
    # No tests specific to `DeclEnumType`, it's tested in conjunction with its DeclEnum parent.
    pass
