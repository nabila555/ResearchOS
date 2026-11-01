"""API tests for the research library: import, search, filters, organisation."""

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.document_processing import web
from app.services import document_service
from tests.fixtures.samples import PAPER_AUTHORS, PAPER_TITLE, write_docx, write_paper_pdf

PDF_MIME = "application/pdf"


def upload(client: TestClient, path: Path, options: dict | None = None, name: str | None = None):  # type: ignore[no-untyped-def]
    with path.open("rb") as fh:
        files = {"file": (name or path.name, fh, "application/octet-stream")}
        data = {"options": json.dumps(options)} if options else None
        return client.post("/api/documents/upload", files=files, data=data)


@pytest.fixture
def paper(client: TestClient, tmp_path: Path) -> dict:
    response = upload(client, write_paper_pdf(tmp_path / "paper.pdf"))
    assert response.status_code == 201, response.text
    return response.json()


def note(client: TestClient, title: str, body: str, **extra) -> dict:  # type: ignore[no-untyped-def]
    response = client.post("/api/documents/notes", json={"title": title, "body": body, **extra})
    assert response.status_code == 201, response.text
    return response.json()


# --- Upload --------------------------------------------------------------------------


def test_upload_pdf_extracts_metadata_and_chunks(
    client: TestClient, paper: dict, settings: Settings
) -> None:
    assert paper["title"] == PAPER_TITLE
    assert paper["authors"] == PAPER_AUTHORS
    assert paper["publication_year"] == 2021
    assert paper["doi"] == "10.1234/jsr.2021.0042"
    assert paper["page_count"] == 4
    assert paper["doc_type"] == "pdf" and paper["status"] == "ready"
    assert paper["has_file"] is True
    assert paper["metadata_sources"]["authors"] == "heuristic"
    assert len(paper["reference_list"]) == 3
    assert paper["chunk_count"] >= 4

    chunks = client.get(f"/api/documents/{paper['id']}/chunks").json()
    assert chunks["total"] == paper["chunk_count"]
    assert {c["page_start"] for c in chunks["items"]} == {1, 2, 3, 4}
    page3 = client.get(f"/api/documents/{paper['id']}/chunks", params={"page": 3}).json()
    assert page3["items"] and all(c["page_start"] <= 3 <= c["page_end"] for c in page3["items"])

    # Stored under a content hash, never under the uploaded name.
    stored = list(settings.documents_dir.rglob("*.pdf"))
    assert len(stored) == 1 and stored[0].name != "paper.pdf"
    file_response = client.get(f"/api/documents/{paper['id']}/file")
    assert file_response.status_code == 200
    assert file_response.headers["content-type"] == PDF_MIME
    assert file_response.content.startswith(b"%PDF-")
    assert not list((settings.data_dir / "tmp").iterdir())


def test_upload_duplicate_returns_conflict(client: TestClient, paper: dict, tmp_path: Path) -> None:
    # Same bytes under a different name (regenerating the PDF would change its timestamp).
    response = upload(client, tmp_path / "paper.pdf", name="renamed-copy.pdf")
    assert response.status_code == 409
    assert response.json()["existing_document_id"] == paper["id"]


def test_upload_rejects_unsupported_and_spoofed_files(client: TestClient, tmp_path: Path) -> None:
    exe = tmp_path / "tool.exe"
    exe.write_bytes(b"MZ\x90\x00")
    assert upload(client, exe).status_code == 415

    spoofed = tmp_path / "paper.pdf"
    spoofed.write_bytes(b"MZ\x90\x00 definitely not a pdf")
    response = upload(client, spoofed)
    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]

    empty = tmp_path / "empty.txt"
    empty.write_bytes(b"")
    assert upload(client, empty).status_code == 400


def test_upload_enforces_size_limit(tmp_path: Path) -> None:
    from app.main import create_app

    settings = Settings(_env_file=None, data_dir=tmp_path / "data", max_upload_mb=1)
    big = tmp_path / "big.txt"
    big.write_bytes(b"a" * (1024 * 1024 + 10))
    with TestClient(create_app(settings)) as small_client:
        response = upload(small_client, big)
    assert response.status_code == 413
    assert not list((settings.data_dir / "tmp").iterdir())


def test_upload_docx_and_markdown_with_options(client: TestClient, tmp_path: Path) -> None:
    collection = client.post("/api/collections", json={"name": "Reefs"}).json()
    project = client.post("/api/projects", json={"name": "Ocean"}).json()
    response = upload(
        client,
        write_docx(tmp_path / "notes.docx"),
        {
            "collection_ids": [collection["id"]],
            "project_ids": [project["id"]],
            "tags": ["Coral", "coral", " field work "],
        },
    )
    assert response.status_code == 201, response.text
    doc = response.json()
    assert doc["title"] == "Field Notes on Coral Bleaching"
    assert [t["name"] for t in doc["tags"]] == ["Coral", "field work"]
    assert doc["collections"] == [{"id": collection["id"], "name": "Reefs"}]
    assert doc["projects"] == [{"id": project["id"], "name": "Ocean"}]
    assert client.get(f"/api/projects/{project['id']}").json()["document_count"] == 1

    md = tmp_path / "attention.md"
    md.write_text(
        "---\ntitle: Attention Notes\nyear: 2017\n---\n# Self-attention\nQueries and keys.\n",
        encoding="utf-8",
    )
    md_doc = upload(client, md).json()
    assert md_doc["title"] == "Attention Notes" and md_doc["doc_type"] == "markdown"
    assert md_doc["publication_year"] == 2017


def test_upload_with_unknown_collection_is_rejected(
    client: TestClient, tmp_path: Path, settings: Settings
) -> None:
    response = upload(client, write_docx(tmp_path / "n.docx"), {"collection_ids": [999]})
    assert response.status_code == 404
    # Nothing stored or half-created.
    assert client.get("/api/documents").json()["total"] == 0
    assert not list(settings.documents_dir.rglob("*.docx"))


# --- Notes & editing -------------------------------------------------------------------


def test_note_create_and_edit_body_rechunks(client: TestClient) -> None:
    created = note(client, "Reading plan", "Read about hippocampal replay.", tags=["todo"])
    assert created["doc_type"] == "note" and created["has_file"] is False
    assert client.get("/api/documents", params={"q": "hippocampal"}).json()["total"] == 1

    response = client.patch(
        f"/api/documents/{created['id']}", json={"note_body": "Now about cortical spindles."}
    )
    assert response.status_code == 200
    assert client.get("/api/documents", params={"q": "hippocampal"}).json()["total"] == 0
    assert client.get("/api/documents", params={"q": "cortical"}).json()["total"] == 1


def test_edit_metadata_marks_manual_and_reindexes(client: TestClient, paper: dict) -> None:
    response = client.patch(
        f"/api/documents/{paper['id']}",
        json={
            "title": "Renamed Study",
            "authors": ["Marie Curie", "marie curie", "Ada Lovelace"],
            "publication_year": None,
            "keywords": ["sleep", " ", "sleep", "EEG"],
            "doi": "https://doi.org/10.9999/ABC",
        },
    )
    assert response.status_code == 200, response.text
    doc = response.json()
    assert doc["title"] == "Renamed Study"
    assert doc["authors"] == ["Marie Curie", "Ada Lovelace"]
    assert doc["publication_year"] is None
    assert doc["keywords"] == ["sleep", "EEG"]
    assert doc["doi"] == "10.9999/abc"
    assert doc["metadata_sources"]["title"] == "manual"
    hits = client.get("/api/documents", params={"q": "renamed"}).json()
    assert [d["id"] for d in hits["items"]] == [paper["id"]]
    assert client.get("/api/documents", params={"author": "curie"}).json()["total"] == 1


def test_note_body_not_editable_on_pdf(client: TestClient, paper: dict) -> None:
    response = client.patch(f"/api/documents/{paper['id']}", json={"note_body": "x"})
    assert response.status_code == 400


# --- Search & filters --------------------------------------------------------------------


def test_search_returns_snippet_and_page(client: TestClient, paper: dict) -> None:
    note(client, "Unrelated", "Coral reefs and ocean temperature.")
    result = client.get("/api/documents", params={"q": "polysomnography"}).json()
    assert result["total"] == 1
    hit = result["items"][0]
    assert hit["id"] == paper["id"]
    # Best passage: the Methods page mentions the term six times.
    assert hit["match_page"] == 2
    assert "\x02" in hit["snippet"] and "\x03" in hit["snippet"]

    # Stemming and prefix matching.
    assert client.get("/api/documents", params={"q": "spindle"}).json()["total"] == 1
    assert client.get("/api/documents", params={"q": "consolid"}).json()["total"] == 1
    # Author search via the document index.
    assert client.get("/api/documents", params={"q": "Lovelace"}).json()["total"] == 1


@pytest.mark.parametrize(
    "query", ['"', "AND OR NOT", "title:(x", "*", "NEAR(a b)", "'; DROP TABLE documents; --"]
)
def test_search_handles_hostile_queries(client: TestClient, paper: dict, query: str) -> None:
    response = client.get("/api/documents", params={"q": query})
    assert response.status_code == 200


def test_filters_and_sorting(client: TestClient, paper: dict, tmp_path: Path) -> None:
    collection = client.post("/api/collections", json={"name": "Sleep"}).json()
    client.put(f"/api/documents/{paper['id']}/collections", json={"ids": [collection["id"]]})
    client.put(f"/api/documents/{paper['id']}/tags", json={"names": ["memory"]})
    a = note(client, "Alpha note", "First.")
    b = note(client, "Beta note", "Second.")
    client.patch(f"/api/documents/{a['id']}", json={"publication_year": 2010})

    def ids(**params) -> list[int]:  # type: ignore[no-untyped-def]
        return [d["id"] for d in client.get("/api/documents", params=params).json()["items"]]

    assert ids(doc_type="note") == [b["id"], a["id"]]
    assert set(ids(doc_type=["note", "pdf"])) == {paper["id"], a["id"], b["id"]}
    assert ids(tag="MEMORY") == [paper["id"]]
    assert ids(collection_id=collection["id"]) == [paper["id"]]
    assert ids(year_from=2015) == [paper["id"]]
    assert ids(year_from=2000, year_to=2012) == [a["id"]]
    assert ids(sort="title") == [a["id"], b["id"], paper["id"]]
    assert ids(sort="year") == [paper["id"], a["id"], b["id"]]
    page = client.get("/api/documents", params={"limit": 2, "offset": 2}).json()
    assert page["total"] == 3 and len(page["items"]) == 1


def test_facets(client: TestClient, paper: dict) -> None:
    client.put(f"/api/documents/{paper['id']}/tags", json={"names": ["sleep"]})
    note(client, "N", "body")
    facets = client.get("/api/library/facets").json()
    assert facets["total"] == 2
    assert {f["value"]: f["count"] for f in facets["types"]} == {"pdf": 1, "note": 1}
    assert facets["years"] == [{"value": "2021", "count": 1}]
    assert {a["value"] for a in facets["authors"]} == set(PAPER_AUTHORS)
    assert [t["name"] for t in facets["tags"]] == ["sleep"]


# --- Collections & tags ---------------------------------------------------------------------


def test_collection_crud(client: TestClient, paper: dict) -> None:
    created = client.post("/api/collections", json={"name": "Thesis", "description": "Chapter 2"})
    assert created.status_code == 201
    cid = created.json()["id"]
    assert client.post("/api/collections", json={"name": "thesis"}).status_code == 409
    client.put(f"/api/documents/{paper['id']}/collections", json={"ids": [cid]})
    listed = client.get("/api/collections").json()
    assert listed[0]["document_count"] == 1
    renamed = client.patch(f"/api/collections/{cid}", json={"name": "Thesis ch.2"}).json()
    assert renamed["name"] == "Thesis ch.2" and renamed["document_count"] == 1
    assert client.delete(f"/api/collections/{cid}").status_code == 204
    # Deleting a collection keeps its documents.
    assert client.get(f"/api/documents/{paper['id']}").json()["collections"] == []


def test_delete_tag(client: TestClient, paper: dict) -> None:
    doc = client.put(f"/api/documents/{paper['id']}/tags", json={"names": ["x", "y"]}).json()
    tag_id = doc["tags"][0]["id"]
    assert client.delete(f"/api/tags/{tag_id}").status_code == 204
    assert [t["name"] for t in client.get(f"/api/documents/{paper['id']}").json()["tags"]] == ["y"]


# --- Delete ----------------------------------------------------------------------------------


def test_delete_document_removes_file_and_index(
    client: TestClient, paper: dict, settings: Settings
) -> None:
    assert client.delete(f"/api/documents/{paper['id']}").status_code == 204
    assert client.get(f"/api/documents/{paper['id']}").status_code == 404
    assert not list(settings.documents_dir.rglob("*.pdf"))
    assert not list(settings.documents_dir.iterdir())  # empty hash folder removed too
    assert client.get("/api/documents", params={"q": "polysomnography"}).json()["total"] == 0
    activity = client.get("/api/dashboard").json()["recent_activity"]
    assert activity[0]["action"] == "document.deleted"


# --- URL import ---------------------------------------------------------------------------------


@pytest.fixture
def fake_web(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):  # type: ignore[no-untyped-def]
    pdf_bytes = write_paper_pdf(tmp_path / "remote.pdf").read_bytes()
    html = (
        b'<html><head><meta name="citation_title" content="Remote Article">'
        b'<meta name="citation_author" content="Grace Hopper"></head>'
        b"<body><article><p>Compilers changed computing forever.</p></article></body></html>"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith(".pdf"):
            return httpx.Response(200, headers={"content-type": PDF_MIME}, content=pdf_bytes)
        return httpx.Response(
            200, headers={"content-type": "text/html; charset=utf-8"}, content=html
        )

    real_fetch = web.fetch_url

    def fetch(url: str, **kwargs):  # type: ignore[no-untyped-def]
        kwargs.update(transport=httpx.MockTransport(handler), resolver=lambda _h: ["93.184.216.34"])
        return real_fetch(url, **kwargs)

    monkeypatch.setattr(document_service, "fetch_url", fetch)


def test_import_web_article(client: TestClient, fake_web: None) -> None:
    response = client.post(
        "/api/documents/url", json={"url": "https://example.org/article", "tags": ["web"]}
    )
    assert response.status_code == 201, response.text
    doc = response.json()
    assert doc["doc_type"] == "web" and doc["title"] == "Remote Article"
    assert doc["authors"] == ["Grace Hopper"]
    assert doc["source_url"] == "https://example.org/article"
    assert client.get("/api/documents", params={"q": "compilers"}).json()["total"] == 1
    again = client.post("/api/documents/url", json={"url": "https://example.org/article"})
    assert again.status_code == 409


def test_import_pdf_by_url(client: TestClient, fake_web: None) -> None:
    response = client.post(
        "/api/documents/url", json={"url": "https://example.org/papers/spindles.pdf"}
    )
    assert response.status_code == 201, response.text
    doc = response.json()
    assert doc["doc_type"] == "pdf" and doc["has_file"] is True
    assert doc["title"] == PAPER_TITLE
    assert doc["original_filename"] == "spindles.pdf"


def test_import_private_url_rejected(client: TestClient) -> None:
    response = client.post("/api/documents/url", json={"url": "http://127.0.0.1:8000/api/health"})
    assert response.status_code == 400
    assert "private" in response.json()["detail"]
