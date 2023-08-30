from logging import Filter, LogRecord

from .middleware import request_id_ctxvar


class RequestIdFilter(Filter):
    def filter(self, record: LogRecord) -> bool:
        record.request_id = request_id_ctxvar.get()
        return True
