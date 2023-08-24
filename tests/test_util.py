from contextlib import nullcontext
from typing import List, Tuple, Union
from unittest import mock

import pytest

from duffy.util import RetryContext, camel_case_to_lower_with_underscores, merge_dicts


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


class TestRetryContext:
    def test___init___with_params(self):
        with RetryContext(
            exceptions=RuntimeError,
            no_attempts=1,
            delay_min=2,
            delay_max=3,
            delay_backoff_factor=4,
            delay_add_fuzz=5,
        ) as retry:
            assert retry.exceptions == RuntimeError
            assert retry.no_attempts == 1
            assert retry.delay_min == 2
            assert retry.delay_max == 3
            assert retry.delay_backoff_factor == 4
            assert retry.delay_add_fuzz == 5
            assert retry.exception_wrapper is None

            assert repr(retry) == (
                f"RetryContext(exceptions={retry.exceptions}, no_attempts={retry.no_attempts})"
            )

    @pytest.mark.parametrize("testcase", ("success", "exhausted"))
    @mock.patch("duffy.util.time.sleep")
    def test_sync(self, sleep, testcase, caplog):
        caplog.set_level("DEBUG", "duffy")
        if testcase == "success":
            limit = 3
            expectation = nullcontext()
        else:
            limit = 6
            expectation = pytest.raises(RuntimeError)

        result = None

        with expectation:
            with RetryContext() as retry:
                for attempt in retry.attempts:
                    try:
                        if attempt < limit:
                            raise RuntimeError()
                        result = attempt
                    except retry.exceptions as exc:
                        retry.process_exception(exc)

        if testcase == "success":
            assert result == limit
        else:
            assert result is None

        assert sleep.call_count == min(4, limit - 1)

    @pytest.mark.parametrize("testcase", ("success", "exhausted"))
    @mock.patch("duffy.util.asyncio.sleep")
    async def test_async(self, sleep, testcase):
        if testcase == "success":
            limit = 3
            expectation = nullcontext()
        else:
            limit = 6
            expectation = pytest.raises(RuntimeError)

        result = None

        with expectation:
            async with RetryContext() as retry:
                async for attempt in retry.attempts:
                    try:
                        if attempt < limit:
                            raise RuntimeError()
                        result = attempt
                    except retry.exceptions as exc:
                        retry.process_exception(exc)

        if testcase == "success":
            assert result == 3
        else:
            assert result is None

        assert sleep.await_count == min(4, limit - 1)

    @pytest.mark.parametrize("testcase", ("success", "no-match"))
    @mock.patch("duffy.util.time.sleep")
    def test_exception_matches(self, sleep, testcase):
        class MyRetryContext(RetryContext):
            def exception_matches(self, exc):
                if not super().exception_matches(exc):
                    return False

                return exc.args and "FOO" in exc.args[0]

        if testcase == "success":
            expectation = nullcontext()
        else:
            expectation = pytest.raises(RuntimeError)

        result = None

        with expectation:
            with MyRetryContext() as retry:
                for attempt in retry.attempts:
                    try:
                        if attempt < 3:
                            if testcase == "no-match":
                                raise RuntimeError()
                            else:
                                raise RuntimeError("Find this: >>> FOO <<<")
                        result = attempt
                    except retry.exceptions as exc:
                        retry.process_exception(exc)

        if testcase == "success":
            assert result == 3
            assert sleep.call_count == 2
        else:
            assert result is None
            assert sleep.call_count == 0

    @pytest.mark.parametrize("testcase", ("wrap", "nowrap"))
    def test_wrapping_exception(self, testcase):
        kwargs = {
            "exceptions": RuntimeError,
            "no_attempts": 1,
            "delay_min": 0,
            "delay_max": 0,
            "delay_backoff_factor": 1,
            "delay_add_fuzz": 0,
        }

        if testcase == "nowrap":
            expected_exception = RuntimeError
        else:
            expected_exception = ValueError
            kwargs["exception_wrapper"] = lambda exc: ValueError(str(exc))

        with pytest.raises(expected_exception) as excinfo:
            with RetryContext(**kwargs) as retry:
                for attempt in retry.attempts:
                    try:
                        raise RuntimeError("Boo!")
                    except retry.exceptions as exc:
                        retry.process_exception(exc)

        assert type(excinfo.value) is expected_exception
        assert str(excinfo.value) == "Boo!"
