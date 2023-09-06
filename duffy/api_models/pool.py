from abc import ABC
from typing import List, Union

from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import Annotated

from .common import APIResult

# pool model


class PoolLevelsModel(BaseModel):
    provisioning: Annotated[int, Field(ge=0)]
    ready: Annotated[int, Field(ge=0)]
    contextualizing: Annotated[int, Field(ge=0)]
    deployed: Annotated[int, Field(ge=0)]
    deprovisioning: Annotated[int, Field(ge=0)]


class PoolBase(BaseModel, ABC):
    name: str
    fill_level: Annotated[int, Field(ge=0)] = Field(alias="fill-level")
    model_config = ConfigDict(extra="forbid")


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
