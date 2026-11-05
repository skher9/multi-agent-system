"""The project runs work on: its GitHub repo and Jira board, for the dashboard."""

from fastapi import APIRouter, Depends

from api.auth import current_user
from api.routes.runs import ProjectLinks, project_links

# Logged-in website users only (api/auth.py)
router = APIRouter(prefix="/project", tags=["project"], dependencies=[Depends(current_user)])


@router.get("")
def get_project() -> ProjectLinks:
    return project_links()
