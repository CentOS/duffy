from typing import TYPE_CHECKING, Any, Dict, List

from ...database.model import Node

if TYPE_CHECKING:
    from ..node_pools import NodePool


class MechanismFailure(Exception):
    pass


class Mechanism(dict):

    known_mechanisms: Dict[str, "Mechanism"] = {}

    def __init_subclass__(cls, mech_type: str, **kwargs):
        super().__init_subclass__()

        # Register subclasses.
        if mech_type in cls.known_mechanisms:
            raise TypeError(f"Mechanism type isn't unique: {mech_type}")

        cls.known_mechanisms[mech_type] = cls
        cls.mech_type = mech_type

    def __init__(self, *, nodepool: "NodePool", **kwargs):
        super().__init__(**kwargs)
        self.nodepool = nodepool

    @classmethod
    def from_configuration(cls, nodepool: "NodePool", configuration: Dict[str, Any]):
        configuration = configuration.copy()
        mech_type = configuration.pop("type")
        return cls.known_mechanisms[mech_type](nodepool=nodepool, **configuration[mech_type])

    def provision(self, nodes: List[Node]) -> Dict[str, Any]:
        raise NotImplementedError()

    def deprovision(self, nodes: List[Node]) -> Dict[str, Any]:
        raise NotImplementedError()
