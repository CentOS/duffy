from unittest import mock

import pytest

from duffy.tasks.mechanisms.ansible import AnsibleMechanism
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
    def create_mech(self, with_extra_vars: bool = True):
        mech_config = {
            "type": "ansible",
            "ansible": {
                "topdir": "/foo",
                "extra-vars": {
                    "nodepool": "{{ name }}",
                    "template_name": (
                        "{% set parts=name.split('-') %}" + "duffy-{{ parts[1:] | join('-') }}"
                    ),
                },
                "playbooks": {"provision": "provision.yml", "deprovision": "deprovision.yml"},
            },
        }
        if not with_extra_vars:
            del mech_config["ansible"]["extra-vars"]

        pool = ConcreteNodePool(name="virtual-boop", mechanism=mech_config)

        return pool.mechanism

    @pytest.mark.parametrize("with_extra_vars", (True, False))
    def test_extra_vars(self, with_extra_vars):
        mech = self.create_mech(with_extra_vars=with_extra_vars)
        if with_extra_vars:
            assert mech.extra_vars == {"nodepool": "virtual-boop", "template_name": "duffy-boop"}
        else:
            assert mech.extra_vars == {}

    @pytest.mark.parametrize("error", (False, "no-matching-event", "run-failed"))
    @pytest.mark.parametrize("add_run_extra_vars", (False, True))
    @mock.patch("duffy.tasks.mechanisms.ansible.ansible_runner")
    def test_run_playbook(self, ansible_runner, add_run_extra_vars, error):
        mech = self.create_mech()

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
            else:
                expectation = noop_context()

        with expectation:
            if add_run_extra_vars:
                result = mech.run_playbook("bar.yml", "bloop", {"more-extra-vars": "!!!"})
            else:
                result = mech.run_playbook("bar.yml", "bloop")

        ansible_runner.run.assert_called_once()
        args, kwargs = ansible_runner.run.call_args
        assert not args
        assert kwargs["project_dir"] == "/foo"
        assert kwargs["playbook"] == "bar.yml"
        assert kwargs["json_mode"] is True
        expected_extravars = {"nodepool": "virtual-boop", "template_name": "duffy-boop"}
        if add_run_extra_vars:
            expected_extravars["more-extra-vars"] = "!!!"
        assert kwargs["extravars"] == expected_extravars

        if not error:
            assert result == duffy_result

    @pytest.mark.parametrize("method", ("provision", "deprovision"))
    @mock.patch.object(AnsibleMechanism, "run_playbook")
    def test_provision_deprovision(self, run_playbook, method):
        failuremsg = f"{method.title()}ing failed"
        playbook = f"{method}.yml"

        node = mock.Mock(id=5, hostname="hostname", ipaddr="ipaddr")
        expected_result = {
            "duffy_in": {
                "nodes": [{"id": node.id, "hostname": node.hostname, "ipaddr": node.ipaddr}]
            }
        }
        if method == "deprovision":
            node.data = {"provision": {"mechanism-specific": 5}}
            expected_result["duffy_in"]["nodes"][0]["data"] = node.data

        run_playbook.return_value = expected_result
        mech = self.create_mech({"playbooks": {method: playbook}})
        result = getattr(mech, method)(nodes=[node])
        assert result == expected_result
        run_playbook.assert_called_once_with(playbook, failuremsg, expected_result)
