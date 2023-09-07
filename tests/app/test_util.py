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
    (
        "matches",
        "no-match-other-toplevel-exception",
        "no-match-other-toplevel-exception-programming-error",
        "no-match-other-wrapped-exception",
        "no-match-other-pgcode",
        "no-match-no-asyncpg",
    ),
)
@mock.patch("duffy.app.util.config_get", mock_config_get)
async def test_serializationerror_retry_context(testcase, caplog):
    hide_asyncpg = nullcontext()

    toplvl_exc = catch_exceptions = None
    orig_exc = mock.MagicMock(spec=SerializationError, pgcode=SerializationError.sqlstate)

    if "matches" in testcase:
        expectation = nullcontext()
    else:
        if "other-toplevel-exception" in testcase:
            toplvl_exc = RuntimeError("this is breaking")
            expectation = pytest.raises(RuntimeError)
            if "programming-error" in testcase:
                catch_exceptions = Exception
        else:
            expectation = pytest.raises(DBAPIError)
            if "other-wrapped-exception" in testcase:
                orig_exc = RuntimeError("this is breaking, but wrapped")
            elif "match-other-pgcode" in testcase:
                orig_exc.pgcode = str(orig_exc.pgcode) + "Boo"
            elif "no-asyncpg" in testcase:
                expectation = pytest.raises(AttributeError)
                hide_asyncpg = mock.patch.object(duffy.app.util, "asyncpg", None)

    if not toplvl_exc:
        toplvl_exc = DBAPIError("", "", orig_exc)

    mocked_fn = mock.MagicMock()
    mocked_fn.side_effect = [toplvl_exc, 5]

    async def fn():
        return mocked_fn()

    result = None

    with expectation, hide_asyncpg, caplog.at_level("DEBUG"):
        async with SerializationErrorRetryContext() as retry:
            if not catch_exceptions:
                catch_exceptions = retry.exceptions
            async for attempt in retry.attempts:
                try:
                    result = await fn()
                # NB: The following should be `except retry.exceptions as exc` in real code, but we
                # want to test that programming errors like this at least get logged.
                except catch_exceptions as exc:
                    retry.process_exception(exc)

    if "matches" in testcase:
        assert result == 5
    else:
        assert result is None
        if "programming-error" in testcase:
            assert "Smoke tests failed" in caplog.text
