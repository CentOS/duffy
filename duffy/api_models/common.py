from abc import ABC
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class CreatableMixin(BaseModel):
    created_at: datetime


class RetirableMixin(BaseModel):
    retired_at: Optional[datetime]
    active: bool


class APIResultAction(str, Enum):
    delete = "delete"
    get = "get"
    post = "post"
    put = "put"


class APIResult(BaseModel, ABC):
    action: Optional[APIResultAction]
