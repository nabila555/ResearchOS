from fastapi.testclient import TestClient

from app.ai.ollama import _model_installed
from app.core.config import Settings


def test_health_reports_database_ok(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"


def test_data_directories_created(client: TestClient, settings: Settings) -> None:
    assert settings.documents_dir.is_dir()
    assert settings.embeddings_dir.is_dir()
    assert (settings.database_dir / "researchos.db").is_file()


def test_system_status_when_ollama_unreachable(client: TestClient) -> None:
    body = client.get("/api/system/status").json()
    ollama = body["ai"]["ollama"]
    assert ollama["reachable"] is False
    assert ollama["models"] == []
    assert ollama["error"]
    assert body["ai"]["anthropic"]["configured"] is False
    assert body["storage"]["database_backend"] == "sqlite"


def test_system_status_never_returns_api_key(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from app.main import create_app

    secret = "sk-test-should-never-leak"
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path,
        anthropic_api_key=secret,
        ollama_base_url="http://127.0.0.1:9",
        ollama_timeout_seconds=0.5,
        run_background_worker=False,
    )
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/system/status")
    assert response.json()["ai"]["anthropic"]["configured"] is True
    assert secret not in response.text


def test_model_name_matching() -> None:
    installed = ["llama3.1:8b", "nomic-embed-text:latest"]
    assert _model_installed("llama3.1:8b", installed)
    assert _model_installed("nomic-embed-text", installed)
    assert not _model_installed("llama3.1:70b", installed)
    assert not _model_installed("mistral", installed)


def test_relative_data_dir_resolves_to_project_root() -> None:
    from app.core.config import PROJECT_ROOT

    settings = Settings(_env_file=None, data_dir="data")
    assert settings.data_dir == (PROJECT_ROOT / "data").resolve()
