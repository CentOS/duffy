from pathlib import Path
from unittest import mock

import pytest
from sqlalchemy import func, select

from duffy.database.model import Node
from duffy.tasks import provision
from duffy.tasks.mechanisms import Mechanism, MechanismFailure
from duffy.tasks.node_pools import ConcreteNodePool

from ..util import noop_context

HERE = Path(__file__).parent
PLAYBOOK_PATH = HERE / "playbooks"


@pytest.fixture
def foo_pool(test_mechanism):
    with mock.patch.dict("duffy.tasks.node_pools.ConcreteNodePool.known_pools", clear=True):
        yield ConcreteNodePool(
            name="foo",
            bar="this is a bar",
            mechanism={"type": "test", "test": {}},
            **{"fill-level": 5, "reuse-nodes": False},
        )


def _gen_provision_nodes_into_pool_param_combinations():
    testcases = (
        "success",
        "success-real-playbook",
        "partial-success-missing-nodes",
        "partial-success-invalid-node-results",
        "partial-success-fewer-provisions",
        "unknown-pool",
        "no-node-ids",
        "no-nodes",
        "mechanism-failure",
    )
    return [
        (reuse_nodes, testcase)
        for reuse_nodes in ("fresh-nodes", "reuse-nodes")
        for testcase in testcases
        if reuse_nodes != "reuse-nodes" or "invalid-node-results" not in testcase
    ]


@pytest.mark.parametrize(
    "reuse_nodes, testcase", _gen_provision_nodes_into_pool_param_combinations()
)
def test_provision_nodes_into_pool(reuse_nodes, testcase, foo_pool, db_sync_session, caplog):
    """Test the provision_nodes_into_pool() task."""
    reuse_nodes = reuse_nodes == "reuse-nodes"
    real_playbook = "real-playbook" in testcase

    pool_name = "foo"
    created_node_ids = []

    if reuse_nodes:
        foo_pool["reuse-nodes"] = {"architecture": "zumbitsu_8000"}

    if "no-nodes" not in testcase:
        with db_sync_session.begin():
            for node_id in range(1, 11):
                node = Node(
                    id=node_id,
                    hostname=f"node-{node_id}",
                    ipaddr=f"172.16.13.{node_id}",
                    state="provisioning",
                    pool=pool_name,
                    reusable=reuse_nodes,
                    data={"architecture": "zumbitsu_8000"} if reuse_nodes else {},
                )
                if "missing-nodes" not in testcase or node_id % 2:
                    db_sync_session.add(node)

                created_node_ids.append(node_id)

    supplied_node_ids = created_node_ids

    expectation = noop_context()

    if "unknown-pool" in testcase:
        pool_name = "bar"
        expectation = pytest.raises(RuntimeError)
    elif "no-node-ids" in testcase:
        supplied_node_ids = []
        expectation = pytest.raises(RuntimeError)
    elif "no-nodes" in testcase:
        supplied_node_ids = [1, 2, 3, 4, 5]
        expectation = pytest.raises(RuntimeError)

    if real_playbook:
        foo_pool["mechanism"] = {
            "type": "ansible",
            "ansible": {
                "topdir": str(PLAYBOOK_PATH.absolute()),
                "provision": {"playbook": "provision.yml"},
            },
        }
        foo_pool.mechanism = Mechanism.from_configuration(foo_pool, foo_pool["mechanism"])

        wraps_pool_provision = foo_pool.provision
        wraps_pool_mech_provision = foo_pool.mechanism.provision
    else:
        wraps_pool_provision = wraps_pool_mech_provision = None

    caplog.clear()

    with mock.patch.object(
        foo_pool, "provision", wraps=wraps_pool_provision
    ) as pool_provision, mock.patch.object(
        foo_pool.mechanism, "provision", wraps=wraps_pool_mech_provision
    ) as pool_mech_provision, caplog.at_level(
        "DEBUG"
    ), expectation:
        if "mechanism-failure" in testcase:
            pool_provision.side_effect = MechanismFailure()
        elif not real_playbook:
            if "fewer-provisions" in testcase:
                prov_count = 8
            elif "no-provisions" in testcase:
                prov_count = 0
            else:
                prov_count = len(created_node_ids)

            pool_provision.return_value = provision_result = {
                "nodes": [
                    {
                        "id": idx + 1,
                        "hostname": f"node-{idx + 1}",
                        "ipaddr": f"192.168.123.{idx + 1}",
                        "opennebula": {"id": idx + 1},
                    }
                    for idx in range(prov_count)
                ],
            }

            if "invalid-node-results" in testcase:
                del provision_result["nodes"][0]["ipaddr"]
                provision_result["nodes"][1] = {"boo": "spooky"}

        provision.provision_nodes_into_pool(pool_name, supplied_node_ids)

    if "success" in testcase:
        assert "COMMIT" in caplog.messages

        with db_sync_session.begin():
            nodes = (
                db_sync_session.execute(
                    select(Node).filter_by(active=True, state="ready", pool="foo")
                )
                .scalars()
                .all()
            )
            node_ids = {node.id for node in nodes}

        pool_provision.assert_called_once()
        args, kwargs = pool_provision.call_args
        (nodes_in_call,) = args
        assert len(kwargs) == 0
        if "invalid-node-results" in testcase or "fewer-provisions" in testcase:
            assert nodes_in_call
            assert {node.id for node in nodes_in_call} > node_ids
            if reuse_nodes:
                assert "[foo] Returning 2 left-over reusable node(s)" in caplog.messages
            else:
                assert "[foo] Cleaning up 2 left-over preallocated node(s)" in caplog.messages
        else:
            assert {node.id for node in nodes_in_call} == node_ids

        if real_playbook:
            assert any("[foo] Result: {" in msg for msg in caplog.messages)
            pool_mech_provision.assert_called_once()
            mechargs, mechkwargs = pool_mech_provision.call_args
            assert not mechargs
            assert {node.id for node in mechkwargs["nodes"]} == node_ids
        else:
            assert f"[foo] Result: {provision_result!r}" in caplog.messages

            # verify patching above worked
            pool_mech_provision.assert_not_called()

    if "unknown-pool" in testcase or "no-node-ids" in testcase:
        assert not caplog.messages

    if "no-nodes" in testcase:
        assert "ROLLBACK" in caplog.messages

    if "mechanism-failure" in testcase:
        assert "[foo] Provisioning failed." in caplog.messages
        if not reuse_nodes:
            with db_sync_session.begin():
                # all dynamically created nodes should have been deleted again
                nodes_count = db_sync_session.execute(
                    select(func.count()).select_from(select(Node).subquery())
                ).scalar_one()
                assert nodes_count == 0
        else:  # reuse_nodes
            with db_sync_session.begin():
                # all previously existing nodes should be back to where they were
                nodes_count = db_sync_session.execute(
                    select(func.count()).select_from(
                        select(Node).filter_by(active=True, state="unused", pool=None).subquery()
                    )
                ).scalar_one()
                assert nodes_count == len(created_node_ids)


@pytest.mark.duffy_config(example_config=True)
@pytest.mark.usefixtures("db_sync_model_initialized")
@pytest.mark.parametrize(
    "testcase",
    (
        "fresh-nodes-run-once",
        "fresh-nodes-run-parallel",
        "reuse-nodes-run-once",
        "reuse-nodes-run-parallel",
        "reuse-nodes-no-reusable",
        "reuse-nodes-broken-spec",
        "unknown-pool",
        "pool-is-filled-to-spec",
        "pool-is-filled-above-spec",
    ),
)
@mock.patch("duffy.tasks.provision.provision_nodes_into_pool")
@mock.patch("duffy.tasks.provision.Lock")
def test_fill_single_pool(
    Lock, provision_nodes_into_pool, testcase, db_sync_session, foo_pool, caplog
):
    """Test the fill_single_pool() task."""
    Lock.return_value = noop_context()

    if "run-once" in testcase:
        foo_pool["run-parallel"] = False

    if "reuse-nodes" in testcase or "pool-is-filled" in testcase:
        # Create 30 nodes
        with db_sync_session.begin():
            matching_nodes_count = 0
            not_matching_nodes_count = 0

            for idx in range(0, 30):
                if idx % 3 - 1:
                    foo_value = "this is a bar"
                else:
                    foo_value = "this is not a bar"

                if "no-reusable" not in testcase:
                    if idx % 3 - 2:
                        reusable = True
                    else:
                        reusable = False
                else:
                    reusable = False

                if foo_value == "this is a bar" and reusable:
                    matching_nodes_count += 1
                else:
                    not_matching_nodes_count += 1

                node = Node(
                    hostname=f"vmhost{idx + 1}",
                    ipaddr=f"192.168.0.{idx + 1}",
                    state="unused",
                    reusable=reusable,
                    data={"foo": foo_value, "someint": 5},
                )
                if "pool-is-filled" in testcase and ("above-spec" in testcase or idx < 5):
                    node.state = "ready"
                    node.pool = "foo"
                db_sync_session.add(node)

        reuse_nodes = {"foo": "{{ bar }}", "someint": 5}
        if "broken-spec" in testcase:
            reuse_nodes["baz"] = AssertionError("nope")
    else:
        reuse_nodes = False

    foo_pool["reuse-nodes"] = reuse_nodes

    if "unknown-pool" not in testcase:
        pool_name = "foo"
        if "broken-spec" in testcase:
            expectation = pytest.raises(RuntimeError, match=r"\[foo\] Skipping filling up")
        else:
            expectation = noop_context()
    else:
        pool_name = "bar"
        expectation = pytest.raises(RuntimeError, match=r"\[bar\] Unknown pool, bailing out")

    caplog.clear()

    with mock.patch(
        "duffy.tasks.provision.provision_nodes_into_pool"
    ) as provision_nodes_into_pool, caplog.at_level("DEBUG"), expectation:
        provision.fill_single_pool(pool_name)

    if testcase == "unknown-pool":
        assert not caplog.messages
        Lock.assert_not_called()
    else:
        Lock.assert_called_once()
        if testcase == "reuse-nodes-broken-spec":
            assert any(
                rec.levelname == "ERROR" and "Can't build query for" in rec.message
                for rec in caplog.records
            )
            assert "ROLLBACK" in caplog.messages
            assert "COMMIT" not in caplog.messages
        elif "pool-is-filled" in testcase:
            provision_nodes_into_pool.assert_not_called()
            assert "[foo] Pool is filled to or above spec." in caplog.messages
        elif "no-reusable" in testcase:
            provision_nodes_into_pool.assert_not_called()
            assert "[foo] No sense continuing, bailing out." in caplog.messages
        else:
            assert "COMMIT" in caplog.messages

            with db_sync_session.begin():
                nodes = (
                    db_sync_session.execute(
                        select(Node).filter_by(active=True, state="provisioning", pool="foo")
                    )
                    .scalars()
                    .all()
                )
                assert len(nodes) == foo_pool["fill-level"]
            node_ids = {node.id for node in nodes}

            if "run-once" in testcase:
                provision_nodes_into_pool.delay.assert_called_once()
                (pool_name, node_ids_in_call), kwargs = provision_nodes_into_pool.delay.call_args
                assert pool_name == "foo"
                assert not kwargs
                assert set(node_ids_in_call) == node_ids
            else:
                assert provision_nodes_into_pool.delay.call_count == foo_pool["fill-level"]
                for call, node in zip(provision_nodes_into_pool.delay.call_args_list, nodes):
                    assert not call.kwargs
                    pool_name, node_ids_in_call = call.args
                    assert pool_name == "foo"
                    assert node_ids_in_call == [node.id]

            assert any(
                f"we want {foo_pool['fill-level']}, i.e. need {foo_pool['fill-level']}" in msg
                for msg in caplog.messages
            )

            if "reuse-nodes" in testcase:
                assert "[foo] Searching for 5 reusable nodes in database" in caplog.messages
            else:
                assert "[foo] Allocating 5 new node objects in database" in caplog.messages
                if "fewer-provisions" in testcase:
                    assert "[foo] Cleaning up 3 left-over preallocated nodes" in caplog.messages


@pytest.mark.usefixtures("test_mechanism")
@pytest.mark.parametrize("testcase", ("all-pools", "one-pool", "unknown-pool"))
@mock.patch("duffy.tasks.provision.fill_single_pool")
@mock.patch.dict("duffy.tasks.node_pools.ConcreteNodePool.known_pools", clear=True)
def test_fill_pools(fill_single_pool, testcase):
    all_pool_names = ("foo", "bar")
    for name in all_pool_names:
        ConcreteNodePool(name=name, mechanism={"type": "test", "test": {}})

    if testcase == "all-pools":
        pool_names = None
    elif testcase == "one-pool":
        pool_names = ["foo"]
    else:  # unknown-pool
        pool_names = ["unknown"]

    provision.fill_pools(pool_names=pool_names)

    if testcase == "all-pools":
        fill_single_pool.delay.has_calls([pool for pool in all_pool_names])
    elif testcase == "one-pool":
        fill_single_pool.delay.assert_called_once_with("foo")
    else:  # testcase == "unknown-pool"
        fill_single_pool.delay.assert_not_called()
