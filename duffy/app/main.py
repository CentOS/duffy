import logging

from fastapi import FastAPI

from .controllers import project

log = logging.getLogger(__name__)
app = FastAPI()

# API v1

PREFIX = "/api/v1"

app.include_router(project.router, prefix=PREFIX)
