from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from api.config import Settings, get_settings
from api.providers import zones_provider
from core.schemas.zones import ZonesResponse

router = APIRouter(prefix="/api")


@router.get("/zones", response_model=ZonesResponse)
def zones(
    ts: datetime | None = Query(default=None),
    settings: Settings = Depends(get_settings),
) -> ZonesResponse:
    provider = zones_provider(settings)
    return provider(ts)
