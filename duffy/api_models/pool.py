from abc import ABC
from typing import List, Union

from pydantic import BaseModel, Field, conint

from .common import APIResult

# pool model


class PoolLevelsModel(BaseModel):
    provisioning: conint(ge=0)
    ready: conint(ge=0)
    contextualizing: conint(ge=0)
    deployed: conint(ge=0)
    deprovisioning: conint(ge=0)


class PoolBase(BaseModel, ABC):
    name: str
    fill_level: conint(ge=0) = Field(alias="fill-level")

    class Config:
        extra = "forbid"


class PoolConciseModel(PoolBase):
    pass


class PoolVerboseModel(PoolConciseModel):
    levels: PoolLevelsModel


PoolModel = Union[PoolConciseModel, PoolVerboseModel]


# API results


class PoolResult(APIResult):
    pool: PoolModel


class PoolResultCollection(APIResult):
    pools: List[PoolModel]
