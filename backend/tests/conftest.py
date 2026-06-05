"""
pytest 공용 픽스처 — SQLite in-memory DB

StaticPool 사용 이유:
  FastAPI 동기 엔드포인트는 thread pool에서 실행된다.
  StaticPool 없이 `:memory:` DB를 쓰면 스레드마다 별도 커넥션이 생겨
  Base.metadata.create_all()로 만든 테이블이 TestClient 스레드에서 보이지 않는다.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# 모든 모델을 메타데이터에 등록
import api.programming.metadata.models  # noqa: F401
import api.meta_core.models  # noqa: F401
import api.meta_core.public_api.models  # noqa: F401
import api.distribution.models  # noqa: F401
import api.programming.catalog.models  # noqa: F401
from shared.database import Base


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)
