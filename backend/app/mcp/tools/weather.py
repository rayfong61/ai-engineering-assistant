from app.services import weather_service


def run(location: str) -> dict:
    """Thin MCP wrapper -- no DB access needed, so no SessionLocal here
    (unlike search_documents.py). Never raises: external-API failures are
    caught and returned as {"error": ...} so a flaky CWA response degrades
    the Agent's answer gracefully instead of failing the whole /agent
    request."""
    try:
        return weather_service.fetch_forecast(location)
    except Exception as exc:
        return {"error": f"無法取得 {location} 的天氣資訊：{exc}"}
