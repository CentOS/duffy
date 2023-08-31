import logging
import uuid
from unittest import mock

import pytest

from duffy.app import logging as app_logging
from duffy.app.middleware import request_id_ctxvar


def test_lazy_short_request_id():
    long_id = uuid.uuid4()

    short_id = app_logging.LazyShortRequestId(long_id)

    with mock.patch.object(app_logging, "str", wraps=str) as wrapped_str:
        assert str(short_id) == short_id.data == str(long_id)[-12:]
        wrapped_str.assert_called_once_with(long_id)

        wrapped_str.reset_mock()

        assert str(short_id) == short_id.data == str(long_id)[-12:]
        wrapped_str.assert_not_called()


def test_lazy_formatted_string():
    foo = mock.Mock()
    foo.__str__ = wrapped_str = mock.Mock(return_value="foo")

    lazy_str = app_logging.LazyFormattedString("{foo}", foo=foo)

    assert str(lazy_str) == lazy_str.data == "foo"
    wrapped_str.assert_called_once_with()

    wrapped_str.reset_mock()

    assert str(lazy_str) == lazy_str.data == "foo"
    wrapped_str.assert_not_called()


class TestRequestIdFilter:
    @pytest.mark.parametrize("id_set", (True, False), ids=["id-set", "id-unset"])
    def test_filter(self, id_set):
        if id_set:
            expected = uuid.uuid4()
            token = request_id_ctxvar.set(expected)
        else:
            expected = None

        record = mock.Mock()

        retval = app_logging.RequestIdFilter().filter(record)

        assert retval is True
        assert record.request_id is expected

        if id_set:
            expected_short = str(expected)[-12:]
            assert record.short_request_id == expected_short
            assert record.request_id_optional == f"[{expected}] "
            assert record.short_request_id_optional == f"[{expected_short}] "
            request_id_ctxvar.reset(token)
        else:
            assert record.short_request_id is None
            assert record.request_id_optional == ""
            assert record.short_request_id_optional == ""
