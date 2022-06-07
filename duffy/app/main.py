import logging
import sys

from fastapi import FastAPI

from .. import database, tasks
from ..exceptions import DuffyConfigurationError
from ..nodes.pools import NodePool
from ..version import __version__
from .controllers import node, pool, session, tenant

log = logging.getLogger(__name__)

description = """
Duffy is the middle layer running [`ci.centos.org`](https://ci.centos.org). It provisions, tears
down and rebuilds physical and virtual machines which are used to run tests in the CentOS CI
Cluster.
"""

tags_metadata = [
    {"name": "sessions", "description": "Operations on sessions"},
    {"name": "pools", "description": "Operations on node pools"},
    {"name": "nodes", "description": "Operations on physical and virtual nodes"},
    {"name": "tenants", "description": "Operations on tenants"},
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

app.include_router(session.router, prefix=PREFIX)
app.include_router(pool.router, prefix=PREFIX)
app.include_router(node.router, prefix=PREFIX)
app.include_router(tenant.router, prefix=PREFIX)


# Post-process configuration


@app.on_event("startup")
async def post_process_config():
    NodePool.process_configuration()


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
