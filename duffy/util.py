import asyncio
import enum
import logging
import time
from random import random
from typing import AsyncIterator, Iterator, Tuple, Union

log = logging.getLogger(__name__)


def camel_case_to_lower_with_underscores(camelcased: str) -> str:
    """Convert CamelCased names to lower_case_with_underscores."""
    chunk_positions = []
    prev_split_pos = 0

    for pos, (prev_is_upper, char_is_upper, next_is_upper) in enumerate(
        zip(
            (x.isupper() for x in camelcased[:-2]),
            (x.isupper() for x in camelcased[1:-1]),
            (x.isupper() for x in camelcased[2:]),
        ),
        start=1,
    ):
        if char_is_upper and (not prev_is_upper or not next_is_upper):
            chunk_positions.append((prev_split_pos, pos))
            prev_split_pos = pos

    chunk_positions.append((prev_split_pos, len(camelcased)))

    lowercased = camelcased.lower()

    return "_".join(
        lowercased[prev_split_pos:split_pos] for prev_split_pos, split_pos in chunk_positions
    )


def merge_dicts(*src_dicts):
    """Create a deep merge of several dictionaries.

    The structure of the dictionaries must be compatible, i.e. sub-dicts
    may not be differently typed between the source dictionaries."""
    if not src_dicts:
        raise ValueError("Can't merge nothing")

    if not all(isinstance(src_dict, dict) for src_dict in src_dicts):
        raise TypeError("All objects to be merged have to be dictionaries")

    res_dict = {}

    for src_dict in src_dicts:
        for key, src_value in src_dict.items():
            if isinstance(src_value, dict):
                if key not in res_dict:
                    res_dict[key] = src_value.copy()
                else:
                    res_dict[key] = merge_dicts(res_dict[key], src_value)
            elif key in res_dict and isinstance(res_dict[key], dict):
                raise TypeError("All objects to be merged have to be dictionaries")
            else:
                res_dict[key] = src_value

    return res_dict


class SentinelType(enum.Enum):
    UNSET = 1


UNSET = SentinelType.UNSET
"""A sentinel object for unset values."""


IntOrFloat = Union[int, float]


class RetryContext:
    """A wrapper for code blocks that should be retried on certain exceptions.

    Use it e.g. like this:

        async with RetryContext(exceptions=RuntimeError) as retry:
            async for attempt in retry.attempts:
                # ... set up the things ...
                try:
                    # ... do the things ...
                except retry.exceptions as exc:
                    # ... undo the things ...
                    retry.process_exception(exc)
                finally:
                    # ... tear down the things ...

    Subclass it e.g. to inspect caught exceptions further in
    process_exception(), making a decision whether to re-raise or continue
    with attempts.
    """

    exceptions: Union[Exception, Tuple[Exception]] = Exception
    no_attempts: int = 5
    delay_min: IntOrFloat = 0.1
    delay_max: IntOrFloat = 1.6
    delay_backoff_factor: IntOrFloat = 2
    delay_add_fuzz: IntOrFloat = 0.3

    def __init__(
        self,
        *,
        exceptions: Union[Exception, Tuple[Exception]] = None,
        no_attempts: int = None,
        delay_min: IntOrFloat = None,
        delay_max: IntOrFloat = None,
        delay_backoff_factor: IntOrFloat = None,
        delay_add_fuzz: IntOrFloat = None,
    ):
        self._is_async = None

        if exceptions is not None:
            self.exceptions = exceptions

        if no_attempts is not None:
            self.no_attempts = no_attempts

        if delay_min is not None:
            self.delay_min = delay_min

        if delay_max is not None:
            self.delay_max = delay_max

        if delay_backoff_factor is not None:
            self.delay_backoff_factor = delay_backoff_factor

        if delay_add_fuzz is not None:
            self.delay_add_fuzz = delay_add_fuzz

    def __enter__(self):
        self._is_async = False
        self._exc = None
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    async def __aenter__(self):
        self._is_async = True
        self._exc = None
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        pass

    async def _async_attempts(self) -> AsyncIterator[int]:
        delay = self.delay_min

        for attempt in range(1, self.no_attempts + 1):
            log.debug("[%r] Attempt %d of %d", self, attempt, self.no_attempts)

            self._exc = None

            yield attempt

            if not self._exc:
                break

            if attempt < self.no_attempts:
                log.debug("[%r] Retrying...", self)
                current_delay = delay + self.delay_add_fuzz * random()
                await asyncio.sleep(current_delay)
                delay = max(self.delay_max, delay * self.delay_backoff_factor)

        if self._exc:
            log.warning(
                "[%r] Number of attempts (%d) exhausted, re-raising.", self, self.no_attempts
            )
            raise self._exc

    def _sync_attempts(self) -> Iterator[int]:
        # This is the same as _async_attempts, only synchronous
        delay = self.delay_min

        for attempt in range(1, self.no_attempts + 1):
            log.debug("[%r] Attempt %d of %d", self, attempt, self.no_attempts)

            self._exc = None

            yield attempt

            if not self._exc:
                break

            if attempt < self.no_attempts:
                log.debug("[%r] Retrying...", self)
                current_delay = delay + self.delay_add_fuzz * random()
                time.sleep(current_delay)
                delay = max(self.delay_max, delay * self.delay_backoff_factor)

        if self._exc:
            log.warning(
                "[%r] Number of attempts (%d) exhausted, re-raising.", self, self.no_attempts
            )
            raise self._exc

    @property
    def attempts(self) -> Union[AsyncIterator[int], Iterator[int]]:
        if self._is_async:
            return self._async_attempts()
        else:
            return self._sync_attempts()

    def exception_matches(self, exc: Exception) -> bool:
        """Check if exception should cause a retry.

        This method can be used to inspect the exception and re-raise it if it
        doesn't match certain criteria.
        """
        return isinstance(exc, self.exceptions)

    def process_exception(self, exc: Exception) -> None:
        """Further process caught exception.

        This method needs to be called when an exception is caught.
        """
        exception_matches = self.exception_matches(exc)
        log.debug("[%r] Exception %r matches: %r", self, exc, exception_matches)
        if exception_matches:
            log.debug("[%r] Setting self._exc: %r", self, exc)
            self._exc = exc
        else:
            raise exc
