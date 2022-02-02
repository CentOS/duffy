import logging
import sys

from fastapi import FastAPI

from .. import database, tasks
from ..exceptions import DuffyConfigurationError
from ..version import __version__
from .controllers import node, session, tenant

log = logging.getLogger(__name__)

description = """
Duffy is the middle layer running [`ci.centos.org`](https://ci.centos.org). It provisions, tears
down and rebuilds physical and virtual machines which are used to run tests in the CentOS CI
Cluster.
"""

tags_metadata = [
    {"name": "nodes", "description": "Operations with physical and virtual nodes"},
    {"name": "sessions", "description": "Operations with sessions"},
    {"name": "tenants", "description": "Operations with tenants"},
]

app = FastAPI(
    title="Duffy",
    description=description,
    version=__version__,
    contact={"name": "CentOS CI", "email": "ci-sysadmin@centos.org"},
    openapi_tags=tags_metadata,
)


# API v1

PREFIX = "/api/v1"

app.include_router(node.router, prefix=PREFIX)
app.include_router(tenant.router, prefix=PREFIX)
app.include_router(session.router, prefix=PREFIX)


# DB model initialization


@app.on_event("startup")
async def init_model():
    try:
        database.init_sync_model()
        await database.init_async_model()
    except DuffyConfigurationError as exc:
        log.error("Configuration key missing or wrong: %s", exc.args[0])
        sys.exit(1)


# Celery tasks initialization


@app.on_event("startup")
def init_tasks():
    tasks.init_tasks()
