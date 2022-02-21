from typing import Any, Dict, Iterator, List, Optional, Union

import jinja2

from ..configuration import config
from ..database.model import Node
from ..util import merge_dicts
from .mechanisms import Mechanism


class NodePool(dict):

    subcls_per_cls_type: Dict[str, type] = {}
    known_pools: Dict[str, "NodePool"] = {}

    def __init_subclass__(cls, cls_type: bool, **kwargs):
        if cls_type in cls.subcls_per_cls_type:
            raise TypeError(f"Subclass type isn't unique: {cls_type}")

        cls.subcls_per_cls_type[cls_type] = cls
        cls.cls_type = cls_type

    def __init__(
        self, *, name: str, extends: Optional[Union[List[str], str]] = None, **configuration
    ):
        if name in self.known_pools:
            raise ValueError(f"Pool {name} is defined already")

        self.name = name

        if not extends:
            extends = []
            merged_configuration = configuration
        else:
            if isinstance(extends, str):
                extends = [extends]
            configs_to_be_merged = [self.known_pools[name] for name in extends] + [configuration]
            merged_configuration = merge_dicts(*configs_to_be_merged)

        self.extends = extends

        merged_configuration.pop("name", None)
        super().__init__(name=name, **merged_configuration)

        self.known_pools[name] = self

    def __str__(self):
        return str(dict(self))

    def __repr__(self):
        filtered_dict = {k: v for k, v in self.items() if k != "name"}
        return (
            f"{type(self).__name__}(name={self.name!r}, extends={self.extends!r},"
            + f" **{filtered_dict!r})"
        )

    @classmethod
    def process_configuration(cls):
        for cls_type, pool_configurations in config["nodepools"].items():
            for pool_name, pool_configuration in pool_configurations.items():
                pool_configuration = pool_configuration.copy()
                extends = pool_configuration.pop("extends", None)
                cls.subcls_per_cls_type[cls_type](
                    name=pool_name,
                    extends=extends,
                    **pool_configuration,
                )

    @classmethod
    def iter_pools(cls) -> Iterator["NodePool"]:
        for pool in cls.known_pools.values():
            yield pool

    def render_template(self, template: str, overrides: Optional[Dict[str, Any]] = None) -> str:
        template_vars = dict(self)
        if overrides:
            template_vars = {**self, **overrides}
        return jinja2.Template(template).render(**template_vars)

    def render_templates_in_obj(self, obj: Any, overrides: Optional[Dict[str, Any]] = None) -> Any:
        if isinstance(obj, str):
            return self.render_template(obj, overrides)
        elif isinstance(obj, dict):
            return {
                key: self.render_templates_in_obj(value, overrides) for key, value in obj.items()
            }
        else:
            return obj


class AbstractNodePool(NodePool, cls_type="abstract"):
    pass


class ConcreteNodePool(NodePool, cls_type="concrete"):
    def __init__(
        self, *, name: str, extends: Optional[Union[List[str], str]] = None, **configuration
    ):
        super().__init__(name=name, extends=extends, **configuration)

        self.mechanism = Mechanism.from_configuration(self, self["mechanism"])

    @classmethod
    def iter_pools(cls) -> Iterator["ConcreteNodePool"]:
        for pool in super().iter_pools():
            # filter for pools of this class or children
            if isinstance(pool, cls):
                yield pool

    def provision(self, nodes: List[Node]) -> Dict[str, Any]:
        return self.mechanism.provision(nodes=nodes)

    def deprovision(self, nodes: List[Node]) -> Dict[str, Any]:
        return self.mechanism.deprovision(nodes=nodes)
