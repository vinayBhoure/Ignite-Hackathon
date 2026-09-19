from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from core.alerts.evaluator import ack_alert, list_alerts
from core.schemas.alerts import AlertAckResponse, AlertOut

router = APIRouter(prefix="/api/alerts")


@router.get("", response_model=list[AlertOut])
def get_alerts(
    status: str | None = Query(default=None),
    rider_id: str | None = Query(default=None),
) -> list[AlertOut]:
    return list_alerts(status=status, rider_id=rider_id)


@router.post("/{alert_id}/ack", response_model=AlertAckResponse)
def ack(alert_id: str) -> AlertAckResponse:
    try:
        return ack_alert(alert_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
