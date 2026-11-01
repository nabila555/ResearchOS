from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.ai.registry import AIServices
from app.core.config import Settings
from app.main import create_app
from tests.fixtures.fake_ai import make_fake_ai


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    # Each test gets an isolated data directory and SQLite file. The Ollama URL
    # points at a closed port so tests never depend on a running Ollama, and the
    # background indexer is off: tests drive indexing explicitly.
    return Settings(
        _env_file=None,
        environment="test",
        data_dir=tmp_path / "data",
        ollama_base_url="http://127.0.0.1:9",
        ollama_timeout_seconds=0.5,
        anthropic_api_key=None,
        run_background_worker=False,
        retrieval_min_similarity=0.2,
    )


@pytest.fixture
def ai() -> AIServices:
    return make_fake_ai()


@pytest.fixture
def client(settings: Settings, ai: AIServices) -> Iterator[TestClient]:
    with TestClient(create_app(settings, ai=ai)) as test_client:
        yield test_client
