from datetime import timedelta

import pytest
from pydantic import BaseModel

from duffy.misc import APITimeDelta, ConfigTimeDelta, _TimeDelta


class _BaseTestTimeDelta:
    cls_to_test: _TimeDelta

    def test_validate(self, test_input):
        expected = self.input_to_expected[test_input]

        if isinstance(expected, type) and issubclass(expected, Exception):
            with pytest.raises(expected):
                self.cls_to_test.validate(test_input)
        else:
            validated = self.cls_to_test.validate(test_input)
            assert validated == expected

    def test_schema(self):
        class FooModel(BaseModel):
            td: self.cls_to_test

        schema = FooModel.schema()

        td = schema["properties"]["td"]
        pattern = td["pattern"]
        assert pattern.startswith("^")
        assert pattern.endswith("$")
        examples = td["examples"]
        assert isinstance(examples, list)
        assert all(isinstance(item, str) for item in examples)


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

    @pytest.mark.parametrize("test_input", input_to_expected)
    def test_validate(self, test_input):
        super().test_validate(test_input)


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

    @pytest.mark.parametrize("test_input", input_to_expected)
    def test_validate(self, test_input):
        super().test_validate(test_input)
