from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.security import require_rider
from core.alerts.push import MissingVapidConfig, get_vapid_public_key, subscribe
from core.auth import Session
from core.schemas.push import PushSubscribeRequest, PushSubscribeResponse, VapidPublicKeyResponse

router = APIRouter(prefix="/api/push")


@router.get("/vapid-public-key", response_model=VapidPublicKeyResponse)
def vapid_public_key() -> VapidPublicKeyResponse:
    try:
        return VapidPublicKeyResponse(public_key=get_vapid_public_key())
    except MissingVapidConfig as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/subscribe", response_model=PushSubscribeResponse)
def push_subscribe(req: PushSubscribeRequest, session: Session = Depends(require_rider)) -> PushSubscribeResponse:
    # Subscriptions always belong to the signed-in rider, never a body-supplied id.
    return subscribe(req.model_copy(update={"rider_id": session.sub}))
