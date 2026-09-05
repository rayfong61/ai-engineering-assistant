import pytest

from app.models import VisionAnalysis
from app.services import claude_service


def _image_bytes() -> bytes:
    # Not a real decodable PNG -- fine, since analyze_engineering_image is
    # mocked (see below) and the route never decodes the image itself, only
    # checks extension/content-type and forwards raw bytes to Storage.
    return b"\x89PNG\r\n\x1a\nfake-png-bytes-for-testing"


@pytest.fixture(autouse=True)
def _skip_real_vision_call(monkeypatch):
    """These tests exercise upload auth/validation/storage and response
    shape, not the real Claude Vision call -- matches test_documents.py's
    treatment of rag_service.ingest_document."""
    monkeypatch.setattr(
        "app.services.vision_service.analyze_engineering_image",
        lambda *a, **k: {
            "analysis": "測試分析",
            "observations": ["可觀察到測試內容"],
            "limitations": ["僅憑圖片無法確認結構安全性，需人工確認"],
        },
    )


def test_non_member_cannot_upload_image(client, current_user_override, alice, bob):
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    current_user_override(bob)
    response = client.post(
        f"/api/projects/{project_id}/vision",
        files={"file": ("photo.png", _image_bytes(), "image/png")},
    )

    assert response.status_code == 403


def test_non_member_cannot_list_vision_analyses(client, current_user_override, alice, bob):
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    current_user_override(bob)
    response = client.get(f"/api/projects/{project_id}/vision")

    assert response.status_code == 403


def test_upload_rejects_non_image_file(client, current_user_override, alice):
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    response = client.post(
        f"/api/projects/{project_id}/vision",
        files={"file": ("test.pdf", b"not an image", "application/pdf")},
    )

    assert response.status_code == 400


def test_upload_rejects_oversized_image(client, current_user_override, alice, monkeypatch):
    monkeypatch.setattr("app.api.vision.MAX_IMAGE_SIZE", 10)
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    response = client.post(
        f"/api/projects/{project_id}/vision",
        files={"file": ("photo.png", _image_bytes(), "image/png")},
    )

    assert response.status_code == 400


def test_member_can_upload_and_list_vision_analysis(client, current_user_override, alice, db_session):
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    upload = client.post(
        f"/api/projects/{project_id}/vision",
        files={"file": ("photo.png", _image_bytes(), "image/png")},
    )
    assert upload.status_code == 200
    body = upload.json()
    assert body["analysis"] == "測試分析"
    assert body["observations"] == ["可觀察到測試內容"]
    assert body["limitations"] == ["僅憑圖片無法確認結構安全性，需人工確認"]
    assert body["image_url"]  # real signed URL from real local/cloud Storage, not mocked

    record = db_session.query(VisionAnalysis).filter(VisionAnalysis.id == body["id"]).first()
    assert record is not None
    assert record.project_id == uuid_of(project_id)

    listed = client.get(f"/api/projects/{project_id}/vision").json()
    assert len(listed) == 1
    assert listed[0]["id"] == body["id"]
    assert listed[0]["image_url"]


def uuid_of(value: str):
    import uuid

    return uuid.UUID(value)


def test_vision_safety_boundary_phrasing_is_locked():
    # spec2.md section 18's exact wording is load-bearing -- Claude is
    # instructed to use these phrases, never an affirmative safety/
    # compliance/quality claim. Locks the prompt against accidental edits,
    # mirroring how NO_CONTEXT_ANSWER's exact wording is pinned elsewhere.
    prompt = claude_service.VISION_SYSTEM_PROMPT
    assert "可觀察到" in prompt
    assert "疑似" in prompt
    assert "需要人工確認" in prompt
    assert "結構安全" in prompt
    assert "施工品質合格" in prompt
    assert "法規合規" in prompt
