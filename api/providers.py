"""Single switch point between mock and real core/ providers (USE_MOCKS).

Real paths use core/navigation (Google Routes + Geocoding, dose scoring on
the replayed zone layer) and core/clock/zones. Nothing else in api/ or ui/
should branch on settings.use_mocks - callers just use what this returns.
"""

from __future__ import annotations

from typing import Callable

from api.config import Settings
from core.schemas.orders import OrderAssignRequest, OrderAssignResponse
from core.schemas.places import PlaceResolveResponse
from core.schemas.routes import RoutePlanRequest, RoutePlanResponse
from core.schemas.zones import ZonesResponse


def places_provider(settings: Settings) -> Callable[[str], PlaceResolveResponse]:
    if settings.use_mocks:
        from api.mocks.places import resolve_place
    else:
        from core.navigation.places import resolve_place
    return resolve_place


def routes_provider(settings: Settings) -> Callable[[RoutePlanRequest], RoutePlanResponse]:
    if settings.use_mocks:
        from api.mocks.routes import plan_routes
    else:
        from core.navigation.planner import plan as plan_routes
    return plan_routes


def zones_provider(settings: Settings) -> Callable[..., ZonesResponse]:
    if settings.use_mocks:
        from api.mocks.zones import get_zones
    else:
        from core.clock.zones import get_zones
    return get_zones


def orders_provider(settings: Settings) -> Callable[[str, OrderAssignRequest], OrderAssignResponse]:
    if settings.use_mocks:
        from api.mocks.orders import assign_order
    else:
        from core.navigation.assignments import assign_order
    return assign_order
