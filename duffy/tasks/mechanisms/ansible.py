from typing import Any, Dict, List, Optional

import ansible_runner

from ...database.model import Node
from .main import Mechanism, MechanismFailure


class AnsibleMechanism(Mechanism, mech_type="ansible"):
    @property
    def extra_vars(self):
        if "extra-vars" in self:
            return self.nodepool.render_templates_in_obj(self["extra-vars"])
        else:
            return {}

    def run_playbook(
        self, playbook: str, failure_msg: str, extra_vars: Optional[Dict[str, Any]] = None
    ):
        if not extra_vars:
            extra_vars = self.extra_vars
        else:
            extra_vars = {**self.extra_vars, **extra_vars}

        run = ansible_runner.run(
            project_dir=self["topdir"], playbook=playbook, json_mode=True, extravars=extra_vars
        )

        if run.status != "successful":
            raise MechanismFailure(failure_msg)

        for event in reversed(list(run.events)):
            event_type = event["event"]
            event_data = event["event_data"]
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
        extra_vars = {
            "duffy_in": {
                "nodes": [
                    {"id": node.id, "hostname": node.hostname, "ipaddr": node.ipaddr}
                    for node in nodes
                ],
            },
        }
        return self.run_playbook(self["playbooks"]["provision"], "Provisioning failed", extra_vars)

    def deprovision(self, nodes: List[Node]) -> Dict[str, Any]:
        extra_vars = {
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
        return self.run_playbook(
            self["playbooks"]["deprovision"], "Deprovisioning failed", extra_vars
        )
