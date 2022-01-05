from fastapi import HTTPException, Security
from fastapi.security import APIKeyQuery
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from ..configuration import config
from .api_models import Credentials


def _req_credentials_factory(optional: bool = False):
    security = APIKeyQuery(name="key", auto_error=not optional)

    def _req_credentials(key: str = Security(security)):
        if not key:
            if not optional:
                raise HTTPException(HTTP_401_UNAUTHORIZED)
            else:
                return None

        usermap = config["metaclient"]["usermap"]
        if key not in usermap:
            raise HTTPException(HTTP_403_FORBIDDEN)
        username, password = usermap[key], key
        return Credentials(username=username, password=password)

    return _req_credentials


req_credentials = _req_credentials_factory()
req_credentials_optional = _req_credentials_factory(optional=True)
