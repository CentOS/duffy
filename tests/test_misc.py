from datetime import timedelta
from typing import Any, Dict, Type, Union

import pytest
from pydantic import BaseModel, TypeAdapter

from duffy.misc import APITimeDelta, ConfigTimeDelta, CustomTimeDelta


class _BaseTestTimeDelta:
    cls_to_test: type
    input_to_expected: Dict[Any, Union[timedelta, Type[Exception]]]

    def test_validate(self, test_input):
        expected = self.input_to_expected[test_input]

        adapter = TypeAdapter(self.cls_to_test)

        if isinstance(expected, type) and issubclass(expected, Exception):
            with pytest.raises(expected):
                adapter.validate_python(test_input)
        else:
            validated = adapter.validate_python(test_input)
            assert validated == expected

    def test_serialize(self, test_input):
        expected = self.value_to_serialized[test_input]

        adapter = TypeAdapter(self.cls_to_test)

        serialized = adapter.serializer.to_python(test_input)

        assert serialized == expected

    def test_schema(self):
        class FooModel(BaseModel):
            td: self.cls_to_test

        schema = FooModel.model_json_schema()

        td = schema["properties"]["td"]
        pattern = td["pattern"]
        assert pattern.startswith("^")
        assert pattern.endswith("$")
        examples = td["examples"]
        assert isinstance(examples, list)
        assert all(isinstance(item, str) for item in examples)


class TestCustomTimeDeltaCornerCases1(_BaseTestTimeDelta):
    cls_to_test = CustomTimeDelta(
        strip_whitespace=False,
        to_lower=False,
        needs_sign=False,
        allow_negative=True,
        allow_dimensionless_seconds=False,
        serialize_to_seconds=False,
    ).pydantic_type

    input_to_expected = {
        timedelta(minutes=5): timedelta(minutes=5),
        "3w": timedelta(days=3 * 7),
        "-3w": -timedelta(days=3 * 7),
        "+3h30m": timedelta(hours=3, minutes=30),
        " +3h30m ": ValueError,
        "+3H30M": ValueError,
        "1h": timedelta(hours=1),
        "300": ValueError,
        300: TypeError,
        600.0: TypeError,
        "-2d": timedelta(days=-2),
        "": ValueError,
        "+": ValueError,
        object(): TypeError,
    }

    value_to_serialized = {
        timedelta(): "0s",
        timedelta(
            days=10, hours=3, minutes=30, seconds=26, microseconds=123000
        ): "1w3d3h30m26s123ms",
        -timedelta(hours=3, minutes=30): "-3h30m",
        timedelta(hours=1): "1h",
        timedelta(minutes=5): "5m",
        -timedelta(minutes=10): "-10m",
    }

    @pytest.mark.parametrize("test_input", input_to_expected)
    def test_validate(self, test_input):
        super().test_validate(test_input)

    @pytest.mark.parametrize("test_input", value_to_serialized)
    def test_serialize(self, test_input):
        super().test_serialize(test_input)


class TestCustomTimeDeltaCornerCases2(_BaseTestTimeDelta):
    cls_to_test = CustomTimeDelta(
        strip_whitespace=True,
        to_lower=True,
        needs_sign=False,
        allow_negative=True,
        allow_dimensionless_seconds=True,
        serialize_to_seconds=True,
    ).pydantic_type

    input_to_expected = {
        timedelta(minutes=5): timedelta(minutes=5),
        "3w": timedelta(days=3 * 7),
        "-3w": -timedelta(days=3 * 7),
        "+3h30m": timedelta(hours=3, minutes=30),
        " +3h30m ": timedelta(hours=3, minutes=30),
        "+3H30M": timedelta(hours=3, minutes=30),
        "1h": timedelta(hours=1),
        "300": timedelta(minutes=5),
        300: timedelta(minutes=5),
        600.0: timedelta(minutes=10),
        "-2d": timedelta(days=-2),
        "": ValueError,
        "+": ValueError,
        object(): TypeError,
    }

    value_to_serialized = {
        timedelta(): 0,
        timedelta(seconds=1): 1,
        -timedelta(seconds=2): -2,
        timedelta(microseconds=3000): 0.003,
    }

    @pytest.mark.parametrize("test_input", input_to_expected)
    def test_validate(self, test_input):
        super().test_validate(test_input)

    @pytest.mark.parametrize("test_input", value_to_serialized)
    def test_serialize(self, test_input):
        super().test_serialize(test_input)


class TestConfigTimeDelta(_BaseTestTimeDelta):
    cls_to_test = ConfigTimeDelta

    input_to_expected = {
        timedelta(minutes=5): timedelta(minutes=5),
        "+3h30m": timedelta(hours=3, minutes=30),
        "1h": timedelta(hours=1),
        "300": timedelta(minutes=5),
        300: timedelta(minutes=5),
        600.0: timedelta(minutes=10),
        "-2d": ValueError,
        "": ValueError,
        "+": ValueError,
        object(): TypeError,
    }

    value_to_serialized = {
        timedelta(hours=3, minutes=30): 3 * 3600 + 30 * 60,
        timedelta(hours=1): 3600,
        timedelta(minutes=5): 300,
        timedelta(minutes=10): 600,
    }

    @pytest.mark.parametrize("test_input", input_to_expected)
    def test_validate(self, test_input):
        super().test_validate(test_input)

    @pytest.mark.parametrize("test_input", value_to_serialized)
    def test_serialize(self, test_input):
        super().test_serialize(test_input)


class TestAPITimeDelta(_BaseTestTimeDelta):
    cls_to_test = APITimeDelta

    input_to_expected = {
        timedelta(minutes=5): timedelta(minutes=5),
        "+3h30m": timedelta(hours=3, minutes=30),
        "-2d": timedelta(days=-2),
        "300": ValueError,
        300: TypeError,
        "1h": ValueError,
        "": ValueError,
        "+": ValueError,
        object(): TypeError,
    }

    value_to_serialized = {
        timedelta(minutes=5): "+5m",
        timedelta(hours=3, minutes=30): "+3h30m",
        timedelta(days=-2): "-2d",
    }

    @pytest.mark.parametrize("test_input", input_to_expected)
    def test_validate(self, test_input):
        super().test_validate(test_input)

    @pytest.mark.parametrize("test_input", value_to_serialized)
    def test_serialize(self, test_input):
        super().test_serialize(test_input)
