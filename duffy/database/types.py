from .util import DeclEnum


class NodeState(str, DeclEnum):
    ready = "ready"
    active = "active"
    contextualizing = "contextualizing"
    deployed = "deployed"
    deprovisioning = "deprovisioning"
    done = "done"
    failing = "failing"
    failed = "failed"
