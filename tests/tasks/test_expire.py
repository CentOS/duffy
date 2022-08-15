import datetime as dt
import uuid
from contextlib import nullcontext
from unittest import mock

from duffy.database.model import Node, Session, SessionNode, Tenant
from duffy.tasks import expire_sessions


@mock.patch("duffy.tasks.expire.deprovision_nodes")
@mock.patch("duffy.tasks.expire.Lock")
def test_expire_sessions(Lock, deprovision_nodes, db_sync_session, caplog):
    Lock.return_value = nullcontext()
    deprovision_nodes.delay.return_value = async_result = mock.Mock()

    with db_sync_session.begin():
        now = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)

        tenant = Tenant(
            name="tenant", ssh_key="BOOP", api_key=uuid.uuid5(uuid.NAMESPACE_OID, "tenant")
        )

        sessions = []
        sessions_to_expire = []
        sessions_to_leave_alone = []
        for i in range(1, 5):
            if i % 2:
                delta = dt.timedelta(hours=1)
            else:
                delta = dt.timedelta(hours=-1)

            session = Session(tenant=tenant, expires_at=now + delta)
            session.session_nodes = [
                SessionNode(
                    session=session,
                    node=Node(hostname=f"host{i}", ipaddr=f"192.168.1.{i}"),
                    pool="A pool",
                )
            ]
            db_sync_session.add(session)
            sessions.append(session)
            if i % 2:
                sessions_to_leave_alone.append(session)
            else:
                sessions_to_expire.append(session)

        db_sync_session.flush()

    expire_sessions()

    Lock.assert_called_once()

    with db_sync_session.begin():
        for session in sessions_to_leave_alone + sessions_to_expire:
            db_sync_session.refresh(session)

        deprovision_nodes.assert_not_called()

        for session in sessions_to_expire:
            assert not session.active

            deprovision_nodes.delay.assert_has_calls(
                [
                    mock.call(
                        node_ids=[session_node.node_id for session_node in session.session_nodes]
                    ),
                ]
            )

        for session in sessions_to_leave_alone:
            assert session.active

            for call_args in deprovision_nodes.delay.call_args_list:
                args, kwargs = call_args
                assert len(args) == 0
                for session_node in session.session_nodes:
                    assert session_node.node_id not in kwargs["node_ids"]

        async_result.forget.assert_has_calls([mock.call()] for session in sessions_to_expire)
