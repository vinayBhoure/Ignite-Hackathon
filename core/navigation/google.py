"""Google Routes API (computeRoutes) + Geocoding API client.

Routes are traffic-aware, two-wheeler, with alternatives and turn-by-turn
steps. Geometry is held in memory only (CLAUDE.md rule 9: never persist raw
Google geometry beyond the session - only derived scores and zone lists go to
Neo4j). The key is never logged or included in error messages.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field

import requests

from core.navigation.geometry import LatLngT, decode_polyline

ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

# Delhi NCR - keeps geocoding from resolving "Saket" to somewhere in Bihar.
NCR_BOUNDS = (28.20, 76.80, 28.95, 77.65)

_FIELD_MASK = ",".join(
    [
        "routes.duration",
        "routes.staticDuration",
        "routes.distanceMeters",
        "routes.routeLabels",
        "routes.polyline.encodedPolyline",
        "routes.legs.steps.distanceMeters",
        "routes.legs.steps.staticDuration",
        "routes.legs.steps.startLocation",
        "routes.legs.steps.endLocation",
        "routes.legs.steps.navigationInstruction",
    ]
)

_CACHE_TTL_S = 300
_cache: dict[tuple, tuple[float, list["GoogleRoute"]]] = {}
_cache_lock = threading.Lock()


class RoutingUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class Step:
    instruction: str
    maneuver: str
    distance_m: float
    duration_s: float
    start: LatLngT
    end: LatLngT


@dataclass(frozen=True)
class GoogleRoute:
    index: int
    duration_s: float
    static_duration_s: float
    distance_m: float
    encoded_polyline: str
    labels: tuple[str, ...]
    steps: tuple[Step, ...]
    points: tuple[LatLngT, ...] = field(repr=False)


def _key() -> str:
    key = os.getenv("GOOGLE_MAPS_SERVER_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")
    if not key:
        raise RoutingUnavailable("GOOGLE_MAPS_SERVER_KEY / GOOGLE_MAPS_API_KEY is not set")
    return key


def _seconds(value: str | None) -> float:
    return float(value.rstrip("s")) if value else 0.0


def _latlng(loc: dict) -> LatLngT:
    ll = loc.get("latLng", {})
    return (ll.get("latitude", 0.0), ll.get("longitude", 0.0))


def compute_routes(origin: LatLngT, destination: LatLngT) -> list[GoogleRoute]:
    cache_key = (round(origin[0], 5), round(origin[1], 5), round(destination[0], 5), round(destination[1], 5))
    now = time.time()
    with _cache_lock:
        hit = _cache.get(cache_key)
        if hit and now - hit[0] < _CACHE_TTL_S:
            return hit[1]

    try:
        resp = requests.post(
            ROUTES_URL,
            headers={"X-Goog-Api-Key": _key(), "X-Goog-FieldMask": _FIELD_MASK},
            json={
                "origin": {"location": {"latLng": {"latitude": origin[0], "longitude": origin[1]}}},
                "destination": {"location": {"latLng": {"latitude": destination[0], "longitude": destination[1]}}},
                "travelMode": "TWO_WHEELER",
                "routingPreference": "TRAFFIC_AWARE",
                "computeAlternativeRoutes": True,
                "languageCode": "en-IN",
                "units": "METRIC",
            },
            timeout=20,
        )
    except requests.RequestException as exc:
        raise RoutingUnavailable(f"Routes API unreachable ({exc.__class__.__name__})") from exc

    if resp.status_code != 200:
        message = resp.json().get("error", {}).get("message", "") if resp.content else ""
        raise RoutingUnavailable(f"Routes API returned {resp.status_code}: {message[:160]}")

    routes: list[GoogleRoute] = []
    for i, raw in enumerate(resp.json().get("routes", [])):
        encoded = raw.get("polyline", {}).get("encodedPolyline", "")
        steps = tuple(
            Step(
                instruction=s.get("navigationInstruction", {}).get("instructions", "Continue"),
                maneuver=s.get("navigationInstruction", {}).get("maneuver", "STRAIGHT"),
                distance_m=float(s.get("distanceMeters", 0)),
                duration_s=_seconds(s.get("staticDuration")),
                start=_latlng(s.get("startLocation", {})),
                end=_latlng(s.get("endLocation", {})),
            )
            for leg in raw.get("legs", [])
            for s in leg.get("steps", [])
        )
        routes.append(
            GoogleRoute(
                index=i,
                duration_s=_seconds(raw.get("duration")),
                static_duration_s=_seconds(raw.get("staticDuration")),
                distance_m=float(raw.get("distanceMeters", 0)),
                encoded_polyline=encoded,
                labels=tuple(raw.get("routeLabels", [])),
                steps=steps,
                points=tuple(decode_polyline(encoded)),
            )
        )

    if not routes:
        raise RoutingUnavailable("Routes API found no route between these points")

    with _cache_lock:
        _cache[cache_key] = (now, routes)
    return routes


@dataclass(frozen=True)
class GeocodeResult:
    place_id: str
    name: str
    lat: float
    lng: float
    partial_match: bool
    location_type: str


def _in_ncr(lat: float, lng: float) -> bool:
    s, w, n, e = NCR_BOUNDS
    return s <= lat <= n and w <= lng <= e


def geocode(query: str) -> list[GeocodeResult]:
    s, w, n, e = NCR_BOUNDS
    try:
        resp = requests.get(
            GEOCODE_URL,
            params={
                "address": query,
                "key": _key(),
                "region": "in",
                "components": "country:IN",
                "bounds": f"{s},{w}|{n},{e}",
            },
            timeout=15,
        )
    except requests.RequestException as exc:
        raise RoutingUnavailable(f"Geocoding API unreachable ({exc.__class__.__name__})") from exc

    body = resp.json()
    if body.get("status") not in ("OK", "ZERO_RESULTS"):
        raise RoutingUnavailable(f"Geocoding API status {body.get('status')}")

    results = []
    for r in body.get("results", []):
        loc = r["geometry"]["location"]
        if not _in_ncr(loc["lat"], loc["lng"]):
            continue
        results.append(
            GeocodeResult(
                place_id=r.get("place_id", ""),
                name=r.get("formatted_address", query),
                lat=loc["lat"],
                lng=loc["lng"],
                partial_match=bool(r.get("partial_match")),
                location_type=r["geometry"].get("location_type", ""),
            )
        )
    return results
