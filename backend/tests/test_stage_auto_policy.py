"""
StageAutoPolicy — 단계별 자동 실행 게이트 회귀 테스트

advance-out 정렬: s1=생성→보완, s2=보완→AI, s3=AI→검수, s4=검수→승인, s5=승인→게시(stub).

핵심 가드 (전부 OFF면 자동 전이 0):
  - advance_to_review=False(AI→검수 s3 OFF) → score 무관 ai 에서 정지
  - advance_to_review=True + auto_approve=False(검수→승인 s4 OFF) → score≥90 이어도 review 까지만
  - advance_to_review=True + auto_approve=True → score≥90 → approved
  - enrich_content(use_cache_db=False) → 외부 소스 호출 없이 early return
  - stage-auto-policy GET/PATCH API

LLM은 monkeypatch로 mock.

pytest tests/test_stage_auto_policy.py -q
"""
import asyncio
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import api.programming.metadata.models  # noqa: F401
import api.meta_core.models  # noqa: F401
import api.meta_core.public_api.models  # noqa: F401
import api.distribution.models  # noqa: F401
from shared.database import Base, get_db
from main import app

from api.programming.metadata.models import (
    Content, ContentMetadata, ContentStatus, ContentType,
)
from api.programming.metadata.schemas import AIGenerateResponse


# ── 픽스처 ────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    def override_get_db():
        d = Session()
        try:
            yield d
        finally:
            d.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def _make_content(db, *, status=ContentStatus.enriched, title="게이트 테스트"):
    c = Content(title=title, content_type=ContentType.movie, cp_name="TEST_GATE", status=status)
    db.add(c)
    db.flush()
    db.add(ContentMetadata(content_id=c.id, cp_synopsis="테스트 시놉시스"))
    db.flush()
    return c


def _mock_generate(score: float):
    async def _inner(req, db_):
        return AIGenerateResponse(
            synopsis="가짜 시놉시스입니다.",
            genre_primary="드라마",
            genre_secondary=None,
            mood_tags=["감동"],
            rating_suggestion="15세이상관람가",
            quality_score=score,
        ), "mock_engine"
    return _inner


# ── process_content_ai 단계별 게이트 ──────────────────────────────────────────

def test_s3_off_stops_at_ai(db, monkeypatch):
    """AI→검수 진행(s3) OFF: advance_to_review=False → score 95여도 ai 정지."""
    import api.programming.metadata.ai_engine as engine_mod
    monkeypatch.setattr(engine_mod, "_generate_metadata_with_engine", _mock_generate(95.0))

    content = _make_content(db)
    asyncio.run(engine_mod.process_content_ai(
        content.id, db, auto_chain=True, advance_to_review=False, auto_approve=True,
    ))
    db.refresh(content)
    assert content.status == ContentStatus.ai, f"s3 OFF인데 status={content.status}"


def test_s4_off_stops_at_review(db, monkeypatch):
    """검수→승인 진행(s4) OFF: advance_to_review=True + auto_approve=False → score 95여도 review 까지만."""
    import api.programming.metadata.ai_engine as engine_mod
    monkeypatch.setattr(engine_mod, "_generate_metadata_with_engine", _mock_generate(95.0))

    content = _make_content(db)
    asyncio.run(engine_mod.process_content_ai(
        content.id, db, auto_chain=True, advance_to_review=True, auto_approve=False,
    ))
    db.refresh(content)
    assert content.status == ContentStatus.review, f"s4 OFF인데 status={content.status}"


def test_s3_s4_on_high_score_approves(db, monkeypatch):
    """검수진행+승인 ON + score≥90 → approved."""
    import api.programming.metadata.ai_engine as engine_mod
    monkeypatch.setattr(engine_mod, "_generate_metadata_with_engine", _mock_generate(95.0))

    content = _make_content(db)
    asyncio.run(engine_mod.process_content_ai(
        content.id, db, auto_chain=True, advance_to_review=True, auto_approve=True,
    ))
    db.refresh(content)
    assert content.status == ContentStatus.approved, f"기대 approved, 실제={content.status}"


# ── enrich use_cache_db 게이트 ────────────────────────────────────────────────

def test_enrich_no_cache_db_is_noop(db):
    """use_cache_db=False → 외부 소스 호출 없이 candidates=0 early return."""
    from api.meta_core.enrich import enrich_content
    content = _make_content(db, status=ContentStatus.raw)
    result = enrich_content(content.id, db, use_cache_db=False)
    assert result.candidates_upserted == 0
    assert result.sources_hit == []


# ── 서비스 헬퍼 / API ─────────────────────────────────────────────────────────

def test_get_stage_auto_policy_default(db):
    """DB 행 없으면 전부 False."""
    from api.programming.metadata.service_bulk import get_stage_auto_policy
    policy = get_stage_auto_policy(db)
    assert policy == {f"s{i}_auto": False for i in range(1, 7)}


def test_stage_auto_policy_api_default(client):
    res = client.get("/api/programming/metadata/ai-tasks/stage-auto-policy")
    assert res.status_code == 200
    data = res.json()
    assert all(data[f"s{i}_auto"] is False for i in range(1, 7))


def test_stage_auto_policy_api_patch(client):
    res = client.patch(
        "/api/programming/metadata/ai-tasks/stage-auto-policy",
        json={"s3_auto": True, "s4_auto": True},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["s3_auto"] is True
    assert data["s4_auto"] is True
    assert data["s5_auto"] is False  # 미지정 필드 유지

    # 부분 갱신 — s3만 끔
    res2 = client.patch(
        "/api/programming/metadata/ai-tasks/stage-auto-policy",
        json={"s3_auto": False},
    )
    d2 = res2.json()
    assert d2["s3_auto"] is False
    assert d2["s4_auto"] is True  # 이전 값 유지
