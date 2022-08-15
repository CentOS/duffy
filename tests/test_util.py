from contextlib import nullcontext
from typing import List, Tuple, Union

import pytest

from duffy.util import camel_case_to_lower_with_underscores, merge_dicts


@pytest.mark.parametrize(
    "camelcased,converted",
    (
        ("AssetType", "asset_type"),
        ("EXIFFieldType", "exif_field_type"),
        ("BlahEXIF", "blah_exif"),
    ),
)
def test_camel_case_to_lower_with_underscores(camelcased, converted):
    assert camel_case_to_lower_with_underscores(camelcased) == converted


class TestMergeDicts:
    """Test the merge_dicts() function."""

    # this contains tuples of ([input_dict1, input_dict2, ...], expected result or exception)
    test_cases: List[Tuple[List[dict], Union[dict, Exception]]] = [
        ([{"a": 1}, {"b": 2}], {"a": 1, "b": 2}),
        ([{"a": {"b": 1}}, {"a": {"b": 2, "c": 3}, "d": 4}], {"a": {"b": 2, "c": 3}, "d": 4}),
        ([], ValueError),
        ([{"a": {"b": 1}}, {"a": 5}], TypeError),
        ([{"a": 5}, {"a": {"b": 1}}], TypeError),
    ]

    @pytest.mark.parametrize("input_dicts,expected", test_cases)
    def test_merge_dicts(self, input_dicts, expected):
        if isinstance(expected, type) and issubclass(expected, Exception):
            expectation = pytest.raises(expected)
        else:
            expectation = nullcontext()

        with expectation:
            result = merge_dicts(*input_dicts)

        if isinstance(expected, dict):
            assert expected == result
