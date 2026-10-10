"""Nearby healthcare lookup using the OpenStreetMap Overpass API.

No API key and no account needed, which keeps deployment simple. Results are
classified into Ayurvedic / Homeopathy / General / Pharmacy from OSM tags and names.
"""

from __future__ import annotations

import asyncio
import math
import re
import time
from typing import Any

import httpx

from .certs import ssl_verify
from .config import Settings

# GenAI Generated code - Start

#: Public Overpass instances. They rate-limit aggressively and fail intermittently
#: with 429/500/504, so we rotate through them and retry one extra round.
MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

_CACHE_TTL = 600.0  # seconds
_CACHE_MAX = 200
#: (lat2dp, lon2dp, radius) -> (expires_at, payload)
_cache: dict[tuple[float, float, float], tuple[float, dict[str, Any]]] = {}

CATEGORIES = ("all", "ayurveda", "homeopathy", "general", "pharmacy")

_AYURVEDA_RE = re.compile(
    r"ayurved|ayush|siddha|unani|arya\s*vaidya|panchakarma|kottakkal|vaidya",
    re.IGNORECASE,
)
_HOMEO_RE = re.compile(r"homeo|homoeo|homoeopath", re.IGNORECASE)


class HospitalLookupError(RuntimeError):
    """Raised when the Overpass service cannot be reached."""


def _query(lat: float, lon: float, radius_m: int) -> str:
    return (
        "[out:json][timeout:30];"
        "("
        f'nwr["amenity"~"^(hospital|clinic|doctors|pharmacy)$"](around:{radius_m},{lat},{lon});'
        f'nwr["healthcare"~"^(hospital|clinic|doctor|centre|center|alternative|pharmacy)$"](around:{radius_m},{lat},{lon});'
        ");"
        # Cap the response so a dense city cannot blow up the payload. Category
        # filtering happens after this cap, so keep it generous.
        "out center 300;"
    )


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0088
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(a))


def _classify(tags: dict[str, str]) -> str:
    amenity = (tags.get("amenity") or "").lower()
    healthcare = (tags.get("healthcare") or "").lower()
    speciality = " ".join(
        [
            tags.get("healthcare:speciality", ""),
            tags.get("healthcare:speciality:ayurveda", ""),
            tags.get("medical_system", ""),
            tags.get("medical_system:ayurveda", ""),
            tags.get("medical_system:homeopathy", ""),
        ]
    ).lower()
    name_blob = " ".join(
        tags.get(key, "")
        for key in ("name", "name:en", "official_name", "operator", "brand")
    )
    blob = f"{speciality} {name_blob}"

    if _HOMEO_RE.search(blob) or "homeopath" in speciality:
        return "homeopathy"
    if _AYURVEDA_RE.search(blob) or "ayurved" in speciality:
        return "ayurveda"
    if amenity == "pharmacy" or healthcare == "pharmacy":
        return "pharmacy"
    return "general"


def _address(tags: dict[str, str]) -> str:
    bits = [
        tags.get("addr:housenumber"),
        tags.get("addr:street"),
        tags.get("addr:suburb") or tags.get("addr:neighbourhood"),
        tags.get("addr:city") or tags.get("addr:village") or tags.get("addr:town"),
        tags.get("addr:postcode"),
    ]
    return ", ".join(b for b in bits if b)


def _place_name(tags: dict[str, str], category: str) -> str:
    name = (
        tags.get("name")
        or tags.get("name:en")
        or tags.get("official_name")
        or tags.get("operator")
    )
    if name:
        return name
    fallback = {
        "pharmacy": "Unnamed pharmacy",
        "ayurveda": "Unnamed Ayurvedic clinic",
        "homeopathy": "Unnamed homeopathy clinic",
    }
    return fallback.get(category, "Unnamed clinic")


def _cache_get(key: tuple[float, float, float]) -> dict[str, Any] | None:
    entry = _cache.get(key)
    if not entry:
        return None
    expires_at, payload = entry
    if expires_at < time.time():
        _cache.pop(key, None)
        return None
    return payload


def _cache_put(key: tuple[float, float, float], payload: dict[str, Any]) -> None:
    if len(_cache) >= _CACHE_MAX:
        now = time.time()
        for stale in [k for k, (exp, _) in _cache.items() if exp < now]:
            _cache.pop(stale, None)
        if len(_cache) >= _CACHE_MAX:
            _cache.pop(next(iter(_cache)), None)
    _cache[key] = (time.time() + _CACHE_TTL, payload)


async def _fetch_overpass(
    lat: float, lon: float, radius_km: float, settings: Settings
) -> dict[str, Any]:
    """POST the query, rotating mirrors and retrying one extra round."""
    body = _query(lat, lon, int(radius_km * 1000))
    endpoints = [settings.overpass_url] + [
        m for m in MIRRORS if m != settings.overpass_url
    ]
    last_error = ""

    async with httpx.AsyncClient(
        timeout=settings.overpass_timeout,
        verify=ssl_verify(),
        headers={"User-Agent": "ArogyaAI/1.0 (health assistant; OSM Overpass client)"},
    ) as client:
        for attempt in range(2):
            for endpoint in endpoints:
                try:
                    response = await client.post(endpoint, data={"data": body})
                    if response.status_code == 200:
                        return response.json()
                    last_error = f"{endpoint} returned {response.status_code}"
                except (httpx.HTTPError, ValueError) as exc:
                    last_error = f"{endpoint}: {type(exc).__name__}"
            if attempt == 0:
                await asyncio.sleep(1.0)

    raise HospitalLookupError(
        "The OpenStreetMap lookup service is busy right now. Please try again in a "
        f"moment. ({last_error})"
    )


async def find_nearby(
    lat: float,
    lon: float,
    *,
    settings: Settings,
    radius_km: float = 5.0,
    category: str = "all",
    limit: int = 25,
) -> dict[str, Any]:
    """Look up healthcare places around a coordinate."""
    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        raise ValueError("Coordinates out of range")
    radius_km = max(0.5, min(radius_km, 25.0))
    category = category if category in CATEGORIES else "all"

    cache_key = (round(lat, 2), round(lon, 2), radius_km)
    payload = _cache_get(cache_key)

    if payload is None:
        payload = await _fetch_overpass(lat, lon, radius_km, settings)
        _cache_put(cache_key, payload)

    seen: set[tuple[str, int]] = set()
    places: list[dict[str, Any]] = []
    for element in payload.get("elements", []):
        key = (element.get("type", ""), element.get("id", 0))
        if key in seen:
            continue
        seen.add(key)

        if element.get("type") == "node":
            plat, plon = element.get("lat"), element.get("lon")
        else:
            center = element.get("center") or {}
            plat, plon = center.get("lat"), center.get("lon")
        if plat is None or plon is None:
            continue

        tags = element.get("tags") or {}
        cat = _classify(tags)
        places.append(
            {
                "id": f"{element['type']}/{element['id']}",
                "name": _place_name(tags, cat),
                "category": cat,
                "type": tags.get("amenity") or tags.get("healthcare") or "clinic",
                "distance_km": round(_haversine_km(lat, lon, plat, plon), 2),
                "lat": plat,
                "lon": plon,
                "phone": tags.get("phone") or tags.get("contact:phone") or "",
                "address": _address(tags),
                "emergency": (tags.get("emergency") or "").lower() == "yes",
                "open_hours": tags.get("opening_hours", ""),
                "website": tags.get("website") or tags.get("contact:website") or "",
                "maps_url": (
                    "https://www.google.com/maps/dir/?api=1"
                    f"&destination={plat},{plon}"
                ),
                "osm_url": f"https://www.openstreetmap.org/{element['type']}/{element['id']}",
            }
        )

    if category != "all":
        places = [p for p in places if p["category"] == category]

    places.sort(key=lambda p: p["distance_km"])
    counts: dict[str, int] = {c: 0 for c in CATEGORIES if c != "all"}
    for place in places:
        counts[place["category"]] = counts.get(place["category"], 0) + 1

    return {
        "origin": {"lat": lat, "lon": lon},
        "radius_km": radius_km,
        "category": category,
        "counts": counts,
        "total": len(places),
        "results": places[:limit],
        "attribution": "Data (c) OpenStreetMap contributors, ODbL - via Overpass API",
    }
# GenAI Generated code - End
