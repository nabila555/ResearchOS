from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    # Each test gets an isolated data directory and SQLite file. The Ollama URL
    # points at a closed port so tests never depend on a running Ollama.
    return Settings(
        _env_file=None,
        environment="test",
        data_dir=tmp_path / "data",
        ollama_base_url="http://127.0.0.1:9",
        ollama_timeout_seconds=0.5,
        anthropic_api_key=None,
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client
