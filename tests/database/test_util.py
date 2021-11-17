import pickle

import pytest
from sqlalchemy import Column, Integer
from sqlalchemy.exc import StatementError

from duffy.database import Base, SyncDBSession
from duffy.database.util import DeclEnum


class UselessEnum(DeclEnum):
    enval1 = "enval1", "Enum value 1"
    enval2 = "Enum value 2"


class UselessThing(Base):
    __tablename__ = "useless_things"

    id = Column(Integer, primary_key=True)

    useless_enum = Column(UselessEnum.db_type(), nullable=True)


class TestEnumSymbol:
    def test_pickle(self):
        """Test that EnumSymbol objects can be pickled and unpickled."""
        obj = UselessEnum.enval1
        pickled = pickle.loads(pickle.dumps(obj))

        assert obj == pickled

    def test_iter(self):
        """Test that EnumSymbol objects can be iterated."""
        obj = UselessEnum.enval1
        obj_iter = iter(obj)

        assert next(obj_iter) == obj.value
        assert next(obj_iter) == obj.description

        with pytest.raises(StopIteration):
            next(obj_iter)

    def test_db_type(self):
        """Test the db_type() method."""
        db_type = UselessEnum.db_type()

        assert db_type.enum == UselessEnum

    def test_comparator(self):
        """Test the __lt__() method."""
        assert UselessEnum.enval1 < UselessEnum.enval2


@pytest.mark.usefixtures("db_sync_model_initialized")
class TestEnum:
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
