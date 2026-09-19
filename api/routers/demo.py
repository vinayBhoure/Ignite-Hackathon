from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.security import require_dispatcher
from core.clock.demo_clock import apply_action, get_state
from core.clock.spikes import inject_spike, reset_spikes
from core.schemas.demo import ClockActionRequest, ClockState, DemoResetResponse, SpikeRequest, SpikeResponse

router = APIRouter(prefix="/api/demo", dependencies=[Depends(require_dispatcher)])


@router.get("/clock", response_model=ClockState)
def read_clock() -> ClockState:
    return get_state()


@router.post("/clock", response_model=ClockState)
def update_clock(action: ClockActionRequest) -> ClockState:
    try:
        return apply_action(action)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/spike", response_model=SpikeResponse)
def spike(req: SpikeRequest) -> SpikeResponse:
    return inject_spike(req)


@router.post("/reset", response_model=DemoResetResponse)
def reset() -> DemoResetResponse:
    return reset_spikes()
