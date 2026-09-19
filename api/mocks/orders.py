"""Mock POST /api/orders/{id}/assign. Swapped for a real Neo4j write once
core/dispatch exists and this contract is reviewed with Track A.
"""

from __future__ import annotations

from core.schemas.orders import OrderAssignRequest, OrderAssignResponse


def assign_order(order_id: str, req: OrderAssignRequest) -> OrderAssignResponse:
    return OrderAssignResponse(order_id=order_id, route_id=req.route_id, rider_id=req.rider_id)
