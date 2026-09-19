"""Live navigation endpoints: the rider's own orders, turn-by-turn state and
reroute; and a dispatcher fleet feed for the console's live map."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.security import require_dispatcher, require_rider, require_session
from core.auth import Session
from core.clock.demo_clock import get_state
from core.schemas.demo import ClockState
from core.navigation.assignments import (
    NotFound,
    active_assignments,
    navigation,
    reroute_commit,
    reroute_preview,
    rider_orders,
)
from core.navigation.google import RoutingUnavailable
from core.schemas.navigation import AssignmentSummary, NavigationState, RerouteCommit, ReroutePreview

router = APIRouter(tags=["navigation"])


def _guard(fn, *args):
    try:
        return fn(*args)
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RoutingUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/api/clock", response_model=ClockState, dependencies=[Depends(require_session)])
def clock() -> ClockState:
    """Read-only replay clock for any signed-in user (controls stay dispatcher-only)."""
    return get_state()


@router.get("/api/rider/orders", response_model=list[AssignmentSummary])
def my_orders(session: Session = Depends(require_rider)) -> list[AssignmentSummary]:
    return rider_orders(session.sub)


@router.get("/api/rider/orders/{order_id}/navigation", response_model=NavigationState)
def my_navigation(order_id: str, session: Session = Depends(require_rider)) -> NavigationState:
    return _guard(navigation, order_id, session.sub)


@router.get("/api/rider/orders/{order_id}/reroute", response_model=ReroutePreview)
def my_reroute_preview(order_id: str, session: Session = Depends(require_rider)) -> ReroutePreview:
    return _guard(reroute_preview, order_id, session.sub)


@router.post("/api/rider/orders/{order_id}/reroute", response_model=NavigationState)
def my_reroute(order_id: str, body: RerouteCommit, session: Session = Depends(require_rider)) -> NavigationState:
    return _guard(reroute_commit, order_id, session.sub, body.route_id)


@router.get("/api/fleet/live", response_model=list[NavigationState], dependencies=[Depends(require_dispatcher)])
def fleet_live() -> list[NavigationState]:
    out = []
    for a in active_assignments():
        try:
            out.append(navigation(a.order_id))
        except (NotFound, RoutingUnavailable):
            continue
    return out
