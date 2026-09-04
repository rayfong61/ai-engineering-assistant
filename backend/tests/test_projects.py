from app.models import ProjectMember


def test_create_project_returns_it(client, current_user_override, alice):
    current_user_override(alice)

    response = client.post("/api/projects", json={"name": "T3", "description": "test"})

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "T3"
    assert body["created_by"] == alice["id"]


def test_duplicate_name_for_same_creator_is_rejected(client, current_user_override, alice):
    current_user_override(alice)
    client.post("/api/projects", json={"name": "T3"})

    response = client.post("/api/projects", json={"name": "T3"})

    assert response.status_code == 409


def test_same_name_allowed_for_different_creators(client, current_user_override, alice, bob):
    current_user_override(alice)
    assert client.post("/api/projects", json={"name": "T3"}).status_code == 200

    current_user_override(bob)
    assert client.post("/api/projects", json={"name": "T3"}).status_code == 200


def test_creator_is_added_as_owner_member(client, db_session, current_user_override, alice):
    current_user_override(alice)

    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    membership = (
        db_session.query(ProjectMember)
        .filter_by(project_id=project_id, user_id=alice["id"])
        .one()
    )
    assert membership.role == "owner"


def test_list_projects_only_returns_own_projects(client, current_user_override, alice, bob):
    current_user_override(alice)
    client.post("/api/projects", json={"name": "Alice's project"})

    current_user_override(bob)
    response = client.get("/api/projects")

    assert response.status_code == 200
    assert response.json() == []


def test_owner_can_fetch_own_project(client, current_user_override, alice):
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    response = client.get(f"/api/projects/{project_id}")

    assert response.status_code == 200
    assert response.json()["id"] == project_id


def test_non_member_cannot_fetch_project(client, current_user_override, alice, bob):
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    current_user_override(bob)
    response = client.get(f"/api/projects/{project_id}")

    assert response.status_code == 403


def test_get_nonexistent_project_returns_403_not_404(client, current_user_override, alice):
    # Membership is checked before existence, so a nonexistent project and
    # an existing one the caller isn't a member of are indistinguishable —
    # this avoids leaking which project ids are valid to non-members.
    current_user_override(alice)

    response = client.get("/api/projects/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 403


def test_owner_can_delete_project(client, current_user_override, alice):
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    response = client.delete(f"/api/projects/{project_id}")
    assert response.status_code == 204

    assert client.get(f"/api/projects/{project_id}").status_code == 403


def test_non_owner_member_cannot_delete_project(client, db_session, current_user_override, alice, bob):
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    db_session.add(ProjectMember(project_id=project_id, user_id=bob["id"], role="member"))
    db_session.flush()

    current_user_override(bob)
    response = client.delete(f"/api/projects/{project_id}")

    assert response.status_code == 403
    assert client.get(f"/api/projects/{project_id}").status_code == 200


def test_non_member_cannot_delete_project(client, current_user_override, alice, bob):
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    current_user_override(bob)
    response = client.delete(f"/api/projects/{project_id}")

    assert response.status_code == 403
