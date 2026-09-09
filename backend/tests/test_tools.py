import json

import httpx

from app.tools import create_calendar_event, fetch_url, geo, search_documents, send_email, weather
from app.models import Document, DocumentChunk, Project
from app.models.document import EMBEDDING_DIM

# Hand-crafted fixture polygon, not the real dataset -- a simple square
# roughly covering (121.0, 25.0) in (lng, lat) GeoJSON order.
_FIXTURE_ZONE = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"zone_type": "地質敏感區(測試)"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[120.9, 24.9], [121.1, 24.9], [121.1, 25.1], [120.9, 25.1], [120.9, 24.9]]
                ],
            },
        }
    ],
}


def _write_fixture_geojson(tmp_path, geojson=_FIXTURE_ZONE):
    path = tmp_path / "zones.geojson"
    path.write_text(json.dumps(geojson), encoding="utf-8")
    return path


def _fake_geocode_get(lat, lng, display_name="桃園市測試地址"):
    # Nominatim returns a bare JSON array (not {"results": [...]}), with
    # lat/lon as strings -- geo_service.geocode_address() converts them
    # with float(), so the fixture mirrors that string-typed shape.
    return lambda url, params=None, headers=None, timeout=None: _Response(
        json_data=[{"display_name": display_name, "lat": str(lat), "lon": str(lng)}]
    )


class _Response:
    """Minimal stand-in for httpx.Response -- matches tests/test_gmail.py's
    _Response, just enough for the code paths weather_service touches
    (raise_for_status / json)."""

    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)

    def json(self):
        return self._json


class _NonClosingSession:
    """Wraps the test's db_session so app.tools.search_documents.run()
    (which opens its own SessionLocal(), since it has no FastAPI
    Depends(get_db) request-scoped session to reuse) operates against the
    test's SAVEPOINT-rolled-back session instead of a real, separate
    connection -- close() is swallowed so the fixture's session stays open
    for the test's own assertions afterward."""

    def __init__(self, session):
        self._session = session

    def close(self):
        pass

    def __getattr__(self, name):
        return getattr(self._session, name)


def test_search_documents_tool_scopes_to_project(db_session, alice, monkeypatch):
    monkeypatch.setattr(
        "app.tools.search_documents.SessionLocal", lambda: _NonClosingSession(db_session)
    )
    monkeypatch.setattr(
        "app.services.embedding_service.embed_query", lambda text: [0.1] * EMBEDDING_DIM
    )

    project_a = Project(name="Project A", created_by=alice["id"])
    project_b = Project(name="Project B", created_by=alice["id"])
    db_session.add_all([project_a, project_b])
    db_session.flush()

    doc_a = Document(
        project_id=project_a.id, uploaded_by=alice["id"], filename="a.pdf",
        storage_path="x", status="ready",
    )
    doc_b = Document(
        project_id=project_b.id, uploaded_by=alice["id"], filename="b.pdf",
        storage_path="x", status="ready",
    )
    db_session.add_all([doc_a, doc_b])
    db_session.flush()

    shared_vector = [0.1] * EMBEDDING_DIM
    db_session.add(
        DocumentChunk(
            document_id=doc_a.id, project_id=project_a.id, page=1, chunk_index=0,
            content="content in project A", embedding=shared_vector,
        )
    )
    db_session.add(
        DocumentChunk(
            document_id=doc_b.id, project_id=project_b.id, page=1, chunk_index=0,
            content="content in project B", embedding=shared_vector,
        )
    )
    db_session.flush()

    results = search_documents.run("query", str(project_a.id))

    assert len(results) == 1
    assert results[0]["filename"] == "a.pdf"
    assert results[0]["content"] == "content in project A"


def test_search_documents_tool_returns_empty_for_project_with_no_chunks(db_session, alice, monkeypatch):
    monkeypatch.setattr(
        "app.tools.search_documents.SessionLocal", lambda: _NonClosingSession(db_session)
    )
    monkeypatch.setattr(
        "app.services.embedding_service.embed_query", lambda text: [0.1] * EMBEDDING_DIM
    )

    project = Project(name="Empty Project", created_by=alice["id"])
    db_session.add(project)
    db_session.flush()

    assert search_documents.run("query", str(project.id)) == []


def test_send_email_tool_mock_mode_returns_sent(monkeypatch):
    monkeypatch.setattr("app.tools.send_email.EMAIL_MODE", "mock")

    result = send_email.run("pm@example.com", "subject", "body")

    assert result["status"] == "sent"


def test_send_email_tool_non_mock_mode_fails_cleanly(monkeypatch):
    # Gmail mode requires a user_id (there's no one to send on behalf of
    # otherwise) -- missing it must fail rather than silently pretending to
    # send.
    monkeypatch.setattr("app.tools.send_email.EMAIL_MODE", "gmail")

    result = send_email.run("pm@example.com", "subject", "body")

    assert result["status"] == "failed"


def test_send_email_tool_gmail_mode_delegates_to_gmail_service(monkeypatch, alice):
    monkeypatch.setattr("app.tools.send_email.EMAIL_MODE", "gmail")
    monkeypatch.setattr(
        "app.services.gmail_service.send_email",
        lambda db, user_id, to, subject, body: {"status": "sent", "message": f"sent to {to}"},
    )

    result = send_email.run("pm@example.com", "subject", "body", user_id=alice["id"])

    assert result == {"status": "sent", "message": "sent to pm@example.com"}


def test_send_email_tool_unknown_mode_fails_cleanly(monkeypatch):
    monkeypatch.setattr("app.tools.send_email.EMAIL_MODE", "something-else")

    result = send_email.run("pm@example.com", "subject", "body")

    assert result["status"] == "failed"


_CAL_START = "2026-09-16T14:00:00+08:00"
_CAL_END = "2026-09-16T15:00:00+08:00"


def test_create_calendar_event_tool_mock_mode_returns_created(monkeypatch):
    monkeypatch.setattr("app.tools.create_calendar_event.CALENDAR_MODE", "mock")

    result = create_calendar_event.run("會勘", _CAL_START, _CAL_END)

    assert result["status"] == "created"


def test_create_calendar_event_tool_non_mock_mode_without_user_id_fails_cleanly(monkeypatch):
    # google_calendar mode requires a user_id (there's no one to create the
    # event on behalf of otherwise) -- missing it must fail rather than
    # silently pretending to create.
    monkeypatch.setattr("app.tools.create_calendar_event.CALENDAR_MODE", "google_calendar")

    result = create_calendar_event.run("會勘", _CAL_START, _CAL_END)

    assert result["status"] == "failed"


def test_create_calendar_event_tool_google_calendar_mode_delegates_to_calendar_service(monkeypatch, alice):
    monkeypatch.setattr("app.tools.create_calendar_event.CALENDAR_MODE", "google_calendar")
    monkeypatch.setattr(
        "app.services.calendar_service.create_event",
        lambda db, user_id, summary, start_datetime, end_datetime, description=None, attendees=None: {
            "status": "created",
            "message": "ok",
            "google_event_id": "evt-1",
        },
    )

    result = create_calendar_event.run("會勘", _CAL_START, _CAL_END, user_id=alice["id"])

    assert result == {"status": "created", "message": "ok", "google_event_id": "evt-1"}


def test_create_calendar_event_tool_unknown_mode_fails_cleanly(monkeypatch):
    monkeypatch.setattr("app.tools.create_calendar_event.CALENDAR_MODE", "something-else")

    result = create_calendar_event.run("會勘", _CAL_START, _CAL_END)

    assert result["status"] == "failed"


def _fake_weekly_location(name, periods):
    """Builds one CWA F-D0047-091 Location entry. `periods` is a list of
    dicts with start/end/description/rain_probability/min_temp/max_temp --
    aligned by list position across the four elements the parser reads."""
    return {
        "LocationName": name,
        "WeatherElement": [
            {
                "ElementName": "天氣現象",
                "Time": [
                    {"StartTime": p["start"], "EndTime": p["end"], "ElementValue": [{"Weather": p["description"]}]}
                    for p in periods
                ],
            },
            {
                "ElementName": "12小時降雨機率",
                "Time": [{"ElementValue": [{"ProbabilityOfPrecipitation": p["rain_probability"]}]} for p in periods],
            },
            {
                "ElementName": "最低溫度",
                "Time": [{"ElementValue": [{"MinTemperature": p["min_temp"]}]} for p in periods],
            },
            {
                "ElementName": "最高溫度",
                "Time": [{"ElementValue": [{"MaxTemperature": p["max_temp"]}]} for p in periods],
            },
        ],
    }


def test_get_site_weather_tool_parses_cwa_response(monkeypatch):
    # Real CWA F-D0047-091 responses carry ~15 ~12-hour periods (1-week
    # forecast) per element, and always return every county regardless of
    # the locationName query param -- this fixture mirrors both, guarding
    # against regressing to reading only the first period or the first
    # (wrong) county in the list.
    fake_response = {
        "records": {
            "Locations": [
                {
                    "Location": [
                        _fake_weekly_location(
                            "連江縣",
                            [
                                {
                                    "start": "2026-09-08T18:00:00+08:00", "end": "2026-09-09T06:00:00+08:00",
                                    "description": "晴", "rain_probability": "0", "min_temp": "20", "max_temp": "24",
                                }
                            ],
                        ),
                        _fake_weekly_location(
                            "桃園市",
                            [
                                {
                                    "start": "2026-09-08T18:00:00+08:00", "end": "2026-09-09T06:00:00+08:00",
                                    "description": "多雲", "rain_probability": "30", "min_temp": "24", "max_temp": "30",
                                },
                                {
                                    "start": "2026-09-09T06:00:00+08:00", "end": "2026-09-09T18:00:00+08:00",
                                    "description": "晴時多雲", "rain_probability": "10", "min_temp": "26", "max_temp": "32",
                                },
                            ],
                        ),
                    ]
                }
            ]
        }
    }
    monkeypatch.setattr(
        "app.services.weather_service.httpx.get",
        lambda url, params=None, timeout=None: _Response(json_data=fake_response),
    )

    result = weather.run("桃園市")

    assert len(result["forecasts"]) == 2
    first, second = result["forecasts"]
    assert first["description"] == "多雲"
    assert first["rain_probability"] == "30"
    assert first["start_time"] == "2026-09-08T18:00:00+08:00"
    assert first["end_time"] == "2026-09-09T06:00:00+08:00"
    assert second["description"] == "晴時多雲"
    assert second["min_temp"] == "26"
    assert "retrieved_at" in result


def test_get_site_weather_tool_fails_cleanly_on_unknown_location(monkeypatch):
    fake_response = {
        "records": {
            "Locations": [
                {
                    "Location": [
                        _fake_weekly_location(
                            "連江縣",
                            [
                                {
                                    "start": "2026-09-08T18:00:00+08:00", "end": "2026-09-09T06:00:00+08:00",
                                    "description": "晴", "rain_probability": "0", "min_temp": "20", "max_temp": "24",
                                }
                            ],
                        )
                    ]
                }
            ]
        }
    }
    monkeypatch.setattr(
        "app.services.weather_service.httpx.get",
        lambda url, params=None, timeout=None: _Response(json_data=fake_response),
    )

    result = weather.run("不存在的縣市")

    assert "error" in result


def test_get_site_weather_tool_fails_cleanly_on_http_error(monkeypatch):
    def _raise(*args, **kwargs):
        raise httpx.HTTPError("boom")

    monkeypatch.setattr("app.services.weather_service.httpx.get", _raise)

    result = weather.run("桃園市")

    assert "error" in result


def test_check_site_location_tool_detects_point_in_fixture_polygon(monkeypatch, tmp_path):
    monkeypatch.setattr("app.services.geo_service._zones_cache", None)
    monkeypatch.setattr("app.services.geo_service.GEOJSON_PATH", _write_fixture_geojson(tmp_path))
    monkeypatch.setattr("app.services.geo_service.httpx.get", _fake_geocode_get(lat=25.0, lng=121.0))

    result = geo.run("some address inside the fixture zone")

    assert result["potential_geological_sensitive_zone"] is True
    assert result["zone_type"] == "地質敏感區(測試)"
    assert result["data_available"] is True
    assert "disclaimer" in result and result["disclaimer"]


def test_check_site_location_tool_covers_boundary_point_as_overlap(monkeypatch, tmp_path):
    # A point exactly on the fixture polygon's edge -- contains() would
    # (wrongly, for this preliminary-screening use case) say False here;
    # covers() must say True. This test exists specifically to pin that
    # choice.
    monkeypatch.setattr("app.services.geo_service._zones_cache", None)
    monkeypatch.setattr("app.services.geo_service.GEOJSON_PATH", _write_fixture_geojson(tmp_path))
    monkeypatch.setattr("app.services.geo_service.httpx.get", _fake_geocode_get(lat=24.9, lng=121.0))

    result = geo.run("address exactly on the fixture zone boundary")

    assert result["potential_geological_sensitive_zone"] is True


def test_check_site_location_tool_outside_fixture_zone_still_carries_coverage_disclaimer(monkeypatch, tmp_path):
    # A point outside the fixture polygon but where zone data *did* load
    # successfully -- data_available=True, no overlap. The disclaimer must
    # still mention the geographic-coverage limitation ("僅涵蓋桃園市"),
    # since a point outside Taoyuan entirely would look identical to this
    # at the field level otherwise.
    monkeypatch.setattr("app.services.geo_service._zones_cache", None)
    monkeypatch.setattr("app.services.geo_service.GEOJSON_PATH", _write_fixture_geojson(tmp_path))
    monkeypatch.setattr("app.services.geo_service.httpx.get", _fake_geocode_get(lat=1.0, lng=1.0))

    result = geo.run("address far outside the fixture zone")

    assert result["potential_geological_sensitive_zone"] is False
    assert result["data_available"] is True
    assert "僅涵蓋桃園市" in result["disclaimer"]


def test_check_site_location_tool_degrades_gracefully_when_geojson_missing(monkeypatch, tmp_path):
    monkeypatch.setattr("app.services.geo_service._zones_cache", None)
    monkeypatch.setattr("app.services.geo_service.GEOJSON_PATH", tmp_path / "missing.geojson")
    monkeypatch.setattr("app.services.geo_service.httpx.get", _fake_geocode_get(lat=25.0, lng=121.0))

    result = geo.run("some address")

    assert result["potential_geological_sensitive_zone"] is False
    assert result["data_available"] is False
    assert "disclaimer" in result and result["disclaimer"]


def test_check_site_location_tool_fails_cleanly_on_geocode_error(monkeypatch):
    monkeypatch.setattr(
        "app.services.geo_service.httpx.get",
        lambda url, params=None, headers=None, timeout=None: _Response(status_code=400),
    )

    result = geo.run("unresolvable address")

    assert "error" in result


def test_fetch_url_tool_returns_content_from_external_mcp_server(monkeypatch):
    async def _fake_call_fetch_tool(url, max_length):
        return "# Example Domain\nThis domain is for illustrative examples."

    monkeypatch.setattr(
        "app.services.web_fetch_service._call_fetch_tool", _fake_call_fetch_tool
    )

    result = fetch_url.run("https://example.com")

    assert result["url"] == "https://example.com"
    assert "Example Domain" in result["content"]


def test_fetch_url_tool_fails_cleanly_when_mcp_server_errors(monkeypatch):
    async def _raise(url, max_length):
        raise RuntimeError("subprocess boom")

    monkeypatch.setattr("app.services.web_fetch_service._call_fetch_tool", _raise)

    result = fetch_url.run("https://example.com")

    assert "error" in result


# There is no dispatch/transport layer to test for most of these -- Agent
# tool calls (agent_service.py) and the email send path
# (email_service.confirm_and_send) each import and call the relevant
# app.tools.<name>.run() function directly, exactly like any other in-repo
# function call. fetch_url is the one exception: it really does talk to an
# external MCP server subprocess, so its test mocks at that boundary
# (_call_fetch_tool) instead of asserting there's nothing to mock.
