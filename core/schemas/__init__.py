"""Shared request/response contracts between core/, api/ and ui/.

v0 - frozen per docs/TrackB_Implementation_Plan.md T1.2. Only additive
changes after Track A sign-off.
"""

from core.schemas.alerts import AlertAckResponse, AlertOut, AlertStatus, AlertType
from core.schemas.common import (
    ErrorDetail,
    ErrorEnvelope,
    LatLng,
    MaskType,
    ReadingSource,
    RouteConfidence,
    SeverityBand,
    ZoneConfidence,
)
from core.schemas.demo import (
    ClockActionRequest,
    ClockActionType,
    ClockState,
    DemoResetResponse,
    MAX_SPEED,
    MIN_SPEED,
    SpikeRequest,
    SpikeResponse,
)
from core.schemas.orders import OrderAssignRequest, OrderAssignResponse
from core.schemas.places import (
    NEEDS_PICK_THRESHOLD,
    PlaceCandidate,
    PlaceResolveRequest,
    PlaceResolveResponse,
)
from core.schemas.push import (
    PushSubscribeRequest,
    PushSubscribeResponse,
    PushSubscription,
    PushSubscriptionKeys,
    VapidPublicKeyResponse,
)
from core.schemas.routes import (
    RouteOption,
    RoutePlanRequest,
    RoutePlanResponse,
    RouteRecommendation,
    RouteZoneSegment,
)
from core.schemas.zones import ZoneReadingOut, ZonesResponse

__all__ = [
    "AlertAckResponse",
    "AlertOut",
    "AlertStatus",
    "AlertType",
    "ClockActionRequest",
    "ClockActionType",
    "ClockState",
    "DemoResetResponse",
    "ErrorDetail",
    "ErrorEnvelope",
    "LatLng",
    "MAX_SPEED",
    "MIN_SPEED",
    "MaskType",
    "NEEDS_PICK_THRESHOLD",
    "OrderAssignRequest",
    "OrderAssignResponse",
    "PlaceCandidate",
    "PlaceResolveRequest",
    "PlaceResolveResponse",
    "PushSubscribeRequest",
    "PushSubscribeResponse",
    "PushSubscription",
    "PushSubscriptionKeys",
    "ReadingSource",
    "RouteConfidence",
    "RouteOption",
    "RoutePlanRequest",
    "RoutePlanResponse",
    "RouteRecommendation",
    "RouteZoneSegment",
    "SeverityBand",
    "SpikeRequest",
    "SpikeResponse",
    "VapidPublicKeyResponse",
    "ZoneConfidence",
    "ZoneReadingOut",
    "ZonesResponse",
]
