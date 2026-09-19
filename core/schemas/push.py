"""POST /api/push/subscribe contract.

Never log or print subscription endpoints or keys (CLAUDE.md working rules) -
these models must not appear in any log/print statement, only in request
handling and Neo4j PushSub storage.
"""

from __future__ import annotations

from pydantic import BaseModel


class PushSubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscription(BaseModel):
    endpoint: str
    keys: PushSubscriptionKeys


class PushSubscribeRequest(BaseModel):
    rider_id: str
    subscription: PushSubscription


class PushSubscribeResponse(BaseModel):
    status: str = "subscribed"


class VapidPublicKeyResponse(BaseModel):
    public_key: str
