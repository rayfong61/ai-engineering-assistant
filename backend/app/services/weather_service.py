from datetime import UTC, datetime

import httpx

from app.core.config import CWA_API_KEY

CWA_BASE_URL = "https://opendata.cwa.gov.tw/api/v1/rest/datastore"
# County-level 1-week forecast (~15 periods of ~12 hours each), superset of
# the old 36-hour-only F-C0032-001 dataset at the same location granularity
# -- locationName must match a Taiwan county/city name (e.g. "桃園市"), not a
# district. CWA does not actually filter server-side on locationName for
# this dataset (it always returns all ~22 counties), so filtering happens
# client-side in _parse_forecast.
FORECAST_DATASET_ID = "F-D0047-091"


def fetch_forecast(location_name: str) -> dict:
    """Raw CWA call + parse into a simplified summary. Raises
    httpx.HTTPError/ValueError on failure -- caller (weather.py's run())
    turns that into a tool-error dict, never an unhandled 502."""
    response = httpx.get(
        f"{CWA_BASE_URL}/{FORECAST_DATASET_ID}",
        params={"Authorization": CWA_API_KEY, "format": "JSON", "locationName": location_name},
        timeout=10,
    )
    response.raise_for_status()
    return _parse_forecast(response.json(), location_name)


def _parse_forecast(data: dict, location_name: str) -> dict:
    """Pulls ALL forecast time periods for the requested county out of CWA's
    nested records.Locations[0].Location[].WeatherElement[].Time[] shape.
    CWA ignores the locationName query param for this dataset and always
    returns every county, so the matching entry is picked out here instead.
    Each WeatherElement's Time[] entries align by list position across
    elements (same StartTime/EndTime per index) -- 天氣現象 carries the
    period boundaries since it's the one element every period reliably has.
    retrieved_at/source matter here -- engineering context cares about "as
    of when" this data is, mirroring this project's existing document
    source+page and Activity Log traceability."""
    locations = data.get("records", {}).get("Locations", [])
    if not locations:
        raise ValueError(f"CWA 未回傳 {location_name} 的預報資料")
    location = next(
        (loc for loc in locations[0].get("Location", []) if loc["LocationName"] == location_name),
        None,
    )
    if location is None:
        raise ValueError(f"CWA 資料中找不到「{location_name}」，請確認是否為正確的縣市名稱")
    elements = {el["ElementName"]: el["Time"] for el in location["WeatherElement"]}
    forecasts = [
        {
            "start_time": period.get("StartTime"),
            "end_time": period.get("EndTime"),
            "description": period["ElementValue"][0]["Weather"],
            "rain_probability": elements["12小時降雨機率"][i]["ElementValue"][0]["ProbabilityOfPrecipitation"],
            "min_temp": elements["最低溫度"][i]["ElementValue"][0]["MinTemperature"],
            "max_temp": elements["最高溫度"][i]["ElementValue"][0]["MaxTemperature"],
        }
        for i, period in enumerate(elements["天氣現象"])
    ]
    return {
        "location": location_name,
        "retrieved_at": datetime.now(UTC).isoformat(),
        "source": "中央氣象署開放資料平台",
        "forecasts": forecasts,
    }
