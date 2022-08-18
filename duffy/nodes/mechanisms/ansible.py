from enum import Enum, auto
from tempfile import TemporaryDirectory
from typing import Any, Dict, List, Optional

import ansible_runner
from celery.utils.log import get_task_logger

from ...database.model import Node
from .main import Mechanism, MechanismFailure

log = get_task_logger(__name__)


class PlaybookType(Enum):
    provision = auto()
    deprovision = auto()


class AnsibleMechanism(Mechanism, mech_type="ansible"):
    def run_playbook(
        self,
        playbook_type: PlaybookType,
        failure_msg: str,
        extra_vars: Optional[Dict[str, Any]] = None,
        overrides: Optional[Dict[str, Any]] = None,
    ):
        log.debug(
            "AnsibleMechanism.run_playbook(%r, %r)\n\t%r\n\t%r",
            self,
            playbook_type,
            extra_vars,
            overrides,
        )
        subconf = self[playbook_type.name]

        run_extra_vars = self.get("extra-vars", {})
        if "extra-vars" in subconf:
            run_extra_vars = {**run_extra_vars, **subconf["extra-vars"]}
        if extra_vars:
            run_extra_vars = {**run_extra_vars, **extra_vars}

        run_extra_vars = self.nodepool.render_templates_in_obj(run_extra_vars, overrides=overrides)

        with TemporaryDirectory() as tmpdir:
            log.debug(
                (
                    "ansible_runner.run(project_dir=%r, playbook=%r, json_mode=True, extravars=%r"
                    + ", private_data_dir=%r)"
                ),
                self["topdir"],
                self[playbook_type.name]["playbook"],
                run_extra_vars,
                tmpdir,
            )
            run = ansible_runner.run(
                project_dir=self["topdir"],
                playbook=self[playbook_type.name]["playbook"],
                json_mode=True,
                extravars=run_extra_vars,
                private_data_dir=tmpdir,
            )

            if run.status != "successful":
                raise MechanismFailure(failure_msg)

            for event in reversed(list(run.events)):
                try:
                    event_type = event["event"]
                    event_data = event["event_data"]
                except KeyError as exc:
                    raise MechanismFailure(f"Key error in Ansible event: {event!r}") from exc
                event_res = event_data.get("res")

                if (
                    event_type == "runner_on_ok"
                    and event_data.get("task_action") == "set_fact"
                    and "duffy_out" in event_res.get("ansible_facts", {})
                ):
                    return event_res["ansible_facts"]["duffy_out"]
            else:
                raise MechanismFailure(failure_msg)

    def provision(self, nodes: List[Node]) -> Dict[str, Any]:
        playbook_input = {
            "duffy_in": {
                "nodes": [
                    {"id": node.id, "hostname": node.hostname, "ipaddr": node.ipaddr}
                    for node in nodes
                ],
            },
        }
        return self.run_playbook(
            PlaybookType.provision,
            "Provisioning failed",
            extra_vars=playbook_input,
            overrides=playbook_input,
        )

    def deprovision(self, nodes: List[Node]) -> Dict[str, Any]:
        playbook_input = {
            "duffy_in": {
                "nodes": [
                    {
                        "id": node.id,
                        "hostname": node.hostname,
                        "ipaddr": node.ipaddr,
                        "data": node.data,
                    }
                    for node in nodes
                ],
            },
        }
        if self.get("deprovision") and self["deprovision"].get("playbook"):
            return self.run_playbook(
                PlaybookType.deprovision,
                "Deprovisioning failed",
                extra_vars=playbook_input,
                overrides=playbook_input,
            )
        else:  # no deprovisioning playbook configured
            return playbook_input["duffy_in"]
