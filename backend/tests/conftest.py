"""
pytest 공용 픽스처 — SQLite in-memory DB
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 모든 모델을 메타데이터에 등록
import api.programming.metadata.models  # noqa: F401
from shared.database import Base


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)
