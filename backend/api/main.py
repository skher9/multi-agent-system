"""FastAPI entry point. Run with: uv run uvicorn api.main:app --reload"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import get_settings
from api.routes import health, jobs, learn, project, realtime, runs


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Multi-Agent System API",
        version="0.1.0",
        # The OpenAPI spec is served at /openapi.json; the web app generates its types from it.
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(jobs.router)
    app.include_router(learn.router)
    app.include_router(project.router)
    app.include_router(realtime.router)
    app.include_router(runs.router)
    return app


app = create_app()
