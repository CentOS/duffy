import uuid
from unittest import mock

import pytest

from duffy.app import logging
from duffy.app.middleware import request_id_ctxvar


class TestRequestIdFilter:
    @pytest.mark.parametrize("id_set", (True, False), ids=["id-set", "id-unset"])
    def test_filter(self, id_set):
        if id_set:
            expected = uuid.uuid4()
            token = request_id_ctxvar.set(expected)
        else:
            expected = None

        record = mock.Mock()

        retval = logging.RequestIdFilter().filter(record)

        assert retval is True
        assert record.request_id is expected

        if id_set:
            request_id_ctxvar.reset(token)
