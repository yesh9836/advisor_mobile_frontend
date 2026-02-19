from __future__ import annotations

import os
from typing import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base


@pytest.fixture(scope="session")
def mysql_database_url() -> str:
    url = os.getenv("TEST_MYSQL_DATABASE_URL", "").strip()
    if not url:
        pytest.skip("TEST_MYSQL_DATABASE_URL not set; skipping MySQL-only webhook concurrency tests")
    return url


@pytest.fixture(scope="session")
def engine(mysql_database_url: str):
    test_engine = create_engine(
        mysql_database_url,
        pool_pre_ping=True,
    )
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def session_factory(engine):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture
def db(session_factory) -> Generator[Session, None, None]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()

