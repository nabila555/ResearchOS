from fastapi.testclient import TestClient

from app.models import Collection, Document, DocumentType, Report, Tag


def test_empty_dashboard(client: TestClient) -> None:
    body = client.get("/api/dashboard").json()
    assert body["stats"]["documents_total"] == 0
    assert set(body["stats"]["documents_by_type"]) == {t.value for t in DocumentType}
    assert body["recent_documents"] == []
    assert body["topics"] == []
    assert body["active_projects"] == []
    assert body["recent_activity"] == []
    assert body["recent_reports"] == []


def test_dashboard_reflects_library_contents(client: TestClient) -> None:
    session = client.app.state.session_factory()  # type: ignore[attr-defined]
    try:
        ml = Tag(name="machine learning")
        ethics = Tag(name="ethics")
        session.add_all(
            [
                Document(title="Paper A", doc_type=DocumentType.PDF, tags=[ml, ethics]),
                Document(title="Paper B", doc_type=DocumentType.PDF, tags=[ml]),
                Document(title="My note", doc_type=DocumentType.NOTE),
                Collection(name="Thesis"),
                Report(title="Gap report", report_type="gap_analysis", content_markdown="# Gaps"),
            ]
        )
        session.commit()
    finally:
        session.close()

    client.post("/api/projects", json={"name": "Active one"})
    paused = client.post("/api/projects", json={"name": "Paused one", "status": "paused"}).json()
    assert paused["status"] == "paused"

    body = client.get("/api/dashboard").json()
    stats = body["stats"]
    assert stats["documents_total"] == 3
    assert stats["documents_by_type"]["pdf"] == 2
    assert stats["documents_by_type"]["note"] == 1
    assert stats["collections_total"] == 1
    assert stats["projects_total"] == 2
    assert stats["projects_active"] == 1
    assert stats["reports_total"] == 1

    assert body["topics"][0] == {"name": "machine learning", "document_count": 2}
    assert [p["name"] for p in body["active_projects"]] == ["Active one"]
    assert body["recent_activity"][0]["action"] == "project.created"
    assert body["recent_reports"][0]["title"] == "Gap report"
    assert len(body["recent_documents"]) == 3
