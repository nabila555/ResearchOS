"""Phase 4: paper profiles, comparison, gap finder, detective (fake providers)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.ai.providers import ProviderError
from app.ai.registry import AIServices
from app.models.library import Chunk
from app.research_analysis.evidence import Excerpt as Ex
from app.research_analysis.evidence import Focus, check_statement, quote_supported, select_excerpts
from app.services import analysis_service
from tests.fixtures.fake_ai import FakeChat, make_fake_ai

PAPER = """# Abstract
We test whether sleep spindles support memory consolidation in healthy adults.

# Methods
We recruited 48 healthy adults from a university sample.
Sleep was recorded with polysomnography over two nights.

# Results
Spindle density correlated with recall of word pairs. The effect was absent in older adults.

# References
Walker, M. (2009). Sleep and memory. Journal of Sleep.
"""

OTHER = """# Abstract
A survey of 300 students examined sleep habits and exam performance.

# Results
Shorter sleep predicted lower exam scores.
"""


def profile_reply(_system: str, _prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
    keys = list(schema["properties"])
    out: dict[str, Any] = {k: {"reported": False, "statements": []} for k in keys}
    if "sample_size" in keys:
        out["sample_size"] = {
            "reported": True,
            "statements": [
                {
                    "text": "48 healthy adults",
                    "source": 2,
                    "quote": "We recruited 48 healthy adults from a university sample",
                }
            ],
        }
        # The number 52 is not in the excerpt: must be flagged.
        out["methodology"] = {
            "reported": True,
            "statements": [
                {
                    "text": "Polysomnography over 52 nights",
                    "source": 2,
                    "quote": "Sleep was recorded with polysomnography over two nights",
                }
            ],
        }
        # Excerpt 9 does not exist.
        out["dataset"] = {
            "reported": True,
            "statements": [
                {
                    "text": "EEG recordings",
                    "source": 9,
                    "quote": "EEG recordings of all participants",
                }
            ],
        }
    if "key_findings" in keys:
        out["key_findings"] = {
            "reported": True,
            "statements": [
                {
                    "text": "Spindle density correlated with recall",
                    "source": 3,
                    "quote": "Spindle density correlated with recall of word pairs",
                },
                {
                    "text": "Spindles cause memory gains",
                    "source": 3,
                    "quote": "spindles directly cause large memory gains in everyone",
                },
            ],
        }
    return out


@pytest.fixture
def chat() -> FakeChat:
    return FakeChat(json_reply=profile_reply)


@pytest.fixture
def ai(chat: FakeChat) -> AIServices:
    return make_fake_ai(chat=chat)


def note(client: TestClient, title: str, body: str) -> dict:
    response = client.post("/api/documents/notes", json={"title": title, "body": body})
    assert response.status_code == 201, response.text
    return response.json()


def run(client: TestClient, kind: str, **body) -> dict:  # type: ignore[no-untyped-def]
    response = client.post("/api/analyses", json={"kind": kind, **body})
    assert response.status_code == 202, response.text
    state = client.app.state  # type: ignore[attr-defined]
    while analysis_service.process_next(state.session_factory, state.ai, state.settings):
        pass
    return client.get(f"/api/analyses/{response.json()['id']}").json()


# --- Evidence verification --------------------------------------------------------------


def test_quote_support_and_number_checks() -> None:
    passage = "We recruited 48 healthy adults. Spindle den-\nsity correlated with recall."
    assert quote_supported("We recruited 48 healthy adults", passage)
    assert quote_supported("spindle density correlated with recall", passage)  # hyphenation, case
    assert not quote_supported("adults", passage)  # too short to count as evidence
    assert not quote_supported("participants were randomly assigned to groups", passage)
    excerpt = Ex(1, 10, 2, 2, "Methods", passage)
    assert check_statement("48 adults", "We recruited 48 healthy adults", excerpt) == (True, None)
    ok, reason = check_statement("52 adults", "We recruited 48 healthy adults", excerpt)
    assert not ok and "52" in reason
    assert check_statement("x", "We recruited 48 healthy adults", None)[0] is False


def test_select_excerpts_prefers_sections_and_skips_references() -> None:
    def chunk(i: int, section: str, text: str) -> Chunk:
        return Chunk(
            id=i,
            document_id=1,
            chunk_index=i,
            page_start=i,
            page_end=i,
            section=section,
            text=text,
            char_count=len(text),
        )

    chunks = [
        chunk(0, "Introduction", "intro " * 50),
        chunk(1, "Methods", "participants sample recruited " * 20),
        chunk(2, "Discussion", "discussion " * 50),
        chunk(3, "References", "Smith J. 2020. " * 10),
    ]
    picked = select_excerpts(
        chunks, Focus(("method",), ("participant", "sample")), budget_chars=650
    )
    assert [e.chunk_id for e in picked] == [1]
    everything = select_excerpts(chunks, Focus(("method",), ()), budget_chars=100_000)
    assert [e.chunk_id for e in everything] == [0, 1, 2]  # references never included
    assert [e.n for e in everything] == [1, 2, 3]


# --- Paper profile -----------------------------------------------------------------------


def test_profile_extraction_verifies_every_statement(client: TestClient, chat: FakeChat) -> None:
    doc = note(client, "Spindles study", PAPER)
    analysis = run(client, "profile", document_ids=[doc["id"]])
    assert analysis["status"] == "done", analysis["error"]
    assert len(chat.json_calls) == 3  # overview, methods, results

    profile = client.get(f"/api/documents/{doc['id']}/profile").json()
    fields = {f["key"]: f for f in profile["fields"]}
    assert profile["stale"] is False and profile["model"] == "fake-chat"
    assert fields["sample_size"]["status"] == "verified"
    evidence = fields["sample_size"]["statements"][0]["evidence"]
    assert evidence["verified"] and evidence["section"] == "Methods"
    assert fields["methodology"]["status"] == "unverified"
    assert "52" in fields["methodology"]["statements"][0]["evidence"]["reason"]
    assert (
        fields["dataset"]["statements"][0]["evidence"]["reason"]
        == "cites an excerpt that was not provided"
    )
    assert fields["key_findings"]["status"] == "partial"
    assert fields["research_objective"]["status"] == "not_reported"

    # The references section is never sent to the model.
    assert all("Walker, M." not in prompt for _, prompt, _ in chat.json_calls)

    # Editing the text makes the cached profile stale.
    client.patch(f"/api/documents/{doc['id']}", json={"note_body": PAPER + "\nExtra paragraph."})
    assert client.get(f"/api/documents/{doc['id']}/profile").json()["stale"] is True


def test_profile_missing_returns_404(client: TestClient) -> None:
    doc = note(client, "Spindles study", PAPER)
    assert client.get(f"/api/documents/{doc['id']}/profile").status_code == 404


# --- Comparison --------------------------------------------------------------------------


def test_comparison_reuses_profiles_and_creates_report(client: TestClient, chat: FakeChat) -> None:
    a, b = note(client, "Spindles study", PAPER), note(client, "Sleep survey", OTHER)
    first = run(client, "comparison", document_ids=[a["id"], b["id"]])
    assert first["status"] == "done", first["error"]
    assert first["title"] == "Comparison: Spindles study vs Sleep survey"
    assert len(chat.json_calls) == 6
    result = first["result"]
    assert [d["id"] for d in result["documents"]] == [a["id"], b["id"]]
    assert result["profiles"][str(a["id"])]["sample_size"]["status"] == "verified"
    assert len(result["fields"]) == 10

    # A second comparison reuses the cached profiles: no new model calls.
    run(client, "comparison", document_ids=[b["id"], a["id"]])
    assert len(chat.json_calls) == 6

    report = client.get(f"/api/reports/{first['report_id']}").json()
    assert report["report_type"] == "comparison"
    assert "| **Sample size** |" in report["content_markdown"]
    assert "⚠ unverified" in report["content_markdown"]
    download = client.get(f"/api/reports/{first['report_id']}/download")
    assert download.headers["content-type"].startswith("text/markdown")
    assert (
        'filename="Comparison-Spindles-study-vs-Sleep-survey.md"'
        in download.headers["content-disposition"]
    )
    dashboard = client.get("/api/dashboard").json()
    assert dashboard["recent_reports"][0]["report_type"] == "comparison"


def test_comparison_limits_and_empty_documents(client: TestClient) -> None:
    a = note(client, "Spindles study", PAPER)
    assert (
        client.post(
            "/api/analyses", json={"kind": "comparison", "document_ids": [a["id"]]}
        ).status_code
        == 400
    )
    empty = note(client, "Empty", "")
    response = client.post(
        "/api/analyses", json={"kind": "comparison", "document_ids": [a["id"], empty["id"]]}
    )
    assert response.status_code == 400 and "no extracted text" in response.json()["detail"]
    assert (
        client.post(
            "/api/analyses", json={"kind": "comparison", "document_ids": [a["id"], 999]}
        ).status_code
        == 404
    )


# --- Gap finder ----------------------------------------------------------------------------


def gap_reply(_system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
    if "underexplored_areas" not in schema["properties"]:
        return profile_reply(_system, prompt, schema)
    item = lambda statement, basis, papers: {  # noqa: E731
        "statement": statement,
        "basis": basis,
        "papers": papers,
        "rationale": "because",
    }
    return {
        "underexplored_areas": [
            item("Older adults are rarely studied", "literature", [1]),
            item("Children are never studied", "literature", []),  # no paper -> hypothesis
        ],
        "contradictions": [item("Spindle effects differ by age", "literature", [1])],  # needs two
        "missing_perspectives": [item("Clinical populations", "hypothesis", [9])],  # P9 unknown
        "methodological_limitations": [item("Small samples", "literature", [1, 2])],
        "future_directions": [],
        "research_questions": [item("Do spindles matter in teens?", "literature", [1])],
    }


def test_gap_finder_enforces_evidence_labels(client: TestClient, chat: FakeChat) -> None:
    chat.json_reply = gap_reply
    a, b = note(client, "Spindles study", PAPER), note(client, "Sleep survey", OTHER)
    collection = client.post("/api/collections", json={"name": "Sleep"}).json()
    for doc in (a, b):
        client.put(f"/api/documents/{doc['id']}/collections", json={"ids": [collection["id"]]})

    analysis = run(client, "gap_analysis", collection_id=collection["id"], focus="age effects")
    assert analysis["status"] == "done", analysis["error"]
    assert analysis["title"] == "Research gaps: Sleep"
    categories = {c["key"]: c["items"] for c in analysis["result"]["categories"]}

    older, children = categories["underexplored_areas"]
    assert older["basis"] == "literature" and older["papers"][0]["document_id"] == a["id"]
    assert children["basis"] == "hypothesis" and children["notes"]
    assert categories["contradictions"][0]["basis"] == "hypothesis"
    assert "P9" in categories["missing_perspectives"][0]["notes"][0]
    assert len(categories["methodological_limitations"][0]["papers"]) == 2
    assert categories["research_questions"][0]["basis"] == "hypothesis"
    assert analysis["result"]["focus"] == "age effects"

    # The gap prompt only uses *verified* profile statements and the requested focus.
    _, gap_prompt, _ = chat.json_calls[-1]
    assert "48 healthy adults" in gap_prompt
    assert "52 nights" not in gap_prompt
    assert "Focus the analysis on: age effects" in gap_prompt

    report = client.get(f"/api/reports/{analysis['report_id']}").json()["content_markdown"]
    assert "[Supported by literature: P1]" in report and "[AI-generated hypothesis]" in report


# --- Detective -----------------------------------------------------------------------------


def detective_reply(_system: str, _prompt: str, _schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "observations": [
            {
                "category": "potential_bias",
                "severity": "medium",
                "observation": "University sample may limit generalisability.",
                "source": 2,
                "quote": "We recruited 48 healthy adults from a university sample",
            },
            {
                "category": "unsupported_claim",
                "severity": "high",
                "observation": "Causal language.",
                "source": 3,
                "quote": "this proves spindles cause memory",
            },
            {
                "category": "reproducibility",
                "severity": "low",
                "observation": "No data availability statement was found in the excerpts.",
                "source": 0,
                "quote": "",
            },
        ],
        "checklist": {
            "data_availability": {"status": "not_found", "source": 0, "quote": ""},
            "code_availability": {"status": "not_found", "source": 0, "quote": ""},
            "preregistration": {
                "status": "reported",
                "source": 2,
                "quote": "the study was preregistered on OSF",
            },
            "sample_size_justification": {"status": "unclear", "source": 0, "quote": ""},
            "statistical_methods": {
                "status": "reported",
                "source": 3,
                "quote": "Spindle density correlated with recall of word pairs",
            },
            "conflicts_of_interest": {"status": "not_found", "source": 0, "quote": ""},
        },
    }


def test_detective_observations_are_verified(client: TestClient, chat: FakeChat) -> None:
    chat.json_reply = detective_reply
    doc = note(client, "Spindles study", PAPER)
    analysis = run(client, "detective", document_ids=[doc["id"]])
    assert analysis["status"] == "done", analysis["error"]
    result = analysis["result"]
    bias, causal, absence = result["observations"]
    assert bias["evidence"]["verified"] is True
    assert causal["evidence"]["verified"] is False
    assert absence["kind"] == "absence" and absence["evidence"] is None
    checklist = {c["key"]: c["status"] for c in result["checklist"]}
    assert checklist["preregistration"] == "unverified"  # quote not in the text
    assert checklist["statistical_methods"] == "reported"
    assert checklist["data_availability"] == "not_found"
    report = client.get(f"/api/reports/{analysis['report_id']}").json()["content_markdown"]
    assert "not definitive judgements" in report and "Based on absence" in report


# --- Lifecycle -----------------------------------------------------------------------------


def test_cancel_dedup_rerun_failure_and_delete(client: TestClient, chat: FakeChat) -> None:
    doc = note(client, "Spindles study", PAPER)
    first = client.post(
        "/api/analyses", json={"kind": "profile", "document_ids": [doc["id"]]}
    ).json()
    again = client.post(
        "/api/analyses", json={"kind": "profile", "document_ids": [doc["id"]]}
    ).json()
    assert again["id"] == first["id"]  # identical queued work is not duplicated

    cancelled = client.post(f"/api/analyses/{first['id']}/cancel").json()
    assert cancelled["status"] == "cancelled"
    state = client.app.state  # type: ignore[attr-defined]
    assert analysis_service.process_next(state.session_factory, state.ai, state.settings) is False
    assert chat.json_calls == []

    chat.error = ProviderError("Ollama is not running. Start the Ollama app and try again.")
    rerun = client.post(f"/api/analyses/{first['id']}/rerun").json()
    assert rerun["id"] != first["id"]
    analysis_service.process_next(state.session_factory, state.ai, state.settings)
    failed = client.get(f"/api/analyses/{rerun['id']}").json()
    assert failed["status"] == "failed" and "Ollama is not running" in failed["error"]

    listed = client.get("/api/analyses", params={"document_id": doc["id"]}).json()
    assert {a["id"] for a in listed} == {first["id"], rerun["id"]}
    assert client.delete(f"/api/analyses/{rerun['id']}").status_code == 204
    assert client.get(f"/api/analyses/{rerun['id']}").status_code == 404


def test_analyses_require_cloud_consent(settings) -> None:  # type: ignore[no-untyped-def]
    from app.main import create_app

    cloud = FakeChat(name="anthropic", model="claude-opus-5-5", json_reply=profile_reply)
    with TestClient(create_app(settings, ai=make_fake_ai(cloud=cloud))) as client:
        doc = note(client, "Spindles study", PAPER)
        client.put("/api/assistant/settings", json={"chat_provider": "anthropic"})
        blocked = client.post(
            "/api/analyses", json={"kind": "profile", "document_ids": [doc["id"]]}
        )
        assert blocked.status_code == 409
        client.put("/api/assistant/settings", json={"cloud_consent": True})
        analysis = run(client, "profile", document_ids=[doc["id"]])
        assert analysis["provider"] == "anthropic" and analysis["status"] == "done"
        assert len(cloud.json_calls) == 3
