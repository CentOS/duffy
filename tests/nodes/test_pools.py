from unittest import mock

import pytest

from duffy.configuration import config
from duffy.nodes.pools import AbstractNodePool, ConcreteNodePool, NodePool


@mock.patch.dict(NodePool.subcls_per_cls_type, clear=False)
@mock.patch.dict(NodePool.known_pools, clear=True)
class TestNodePool:
    @pytest.mark.parametrize("duplicate_cls_type", (False, True))
    def test___init_subclass__(self, duplicate_cls_type):
        class FooNodePool(NodePool, cls_type="foo"):
            pass

        if duplicate_cls_type:
            with pytest.raises(TypeError) as excinfo:

                class AnotherFooNodePool(NodePool, cls_type="foo"):
                    pass

            assert str(excinfo.value) == "Subclass type isn't unique: foo"

        assert NodePool.subcls_per_cls_type["foo"] == FooNodePool
        assert FooNodePool.cls_type == "foo"

    @pytest.mark.usefixtures("test_mechanism")
    @pytest.mark.parametrize("cls_type", ("abstract", "concrete"))
    @pytest.mark.parametrize("extends", (None, "foo", ["foo", "bar"]))
    @pytest.mark.parametrize("pool_defined_error", (False, True))
    def test___init__(self, cls_type, extends, pool_defined_error):
        test_config = {"test": 1, "mechanism": {"type": "test", "test": {}}}

        _extends = extends
        if not _extends:
            _extends = []
        elif isinstance(_extends, str):
            _extends = [_extends]

        node_pool_cls = NodePool.subcls_per_cls_type[cls_type]

        base_pools = {
            pool_name: AbstractNodePool(name=pool_name, **{pool_name: pool_name})
            for pool_name in _extends
        }

        pool = node_pool_cls(name="test", extends=extends, **test_config)

        for base_pool_name in base_pools:
            assert pool[base_pool_name] == base_pool_name

        for test_key, test_value in test_config.items():
            assert pool[test_key] == test_value

        if pool_defined_error:
            with pytest.raises(ValueError) as excinfo:
                node_pool_cls(name="test", extends=extends, **test_config)

            assert str(excinfo.value) == "Pool test is defined already"

    @classmethod
    def dict_is_subset(cls, dict1, dict2):
        """Check if dict1 is a deep subset of dict2"""
        if not isinstance(dict2, dict):
            return False
        for key, value in dict1.items():
            if key not in dict2:
                return False
            if isinstance(value, dict):
                if not cls.dict_is_subset(value, dict2[key]):
                    return False
            else:
                if not dict2[key] == value:
                    return False
        return True

    def test___str__(self):
        pool = NodePool(name="test", foo="bar")
        assert str(pool) == str({"name": "test", "foo": "bar"})

    def test___repr__(self):
        pool = NodePool(name="test", foo="bar")
        assert repr(pool) == "NodePool(name='test', extends=[], **{'foo': 'bar'})"

    @pytest.mark.duffy_config(example_config=True)
    def test_process_configuration(self):
        NodePool.process_configuration()

        for cls_type in ("abstract", "concrete"):
            for pool_name, pool_config in config["nodepools"][cls_type].items():
                pool = NodePool.known_pools[pool_name]

                assert pool.name == pool_name
                assert pool.cls_type == cls_type

                for key, value in pool_config.items():
                    if key == "extends":
                        if not value:
                            value = []
                        elif isinstance(value, str):
                            value = [value]
                        assert pool.extends == value
                    elif isinstance(value, dict):
                        assert self.dict_is_subset(value, pool[key])
                    else:
                        assert pool[key] == value

    @pytest.mark.duffy_config(example_config=True)
    def test_iter_pools(self):
        NodePool.process_configuration()

        expected = set(config["nodepools"]["abstract"]) | set(config["nodepools"]["concrete"])

        assert set(pool.name for pool in NodePool.iter_pools()) == expected

    @pytest.mark.parametrize("with_overrides", (False, True))
    def test_render_template(self, with_overrides):
        if with_overrides:
            pool = NodePool(name="foo")
            overrides = {"bar": "hello"}
        else:
            pool = NodePool(name="foo", bar="hello")
            overrides = None
        assert pool.render_template("{{ bar }} - {{ name }}", overrides) == "hello - foo"

    def test_render_template_in_obj(self):
        pool = NodePool(name="foo", bar="hello", baz="goodbye")
        assert pool.render_templates_in_obj(
            {"key1": "{{ name }} - {{ bar }}", "key2": {"key2.1": 5, "key2.2": "{{ baz }}"}}
        ) == {"key1": "foo - hello", "key2": {"key2.1": 5, "key2.2": "goodbye"}}


@mock.patch.dict(NodePool.known_pools, clear=True)
class TestConcreteNodePool:
    def test___init__(self, test_mechanism):
        pool = ConcreteNodePool(name="test", mechanism={"type": "test", "test": {}})
        assert isinstance(pool.mechanism, test_mechanism)

    @pytest.mark.duffy_config(example_config=True)
    def test_iter_pools(self):
        NodePool.process_configuration()

        expected = set(config["nodepools"]["concrete"])

        assert set(pool.name for pool in ConcreteNodePool.iter_pools()) == expected

    @pytest.mark.usefixtures("test_mechanism")
    @pytest.mark.parametrize("method", ("provision", "deprovision"))
    def test_provision_deprovision(self, method):
        pool = ConcreteNodePool(name="test", mechanism={"type": "test", "test": {}})
        pool.mechanism = mock.Mock()

        sentinel = [object()]
        getattr(pool, method)(sentinel)

        getattr(pool.mechanism, method).assert_called_once_with(nodes=sentinel)
