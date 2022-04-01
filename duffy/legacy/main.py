from typing import Optional

import httpx
from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from starlette.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
)

from ..configuration import config
from ..version import __version__
from .api_models import Credentials
from .auth import req_credentials, req_credentials_optional

description = """
Duffy is the middle layer running [`ci.centos.org`](https://ci.centos.org). It provisions, tears
down and rebuilds physical and virtual machines are used to run tests in the CentOS CI Cluster.

This metaclient exposes older endpoints for legacy support and connects them to the path operations
introduced by the newer version of the Duffy endpoint, until the support for the older endpoints is
deprecated.
"""

app = FastAPI(
    title="Duffy Metaclient for Legacy Support",
    description=description,
    version=__version__,
    contact={"name": "CentOS CI", "email": "ci-sysadmin@centos.org"},
)


@app.get("/Node/get")
async def request_nodes(
    ver: str = "7",
    arch: str = "x86_64",
    count: int = 1,
    flavor: str = None,
    cred: Credentials = Depends(req_credentials),
):
    ver = "".join(i.replace("-", "") for i in ver)
    if arch in ["aarch64", "ppc64", "ppc64le"]:
        if not flavor:
            flavor = "medium"
        nodes_specs = [{"quantity": count, "pool": f"virtual-centos{ver}-{arch}-{flavor}"}]
    else:
        nodes_specs = [{"quantity": count, "pool": f"physical-centos{ver}-{arch}"}]

    async with httpx.AsyncClient() as client:
        dest = config["metaclient"]["dest"].rstrip("/")
        response = await client.post(
            f"{dest}/api/v1/sessions",
            json={"nodes_specs": nodes_specs},
            auth=(cred.username, cred.password),
        )

    if response.status_code == HTTP_201_CREATED:
        session = response.json()["session"]
        legacy_result = {
            "ssid": session["id"],
            "hosts": [node["hostname"] for node in session["nodes"]],
        }
        return legacy_result
    else:
        return JSONResponse(status_code=HTTP_200_OK, content="Failed to allocate nodes")


@app.get("/Node/done")
async def return_nodes_on_completion(
    ssid: str = None, cred: Credentials = Depends(req_credentials)
):
    if ssid:
        async with httpx.AsyncClient() as client:
            dest = config["metaclient"]["dest"].rstrip("/")
            response = await client.put(
                f"{dest}/api/v1/sessions/{ssid}",
                json={"active": False},
                auth=(cred.username, cred.password),
            )
        if response.status_code == HTTP_200_OK:
            return JSONResponse(status_code=HTTP_200_OK, content="Done")
        elif (
            response.status_code == HTTP_401_UNAUTHORIZED
            or response.status_code == HTTP_403_FORBIDDEN
        ):
            return JSONResponse(
                status_code=HTTP_403_FORBIDDEN, content={"msg": "Invalid duffy key"}
            )
        else:
            return JSONResponse(
                status_code=HTTP_200_OK, content="Failed to return nodes on completion"
            )
    else:
        return JSONResponse(status_code=HTTP_200_OK, content="Some parameters are absent")


@app.get("/Node/fail")
async def extend_nodes_on_failure(ssid: str = None, cred: Credentials = Depends(req_credentials)):
    if ssid:
        async with httpx.AsyncClient() as client:
            dest = config["metaclient"]["dest"].rstrip("/")
            response = await client.put(
                f"{dest}/api/v1/sessions/{ssid}",
                json={"expires_at": "+6h"},
                auth=(cred.username, cred.password),
            )
        if response.status_code == HTTP_200_OK:
            return JSONResponse(status_code=HTTP_200_OK, content="Done")
        elif (
            response.status_code == HTTP_401_UNAUTHORIZED
            or response.status_code == HTTP_403_FORBIDDEN
        ):
            return JSONResponse(
                status_code=HTTP_403_FORBIDDEN, content={"msg": "Invalid duffy key"}
            )
        else:
            return JSONResponse(status_code=HTTP_200_OK, content="Failed to change expiration time")
    else:
        return JSONResponse(status_code=HTTP_200_OK, content="Some parameters are absent")


@app.get("/Inventory")
async def get_nodes(cred: Optional[Credentials] = Depends(req_credentials_optional)):
    if cred:
        auth = cred.username, cred.password
        async with httpx.AsyncClient() as client:
            dest = config["metaclient"]["dest"].rstrip("/")
            response = await client.get(f"{dest}/api/v1/sessions", auth=auth)
        if response.status_code == HTTP_200_OK:
            retvals = [
                [session_node.get("hostname"), session.get("id")]
                for session in response.json()["sessions"]
                for session_node in session["nodes"]
            ]
            return JSONResponse(status_code=HTTP_200_OK, content=retvals)
        elif (
            response.status_code == HTTP_401_UNAUTHORIZED
            or response.status_code == HTTP_403_FORBIDDEN
        ):
            return JSONResponse(
                status_code=HTTP_403_FORBIDDEN, content={"msg": "Invalid duffy key"}
            )
        else:
            # Yes, the legacy API returns 200 here.
            return JSONResponse(
                status_code=HTTP_200_OK, content="Failed to retrieve inventory of nodes"
            )
    else:
        auth = None
        async with httpx.AsyncClient() as client:
            dest = config["metaclient"]["dest"].rstrip("/")
            response = await client.get(f"{dest}/api/v1/sessions", auth=auth)
        if response.status_code == HTTP_200_OK:
            retvals = [
                [
                    session_node.get("id"),  # sch.data['id']
                    session_node.get("hostname"),  # sch.data['hostname']
                    session_node.get("ipaddr"),  # sch.data['ip']
                    None,  # sch.data['chassis']
                    0,  # sch.data['used_count']
                    session_node.get("state"),  # sch.data['state']
                    # Yes, 'comment' contains the session id. Don't ask.
                    session.get("id"),  # sch.data['comment']
                    None,  # sch.data['distro']
                    None,  # sch.data['rel']
                    None,  # sch.data['ver']
                    None,  # sch.data['arch']
                    session_node.get("pool"),  # sch.data['pool']
                    None,  # sch.data['console_port']
                    None,  # sch.data['flavor']
                ]
                for session in response.json()["sessions"]
                for session_node in session["nodes"]
            ]
            return JSONResponse(status_code=HTTP_200_OK, content=retvals)
        else:
            # Yes, the legacy API returns 200 here.
            return JSONResponse(
                status_code=HTTP_200_OK, content="Failed to retrieve inventory of nodes"
            )
