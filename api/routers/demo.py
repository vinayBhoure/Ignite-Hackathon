from __future__ import annotations

from fastapi import APIRouter, HTTPException

from core.clock.demo_clock import apply_action, get_state
from core.schemas.demo import ClockActionRequest, ClockState

router = APIRouter(prefix="/api/demo")


@router.get("/clock", response_model=ClockState)
def read_clock() -> ClockState:
    return get_state()


@router.post("/clock", response_model=ClockState)
def update_clock(action: ClockActionRequest) -> ClockState:
    try:
        return apply_action(action)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
