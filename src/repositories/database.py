from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.config import settings


class Base(DeclarativeBase):
    pass


_engine = None
_session_factory = None


def configure_database(url: str | None = None) -> None:
    global _engine, _session_factory
    database_url = url or settings().database_url
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    _engine = create_engine(database_url, connect_args=connect_args)
    _session_factory = sessionmaker(bind=_engine, expire_on_commit=False)


def engine() -> Engine:
    global _engine
    if _engine is None:
        configure_database()
    assert _engine is not None
    return _engine


def session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        configure_database()
    assert _session_factory is not None
    return _session_factory


def create_all() -> None:
    from src.repositories import entities  # noqa: F401

    Base.metadata.create_all(engine())


def get_session() -> Generator[Session, None, None]:
    with session_factory()() as session:
        yield session
