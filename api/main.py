"""FastAPI app shell: config, CORS, error envelope, /health.

No scoring logic here (CLAUDE.md architecture rule 1) - this module only
wires config, middleware and routers; every router calls into core/.

Run: uvicorn api.main:app --reload --port 8000
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.config import get_settings
from api.errors import register_error_handlers
from api.routers import alerts, auth, demo, health, navigation, orders, places, push, rider, routes, zones

STATIC_DIR = Path(__file__).parent / "static"


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

    app.include_router(auth.router)
    app.include_router(health.router)
    app.include_router(places.router)
    app.include_router(routes.router)
    app.include_router(zones.router)
    app.include_router(orders.router)
    app.include_router(demo.router)
    app.include_router(alerts.router)
    app.include_router(push.router)
    app.include_router(navigation.router)
    app.include_router(rider.router)

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/sw.js", include_in_schema=False)
    def service_worker() -> FileResponse:
        # Must be served from site root (not /static/sw.js): a service
        # worker's scope is its own path and below, so the rider app's push
        # notifications need it at "/", not under a subpath.
        return FileResponse(
            STATIC_DIR / "sw.js",
            media_type="application/javascript",
            headers={"Cache-Control": "no-cache"},
        )

    return app


app = create_app()
