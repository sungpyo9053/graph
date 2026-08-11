from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.main import app
from src.repositories.database import configure_database, create_all, session_factory


@pytest.fixture
def session(tmp_path) -> Generator[Session, None, None]:
    configure_database(f"sqlite:///{tmp_path / 'test.db'}")
    create_all()
    with session_factory()() as db:
        yield db


@pytest.fixture
def client(tmp_path) -> Generator[TestClient, None, None]:
    configure_database(f"sqlite:///{tmp_path / 'api.db'}")
    with TestClient(app) as test_client:
        yield test_client
