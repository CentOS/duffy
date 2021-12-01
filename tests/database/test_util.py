import datetime as dt
from unittest import mock

import pytest
from sqlalchemy import Column, DateTime, Integer, select
from sqlalchemy.exc import StatementError

from duffy.database import Base, SyncDBSession
from duffy.database.util import CreatableMixin, DeclEnum, RetirableMixin, TZDateTime

from ..util import noop_context


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


class TestTZDateTime:
    @mock.patch("duffy.database.util.TypeDecorator.__init__")
    def test_init(self, type_decorator_init):
        """Test that `timezone` is set by default."""
        obj = TZDateTime()

        assert obj.impl is DateTime
        type_decorator_init.assert_called_with(timezone=True)

    @pytest.mark.parametrize("testcase", ("with tz", "without tz", "none"))
    def test_process_bind_param(self, testcase):
        """Test the process_bind_param() method."""
        obj = TZDateTime()

        expectation = noop_context()

        if testcase == "none":
            now = None
        else:
            now = dt.datetime.utcnow()
            if testcase == "with tz":
                now = now.replace(tzinfo=dt.timezone.utc)
            elif testcase == "without tz":
                expectation = pytest.raises(TypeError)

        with expectation:
            result = obj.process_bind_param(now, dialect=None)

        if testcase == "with tz":
            assert result.tzinfo is None
            assert now.replace(tzinfo=None) == result
        elif testcase == "none":
            assert result is None

    @pytest.mark.parametrize("testcase", ("with tz", "without tz", "none"))
    def test_process_result_value(self, testcase):
        """Test the process_result_value() method."""
        obj = TZDateTime()

        if testcase == "none":
            now = None
        else:
            now = dt.datetime.utcnow()
            if testcase == "with tz":
                now = now.replace(tzinfo=dt.timezone.utc)

        result = obj.process_result_value(now, dialect=None)

        if testcase == "none":
            assert result is None
        else:
            assert result.tzinfo is dt.timezone.utc
            assert now.replace(tzinfo=dt.timezone.utc) == result


class Creatable(Base, CreatableMixin):
    __tablename__ = "creatables"

    id = Column(Integer, primary_key=True)


class Retirable(Base, RetirableMixin):
    __tablename__ = "retirables"

    id = Column(Integer, primary_key=True)


@pytest.mark.usefixtures("db_sync_model_initialized")
class TestCreatableMixin:
    def test_created_at_gets_set(self):
        """Test that created_at gets set."""
        now = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)
        obj = Creatable()
        SyncDBSession.add(obj)
        SyncDBSession.flush()
        assert obj.created_at - now < dt.timedelta(minutes=1)


@pytest.mark.usefixtures("db_sync_model_initialized")
class TestRetirableMixin:
    def test_getting_active(self):
        obj = Retirable()
        assert obj.active
        SyncDBSession.add(obj)
        SyncDBSession.flush()
        assert obj.retired_at is None

    @pytest.mark.parametrize(
        "value, previously_active",
        (
            (True, True),
            (False, True),
            (False, False),
        ),
    )
    def test_setting_active(self, value, previously_active):
        now = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)
        obj = Retirable()
        if not previously_active:
            inthepast = dt.datetime(2020, 1, 1, 10, 0).replace(tzinfo=dt.timezone.utc)
            obj.retired_at = inthepast
        SyncDBSession.add(obj)
        SyncDBSession.flush()
        obj.active = value
        SyncDBSession.flush()
        if value:
            assert obj.retired_at is None
        else:
            if previously_active:
                assert obj.retired_at - now < dt.timedelta(minutes=1)
            else:
                assert obj.retired_at is inthepast

    @pytest.mark.parametrize("value", (True, False))
    def test_selecting_on_active(self, value):
        objs = {
            True: Retirable(),
            False: Retirable(active=False),
        }

        for obj in objs.values():
            SyncDBSession.add(obj)
        SyncDBSession.flush()

        queried_obj = SyncDBSession.execute(select(Retirable).filter_by(active=value)).scalar_one()

        assert queried_obj is objs[value]
