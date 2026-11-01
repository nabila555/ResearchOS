"""Phase 6: report generators, PDF export, saved reviews, performance guards."""

import io
from typing import Any

import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.ai.registry import AIServices
from app.reports.pdf import markdown_to_html, markdown_to_pdf
from app.services import analysis_service, indexing_service
from tests.fixtures.fake_ai import FakeChat, make_fake_ai
from tests.test_analysis import PAPER, profile_reply


@pytest.fixture
def chat() -> FakeChat:
    return FakeChat(json_reply=profile_reply)


@pytest.fixture
def ai(chat: FakeChat) -> AIServices:
    return make_fake_ai(chat=chat)


def drain(client: TestClient) -> None:
    state = client.app.state  # type: ignore[attr-defined]
    while indexing_service.process_next(state.session_factory, state.ai):
        pass
    while analysis_service.process_next(state.session_factory, state.ai, state.settings):
        pass


def paper(
    client: TestClient, name: str, author: str, year: int, venue: str | None = "Journal of Sleep"
) -> int:
    body = PAPER.replace("# Abstract", f"# {name}\n\n# Abstract")
    doc = client.post(
        "/api/documents/upload",
        files={"file": (f"{name}.md", io.BytesIO(body.encode()), "text/markdown")},
    )
    assert doc.status_code == 201, doc.text
    doc_id = doc.json()["id"]
    client.patch(
        f"/api/documents/{doc_id}",
        json={
            "authors": [author],
            "publication_year": year,
            "venue": venue,
            "volume": "3",
            "pages": "1-9",
        },
    )
    return doc_id


def run(client: TestClient, **body: Any) -> dict[str, Any]:
    response = client.post("/api/analyses", json=body)
    assert response.status_code == 202, response.text
    drain(client)
    return client.get(f"/api/analyses/{response.json()['id']}").json()


# --- PDF ---------------------------------------------------------------------------------


def test_markdown_to_pdf_renders_text_tables_and_page_numbers() -> None:
    markdown = (
        "# Report title\n\nSome *italic* text with ünïcode — “quotes”.\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n"
        + "Long paragraph. " * 900
    )
    data = markdown_to_pdf(markdown, "Report title")
    document = pymupdf.open(stream=data, filetype="pdf")
    assert data.startswith(b"%PDF-")
    assert document.page_count >= 2
    first = document[0].get_text()
    assert "Report title" in first and "ünïcode" in first
    assert f"1 / {document.page_count}" in first
    assert document.metadata["title"] == "Report title"


def test_markdown_html_is_disabled() -> None:
    html = markdown_to_html("<script>alert(1)</script>\n\n<b>bold</b>")
    assert "<script>" not in html and "<b>" not in html
    assert "&lt;script&gt;" in html


# --- Report generators -------------------------------------------------------------------


def test_research_summary_report_without_extra_model_calls(
    client: TestClient, chat: FakeChat
) -> None:
    doc = paper(client, "spindles", "Ada Lovelace", 2021)
    analysis = run(client, kind="summary", document_ids=[doc])
    assert analysis["status"] == "done", analysis["error"]
    assert analysis["title"] == "Research summary: spindles"
    assert len(chat.json_calls) == 3  # the profile passes only
    report = client.get(f"/api/reports/{analysis['report_id']}").json()
    md = report["content_markdown"]
    assert report["report_type"] == "summary"
    assert "**Reference:** Lovelace, A. (2021)." in md
    assert "## Sample size" in md and "48 healthy adults" in md
    assert "⚠ unverified" in md  # the 52-nights statement
    assert "_Not reported in the analysed text._" in md
    assert "no additional AI text" in md


def test_methodology_report_includes_detective_checklist(
    client: TestClient, chat: FakeChat
) -> None:
    from tests.test_analysis import detective_reply

    a, b = paper(client, "a", "Ada Lovelace", 2021), paper(client, "b", "Grace Hopper", 2019)
    without = run(client, kind="methodology", document_ids=[a, b])
    md = client.get(f"/api/reports/{without['report_id']}").json()["content_markdown"]
    assert "| Paper | Methodology & design |" in md
    assert "| Lovelace, 2021 |" in md
    assert "Run the Paper Detective" in md
    assert "## References" in md

    chat.json_reply = detective_reply
    run(client, kind="detective", document_ids=[a])
    chat.json_reply = profile_reply
    with_detective = run(client, kind="methodology", document_ids=[a, b], style="ieee")
    md = client.get(f"/api/reports/{with_detective['report_id']}").json()["content_markdown"]
    assert "## Reproducibility (from Paper Detective runs)" in md
    assert "Unverified" in md  # preregistration quote was not in the text
    assert "[1] A. Lovelace" in md or "[2] A. Lovelace" in md


def proposal_reply(system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
    if "working_title" not in schema["properties"]:
        return profile_reply(system, prompt, schema)
    return {
        "working_title": "Spindles across the lifespan",
        "background": [
            {"text": "P1 linked spindle density to recall.", "papers": [1]},
            {"text": "Memory always improves with sleep.", "papers": []},
        ],
        "problem": [{"text": "Older adults are understudied.", "papers": [1, 2, 9]}],
        "research_questions": ["Does the spindle–memory link weaken with age?"],
        "objectives": ["Measure spindle density across age groups."],
        "methodology": ["Polysomnography in 120 adults aged 20 to 80."],
        "expected_contributions": ["Age-specific evidence."],
        "risks_and_limitations": ["Recruitment of older adults."],
    }


def test_research_proposal_verifies_background_and_uses_gaps(
    client: TestClient, chat: FakeChat
) -> None:
    from tests.test_analysis import gap_reply

    a, b = paper(client, "a", "Ada Lovelace", 2021), paper(client, "b", "Grace Hopper", 2019)
    chat.json_reply = gap_reply
    gaps = run(client, kind="gap_analysis", document_ids=[a, b])
    chat.json_reply = proposal_reply

    bad = client.post("/api/analyses", json={"kind": "proposal", "gap_analysis_id": a + 1000})
    assert bad.status_code == 404
    analysis = run(client, kind="proposal", gap_analysis_id=gaps["id"], topic="Ageing and sleep")
    assert analysis["status"] == "done", analysis["error"]
    assert analysis["document_ids"] == [a, b]  # taken from the gap analysis
    assert analysis["title"] == "Research proposal: Ageing and sleep"
    result = analysis["result"]
    assert [c["supported"] for c in result["background"]] == [True, False]
    assert result["problem"][0]["papers"] == [1, 2]  # P9 dropped
    assert result["used_gap_analysis"] is True
    # The gap findings were given to the model.
    _, prompt, _ = chat.json_calls[-1]
    assert (
        "Research gaps identified earlier" in prompt and "Older adults are rarely studied" in prompt
    )

    md = client.get(f"/api/reports/{analysis['report_id']}").json()["content_markdown"]
    assert md.startswith("# Spindles across the lifespan")
    assert "Lovelace (2021) linked spindle density to recall." in md  # P1 → narrative, no duplicate
    assert "Memory always improves with sleep. [⚠ unsupported]" in md
    assert "(Lovelace, 2021; Hopper, 2019)" in md
    assert "## Proposed research questions" in md and "1. Does the spindle" in md
    assert "Lovelace, A. (2021)" in md and "Hopper, G. (2019)" in md


def test_report_endpoints(client: TestClient) -> None:
    a, b = paper(client, "a", "Ada Lovelace", 2021), paper(client, "b", "Grace Hopper", 2019)
    summary = run(client, kind="summary", document_ids=[a])
    run(client, kind="comparison", document_ids=[a, b])
    assert {r["report_type"] for r in client.get("/api/reports").json()} == {
        "summary",
        "comparison",
    }
    assert [
        r["report_type"]
        for r in client.get("/api/reports", params={"report_type": "summary"}).json()
    ] == ["summary"]

    pdf = client.get(f"/api/reports/{summary['report_id']}/pdf")
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF-")
    assert 'filename="Research-summary-a.pdf"' in pdf.headers["content-disposition"]

    review = client.post("/api/reviews", json={"title": "My review"}).json()
    client.post(f"/api/reviews/{review['id']}/themes", json={"name": "T", "document_ids": [a, b]})
    saved = client.post(f"/api/reviews/{review['id']}/save-report", params={"style": "mla"})
    assert saved.status_code == 201
    report = client.get(f"/api/reports/{saved.json()['report_id']}").json()
    assert (
        report["report_type"] == "literature_review" and "(Lovelace)" in report["content_markdown"]
    )

    assert client.delete(f"/api/reports/{summary['report_id']}").status_code == 204
    assert client.get(f"/api/reports/{summary['report_id']}/pdf").status_code == 404


def test_report_limits(client: TestClient) -> None:
    a = paper(client, "a", "Ada Lovelace", 2021)
    assert (
        client.post("/api/analyses", json={"kind": "methodology", "document_ids": [a]}).status_code
        == 400
    )
    assert (
        client.post("/api/analyses", json={"kind": "proposal", "document_ids": [a]}).status_code
        == 400
    )


# --- Performance guards --------------------------------------------------------------------


def test_shared_reference_edges_are_capped_per_paper(client: TestClient) -> None:
    refs = [f"Classic Reference {i}. Journal of Classics. 1990." for i in range(5)]
    ids = []
    for i in range(8):
        doc = client.post(
            "/api/documents/upload",
            files={
                "file": (f"p{i}.md", io.BytesIO(f"# Paper {i}\nText.".encode()), "text/markdown")
            },
        ).json()
        ids.append(doc["id"])
    state = client.app.state  # type: ignore[attr-defined]
    with state.session_factory() as db:
        from app.models import Document

        for doc_id in ids:
            db.get(Document, doc_id).reference_list = refs
        db.commit()
    graph = client.get("/api/graph", params={"include": ["shared_references"]}).json()
    edges = [e for e in graph["edges"] if e["type"] == "shared_references"]
    # 8 papers all sharing everything would give 28 pairs; each paper keeps its 3 strongest.
    assert len(edges) < 28
    assert edges and all(e["label"] == "5 shared references" for e in edges)


def test_search_snippets_only_for_displayed_page(client: TestClient) -> None:
    for i in range(3):
        client.post(
            "/api/documents/notes",
            json={"title": f"Note {i}", "body": "hippocampal replay during sleep"},
        )
    page = client.get("/api/documents", params={"q": "hippocampal", "limit": 2}).json()
    assert page["total"] == 3 and len(page["items"]) == 2
    assert all("\x02" in item["snippet"] for item in page["items"])
