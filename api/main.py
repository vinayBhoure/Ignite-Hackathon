"""FastAPI app shell: config, CORS, error envelope, /health.

No scoring logic here (CLAUDE.md architecture rule 1) - this module only
wires config, middleware and routers; every router calls into core/.

Run: uvicorn api.main:app --reload --port 8000
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import get_settings
from api.errors import register_error_handlers
from api.routers import health, orders, places, routes, zones


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_settings().validate()
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title="Exposure-Aware Fleet Routing API", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_error_handlers(app)

    app.include_router(health.router)
    app.include_router(places.router)
    app.include_router(routes.router)
    app.include_router(zones.router)
    app.include_router(orders.router)

    return app


app = create_app()
