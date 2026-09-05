import pymupdf
import pytest


def _pdf_bytes(text: str = "測試工程文件內容") -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture(autouse=True)
def _skip_real_ingestion(monkeypatch):
    """These tests exercise upload auth/validation/storage, not the
    Voyage/Claude pipeline -- that path is covered by test_rag.py (pure DB,
    no external calls) plus manual end-to-end testing against real APIs."""
    monkeypatch.setattr("app.services.rag_service.ingest_document", lambda *a, **k: None)


def test_non_member_cannot_list_documents(client, current_user_override, alice, bob):
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    current_user_override(bob)
    response = client.get(f"/api/projects/{project_id}/documents")

    assert response.status_code == 403


def test_non_member_cannot_upload_document(client, current_user_override, alice, bob):
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    current_user_override(bob)
    response = client.post(
        f"/api/projects/{project_id}/documents",
        files={"file": ("test.pdf", _pdf_bytes(), "application/pdf")},
    )

    assert response.status_code == 403


def test_upload_rejects_non_pdf(client, current_user_override, alice):
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    response = client.post(
        f"/api/projects/{project_id}/documents",
        files={"file": ("test.txt", b"not a pdf", "text/plain")},
    )

    assert response.status_code == 400


def test_member_can_upload_list_and_delete_document(client, current_user_override, alice):
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    upload = client.post(
        f"/api/projects/{project_id}/documents",
        files={"file": ("test.pdf", _pdf_bytes(), "application/pdf")},
    )
    assert upload.status_code == 200
    body = upload.json()
    assert body["filename"] == "test.pdf"
    assert body["status"] == "uploaded"

    listed = client.get(f"/api/projects/{project_id}/documents").json()
    assert len(listed) == 1

    delete = client.delete(f"/api/projects/{project_id}/documents/{body['id']}")
    assert delete.status_code == 204
    assert client.get(f"/api/projects/{project_id}/documents").json() == []
