"""The one place every Streamlit page calls into for data (T2.1).

CLAUDE.md: "Streamlit calls the core package directly; the REST layer serves
the rider app and scripted tests." So places/routes/zones/orders reuse
api/providers.py's USE_MOCKS switch directly (no HTTP round trip, no
scoring logic duplicated) - both call the exact same mock or core/ function
the API does. Clock, spikes, alerts and push always hit core/ directly, same
as api/, since they aren't behind USE_MOCKS either.
"""

from __future__ import annotations

from datetime import datetime

from dotenv import load_dotenv

# Every ui/ page imports this module before touching core/, so this is the
# one place that guarantees .env is loaded no matter which page Streamlit
# runs first (unlike api/main.py, `streamlit run` never imports api.main).
load_dotenv()

from api.config import get_settings
from api.providers import orders_provider, places_provider, routes_provider, zones_provider
from core.alerts.evaluator import ack_alert, list_alerts
from core.auth import Session, issue_token, verify_token
from core.clock.demo_clock import apply_action, get_state
from core.clock.spikes import inject_spike, reset_spikes
from core.navigation import assignments as nav
from core.schemas.alerts import AlertAckResponse, AlertOut
from core.schemas.navigation import AssignmentSummary, RiderSummary, RouteZoneAhead
from core.schemas.demo import ClockActionRequest, ClockState, DemoResetResponse, SpikeRequest, SpikeResponse
from core.schemas.orders import OrderAssignRequest, OrderAssignResponse
from core.schemas.places import PlaceResolveResponse
from core.schemas.routes import RoutePlanRequest, RoutePlanResponse
from core.schemas.zones import ZonesResponse


def resolve_place(query: str) -> PlaceResolveResponse:
    return places_provider(get_settings())(query)


def plan_routes(req: RoutePlanRequest) -> RoutePlanResponse:
    return routes_provider(get_settings())(req)


def get_zones(ts: datetime | None = None) -> ZonesResponse:
    return zones_provider(get_settings())(ts)


def assign_order(order_id: str, req: OrderAssignRequest) -> OrderAssignResponse:
    return orders_provider(get_settings())(order_id, req)


def get_clock_state() -> ClockState:
    return get_state()


def update_clock(action: ClockActionRequest) -> ClockState:
    return apply_action(action)


def create_spike(req: SpikeRequest) -> SpikeResponse:
    return inject_spike(req)


def clear_spikes() -> DemoResetResponse:
    return reset_spikes()


def get_alerts(status: str | None = None, rider_id: str | None = None) -> list[AlertOut]:
    return list_alerts(status=status, rider_id=rider_id)


def acknowledge_alert(alert_id: str) -> AlertAckResponse:
    return ack_alert(alert_id)


def using_mocks() -> bool:
    return get_settings().use_mocks


def settings():
    return get_settings()


# --- auth -------------------------------------------------------------------


def verify_session(token: str | None) -> Session | None:
    return verify_token(token)


def session_token(session: Session) -> str:
    return issue_token(session)


# --- fleet / live navigation (always real: these read what dispatch wrote) ---


def list_riders() -> list[RiderSummary]:
    return nav.list_riders()


def active_assignments() -> list[AssignmentSummary]:
    return nav.active_assignments()


def zones_ahead(order_id: str) -> list[RouteZoneAhead]:
    return nav.zones_ahead(order_id)
