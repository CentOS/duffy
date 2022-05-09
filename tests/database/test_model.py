import datetime as dt
from typing import Any, Dict
from unittest import mock
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from duffy.database import model, types
from duffy.database.model.tenant import _defaults_config


class ModelTestBase:
    klass = None
    attrs = {}
    no_validate_attrs = ()

    def test_create_obj(self, db_sync_obj):
        pass

    def test_query_obj_sync(self, db_sync_obj, db_sync_session):
        result = db_sync_session.execute(select(self.klass))
        obj = result.scalar_one()
        for key, value in self.attrs.items():
            if key in self.no_validate_attrs:
                continue
            objvalue = getattr(obj, key)
            if isinstance(objvalue, (int, str)):
                assert objvalue == value
        for key, value in self._db_obj_get_dependencies().items():
            if key in self.no_validate_attrs:
                continue
            objvalue = getattr(obj, key)
            if isinstance(objvalue, (int, str)):
                assert objvalue == value

    async def test_query_obj_async(self, db_async_obj, db_async_session):
        # The selectinload() option tells SQLAlchemy to load related objects and lazy loading breaks
        # things here. See here for details:
        #
        # https://docs.sqlalchemy.org/en/14/orm/extensions/asyncio.html#preventing-implicit-io-when-using-asyncsession
        #
        # You can specify which relation you're interested in but because this code doesn't know
        # anything about the involved ORM class, we specify that we "want it all".
        result = await db_async_session.execute(select(self.klass).options(selectinload("*")))
        obj = result.scalar_one()
        for key, value in self.attrs.items():
            if key in self.no_validate_attrs:
                continue
            objvalue = getattr(obj, key)
            if isinstance(objvalue, (int, str)):
                assert objvalue == value
        for key, value in self._db_obj_get_dependencies().items():
            if key in self.no_validate_attrs:
                continue
            objvalue = getattr(obj, key)
            if isinstance(objvalue, (int, str)):
                assert objvalue == value

    def _db_obj_get_dependencies(self):
        """Get model test dependencies.

        Use this method to pull in other objects that need to be created
        for the tested model object to be built properly.
        """
        return {}


class TestTenant(ModelTestBase):
    klass = model.Tenant
    attrs = {
        "name": "My Fancy Tenant",
        "is_admin": False,
        "api_key": uuid4(),
        "ssh_key": "this is a public ssh key",
    }
    no_validate_attrs = ("api_key",)

    @pytest.mark.parametrize("wrong_key", (False, True))
    def test_validate_api_key(self, wrong_key, db_sync_obj):
        if wrong_key:
            assert not db_sync_obj.validate_api_key(uuid4())
        else:
            assert db_sync_obj.validate_api_key(self.attrs["api_key"])

    @pytest.mark.duffy_config(example_config=True, clear=True)
    @pytest.mark.parametrize("quota_set", (True, False))
    def test_effective_node_quota_instance(self, quota_set, db_sync_obj):
        with mock.patch.dict("duffy.database.model.tenant.config") as config:
            if quota_set:
                db_sync_obj.node_quota = 5
                assert db_sync_obj.effective_node_quota == 5
            else:
                config["defaults"]["node-quota"] = sentinel = object()
                assert db_sync_obj.effective_node_quota is sentinel

    @pytest.mark.duffy_config(example_config=True, clear=True)
    @pytest.mark.parametrize("quota_set", (True, False))
    def test_effective_node_quota_class(self, quota_set, db_sync_session, db_sync_obj):
        with mock.patch.dict("duffy.database.model.tenant.config") as config:
            if quota_set:
                db_sync_obj.node_quota = 5

                selected = db_sync_session.execute(
                    select(model.Tenant).filter(model.Tenant.effective_node_quota == 5)
                ).scalars()

                assert db_sync_obj in selected
            else:
                config["defaults"]["node-quota"] = 10

                selected = db_sync_session.execute(
                    select(model.Tenant).filter(model.Tenant.effective_node_quota == 10)
                ).scalars()

                assert db_sync_obj in selected

    @pytest.mark.duffy_config(example_config=True, clear=True)
    @pytest.mark.parametrize("item_set", (True, False))
    @pytest.mark.parametrize("item", ("session_lifetime", "session_lifetime_max"))
    def test_effective_session_lifetime_instance(self, item, item_set, db_sync_obj):
        with mock.patch.dict("duffy.database.model.tenant.config") as config:
            if item_set:
                setattr(db_sync_obj, item, dt.timedelta(hours=24))
                assert getattr(db_sync_obj, f"effective_{item}") == dt.timedelta(hours=24)
            else:
                _defaults_config.cache_clear()
                config["defaults"][item.replace("_", "-")] = "5h"
                assert getattr(db_sync_obj, f"effective_{item}") == dt.timedelta(hours=5)

    @pytest.mark.duffy_config(example_config=True, clear=True)
    @pytest.mark.parametrize("item_set", (True, False))
    @pytest.mark.parametrize("item", ("session_lifetime", "session_lifetime_max"))
    def test_effective_session_lifetime_class(self, item, item_set, db_sync_session, db_sync_obj):
        with mock.patch.dict("duffy.database.model.tenant.config") as config:
            if item_set:
                setattr(db_sync_obj, item, dt.timedelta(hours=24))

                selected = db_sync_session.execute(
                    select(model.Tenant).filter(
                        getattr(model.Tenant, f"effective_{item}") == dt.timedelta(hours=24)
                    )
                ).scalars()

                assert db_sync_obj in selected
            else:
                _defaults_config.cache_clear()
                config["defaults"][item.replace("_", "-")] = "10h"

                selected = db_sync_session.execute(
                    select(model.Tenant).filter(
                        getattr(model.Tenant, f"effective_{item}") == dt.timedelta(hours=10)
                    )
                ).scalars()

                assert db_sync_obj in selected


class TestSession(ModelTestBase):
    klass = model.Session

    def _db_obj_get_dependencies(self):
        tenant = model.Tenant(
            name="My Other Tenant",
            api_key=uuid4(),
            ssh_key="my other public SSH key",
        )
        return {"tenant": tenant}


def _gen_node_attrs(index: int = None, **addl_attrs: Dict[str, Any]) -> dict:
    lastoctet = 10
    if index:
        suffix = f"-{index}"
        lastoctet += index
    else:
        suffix = ""

    attrs = {
        "hostname": f"lolcathost{suffix}",
        "ipaddr": f"192.0.2.{lastoctet}",  # TEST-NET-1
        "state": types.NodeState.ready,
    }

    attrs.update(addl_attrs)

    return attrs


class TestNode(ModelTestBase):
    klass = model.Node
    attrs = _gen_node_attrs()

    @mock.patch("duffy.database.model.node.dt.datetime")
    def test_fail(self, datetime, db_sync_obj):
        datetime.utcnow.return_value = utcnow = mock.MagicMock()
        utcnow.isoformat.return_value = failed_at_sentinel = object()

        db_sync_obj.fail("information about the error")

        datetime.utcnow.assert_called_once_with()
        utcnow.isoformat.assert_called_once_with()

        assert db_sync_obj.data["error"] == {
            "failed_at": failed_at_sentinel,
            "detail": "information about the error",
        }


class TestSessionNode(ModelTestBase):
    klass = model.SessionNode
    attrs = {"pool": "virtual-centos8stream-x86_64-small"}

    def _db_obj_get_dependencies(self):
        tenant = model.Tenant(
            name="World Domination",
            is_admin=True,
            api_key=uuid4(),
            ssh_key="Muahahahaha!",
        )
        session = model.Session(tenant=tenant)
        node = model.Node(**_gen_node_attrs())

        return {"session": session, "node": node}

    async def test_pydantic_view(self, db_async_obj):
        node = db_async_obj.node

        result = db_async_obj.pydantic_view

        assert result.hostname == node.hostname
        assert str(result.ipaddr) == node.ipaddr
        assert result.pool == node.pool
        assert result.data == node.data
