"""POST /api/orders/{id}/assign contract.

Not detailed in the plan's Appendix A draft; kept minimal until Track A
reviews (CLAUDE.md: only additive changes to core/schemas after freeze).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class OrderAssignRequest(BaseModel):
    route_id: str
    rider_id: str | None = None
    pickup_name: str | None = None
    """Display names (additive, post-v0) - coordinates come from the plan."""
    drop_name: str | None = None


class OrderAssignResponse(BaseModel):
    order_id: str
    route_id: str
    rider_id: str | None = None
    status: Literal["assigned"] = "assigned"
