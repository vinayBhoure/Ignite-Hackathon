"""GET /api/alerts and POST /api/alerts/{id}/ack contracts.

Alert threshold: PM2.5 above 120 (Very poor). Dedupe: same rider + zone within
15 replay-minutes (core/alerts/evaluator.py owns both rules).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

AlertType = Literal["spike"]
AlertStatus = Literal["new", "acked"]


class AlertOut(BaseModel):
    id: str
    type: AlertType
    severity: str
    ts: datetime
    status: AlertStatus
    order_id: str | None = None
    rider_id: str | None = None
    h3: str | None = None
    simulated: bool = False
    """True when the triggering reading was an injected spike (additive, post-v0)."""


class AlertAckResponse(BaseModel):
    id: str
    status: AlertStatus
