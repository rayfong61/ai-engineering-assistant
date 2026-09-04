def test_missing_bearer_token_is_rejected(client):
    response = client.get("/api/projects")
    assert response.status_code == 401


def test_malformed_authorization_header_is_rejected(client):
    response = client.get("/api/projects", headers={"Authorization": "not-a-bearer-token"})
    assert response.status_code == 401
