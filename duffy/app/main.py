import logging

from fastapi import FastAPI

from ..version import __version__
from .controllers import chassis, node, session, tenant

log = logging.getLogger(__name__)

description = """
Duffy is the middle layer running [`ci.centos.org`](https://ci.centos.org). It provisions, tears
down and rebuilds physical and virtual machines are used to run tests in the CentOS CI Cluster.
"""

tags_metadata = [
    {"name": "nodes", "description": "Operations with physical and virtual nodes"},
    {"name": "sessions", "description": "Operations with sessions"},
    {"name": "tenants", "description": "Operations with tenants"},
    {"name": "chassis", "description": "Operations with chassis"},
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

app.include_router(chassis.router, prefix=PREFIX)
app.include_router(node.router, prefix=PREFIX)
app.include_router(tenant.router, prefix=PREFIX)
app.include_router(session.router, prefix=PREFIX)
