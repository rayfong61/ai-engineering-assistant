import json
from pathlib import Path

import httpx
from shapely.geometry import Point, shape

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# TGOS's own address-geocoding service (全國門牌位置比對服務) turned out to be
# gated to government/enterprise/academic/registered-company applicants only
# -- no individual option -- so this uses OpenStreetMap's free Nominatim
# service instead: no registration, no API key, works immediately for an
# individual. Its usage policy requires a real identifying User-Agent (not
# a default httpx one) and caps usage at ~1 req/sec, both fine for this
# tool's one-query-per-Agent-turn pattern.
NOMINATIM_USER_AGENT = "ai-engineering-assistant-demo (https://github.com/rayfong61/ai-engineering-assistant)"
GEOJSON_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "geo" / "taoyuan_geological_sensitive_zones.geojson"
)


def geocode_address(address: str) -> dict:
    """Raw Nominatim geocode call. Returns {"formatted_address", "lat", "lng"}.
    Raises httpx.HTTPError/ValueError on failure. countrycodes=tw narrows
    results to Taiwan; Nominatim's address-matching accuracy for Taiwan is
    weaker than a government-authoritative source like TGOS, but it's the
    option actually available to an individual applicant."""
    response = httpx.get(
        NOMINATIM_URL,
        params={"q": address, "format": "json", "limit": 1, "countrycodes": "tw"},
        headers={"User-Agent": NOMINATIM_USER_AGENT},
        timeout=10,
    )
    response.raise_for_status()
    results = response.json()
    if not results:
        raise ValueError(f"Nominatim 無法解析地址：{address}")
    result = results[0]
    return {
        "formatted_address": result["display_name"],
        "lat": float(result["lat"]),
        "lng": float(result["lon"]),
    }


_zones_cache: list[dict] | None = None


def _load_zones() -> list[dict]:
    """Loaded once at first use (lazy, not at module import) -- keeps
    mcp-server import-time cheap and lets the file be genuinely optional
    (missing file degrades to 'zone data unavailable' rather than crashing
    the whole mcp-server process at startup).

    The source file must be WGS84 (EPSG:4326, matching Nominatim's returned
    lat/lng) -- many Taiwan government geo datasets default to TWD97
    (EPSG:3826); a mismatch here makes point-in-polygon "run fine but be
    silently wrong," so reproject to EPSG:4326 once when sourcing the file,
    not at query time. Also defensive against MultiPolygon geometries and
    features with a null/missing geometry (both real possibilities in
    government open data)."""
    global _zones_cache
    if _zones_cache is None:
        if not GEOJSON_PATH.exists():
            _zones_cache = []
        else:
            geojson = json.loads(GEOJSON_PATH.read_text(encoding="utf-8"))
            _zones_cache = [
                {
                    "geometry": shape(f["geometry"]),
                    "zone_type": f["properties"].get("zone_type", "地質敏感區"),
                }
                for f in geojson["features"]
                if f.get("geometry")  # skip features with null geometry
            ]
    return _zones_cache


def check_point_in_zones(lat: float, lng: float) -> dict:
    """Point-in-polygon screening against the bundled Taoyuan-scoped
    GeoJSON. data_available=False (no zone data loaded) is a distinct
    situation from "checked and found no overlap" -- the caller (geo.py)
    must propagate this so its disclaimer can say which one actually
    happened. Uses covers() rather than contains(): a point exactly on a
    zone boundary should still count as an overlap for this conservative,
    preliminary-screening use case."""
    zones = _load_zones()
    if not zones:
        return {"potential_overlap": False, "zone_type": None, "data_available": False}
    point = Point(lng, lat)  # GeoJSON coordinate order is (lng, lat)
    for zone in zones:
        if zone["geometry"].covers(point):
            return {"potential_overlap": True, "zone_type": zone["zone_type"], "data_available": True}
    return {"potential_overlap": False, "zone_type": None, "data_available": True}
