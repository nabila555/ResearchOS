"""Phase 5: citations, knowledge graph, literature review workspace."""

from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.ai.registry import AIServices
from app.citations import (
    CitationData,
    bibliography,
    format_citation,
    in_text,
    parse_name,
    to_bibtex,
    to_ris,
)
from app.services import analysis_service, indexing_service
from tests.fixtures.fake_ai import FakeChat, make_fake_ai
from tests.test_analysis import PAPER, profile_reply

ARTICLE = CitationData(
    1,
    "article",
    "Screen time before bed and sleep quality",
    [parse_name("Maya Patel"), parse_name("Jonas van der Berg"), parse_name("Jean-Paul Sartre")],
    2024,
    venue="Journal of Sleep Research",
    volume="33",
    issue="2",
    pages="101-115",
    doi="10.1111/jsr.14000",
)
WEB = CitationData(
    2,
    "web",
    "How sleep works",
    [],
    None,
    url="https://www.sleepfoundation.org/how-sleep-works",
    accessed=datetime(2026, 11, 2),
)
REPORT = CitationData(
    3,
    "document",
    "National sleep survey",
    [parse_name("Lee, Kim")],
    2019,
    publisher="Sleep Council",
)


# --- Citations ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "given", "family"),
    [
        ("Maya Patel", "Maya", "Patel"),
        ("Patel, Maya", "Maya", "Patel"),
        ("Jonas van der Berg", "Jonas", "van der Berg"),
        ("Plato", "", "Plato"),
        ("Alan M.  Turing", "Alan M.", "Turing"),
    ],
)
def test_parse_name(raw: str, given: str, family: str) -> None:
    name = parse_name(raw)
    assert (name.given, name.family) == (given, family)


def test_initials() -> None:
    assert parse_name("Jean-Paul Sartre").initials == "J.-P."
    assert parse_name("Alan M. Turing").initials == "A. M."


@pytest.mark.parametrize(
    ("style", "expected"),
    [
        (
            "apa",
            "Patel, M., van der Berg, J., & Sartre, J.-P. (2024). Screen time before bed and sleep quality. "
            "*Journal of Sleep Research*, *33*(2), 101–115. https://doi.org/10.1111/jsr.14000",
        ),
        (
            "mla",
            "Patel, Maya, et al. “Screen time before bed and sleep quality.” *Journal of Sleep Research*, "
            "vol. 33, no. 2, 2024, pp. 101-115. https://doi.org/10.1111/jsr.14000.",
        ),
        (
            "chicago",
            "Patel, Maya, Jonas van der Berg, and Jean-Paul Sartre. 2024. “Screen time before bed and "
            "sleep quality.” *Journal of Sleep Research* 33 (2): 101–115. https://doi.org/10.1111/jsr.14000.",
        ),
        (
            "ieee",
            "M. Patel, J. van der Berg, and J.-P. Sartre, “Screen time before bed and sleep quality,” "
            "*Journal of Sleep Research*, vol. 33, no. 2, pp. 101–115, 2024. doi: 10.1111/jsr.14000.",
        ),
    ],
)
def test_journal_article_styles(style: str, expected: str) -> None:
    formatted = format_citation(ARTICLE, style)  # type: ignore[arg-type]
    assert formatted.markdown == expected
    assert formatted.missing == []


def test_missing_metadata_is_reported_not_invented() -> None:
    apa = format_citation(WEB, "apa")
    assert apa.text.startswith("How sleep works. (n.d.).")
    assert apa.missing == ["authors", "year"]
    mla = format_citation(WEB, "mla")
    assert mla.text.endswith("Accessed 2 Nov. 2026.")
    sparse = CitationData(9, "article", "T", [parse_name("A B")], 2020, venue="J")
    assert format_citation(sparse, "apa").missing == ["volume", "pages", "doi"]
    assert "None" not in format_citation(sparse, "ieee").text


def test_report_and_in_text() -> None:
    assert (
        format_citation(REPORT, "apa").markdown
        == "Lee, K. (2019). *National sleep survey*. Sleep Council."
    )
    assert in_text(ARTICLE, "apa") == "(Patel et al., 2024)"
    assert in_text(ARTICLE, "mla") == "(Patel et al.)"
    assert in_text(REPORT, "chicago") == "(Lee, 2019)"
    assert in_text(WEB, "apa") == "(“How sleep works”, n.d.)"
    assert in_text(ARTICLE, "ieee", 3) == "[3]"
    two = CitationData(4, "document", "X", [parse_name("A One"), parse_name("B Two")], 2020)
    assert (
        in_text(two, "apa") == "(One & Two, 2020)"
        and in_text(two, "chicago") == "(One and Two, 2020)"
    )


def test_bibliography_ordering() -> None:
    items = [ARTICLE, REPORT, WEB]
    assert [d.id for d, _ in bibliography(items, "apa")] == [2, 3, 1]  # How…, Lee, Patel
    assert [d.id for d, _ in bibliography(items, "ieee")] == [1, 3, 2]  # citation order


def test_bibtex_and_ris() -> None:
    tricky = CitationData(
        5,
        "article",
        "Costs & benefits of 100% recall_rate",
        [parse_name("Ana Ruiz")],
        2024,
        venue="J",
        pages="5-9",
    )
    twin = CitationData(6, "article", "Costs of sleep", [parse_name("Ana Ruiz")], 2024, venue="J")
    bib = to_bibtex([ARTICLE, tricky, twin, WEB])
    assert "@article{patel2024screen," in bib
    assert "author = {Patel, Maya and van der Berg, Jonas and Sartre, Jean-Paul}" in bib
    assert r"Costs \& benefits of 100\% recall\_rate" in bib
    assert "pages = {5--9}" in bib
    assert "@article{ruiz2024costs," in bib and "@article{ruiz2024costsa," in bib  # unique keys
    assert "@online{anonndsleep," in bib and "urldate = {2026-11-02}" in bib
    ris = to_ris([ARTICLE])
    assert (
        "TY  - JOUR" in ris
        and "SP  - 101" in ris
        and "EP  - 115" in ris
        and ris.rstrip().endswith("ER  -")
    )


def test_citation_api_excludes_notes_and_exports(client: TestClient) -> None:
    client.post("/api/documents/notes", json={"title": "My note", "body": "x"})
    doc = client.post("/api/documents/notes", json={"title": "Paper", "body": "text"}).json()
    # Turn the second item into something citable by giving it a venue via a PDF-like edit.
    client.patch(
        f"/api/documents/{doc['id']}", json={"venue": "Journal", "volume": "4", "pages": "1-2"}
    )
    detail = client.get(f"/api/documents/{doc['id']}").json()
    assert (detail["volume"], detail["pages"]) == ("4", "1-2")
    # Notes are never cited.
    assert client.get("/api/citations").json() == []
    styles = client.get("/api/citations/styles").json()
    assert set(styles) == {"apa", "mla", "chicago", "ieee"}
    exported = client.get("/api/citations/export", params={"format": "bibtex"})
    assert exported.status_code == 200
    assert 'filename="references.bib"' in exported.headers["content-disposition"]


# --- Knowledge graph -----------------------------------------------------------------------


def _paper(
    client: TestClient,
    title: str,
    body: str,
    *,
    authors: list[str],
    tags: list[str],
    keywords: list[str],
) -> int:
    doc = client.post(
        "/api/documents/notes", json={"title": title, "body": body, "tags": tags}
    ).json()
    client.patch(f"/api/documents/{doc['id']}", json={"authors": authors, "keywords": keywords})
    return doc["id"]


@pytest.fixture
def chat() -> FakeChat:
    return FakeChat(json_reply=profile_reply)


@pytest.fixture
def ai(chat: FakeChat) -> AIServices:
    return make_fake_ai(chat=chat)


def _drain(client: TestClient) -> None:
    state = client.app.state  # type: ignore[attr-defined]
    while indexing_service.process_next(state.session_factory, state.ai):
        pass
    while analysis_service.process_next(state.session_factory, state.ai, state.settings):
        pass


def test_graph_layers_from_real_data(client: TestClient) -> None:
    # The graph only includes non-note documents; convert notes by giving them a venue? No:
    # graph excludes notes by type, so use markdown uploads instead.
    import io

    def upload(name: str, text: str) -> int:
        response = client.post(
            "/api/documents/upload",
            files={"file": (name, io.BytesIO(text.encode()), "text/markdown")},
        )
        assert response.status_code == 201, response.text
        return response.json()["id"]

    a = upload(
        "a.md", "# Spindles and memory\nSleep spindles predict memory consolidation in adults.\n"
    )
    b = upload(
        "b.md", "# Spindle density\nSleep spindles predict memory consolidation in older adults.\n"
    )
    c = upload("c.md", "# Coral reefs\nOcean warming bleaches coral reefs worldwide.\n")
    client.patch(
        f"/api/documents/{a}", json={"authors": ["Ada Lovelace"], "keywords": ["Sleep", "memory"]}
    )
    client.patch(
        f"/api/documents/{b}",
        json={"authors": ["Ada Lovelace", "Alan Turing"], "keywords": ["sleep"]},
    )
    client.patch(f"/api/documents/{c}", json={"authors": ["Rachel Carson"], "keywords": ["coral"]})
    client.put(f"/api/documents/{a}/tags", json={"names": ["neuro"]})
    _drain(client)

    graph = client.get("/api/graph", params={"similarity": 0.5}).json()
    nodes = {n["id"]: n for n in graph["nodes"]}
    edges = {(e["type"], e["source"], e["target"]) for e in graph["edges"]}
    assert graph["stats"]["paper"] == 3 and graph["stats"]["author"] == 3
    assert ("authored", "author:1", f"paper:{a}") in edges and (
        "authored",
        "author:1",
        f"paper:{b}",
    ) in edges
    assert ("tagged", f"paper:{a}", "topic:1") in edges
    # Keywords appear only when shared by two papers ("Sleep" and "sleep" normalise together).
    assert (
        "keyword:sleep" in nodes and "keyword:memory" not in nodes and "keyword:coral" not in nodes
    )
    assert nodes["keyword:sleep"]["label"].lower() == "sleep"
    similar = [e for e in graph["edges"] if e["type"] == "similar"]
    assert {(e["source"], e["target"]) for e in similar} == {
        tuple(sorted((f"paper:{a}", f"paper:{b}")))
    }
    assert nodes[f"paper:{a}"]["data"]["degree"] >= 3

    only_papers = client.get("/api/graph", params={"include": ["topic"]}).json()
    assert set(only_papers["stats"]) == {"paper", "topic"}

    collection = client.post("/api/collections", json={"name": "Reefs"}).json()
    client.put(f"/api/documents/{c}/collections", json={"ids": [collection["id"]]})
    scoped = client.get("/api/graph", params={"collection_id": collection["id"]}).json()
    assert [n["id"] for n in scoped["nodes"] if n["type"] == "paper"] == [f"paper:{c}"]


def test_graph_shared_references() -> None:
    from app.services.graph_service import _normalise

    assert _normalise("Walker, M. (2009). Sleep!") == "walker m 2009 sleep"


def test_paper_details_only_verified_statements(client: TestClient) -> None:
    doc = client.post(
        "/api/documents/notes", json={"title": "Spindles study", "body": PAPER}
    ).json()
    assert client.get(f"/api/graph/papers/{doc['id']}").json()["has_profile"] is False
    client.post("/api/analyses", json={"kind": "profile", "document_ids": [doc["id"]]})
    _drain(client)
    details = client.get(f"/api/graph/papers/{doc['id']}").json()
    kinds = [n["type"] for n in details["nodes"]]
    # methodology statement was unverified (number 52) and one finding was unverified.
    assert kinds == ["finding"]
    assert details["nodes"][0]["data"]["page"] is None or details["nodes"][0]["data"]["quote"]
    assert client.get("/api/graph/papers/999").status_code == 404


# --- Literature review -----------------------------------------------------------------------


def synthesis_reply(system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
    if "synthesis" not in schema["properties"]:
        return profile_reply(system, prompt, schema)
    claim = lambda text, papers: {"text": text, "papers": papers}  # noqa: E731
    return {
        "synthesis": [
            claim("Both studies link spindles to memory.", [1, 2]),
            claim("Sleep is universally essential.", []),  # unsupported
            claim("A third study disagrees.", [7]),  # outside the theme
        ],
        "agreements": [claim("Spindles matter.", [1, 2]), claim("Only one paper says so.", [1])],
        "disagreements": [],
    }


def test_review_workspace_end_to_end(client: TestClient, chat: FakeChat) -> None:
    chat.json_reply = synthesis_reply
    a = client.post("/api/documents/notes", json={"title": "Spindles A", "body": PAPER}).json()[
        "id"
    ]
    b = client.post(
        "/api/documents/notes", json={"title": "Spindles B", "body": PAPER + "\nMore."}
    ).json()["id"]

    review = client.post(
        "/api/reviews",
        json={"title": "Sleep & memory review", "research_question": "Do spindles matter?"},
    ).json()
    review = client.post(
        f"/api/reviews/{review['id']}/themes", json={"name": "Spindles", "document_ids": [a, b]}
    ).json()
    review = client.post(f"/api/reviews/{review['id']}/themes", json={"name": "Other"}).json()
    spindles, other = review["themes"]
    assert [i["document_id"] for i in spindles["items"]] == [a, b] and other["items"] == []

    # Reorder themes and edit item notes.
    review = client.patch(f"/api/reviews/themes/{other['id']}", json={"position": 0}).json()
    assert [t["name"] for t in review["themes"]] == ["Other", "Spindles"]
    review = client.put(
        f"/api/reviews/themes/{spindles['id']}/items",
        json={"items": [{"document_id": b, "note": "Key paper"}, {"document_id": a}]},
    ).json()
    assert review["themes"][1]["items"][0]["note"] == "Key paper"
    dup = client.put(
        f"/api/reviews/themes/{spindles['id']}/items",
        json={"items": [{"document_id": a}, {"document_id": a}]},
    )
    assert dup.status_code == 400
    assert (
        client.post(f"/api/reviews/themes/{other['id']}/summary").status_code == 400
    )  # empty theme

    # AI theme summary with verified claims.
    assert client.post(f"/api/reviews/themes/{spindles['id']}/summary").status_code == 202
    _drain(client)
    theme = client.get(f"/api/reviews/{review['id']}").json()["themes"][1]
    result = theme["summary"]["result"]
    assert theme["summary"]["status"] == "done" and theme["summary"]["stale"] is False
    supported = [c["supported"] for c in result["synthesis"]]
    assert supported == [True, False, False]
    assert "outside this theme" in result["synthesis"][2]["notes"][0]
    assert [c["supported"] for c in result["agreements"]] == [True, False]

    # Export with in-text citations and a references list.
    client.patch(f"/api/reviews/{review['id']}", json={"introduction": "Why this matters."})
    markdown = client.get(f"/api/reviews/{review['id']}/export").text
    assert markdown.startswith("# Sleep & memory review")
    assert "## Introduction" in markdown and "Why this matters." in markdown
    assert "[⚠ unsupported]" in markdown
    assert "Only one paper says so" not in markdown  # unsupported agreements are dropped
    # Notes are not citable, so this review cites nothing and has no references section.
    assert "## References" not in markdown

    # Changing the theme's papers marks the summary stale.
    client.put(f"/api/reviews/themes/{spindles['id']}/items", json={"items": [{"document_id": a}]})
    assert (
        client.get(f"/api/reviews/{review['id']}").json()["themes"][1]["summary"]["stale"] is True
    )

    assert client.delete(f"/api/reviews/{review['id']}").status_code == 204
    assert client.get(f"/api/reviews/{review['id']}").status_code == 404


def test_review_export_cites_papers(client: TestClient) -> None:
    import io

    ids = []
    for name, author, year in (("a.md", "Ada Lovelace", 2021), ("b.md", "Grace Hopper", 2019)):
        doc = client.post(
            "/api/documents/upload",
            files={"file": (name, io.BytesIO(f"# {name}\nBody text.".encode()), "text/markdown")},
        ).json()
        client.patch(
            f"/api/documents/{doc['id']}",
            json={"authors": [author], "publication_year": year, "venue": "J"},
        )
        ids.append(doc["id"])
    review = client.post("/api/reviews", json={"title": "R"}).json()
    client.post(f"/api/reviews/{review['id']}/themes", json={"name": "T", "document_ids": ids})
    apa = client.get(f"/api/reviews/{review['id']}/export").text
    assert "(Lovelace, 2021)" in apa and "(Hopper, 2019)" in apa
    assert apa.index("Hopper, G. (2019)") < apa.index("Lovelace, A. (2021)")  # alphabetical
    ieee = client.get(f"/api/reviews/{review['id']}/export", params={"style": "ieee"}).text
    assert "[1]" in ieee and "[2] G. Hopper" in ieee


def test_suggest_themes_groups_similar_papers(client: TestClient) -> None:
    import io

    def upload(name: str, text: str) -> int:
        return client.post(
            "/api/documents/upload",
            files={"file": (name, io.BytesIO(text.encode()), "text/markdown")},
        ).json()["id"]

    a = upload("a.md", "# Sleep spindles\nSleep spindles predict memory consolidation.")
    b = upload("b.md", "# Spindles again\nSleep spindles predict memory consolidation strongly.")
    c = upload("c.md", "# Reefs\nOcean warming bleaches coral reefs.")
    d = upload("d.md", "# Not indexed\nNothing.")
    state = client.app.state  # type: ignore[attr-defined]
    with state.session_factory() as db:
        from sqlalchemy import update

        from app.models.ai import IndexJob

        db.execute(update(IndexJob).where(IndexJob.document_id == d).values(status="done"))
        db.commit()
    _drain(client)
    review = client.post("/api/reviews", json={"title": "R"}).json()
    result = client.post(
        f"/api/reviews/{review['id']}/suggest-themes", json={"document_ids": [a, b, c, d]}
    ).json()
    groups = sorted(sorted(g["document_ids"]) for g in result["groups"])
    assert groups == [sorted([a, b]), [c]]
    assert result["unindexed_document_ids"] == [d]


def test_narrative_citations_and_ieee_document_doi() -> None:
    from app.citations import narrative

    assert narrative(ARTICLE, "apa") == "Patel et al. (2024)"
    assert narrative(REPORT, "mla") == "Lee"
    assert narrative(ARTICLE, "ieee", 2) == "[2]"
    doc = CitationData(7, "document", "Report", [parse_name("Ann Lee")], 2020, doi="10.1/abc")
    assert format_citation(doc, "ieee").text.endswith("doi: 10.1/abc.")


def test_export_replaces_model_paper_labels(client: TestClient, chat: FakeChat) -> None:
    import io

    def reply(system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        if "synthesis" not in schema["properties"]:
            return profile_reply(system, prompt, schema)
        return {
            "synthesis": [
                {"text": "P1 found an effect that P2 did not replicate.", "papers": [1, 2]}
            ],
            "agreements": [],
            "disagreements": [],
        }

    chat.json_reply = reply
    ids = []
    for name, author, year in (("a.md", "Ada Lovelace", 2021), ("b.md", "Grace Hopper", 2019)):
        body = PAPER.replace("# Abstract", f"# {name}")
        doc = client.post(
            "/api/documents/upload",
            files={"file": (name, io.BytesIO(body.encode()), "text/markdown")},
        ).json()
        client.patch(
            f"/api/documents/{doc['id']}",
            json={"authors": [author], "publication_year": year, "venue": "J"},
        )
        ids.append(doc["id"])
    review = client.post("/api/reviews", json={"title": "R"}).json()
    review = client.post(
        f"/api/reviews/{review['id']}/themes", json={"name": "T", "document_ids": ids}
    ).json()
    client.post(f"/api/reviews/themes/{review['themes'][0]['id']}/summary")
    _drain(client)
    markdown = client.get(f"/api/reviews/{review['id']}/export").text
    # Both papers are named in the sentence, so no duplicate parenthetical citation follows.
    assert "Lovelace (2021) found an effect that Hopper (2019) did not replicate." in markdown
    assert "P1" not in markdown
