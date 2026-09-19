"""Polyline decoding and distance helpers (no external dependencies)."""

from __future__ import annotations

import math

LatLngT = tuple[float, float]


def decode_polyline(encoded: str) -> list[LatLngT]:
    """Google encoded-polyline algorithm, precision 5."""
    points: list[LatLngT] = []
    index = lat = lng = 0
    while index < len(encoded):
        for axis in (0, 1):
            shift = result = 0
            while True:
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else result >> 1
            if axis == 0:
                lat += delta
            else:
                lng += delta
        points.append((lat / 1e5, lng / 1e5))
    return points


def encode_polyline(points: list[LatLngT]) -> str:
    out: list[str] = []
    prev_lat = prev_lng = 0
    for lat, lng in points:
        ilat, ilng = round(lat * 1e5), round(lng * 1e5)
        for delta in (ilat - prev_lat, ilng - prev_lng):
            value = ~(delta << 1) if delta < 0 else delta << 1
            while value >= 0x20:
                out.append(chr((0x20 | (value & 0x1F)) + 63))
                value >>= 5
            out.append(chr(value + 63))
        prev_lat, prev_lng = ilat, ilng
    return "".join(out)


def haversine_m(a: LatLngT, b: LatLngT) -> float:
    r = 6371000.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dphi = p2 - p1
    dlmb = math.radians(b[1] - a[1])
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(h)))


def cumulative_m(points: list[LatLngT]) -> list[float]:
    out = [0.0]
    for a, b in zip(points, points[1:]):
        out.append(out[-1] + haversine_m(a, b))
    return out


def point_at_distance(points: list[LatLngT], cum: list[float], target_m: float) -> tuple[LatLngT, int]:
    """Interpolated point `target_m` metres along the path, plus the index of
    the vertex it sits after."""
    if not points:
        raise ValueError("empty path")
    if target_m <= 0:
        return points[0], 0
    if target_m >= cum[-1]:
        return points[-1], len(points) - 1
    lo, hi = 0, len(cum) - 1
    while lo < hi - 1:
        mid = (lo + hi) // 2
        if cum[mid] <= target_m:
            lo = mid
        else:
            hi = mid
    span = cum[hi] - cum[lo]
    t = 0.0 if span == 0 else (target_m - cum[lo]) / span
    a, b = points[lo], points[hi]
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), lo


def remaining_path(points: list[LatLngT], cum: list[float], from_m: float) -> list[LatLngT]:
    here, idx = point_at_distance(points, cum, from_m)
    return [here] + points[idx + 1 :]
