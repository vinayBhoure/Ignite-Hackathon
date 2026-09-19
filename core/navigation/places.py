"""Real place resolution: the alias graph first (Track A's knowledge layer,
read-only here), then the Google Geocoding API. The geocoder - never an LLM -
is the source of truth for coordinates (CLAUDE.md rule 6).
"""

from __future__ import annotations

import h3

from core.db.client import get_session
from core.navigation.google import geocode
from core.schemas.places import NEEDS_PICK_THRESHOLD, PlaceCandidate, PlaceResolveResponse

H3_RES = 8

# Shorthand the geocoder mangles on its own; expanded before geocoding.
_EXPANSIONS = {
    "cp": "Connaught Place, New Delhi",
    "igi": "Indira Gandhi International Airport, Delhi",
    "airport": "Indira Gandhi International Airport, Delhi",
    "aiims": "AIIMS, Ansari Nagar, New Delhi",
    "cyber hub": "DLF CyberHub, Gurugram",
}


def _normalize(query: str) -> str:
    return " ".join(query.lower().split())


def _candidate(place_id: str, name: str, lat: float, lng: float, confidence: float) -> PlaceCandidate:
    return PlaceCandidate(
        place_id=place_id, name=name, lat=lat, lng=lng,
        h3=h3.latlng_to_cell(lat, lng, H3_RES), confidence=round(confidence, 2),
    )


def _from_graph(text: str) -> list[PlaceCandidate]:
    with get_session() as session:
        rows = list(
            session.run(
                """
                MATCH (a:Alias {text: $text})-[r:REFERS_TO]->(p:Place)
                RETURN p.id AS id, p.name AS name, p.location AS loc, coalesce(r.confidence, 0.9) AS conf
                ORDER BY coalesce(r.votes, 0) DESC
                LIMIT 3
                """,
                text=text,
            )
        )
        if not rows and text not in _EXPANSIONS:
            # "hub", "depot", or any part of a hub's own name ("south delhi hub")
            rows = list(
                session.run(
                    """
                    MATCH (h:Hub)
                    WHERE $text IN ['hub', 'depot', 'the hub'] OR toLower(h.name) CONTAINS $text
                    RETURN h.id AS id, h.name AS name, h.location AS loc, 0.95 AS conf LIMIT 3
                    """,
                    text=text,
                )
            )
    return [_candidate(r["id"], r["name"], r["loc"].y, r["loc"].x, float(r["conf"])) for r in rows]


def resolve_place(query: str) -> PlaceResolveResponse:
    text = _normalize(query)
    candidates = _from_graph(text)

    if not candidates:
        results = geocode(_EXPANSIONS.get(text, query))
        for i, r in enumerate(results[:3]):
            confidence = 0.93 if len(results) == 1 and not r.partial_match else 0.62 - 0.08 * i
            if r.location_type == "APPROXIMATE":
                confidence -= 0.1
            candidates.append(_candidate(r.place_id, r.name, r.lat, r.lng, max(confidence, 0.1)))

    ambiguous = len(candidates) > 1 and candidates[0].confidence < NEEDS_PICK_THRESHOLD
    return PlaceResolveResponse(
        candidates=candidates,
        ambiguous=ambiguous,
        needs_pick=bool(candidates) and candidates[0].confidence < NEEDS_PICK_THRESHOLD,
    )
