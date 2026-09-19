from __future__ import annotations

from fastapi import APIRouter, Depends

from api.config import Settings, get_settings
from api.providers import routes_provider
from core.schemas.routes import RoutePlanRequest, RoutePlanResponse

router = APIRouter(prefix="/api/routes")


@router.post("/plan", response_model=RoutePlanResponse)
def plan(req: RoutePlanRequest, settings: Settings = Depends(get_settings)) -> RoutePlanResponse:
    provider = routes_provider(settings)
    return provider(req)
