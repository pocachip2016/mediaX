"""
Step 1 검증 — ServiceCategory 큐레이션 확장 컬럼
"""
import pytest
from api.distribution.models import ServiceCategory
from api.distribution.schemas import ServiceCategoryCreate, ServiceCategoryUpdate, ServiceCategoryOut
from api.distribution import service


@pytest.fixture
def category_full(db):
    obj = ServiceCategory(
        name="퇴근 후 위로",
        category_type="recommendation",
        platform="ott_watcha",
        headline_copy="퇴근 후 90분의 위로",
        sub_copy="가볍게 즐기는 코미디·드라마",
        theme_features={"genres": ["코미디", "드라마"], "moods": ["가벼운"], "runtime_min": 80},
        source_mode="ai_proposed",
        reference_external_id="watcha:section:top10",
        is_draft=True,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


# ── 모델 컬럼 존재 확인 ──────────────────────────────────────────────────────

def test_model_has_new_columns():
    cols = {c.key for c in ServiceCategory.__table__.columns}
    assert "headline_copy" in cols
    assert "sub_copy" in cols
    assert "theme_features" in cols
    assert "source_mode" in cols
    assert "reference_external_id" in cols
    assert "is_draft" in cols


# ── 기본값 확인 ───────────────────────────────────────────────────────────────

def test_default_source_mode(db):
    obj = ServiceCategory(name="기본", category_type="ranking", platform="ott_watcha")
    db.add(obj)
    db.commit()
    db.refresh(obj)
    assert obj.source_mode == "manual"
    assert obj.is_draft is False
    assert obj.headline_copy is None
    assert obj.theme_features is None


# ── CRUD with new fields ──────────────────────────────────────────────────────

def test_create_with_curation_fields(db):
    data = ServiceCategoryCreate(
        name="AI 큐레이션",
        category_type="recommendation",
        platform="ott_netflix",
        headline_copy="오늘은 짧고 깊게",
        sub_copy="짧은 러닝타임, 큰 여운",
        theme_features={"genres": ["드라마"], "runtime_max": 100},
        source_mode="ai_proposed",
        is_draft=True,
    )
    result = service.create_category(db, data)
    assert result.headline_copy == "오늘은 짧고 깊게"
    assert result.sub_copy == "짧은 러닝타임, 큰 여운"
    assert result.theme_features == {"genres": ["드라마"], "runtime_max": 100}
    assert result.source_mode == "ai_proposed"
    assert result.is_draft is True


def test_update_curation_fields(db, category_full):
    data = ServiceCategoryUpdate(
        headline_copy="야근을 부숴줄 코미디 8선",
        is_draft=False,
        source_mode="manual",
    )
    result = service.update_category(db, category_full.id, data)
    assert result.headline_copy == "야근을 부숴줄 코미디 8선"
    assert result.is_draft is False
    assert result.source_mode == "manual"
    # 건드리지 않은 필드 유지
    assert result.sub_copy == "가볍게 즐기는 코미디·드라마"


def test_update_theme_features_partial(db, category_full):
    data = ServiceCategoryUpdate(theme_features={"genres": ["액션"], "moods": ["신남"]})
    result = service.update_category(db, category_full.id, data)
    assert result.theme_features == {"genres": ["액션"], "moods": ["신남"]}


def test_update_theme_features_to_none(db, category_full):
    data = ServiceCategoryUpdate(theme_features=None)
    result = service.update_category(db, category_full.id, data)
    assert result.theme_features is None


# ── 스키마 직렬화 확인 ────────────────────────────────────────────────────────

def test_out_schema_includes_new_fields(db, category_full):
    out = ServiceCategoryOut.model_validate(category_full)
    assert out.headline_copy == "퇴근 후 90분의 위로"
    assert out.theme_features == {"genres": ["코미디", "드라마"], "moods": ["가벼운"], "runtime_min": 80}
    assert out.source_mode == "ai_proposed"
    assert out.is_draft is True
    assert out.reference_external_id == "watcha:section:top10"


def test_create_schema_new_fields_optional():
    data = ServiceCategoryCreate(name="최소", category_type="ranking", platform="iptv")
    assert data.headline_copy is None
    assert data.source_mode == "manual"
    assert data.is_draft is False


def test_update_schema_all_optional():
    data = ServiceCategoryUpdate()
    assert data.headline_copy is None
    assert data.source_mode is None
    assert data.is_draft is None
