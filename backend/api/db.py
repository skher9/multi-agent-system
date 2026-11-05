"""The database, for API routes that read it (FastAPI dependency)."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session, sessionmaker

from api.config import get_settings
from db.session import make_session_factory


def session_factory() -> sessionmaker[Session]:
    url = get_settings().database_url
    if url is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "database is not configured")
    return make_session_factory(url.get_secret_value())


SessionFactory = Annotated[sessionmaker[Session], Depends(session_factory)]
