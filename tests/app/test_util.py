from contextlib import nullcontext
from unittest import mock

import pytest
from asyncpg import SerializationError
from sqlalchemy.exc import DBAPIError

import duffy.app.util
from duffy.app.util import ConfigRetryContext, SerializationErrorRetryContext


def mock_config_get(key, *args, **kwargs):
    tail = key.rsplit(".", 1)[1]

    return {
        # just some identifiable values different from the defaults
        "no-attempts": 2,
        "delay-min": 0.01,
        "delay-max": 0.02,
        "delay-backoff-factor": 3,
        "delay-add-fuzz": 0.003,
    }[tail]


@pytest.mark.parametrize("with_param", (False, True))
@mock.patch("duffy.app.util.config_get", mock_config_get)
async def test_config_retry_context(with_param):
    if with_param:
        retry = ConfigRetryContext(no_attempts=4)
    else:
        retry = ConfigRetryContext()

    if with_param:
        assert retry.no_attempts == 4
    else:
        assert retry.no_attempts == 2
    assert retry.delay_min == 0.01
    assert retry.delay_max == 0.02
    assert retry.delay_backoff_factor == 3
    assert retry.delay_add_fuzz == 0.003


@pytest.mark.parametrize(
    "testcase",
    ("matches", "no-match-other-exception", "no-match-other-pgcode", "no-match-no-asyncpg"),
)
@mock.patch("duffy.app.util.config_get", mock_config_get)
async def test_serializationerror_retry_context(testcase):
    hide_asyncpg = nullcontext()

    orig_exc = mock.MagicMock(spec=SerializationError, pgcode=SerializationError.sqlstate)
    if "matches" in testcase:
        expectation = nullcontext()
    else:
        expectation = pytest.raises(DBAPIError)
        if "other-exception" in testcase:
            orig_exc = mock.MagicMock(spec=RuntimeError)
        elif "match-other-pgcode" in testcase:
            orig_exc.pgcode = str(orig_exc.pgcode) + "Boo"
        elif "no-asyncpg" in testcase:
            duffy.app.util.asyncpg = None
            hide_asyncpg = mock.patch.object(duffy.app.util, "asyncpg", None)

    toplvl_exc = DBAPIError("", "", orig_exc)

    mocked_fn = mock.MagicMock()
    mocked_fn.side_effect = [toplvl_exc, 5]

    async def fn():
        return mocked_fn()

    result = None

    with expectation, hide_asyncpg:
        async with SerializationErrorRetryContext() as retry:
            async for attempt in retry.attempts:
                try:
                    result = await fn()
                except retry.exceptions as exc:
                    retry.process_exception(exc)

    if "matches" in testcase:
        assert result == 5
    else:
        assert result is None
