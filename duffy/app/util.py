import logging
from typing import Tuple, Union

try:
    import asyncpg
except ImportError:  # pragma: no cover
    asyncpg = None
from sqlalchemy.exc import DBAPIError

from ..configuration import config_get
from ..util import RetryContext

log = logging.getLogger(__name__)


class ConfigRetryContext(RetryContext):
    def __init__(self, *, exceptions: Union[Exception, Tuple[Exception]] = None, **kwargs):
        for key in (
            "no-attempts",
            "delay-min",
            "delay-max",
            "delay-backoff-factor",
            "delay-add-fuzz",
        ):
            key_ = key.replace("-", "_")
            if key_ not in kwargs:
                kwargs[key_] = config_get(f"app.retries.{key}", f"defaults.retries.{key}")
        super().__init__(exceptions=exceptions, **kwargs)


class SerializationErrorRetryContext(ConfigRetryContext):
    exceptions = DBAPIError

    def exception_matches(self, exc):
        log.debug("[%r] Matching %r...", self, exc)
        if not (super().exception_matches(exc) and asyncpg):
            log.debug("[%r] Smoke tests failed", self)
            return False

        result = getattr(exc.orig, "pgcode", None) == asyncpg.SerializationError.sqlstate
        log.debug("[%r] Match result: %r", self, result)

        return result
