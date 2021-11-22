from contextlib import contextmanager
from typing import Any


@contextmanager
def noop_context(context_value: Any = None):
    """An 'empty' context manager, can be used as a stand-in."""
    yield context_value
