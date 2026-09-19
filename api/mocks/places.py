"""Mock POST /api/places/resolve. Hardcoded Delhi NCR landmarks, swapped for
core/places/resolve.py (Gemini + Google Geocoding, alias-graph-backed) at T2.10.
"""

from __future__ import annotations

import h3

from core.schemas.places import NEEDS_PICK_THRESHOLD, PlaceCandidate, PlaceResolveResponse

H3_RES = 8

_LANDMARKS: list[tuple[str, str, float, float]] = [
    ("cp", "Connaught Place, New Delhi", 28.6315, 77.2167),
    ("connaught place", "Connaught Place, New Delhi", 28.6315, 77.2167),
    ("cyber hub", "Cyber Hub, Gurugram", 28.4950, 77.0890),
    ("gurugram", "Cyber Hub, Gurugram", 28.4950, 77.0890),
    ("gurgaon", "Cyber Hub, Gurugram", 28.4950, 77.0890),
    ("noida sector 62", "Sector 62, Noida", 28.6270, 77.3720),
    ("noida", "Sector 62, Noida", 28.6270, 77.3720),
    ("igi airport", "Indira Gandhi International Airport", 28.5562, 77.1000),
    ("airport", "Indira Gandhi International Airport", 28.5562, 77.1000),
    ("saket", "Saket, New Delhi", 28.5245, 77.2066),
    ("dwarka", "Dwarka, New Delhi", 28.5921, 77.0460),
    ("rohini", "Rohini, New Delhi", 28.7041, 77.1025),
]


def _candidate(place_id: str, name: str, lat: float, lng: float, confidence: float) -> PlaceCandidate:
    return PlaceCandidate(
        place_id=place_id,
        name=name,
        lat=lat,
        lng=lng,
        h3=h3.latlng_to_cell(lat, lng, H3_RES),
        confidence=confidence,
    )


def resolve_place(query: str) -> PlaceResolveResponse:
    q = query.strip().lower()

    for key, name, lat, lng in _LANDMARKS:
        if key in q:
            candidate = _candidate(f"mock-{key.replace(' ', '-')}", name, lat, lng, 0.93)
            return PlaceResolveResponse(candidates=[candidate], ambiguous=False, needs_pick=False)

    # Unknown query: return a couple of low-confidence generic guesses so the
    # needs_pick / disambiguation UI path (T2.5) has something to exercise.
    guesses = [
        _candidate("mock-guess-1", f"{query.title()} (near Connaught Place)", 28.63, 77.22, 0.55),
        _candidate("mock-guess-2", f"{query.title()} (near Cyber Hub)", 28.495, 77.089, 0.5),
    ]
    return PlaceResolveResponse(
        candidates=guesses,
        ambiguous=True,
        needs_pick=guesses[0].confidence < NEEDS_PICK_THRESHOLD,
    )
