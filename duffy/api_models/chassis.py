from abc import ABC
from typing import List, Optional

from pydantic import BaseModel

from .common import APIResult, CreatableMixin, RetirableMixin

# chassis model


class ChassisBase(BaseModel, ABC):
    name: str
    description: Optional[str]

    class Config:
        orm_mode = True


class ChassisCreateModel(ChassisBase):
    pass


class ChassisModel(ChassisBase, CreatableMixin, RetirableMixin):
    id: int


# API results


class ChassisResult(APIResult):
    chassis: ChassisModel


class ChassisResultCollection(APIResult):
    chassis: List[ChassisModel]
