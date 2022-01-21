from typing import Any, Dict
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from duffy.database import model, types


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

    @pytest.mark.asyncio
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


@pytest.mark.asyncio
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
