"""POST /api/places/resolve contract. See docs/TrackB_Implementation_Plan.md Appendix A."""

from __future__ import annotations

from pydantic import BaseModel, Field

NEEDS_PICK_THRESHOLD = 0.7
"""confidence below this asks the user to pick from candidates, per PRD UI-2."""


class PlaceResolveRequest(BaseModel):
    query: str = Field(min_length=1)


class PlaceCandidate(BaseModel):
    place_id: str
    name: str
    lat: float
    lng: float
    h3: str
    confidence: float = Field(ge=0.0, le=1.0)


class PlaceResolveResponse(BaseModel):
    candidates: list[PlaceCandidate]
    ambiguous: bool
    needs_pick: bool
    """True when the top candidate's confidence is below NEEDS_PICK_THRESHOLD."""
