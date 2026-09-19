from __future__ import annotations

from fastapi import APIRouter, Depends

from api.config import Settings, get_settings
from api.providers import places_provider
from core.schemas.places import PlaceResolveRequest, PlaceResolveResponse

router = APIRouter(prefix="/api/places")


@router.post("/resolve", response_model=PlaceResolveResponse)
def resolve(req: PlaceResolveRequest, settings: Settings = Depends(get_settings)) -> PlaceResolveResponse:
    provider = places_provider(settings)
    return provider(req.query)
