from app.services import geo_service

# The geographic-coverage caveat ("僅涵蓋桃園市") must appear in BOTH
# branches below, not only when the GeoJSON file is entirely missing --
# an address geocoded successfully but outside Taoyuan looks identical, at
# the field level, to "checked a Taoyuan address and found no overlap"
# (potential_overlap=False, data_available=True). Without this caveat
# always present, that would silently misrepresent an unchecked address as
# a checked-and-clear one.
DISCLAIMER = (
    "此結果僅涵蓋桃園市部分地質敏感區資料，非全面查詢，僅供初步參考，"
    "正式工程評估需洽地質專業技師或主管機關確認。"
)
NO_DATA_DISCLAIMER = (
    "此結果僅涵蓋桃園市部分地質敏感區資料，非全面查詢，"
    "無法確認是否位於地質敏感區，正式工程評估需洽地質專業技師或主管機關確認。"
)


def run(address: str) -> dict:
    """Two steps: OpenStreetMap Nominatim geocoding -> local point-in-polygon screening.
    Never raises -- either step's failure returns {"error": ...}.

    CLAUDE.md rule #8 (Vision must never assert safety/compliance, only use
    "observed/possibly/suspected/needs human confirmation" phrasing)
    extends here, and not only via the disclaimer string: the field itself
    is named potential_geological_sensitive_zone (preliminary, possible
    overlap), not in_geological_sensitive_zone (which reads as an already
    -confirmed fact); data_available is propagated as-is so the Agent/
    frontend can tell "checked, no overlap" apart from "no data to check
    against" -- two very different situations."""
    try:
        location = geo_service.geocode_address(address)
    except Exception as exc:
        return {"error": f"無法定位地址「{address}」：{exc}"}

    zone_result = geo_service.check_point_in_zones(location["lat"], location["lng"])

    return {
        "formatted_address": location["formatted_address"],
        "lat": location["lat"],
        "lng": location["lng"],
        "potential_geological_sensitive_zone": zone_result["potential_overlap"],
        "zone_type": zone_result["zone_type"],
        "data_available": zone_result["data_available"],
        "disclaimer": DISCLAIMER if zone_result["data_available"] else NO_DATA_DISCLAIMER,
    }
