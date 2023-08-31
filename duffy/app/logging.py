import uuid
from collections import UserString
from logging import Filter, LogRecord
from typing import Any, Dict

from .middleware import request_id_ctxvar


class LazyShortRequestId(UserString):
    def __init__(self, request_id: uuid.UUID) -> None:
        self._request_id = request_id

    def __str__(self) -> str:
        if not hasattr(self, "_short"):
            self._short = str(self._request_id)[-12:]
        return self._short

    @property
    def data(self):
        return self.__str__()


class LazyFormattedString(UserString):
    def __init__(self, fmt: str, **kwargs: Dict[str, Any]) -> None:
        self._fmt = fmt
        self._kwargs = kwargs

    def __str__(self) -> str:
        if not hasattr(self, "_formatted"):
            self._formatted = self._fmt.format(**self._kwargs)
        return self._formatted

    @property
    def data(self):
        return self.__str__()


class RequestIdFilter(Filter):
    def filter(self, record: LogRecord) -> bool:
        record.request_id = rid = request_id_ctxvar.get()

        if rid:
            # Use lazily evaluated objects here, so they’re only formatted when actually accessed.
            record.short_request_id = srid = LazyShortRequestId(rid)

            # Note the trailing spaces
            record.request_id_optional = LazyFormattedString("[{rid}] ", rid=rid)
            record.short_request_id_optional = LazyFormattedString("[{srid}] ", srid=srid)
        else:
            record.short_request_id = None
            record.request_id_optional = record.short_request_id_optional = ""

        return True
