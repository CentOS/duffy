from abc import ABC
from typing import List

from pydantic import BaseModel

from .common import APIResult, CreatableMixin, RetirableMixin

# project model


class ProjectBase(BaseModel, ABC):
    name: str
    ssh_key: str

    class Config:
        orm_mode = True


class ProjectCreateModel(ProjectBase):
    pass


class ProjectModel(ProjectBase, CreatableMixin, RetirableMixin):
    id: int


# API results


class ProjectResult(APIResult):
    project: ProjectModel


class ProjectResultCollection(APIResult):
    projects: List[ProjectModel]
