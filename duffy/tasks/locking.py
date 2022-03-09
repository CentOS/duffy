from functools import wraps

from pottery import Redlock
from redis import Redis

from ..configuration import config


class Lock(Redlock):
    """Redlock, using Duffy configuration."""

    @wraps(Redlock.__init__)
    def __init__(self, *, masters=None, **kwargs):
        if not masters:
            masters = {Redis.from_url(config["tasks"]["locking"]["url"])}
        super().__init__(masters=masters, **kwargs)
