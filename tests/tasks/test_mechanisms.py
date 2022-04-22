from unittest import mock

import pytest

from duffy.tasks.mechanisms.ansible import AnsibleMechanism, PlaybookType
from duffy.tasks.mechanisms.main import Mechanism, MechanismFailure
from duffy.tasks.node_pools import ConcreteNodePool, NodePool

from ..util import noop_context


@mock.patch.dict(Mechanism.known_mechanisms, clear=True)
class TestMechanism:
    @pytest.mark.parametrize("duplicate_mech", (False, True))
    def test_subclassing(self, duplicate_mech):
        class FooMechanism(Mechanism, mech_type="foo"):
            pass

        if duplicate_mech:
            with pytest.raises(TypeError) as excinfo:

                class AnotherFooMechanism(Mechanism, mech_type="foo"):
                    pass

            assert str(excinfo.value) == "Mechanism type isn't unique: foo"

        assert Mechanism.known_mechanisms["foo"] == FooMechanism

    def test___init__(self):
        sentinel = object()
        mech = Mechanism(nodepool=sentinel, foo="test")
        assert mech.nodepool == sentinel
        assert "nodepool" not in mech
        assert mech["foo"] == "test"

    def test_from_configuration(self):
        class FooMechanism(Mechanism, mech_type="foo"):
            pass

        mech = Mechanism.from_configuration(mock.Mock(), {"type": "foo", "foo": {"bar": "baz"}})

        assert isinstance(mech, FooMechanism)
        assert mech["bar"] == "baz"

    @pytest.mark.parametrize("method", ("provision", "deprovision"))
    def test_not_implemented_methods(self, method):
        mech = Mechanism(nodepool=mock.Mock())
        with pytest.raises(NotImplementedError):
            getattr(mech, method)([])


@mock.patch.dict(NodePool.known_pools, clear=True)
class TestAnsibleMechanism:
    def create_mech(self, with_extra_vars: bool = True, extra_vars_loc: str = "default"):
        mech_config = {
            "type": "ansible",
            "ansible": {
                "topdir": "/foo",
                "provision": {"playbook": "provision.yaml"},
                "deprovision": {"playbook": "deprovision.yaml"},
            },
        }
        if with_extra_vars:
            extra_vars = {
                "nodepool": "{{ name }}",
                "template_name": (
                    "{% set parts=name.split('-') %}" + "duffy-{{ parts[1:] | join('-') }}"
                ),
            }
            if extra_vars_loc == "default":
                mech_config["ansible"]["extra-vars"] = extra_vars
            else:
                mech_config["ansible"][extra_vars_loc]["extra-vars"] = extra_vars

        pool = ConcreteNodePool(name="virtual-boop", mechanism=mech_config)

        return pool.mechanism

    @pytest.mark.parametrize("extra_vars_loc", ("default", "provision"))
    @pytest.mark.parametrize(
        "error", (False, "no-matching-event", "run-failed", "event_data-missing")
    )
    @pytest.mark.parametrize("add_run_extra_vars", (False, True))
    @mock.patch("duffy.tasks.mechanisms.ansible.ansible_runner")
    def test_run_playbook(self, ansible_runner, add_run_extra_vars, error, extra_vars_loc):
        mech = self.create_mech(extra_vars_loc=extra_vars_loc)

        ansible_runner.run.return_value = run = mock.Mock()
        if error == "run-failed":
            run.status = "failed"
            expectation = pytest.raises(MechanismFailure)
        else:
            run.status = "successful"
            duffy_result = {
                "nodes": [
                    {"hostname": "host1", "ip_address": "192.168.10.11", "id": 11},
                    {"hostname": "host2", "ip_address": "192.168.10.12", "id": 12},
                    {"hostname": "host3", "ip_address": "192.168.10.13", "id": 13},
                    {"hostname": "host4", "ip_address": "192.168.10.14", "id": 14},
                ],
            }
            run.events = [
                {"event": "playbook_on_start", "event_data": {"playbook": "/foo/bar.yml"}},
                {"event": "playbook_on_play_start", "event_data": {"playbook": "/foo/bar.yml"}},
                {"event": "playbook_on_task_start", "event_data": {"playbook": "/foo/bar.yml"}},
                {"event": "runner_on_start", "event_data": {"playbook": "/foo/bar.yml"}},
                {"event": "runner_on_ok", "event_data": {"playbook": "/foo/bar.yml"}},
                {"event": "playbook_on_task_start", "event_data": {"playbook": "/foo/bar.yml"}},
                {
                    "event": "runner_on_start",
                    "event_data": {"playbook": "/foo/bar.yml", "task_action": "set_fact"},
                },
                {
                    "event": "runner_on_ok",
                    "event_data": {
                        "playbook": "/foo/bar.yml",
                        "task_action": "set_fact",
                        "res": {"ansible_facts": {"duffy_out": duffy_result}},
                    },
                },
                {"event": "playbook_on_task_start", "event_data": {"playbook": "/foo/bar.yml"}},
                {"event": "runner_on_start", "event_data": {"playbook": "/foo/bar.yml"}},
                {
                    "event": "runner_on_ok",
                    "event_data": {"task_action": "debug", "res": {"msg": "Hello"}},
                },
                {
                    "event": "playbook_on_stats",
                    "event_data": {"task_action": "debug", "msg": "Hello"},
                },
            ]

            if error == "no-matching-event":
                run.events = [
                    event
                    for event in run.events
                    if "duffy_out"
                    not in event["event_data"].get("res", {}).get("ansible_facts", {})
                ]
                expectation = pytest.raises(MechanismFailure)
            elif error == "event_data-missing":
                del run.events[-2]["event_data"]
                expectation = pytest.raises(MechanismFailure)
            else:
                expectation = noop_context()

        with expectation:
            args = (PlaybookType.provision, "bloop")
            if add_run_extra_vars:
                args += ({"more-extra-vars": "!!!"},)
            result = mech.run_playbook(*args)

        ansible_runner.run.assert_called_once()
        args, kwargs = ansible_runner.run.call_args
        assert not args
        assert kwargs["project_dir"] == "/foo"
        assert kwargs["playbook"] == "provision.yaml"
        assert kwargs["json_mode"] is True
        expected_extravars = {"nodepool": "virtual-boop", "template_name": "duffy-boop"}
        if add_run_extra_vars:
            expected_extravars["more-extra-vars"] = "!!!"
        assert kwargs["extravars"] == expected_extravars

        if not error:
            assert result == duffy_result

    @pytest.mark.parametrize("playbook_type", (PlaybookType.provision, PlaybookType.deprovision))
    @mock.patch.object(AnsibleMechanism, "run_playbook")
    def test_provision_deprovision(self, run_playbook, playbook_type):
        method = playbook_type.name
        failuremsg = f"{method.title()}ing failed"

        node = mock.Mock(id=5, hostname="hostname", ipaddr="ipaddr")
        nodes = [{"id": node.id, "hostname": node.hostname, "ipaddr": node.ipaddr}]
        if playbook_type == PlaybookType.deprovision:
            node.data = {"provision": {"mechanism-specific": 5}}
            nodes[0]["data"] = node.data

        expected_playbook_vars = {"duffy_in": {"nodes": nodes}}
        # run_playbook() strips off "duffy_out"
        expected_result = {"nodes": nodes}
        run_playbook.return_value = expected_result

        mech = self.create_mech()

        result = getattr(mech, method)(nodes=[node])
        assert result == expected_result
        run_playbook.assert_called_once_with(
            playbook_type,
            failuremsg,
            extra_vars=expected_playbook_vars,
            overrides=expected_playbook_vars,
        )
