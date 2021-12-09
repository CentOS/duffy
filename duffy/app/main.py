import logging

from fastapi import FastAPI

from .controllers import chassis, node, session, tenant

log = logging.getLogger(__name__)
app = FastAPI()

# API v1

PREFIX = "/api/v1"

app.include_router(chassis.router, prefix=PREFIX)
app.include_router(node.router, prefix=PREFIX)
app.include_router(tenant.router, prefix=PREFIX)
app.include_router(session.router, prefix=PREFIX)
