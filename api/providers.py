"""Single switch point between mock and real core/ providers (USE_MOCKS).

T2.10 swaps each `raise NotImplementedError` below for the matching core/
import once Track A ships that module. Nothing else in api/ should branch
on settings.use_mocks - route handlers just call whatever this returns.
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

        return resolve_place
    raise NotImplementedError("core.places.resolve is not built yet (Track A) - set USE_MOCKS=true")


def routes_provider(settings: Settings) -> Callable[[RoutePlanRequest], RoutePlanResponse]:
    if settings.use_mocks:
        from api.mocks.routes import plan_routes

        return plan_routes
    raise NotImplementedError("core.routing/core.dispatch are not built yet (Track A) - set USE_MOCKS=true")


def zones_provider(settings: Settings) -> Callable[..., ZonesResponse]:
    if settings.use_mocks:
        from api.mocks.zones import get_zones

        return get_zones
    raise NotImplementedError("core.exposure is not built yet (Track A) - set USE_MOCKS=true")


def orders_provider(settings: Settings) -> Callable[[str, OrderAssignRequest], OrderAssignResponse]:
    if settings.use_mocks:
        from api.mocks.orders import assign_order

        return assign_order
    raise NotImplementedError("core.dispatch is not built yet (Track A) - set USE_MOCKS=true")
