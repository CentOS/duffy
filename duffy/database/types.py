from .util import DeclEnum


class NodeType(str, DeclEnum):
    virtual = "virtual"
    physical = "physical"
    opennebula = "opennebula"
    seamicro = "seamicro"


class NodeState(str, DeclEnum):
    ready = "ready"
    active = "active"
    contextualizing = "contextualizing"
    deployed = "deployed"
    deprovisioning = "deprovisioning"
    done = "done"
    failing = "failing"
    failed = "failed"


class VirtualNodeFlavour(str, DeclEnum):
    small = "small"
    medium = "medium"
    large = "large"
