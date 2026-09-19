from __future__ import annotations

from fastapi import APIRouter, Depends

from api.config import Settings, get_settings

router = APIRouter()


@router.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict:
    return {"status": "ok", "use_mocks": settings.use_mocks}
