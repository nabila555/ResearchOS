from fastapi.testclient import TestClient


def _create(client: TestClient, **overrides) -> dict:  # type: ignore[no-untyped-def]
    payload = {"name": "Sleep and memory", "research_question": "Does sleep consolidate memory?"}
    payload.update(overrides)
    response = client.post("/api/projects", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_and_list_projects(client: TestClient) -> None:
    created = _create(client, name="  Trimmed name  ")
    assert created["name"] == "Trimmed name"
    assert created["status"] == "active"
    assert created["document_count"] == 0

    listed = client.get("/api/projects").json()
    assert [p["id"] for p in listed] == [created["id"]]


def test_create_rejects_blank_name(client: TestClient) -> None:
    response = client.post("/api/projects", json={"name": "   "})
    assert response.status_code == 422


def test_update_status_and_filter(client: TestClient) -> None:
    a = _create(client, name="A")
    _create(client, name="B")
    response = client.patch(f"/api/projects/{a['id']}", json={"status": "completed"})
    assert response.status_code == 200
    assert response.json()["status"] == "completed"

    active = client.get("/api/projects", params={"status": "active"}).json()
    assert [p["name"] for p in active] == ["B"]


def test_patch_ignores_null_name(client: TestClient) -> None:
    project = _create(client)
    response = client.patch(f"/api/projects/{project['id']}", json={"name": None})
    assert response.status_code == 200
    assert response.json()["name"] == project["name"]


def test_delete_project(client: TestClient) -> None:
    project = _create(client)
    assert client.delete(f"/api/projects/{project['id']}").status_code == 204
    assert client.get(f"/api/projects/{project['id']}").status_code == 404
    assert client.delete(f"/api/projects/{project['id']}").status_code == 404


def test_missing_project_returns_404(client: TestClient) -> None:
    assert client.get("/api/projects/999").status_code == 404
    assert client.patch("/api/projects/999", json={"name": "x"}).status_code == 404


def test_timestamps_are_timezone_aware(client: TestClient) -> None:
    project = _create(client)
    # Must carry an explicit UTC offset so browsers don't treat it as local time.
    assert project["created_at"].endswith(("Z", "+00:00"))
    activity = client.get("/api/dashboard").json()["recent_activity"][0]
    assert activity["created_at"].endswith(("Z", "+00:00"))
