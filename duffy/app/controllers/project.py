"""
This is the project controller.
"""

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from starlette.status import HTTP_201_CREATED, HTTP_404_NOT_FOUND, HTTP_409_CONFLICT

from ...api_models import ProjectCreateModel, ProjectResult, ProjectResultCollection
from ...database import DBSession
from ...database.model import Project

router = APIRouter(prefix="/projects")


# http get http://localhost:8080/api/v1/projects
@router.get("", response_model=ProjectResultCollection)
async def get_all_projects():
    """
    Return all projects
    """
    query = select(Project)
    results = await DBSession.execute(query)

    return {"action": "get", "projects": results.scalars().all()}


# http get http://localhost:8080/api/v1/projects/2
@router.get("/{id}", response_model=ProjectResult)
async def get_project(id: int):
    """
    Return the project with the specified ID
    """
    project = (await DBSession.execute(select(Project).filter_by(id=id))).scalar_one_or_none()

    if not project:
        raise HTTPException(HTTP_404_NOT_FOUND)

    return {"action": "get", "project": project}


# http --json post http://localhost:8080/api/v1/projects name="A Project with a unique name"
@router.post("", status_code=HTTP_201_CREATED, response_model=ProjectResult)
async def create_project(data: ProjectCreateModel):
    """
    Create a project with the specified name
    """
    project = Project(name=data.name, ssh_key=data.ssh_key)

    DBSession.add(project)
    try:
        await DBSession.commit()
    except IntegrityError as exc:
        raise HTTPException(HTTP_409_CONFLICT, str(exc))

    return {"action": "post", "project": project}


# http delete http://localhost:8080/api/v1/project/2
@router.delete("/{id}", response_model=ProjectResult)
async def delete_project(id: int):
    """
    Delete the project with the specified ID
    """
    project = (await DBSession.execute(select(Project).filter_by(id=id))).scalar_one_or_none()

    if not project:
        raise HTTPException(HTTP_404_NOT_FOUND)

    await DBSession.delete(project)
    await DBSession.commit()

    return {"action": "delete", "project": project}
