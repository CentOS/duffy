import re
from typing import Dict, Optional

import httpx
import jinja2
from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from starlette.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
)

from ..configuration import config
from ..configuration.validation import LegacyPoolMapModel
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


def lookup_pool_from_map(**req_specs: Dict[str, Optional[str]]) -> Optional[str]:
    req_specs = {k: v for k, v in req_specs.items() if v is not None}
    pool_template = pool = None

    for item in config["metaclient"]["poolmap"]:
        map_spec = LegacyPoolMapModel(**item)

        for sel_key in ("ver", "arch", "flavor"):
            sel_value = getattr(map_spec, sel_key)
            req_value = req_specs.get(sel_key)
            if sel_value:
                if req_value is None:
                    break
                elif isinstance(sel_value, re.Pattern):
                    sel_match = sel_value.match(req_value)
                    if not sel_match:
                        break
                elif sel_value != req_value:
                    break
        else:
            pool_template = map_spec.pool

        if pool_template:
            pool = jinja2.Template(pool_template).render(**req_specs)
            break

    return pool


def mangle_hostname(hostname: str):
    mangle_hostname_template = config["metaclient"].get("mangle_hostname")
    if not mangle_hostname_template:
        return hostname

    return jinja2.Template(mangle_hostname_template).render(hostname=hostname or "")


@app.get("/Node/get")
async def request_nodes(
    ver: str = "7",
    arch: str = "x86_64",
    count: int = 1,
    flavor: str = None,
    cred: Credentials = Depends(req_credentials),
):
    pool = lookup_pool_from_map(ver=ver, arch=arch, flavor=flavor)
    nodes_specs = [{"quantity": count, "pool": pool}]

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
            "hosts": [mangle_hostname(node["hostname"]) for node in session["nodes"]],
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
                [mangle_hostname(session_node.get("hostname")), session.get("id")]
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
                    mangle_hostname(session_node.get("hostname")),  # sch.data['hostname']
                    session_node.get("ipaddr"),  # sch.data['ip']
                    None,  # sch.data['chassis']
                    0,  # sch.data['used_count']
                    session_node.get("state"),  # sch.data['state']
                    # Yes, 'comment' contains the session id. Don't ask.
                    str(session.get("id")),  # sch.data['comment']
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
