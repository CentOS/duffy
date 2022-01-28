from .util import DeclEnum


class NodeState(str, DeclEnum):
    unused = "unused"
    provisioning = "provisioning"
    ready = "ready"
    contextualizing = "contextualizing"
    deployed = "deployed"
    deprovisioning = "deprovisioning"
    done = "done"
    failed = "failed"
