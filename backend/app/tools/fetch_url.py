from app.services import web_fetch_service


def run(url: str, max_length: int = 5000) -> dict:
    """Thin tool wrapper -- no DB access needed, so no SessionLocal here
    (unlike search_documents.py). Never raises: a dead/missing MCP server
    subprocess, a timeout, or a fetch failure inside it is caught and
    returned as {"error": ...} so a flaky external server degrades the
    Agent's answer gracefully instead of failing the whole /agent request."""
    try:
        return web_fetch_service.fetch_url(url, max_length=max_length)
    except Exception as exc:
        return {"error": f"無法擷取網頁內容：{exc}"}
