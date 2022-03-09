from unittest import mock

import pytest

from duffy.configuration import config
from duffy.tasks.locking import Lock


class TestLock:
    @pytest.mark.duffy_config(example_config=True)
    @pytest.mark.parametrize("masters_from_config", (True, False))
    @mock.patch("duffy.tasks.locking.Redis")
    def test_masters___init__(self, Redis, masters_from_config):
        sentinel = mock.Mock()
        Redis.from_url.return_value = sentinel

        kwargs = {"key": "a key"}
        if masters_from_config:
            redis_obj = Redis()
            kwargs["masters"] = {redis_obj}

        lock = Lock(**kwargs)

        if not masters_from_config:
            Redis.from_url.assert_called_once_with(config["tasks"]["locking"]["url"])
            assert lock.masters == {sentinel}
        else:
            Redis.from_url.assert_not_called()
            assert lock.masters == {redis_obj}
