from typing import Any, Dict

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from duffy.database import DBSession, SyncDBSession, model


class ModelTestBase:
    klass = None
    attrs = {}

    def test_create_obj(self, db_sync_obj):
        pass

    def test_query_obj_sync(self, db_sync_obj):
        result = SyncDBSession.execute(select(self.klass))
        obj = result.scalar_one()
        for key, value in self.attrs.items():
            objvalue = getattr(obj, key)
            if isinstance(objvalue, (int, str)):
                assert objvalue == value
        for key, value in self._db_obj_get_dependencies().items():
            objvalue = getattr(obj, key)
            if isinstance(objvalue, (int, str)):
                assert objvalue == value

    @pytest.mark.asyncio
    async def test_query_obj_async(self, db_async_obj):
        # The selectinload() option tells SQLAlchemy to load related objects and lazy loading breaks
        # things here. See here for details:
        #
        # https://docs.sqlalchemy.org/en/14/orm/extensions/asyncio.html#preventing-implicit-io-when-using-asyncsession
        #
        # You can specify which relation you're interested in but because this code doesn't know
        # anything about the involved ORM class, we specify that we "want it all".
        result = await DBSession.execute(select(self.klass).options(selectinload("*")))
        obj = result.scalar_one()
        for key, value in self.attrs.items():
            objvalue = getattr(obj, key)
            if isinstance(objvalue, (int, str)):
                assert objvalue == value
        for key, value in self._db_obj_get_dependencies().items():
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
        "ssh_key": "this is a public ssh key",
    }


class TestSession(ModelTestBase):
    klass = model.Session

    def _db_obj_get_dependencies(self):
        tenant = model.Tenant(name="My Other Tenant", ssh_key="my other public SSH key")
        return {"tenant": tenant}


class TestChassis(ModelTestBase):
    klass = model.Chassis
    attrs = {"name": "hufty"}


def _gen_node_attrs(**addl_attrs: Dict[str, Any]) -> dict:
    attrs = {
        "hostname": "lolcathost",
        "ipaddr": "192.0.2.10",  # TEST-NET-1
        "state": model.NodeState.ready,
    }

    attrs.update(addl_attrs)

    return attrs


class TestVirtualNode(ModelTestBase):
    klass = model.VirtualNode
    attrs = _gen_node_attrs(flavour="medium", comment="Hello!")


class TestOpenNebulaNode(ModelTestBase):
    klass = model.OpenNebulaNode
    attrs = _gen_node_attrs(flavour="large", comment="Good Day!")


class TestPhysicalNode(ModelTestBase):
    klass = model.PhysicalNode
    attrs = _gen_node_attrs()


class TestSeaMicroNode(ModelTestBase):
    klass = model.SeaMicroNode
    attrs = _gen_node_attrs()

    def _db_obj_get_dependencies(self):
        return {"chassis": model.Chassis(name="Infinity Polydome K")}


class TestSessionNode(ModelTestBase):
    klass = model.SessionNode
    attrs = {"distro_type": "CentOS", "distro_version": "8Stream"}

    def _db_obj_get_dependencies(self):
        tenant = model.Tenant(name="World Domination", is_admin=True, ssh_key="Muahahahaha!")
        session = model.Session(tenant=tenant)
        chassis = model.Chassis(name="Celestion Greenback")
        node = model.SeaMicroNode(**_gen_node_attrs(chassis=chassis))

        return {"session": session, "node": node}
