from __future__ import annotations

from fastapi import APIRouter, Depends

from api.config import Settings, get_settings
from api.providers import orders_provider
from api.security import require_dispatcher
from core.schemas.orders import OrderAssignRequest, OrderAssignResponse

router = APIRouter(prefix="/api/orders", dependencies=[Depends(require_dispatcher)])


@router.post("/{order_id}/assign", response_model=OrderAssignResponse)
def assign(
    order_id: str,
    req: OrderAssignRequest,
    settings: Settings = Depends(get_settings),
) -> OrderAssignResponse:
    provider = orders_provider(settings)
    return provider(order_id, req)
