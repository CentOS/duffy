from pathlib import Path
from unittest import mock

import pytest
from sqlalchemy import func, select

from duffy.database.model import Node
from duffy.tasks import provision
from duffy.tasks.mechanisms import MechanismFailure
from duffy.tasks.node_pools import ConcreteNodePool

from ..util import noop_context

HERE = Path(__file__).parent
PLAYBOOK_PATH = HERE / "playbooks"


@pytest.mark.duffy_config(example_config=True)
@pytest.mark.usefixtures("db_sync_model_initialized")
@pytest.mark.parametrize(
    "testcase",
    (
        "fresh-nodes",
        "fresh-nodes-fewer-provisions",
        "fresh-nodes-mechanism-failure",
        "fresh-nodes-invalid-results",
        "fresh-nodes-real-playbook",
        "reuse-nodes",
        "reuse-nodes-fewer-provisions",
        "reuse-nodes-broken-spec",
        "reuse-nodes-mechanism-failure",
        "reuse-nodes-real-playbook",
        "unknown-pool",
        "pool-is-filled-to-spec",
        "pool-is-filled-above-spec",
    ),
)
@mock.patch.dict("duffy.tasks.node_pools.ConcreteNodePool.known_pools", clear=True)
@mock.patch("duffy.tasks.provision.Lock")
def test_fill_single_pool(Lock, testcase, db_sync_session, test_mechanism, caplog):
    real_playbook = "real-playbook" in testcase

    Lock.return_value = noop_context()

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

                if idx % 3 - 2:
                    reusable = True
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

    if real_playbook:
        mech_config = {
            "type": "ansible",
            "ansible": {
                "topdir": str(PLAYBOOK_PATH.absolute()),
                "provision": {"playbook": "provision.yml"},
            },
        }
    else:
        mech_config = {"type": "test", "test": {}}

    pool = ConcreteNodePool(
        name="foo",
        **{
            "fill-level": 5,
            "reuse-nodes": reuse_nodes,
            "bar": "this is a bar",
            "mechanism": mech_config,
        },
    )

    if testcase != "unknown-pool":
        pool_name = "foo"
        if "broken-spec" in testcase:
            expectation = pytest.raises(RuntimeError, match=r"\[foo\] Skipping filling up")
        else:
            expectation = noop_context()
    else:
        pool_name = "bar"
        expectation = pytest.raises(RuntimeError, match=r"\[bar\] Unknown pool, bailing out")

    if real_playbook:
        wraps_pool_provision = pool.provision
        wraps_pool_mech_provision = pool.mechanism.provision
    else:
        wraps_pool_provision = wraps_pool_mech_provision = None

    caplog.clear()

    with mock.patch.object(
        pool, "provision", wraps=wraps_pool_provision
    ) as pool_provision, mock.patch.object(
        pool.mechanism, "provision", wraps=wraps_pool_mech_provision
    ) as pool_mech_provision, caplog.at_level(
        "DEBUG"
    ), expectation:
        invalid_node_result = ""
        prov_count = pool["fill-level"]

        if "mechanism-failure" in testcase:
            pool_provision.side_effect = MechanismFailure()
        elif not real_playbook:
            if "fewer-provisions" in testcase:
                prov_count = 2
            pool_provision.return_value = provision_result = {
                "nodes": [
                    {
                        "id": idx + 1,
                        "hostname": f"vmhost{idx + 1}",
                        "ipaddr": f"192.168.0.{idx + 1}",
                        "opennebula": {"id": idx + 1},
                    }
                    for idx in range(prov_count)
                ],
            }
            if "invalid-results" in testcase:
                invalid_node_result = {"boo": 15}
                provision_result["nodes"].insert(1, invalid_node_result)

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
        elif "mechanism-failure" in testcase:
            assert "[foo] Provisioning failed." in caplog.messages
            if "fresh-nodes" in testcase:
                with db_sync_session.begin():
                    # all dynamically created nodes should have been deleted again
                    nodes_count = db_sync_session.execute(
                        select(func.count()).select_from(select(Node).subquery())
                    ).scalar_one()
                    assert nodes_count == 0
            else:  # "reuse-nodes"
                with db_sync_session.begin():
                    # all previously existing nodes should be back to where they were
                    nodes_count = db_sync_session.execute(
                        select(func.count()).select_from(
                            select(Node)
                            .filter_by(active=True, state="unused", pool=None)
                            .subquery()
                        )
                    ).scalar_one()
                    assert nodes_count == matching_nodes_count + not_matching_nodes_count
        elif "pool-is-filled" in testcase:
            pool_provision.assert_not_called()
            pool_mech_provision.assert_not_called()
            assert "[foo] Pool is filled to or above spec." in caplog.messages
        else:
            assert "COMMIT" in caplog.messages

            with db_sync_session.begin():
                nodes = (
                    db_sync_session.execute(
                        select(Node).filter_by(active=True, state="ready", pool="foo")
                    )
                    .scalars()
                    .all()
                )
                assert len(nodes) == prov_count
            node_ids = {node.id for node in nodes}

            pool_provision.assert_called_once()
            args, kwargs = pool_provision.call_args
            (nodes_in_call,) = args
            assert len(kwargs) == 0
            if "fewer-provisions" in testcase:
                assert {node.id for node in nodes_in_call} > node_ids
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

            assert any(
                f"we want {pool['fill-level']}, i.e. need {pool['fill-level']}" in msg
                for msg in caplog.messages
            )

            if "reuse-nodes" in testcase:
                assert "[foo] Searching for 5 reusable nodes in database" in caplog.messages
            else:
                assert "[foo] Allocating 5 new node objects in database" in caplog.messages
                assert f"[foo] invalid results: [{invalid_node_result}]" in caplog.messages
                assert "[foo] Setting hostname and ipaddr fields of nodes." in caplog.messages
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
