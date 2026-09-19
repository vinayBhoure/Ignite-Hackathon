from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from api.security import require_session
from core.alerts.evaluator import ack_alert, list_alerts
from core.auth import Session
from core.schemas.alerts import AlertAckResponse, AlertOut

router = APIRouter(prefix="/api/alerts")


@router.get("", response_model=list[AlertOut])
def get_alerts(
    status: str | None = Query(default=None),
    rider_id: str | None = Query(default=None),
    session: Session = Depends(require_session),
) -> list[AlertOut]:
    # A rider only ever sees their own alerts, whatever rider_id they pass.
    if session.role == "rider":
        rider_id = session.sub
    return list_alerts(status=status, rider_id=rider_id)


@router.post("/{alert_id}/ack", response_model=AlertAckResponse)
def ack(alert_id: str, session: Session = Depends(require_session)) -> AlertAckResponse:
    if session.role == "rider" and alert_id not in {a.id for a in list_alerts(rider_id=session.sub)}:
        raise HTTPException(status_code=404, detail=f"alert {alert_id} not found")
    try:
        return ack_alert(alert_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
