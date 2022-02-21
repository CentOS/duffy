import logging
from collections import defaultdict
from pathlib import Path
from unittest import mock

import pytest
from sqlalchemy import func, select

from duffy.database.model import Node
from duffy.tasks import deprovision
from duffy.tasks.mechanisms import MechanismFailure
from duffy.tasks.node_pools import ConcreteNodePool, NodePool

from ..util import noop_context

HERE = Path(__file__).parent
PLAYBOOK_PATH = HERE / "playbooks"


@mock.patch.dict(NodePool.known_pools, clear=True)
@pytest.mark.parametrize(
    "testcase",
    (
        "normal-dispose-nodes",
        "normal-dispose-nodes-real-playbook",
        "normal-reuse-nodes",
        "normal-reuse-nodes-real-playbook",
        "normal-unknown-node-id",
        "normal-spurious-mechanism-result",
        "normal-incomplete-result-fields",
        "almost-normal-node-unhandled",
        "unknown-pool",
        "abstract-pool",
        "mechanism-failure",
    ),
)
def test_deprovision_pool_nodes(testcase, test_mechanism, db_sync_session, caplog):
    expectation = noop_context()
    real_playbook = "real-playbook" in testcase

    if "unknown-pool" in testcase:
        pool_name = "bar"
    else:
        pool_name = "foo"

    if "abstract-pool" in testcase:
        pool = NodePool(name="foo")
        # allow this to be mocked below even though it's missing on plain NodePool objects
        pool.deprovision = mock.MagicMock()
        pool.mechanism = mock.MagicMock()
    else:
        if real_playbook:
            mech_config = {
                "type": "ansible",
                "ansible": {
                    "topdir": str(PLAYBOOK_PATH.absolute()),
                    "deprovision": {"playbook": "deprovision.yml"},
                },
            }
        else:
            mech_config = {"type": "test", "test": {}}

        pool = ConcreteNodePool(name="foo", mechanism=mech_config)

    with db_sync_session.begin():
        # create some testing nodes
        reusable = "reuse-nodes" in testcase
        nodes = [
            Node(
                id=id,
                state="deployed",
                pool="foo",
                reusable=reusable,
                data={"provision": {"mech_id": id + 20}},
            )
            for id in range(1, 5)
        ]
        db_sync_session.add_all(nodes)

        node_ids = [node.id for node in nodes]
        if "unknown-node-id" in testcase:
            node_ids.append(32)

    if real_playbook:
        wraps_pool_deprovision = pool.deprovision
        wraps_mech_deprovision = pool.mechanism.deprovision
    else:
        wraps_pool_deprovision = wraps_mech_deprovision = None

    caplog.clear()

    with mock.patch.object(
        pool, "deprovision", wraps=wraps_pool_deprovision
    ) as pool_deprovision, mock.patch.object(
        pool.mechanism, "deprovision", wraps=wraps_mech_deprovision
    ) as pool_mech_deprovision, caplog.at_level(
        "DEBUG"
    ):
        if "mechanism-failure" not in testcase:
            if not real_playbook:
                mech_result = {
                    "nodes": [
                        {
                            "id": node.id,
                            "hostname": node.hostname,
                            "ipaddr": node.ipaddr,
                            "data": node.data,
                            # the following should be ignored when matching results with nodes
                            "something": "unrelated",
                        }
                        for node in nodes
                    ]
                }
                if "node-unhandled" in testcase:
                    del mech_result["nodes"][-1]
                if "spurious-mechanism-result" in testcase:
                    mech_result["nodes"].append({"foo": "boop"})
                if "incomplete-result-fields" in testcase:
                    for node in mech_result["nodes"]:
                        del node["ipaddr"]
                pool_deprovision.return_value = mech_result
        else:
            pool_deprovision.side_effect = MechanismFailure("you should have bought a squirrel")
            expectation = pytest.raises(MechanismFailure)

        with expectation as excinfo:
            deprovision.deprovision_pool_nodes(pool_name, node_ids)

    # expire all objects to avoid getting back cached ones
    db_sync_session.expire_all()

    with db_sync_session.begin():
        nodes = db_sync_session.execute(select(Node)).scalars().all()
        node_ids = {node.id for node in nodes}

        if "normal" in testcase or "mechanism-failure" in testcase:
            pool_deprovision.assert_called_once()
            args, kwargs = pool_deprovision.call_args
            (nodes_in_call,) = args
            assert not kwargs

            if "normal" in testcase:
                for warnings_testcase in (
                    "unknown-node-id",
                    "spurious-mechanism",
                    "node-unhandled",
                ):
                    if warnings_testcase in testcase:
                        max_loglevel = logging.WARNING
                        break
                else:
                    max_loglevel = logging.INFO
                assert all(rec.levelno <= max_loglevel for rec in caplog.records)

                assert {node.id for node in nodes_in_call} == node_ids
                if real_playbook:
                    pool_mech_deprovision.assert_called_once()
                    mechargs, mechkwargs = pool_mech_deprovision.call_args
                    assert not mechargs
                    assert {node.id for node in mechkwargs["nodes"]} == node_ids

                if "reuse-nodes" in testcase:
                    final_state = "unused"
                    active = True
                else:
                    final_state = "done"
                    active = False
                if "node-unhandled" in testcase:
                    assert all(rec.levelno < logging.ERROR for rec in caplog.records)
                    counts = defaultdict(int)
                    for node in nodes:
                        if node.active:
                            counts["active"] += 1
                        else:
                            counts["retired"] += 1
                        if node.state == final_state:
                            counts["final_state"] += 1
                        else:
                            assert node.state == "failed"
                            counts["failed"] += 1
                    assert counts["active"] == 1
                    assert counts["failed"] == 1
                    assert counts["retired"] == len(nodes) - 1
                    assert counts["final_state"] == len(nodes) - 1
                else:
                    assert all(node.active == active for node in nodes)
                    assert all(node.state == final_state for node in nodes)
            else:
                assert "[foo] Deprovisioning mechanism failed." in caplog.messages
                # refreshing node.id won't work on exception
                assert len(nodes_in_call) == len(nodes)
                assert str(excinfo.value) == "you should have bought a squirrel"
                assert all(node.active for node in nodes)
                assert all(node.state == "failed" for node in nodes)
        else:
            pool_deprovision.assert_not_called()
            assert all(node.state == "deployed" for node in nodes)
            if "unknown-pool" in testcase:
                assert "[bar] Can't find pool." in caplog.messages
            elif "abstract-pool" in testcase:
                assert "[foo] Pool must be a concrete node pool." in caplog.messages


@pytest.mark.parametrize("testcase", ("normal", "unknown-ids"))
@mock.patch("duffy.tasks.deprovision.deprovision_pool_nodes")
def test_deprovision_nodes(deprovision_pool_nodes, testcase, db_sync_session, caplog):
    known_ids = []
    unknown_ids = []
    with db_sync_session.begin():
        # create some node objects for testing
        nodes = [
            Node(id=id, state="deployed", pool="odd" if id % 2 else "even") for id in range(1, 6)
        ]
        if "unknown-ids" in testcase:
            # ensure one isn't deployed
            nodes[2].state = "ready"
        for node in nodes:
            if node.state == "deployed":
                known_ids.append(node.id)
            else:
                unknown_ids.append(node.id)
        db_sync_session.add_all(nodes)

    # sort by pool name to verify calls to deprovision_pool_nodes() below
    node_ids_by_pool = {
        pool_name: {
            node.id for node in nodes if node.pool == pool_name and node.state == "deployed"
        }
        for pool_name in ("odd", "even")
    }
    node_ids = [node.id for node in nodes]
    if "unknown-ids" in testcase:
        # add one unknown node id
        node_ids += [32]
        unknown_ids.append(32)

    deprovision_pool_nodes.delay = delay = mock.MagicMock()

    caplog.clear()
    deprovision.deprovision_nodes(node_ids)

    deprovision_pool_nodes.assert_not_called()

    found_pool_names = set()
    for args, kwargs in delay.call_args_list:
        assert not args
        pool_name = kwargs["pool_name"]
        found_pool_names.add(pool_name)
        node_ids = node_ids_by_pool[pool_name]
        assert set(kwargs["node_ids"]) == node_ids

    assert node_ids_by_pool.keys() == found_pool_names
    if "unknown-ids" in testcase:
        assert f"Didn't find deployed nodes with ids: {unknown_ids}" in caplog.messages
    else:
        assert all("Didn't find deployed nodes with ids:" not in m for m in caplog.messages)

    with db_sync_session.begin():
        # deprovision_nodes() doesn't set nodes to "deprovisioning"
        deprovisioning_nodes_count = db_sync_session.execute(
            select(func.count()).select_from(
                select(Node).filter_by(state="deprovisioning").subquery()
            )
        ).scalar_one()
        assert deprovisioning_nodes_count == 0
