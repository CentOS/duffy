import pytest
from sqlalchemy import select

from duffy.database.model import Chassis, Node, Tenant

obj_classes = (Chassis, Node, Tenant)


@pytest.mark.parametrize("obj_class", obj_classes)
def test_objs_sync(obj_class, db_sync_test_data, db_sync_session):
    results = db_sync_session.execute(select(obj_class))
    objects = results.all()
    assert objects


@pytest.mark.parametrize("obj_class", obj_classes)
@pytest.mark.asyncio
async def test_objs_async(obj_class, db_async_test_data, db_async_session):
    results = await db_async_session.execute(select(obj_class))
    objects = results.all()
    assert objects
