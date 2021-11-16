import logging

from fastapi import FastAPI

log = logging.getLogger(__name__)
app = FastAPI()


@app.get("/Node/get")
@app.get("/api/v1/node/get")
async def get_a_node():
    return {"name": "get_a_node"}


@app.get("/Node/done")
@app.get("/api/v1/node/done")
async def node_is_done():
    return {"name": "node_is_done"}


@app.get("/Node/fail")
@app.get("/api/v1/node/fail")
async def node_failed():
    return {"name": "node_failed"}


@app.get("/Inventory")
@app.get("/api/v1/node")
async def get_node_inventory():
    return {"name": "get_node_inventory"}
