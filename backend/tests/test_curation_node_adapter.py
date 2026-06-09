"""
test_curation_node_adapter.py — service_categories → ProgrammingNode(kind=manual/rank) 어댑터 검증

- 큐레이션 노드는 kind∈{manual,rank} AND set_id IS NULL 술어로 식별
- 메타 4필드(platform/category_type/source_mode/reference_external_id)는 theme_features["_curation"]에 저장
- items = ProgrammingLink(child_type=content, rank↔sort_order, score↔confidence)
"""
import pytest
from api.distribution import service as svc
from api.distribution.schemas import (
    ServiceCategoryCreate,
    ServiceCategoryUpdate,
    ServiceCategoryItemCreate,
    ReorderRequest,
    ReorderItem,
)
from api.programming.metadata.models import Content
from api.programming.scheduling.models import NodeKind, ProgrammingNode
from api.programming.scheduling.node_theme_service import compose_theme_text


@pytest.fixture
def content(db):
    obj = Content(title="테스트 영화", content_type="movie", status="raw")
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@pytest.fixture
def content2(db):
    obj = Content(title="테스트 드라마", content_type="series", status="raw")
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


# ── 생성 / 조회 ───────────────────────────────────────────────────────────────

def test_create_category_manual(db):
    data = ServiceCategoryCreate(
        name="추천 섹션",
        category_type="recommendation",
        platform="ott",
        position=1,
    )
    view = svc.create_category(db, data)
    assert view.name == "추천 섹션"
    assert view.category_type == "recommendation"
    assert view.platform == "ott"
    assert view.position == 1
    assert view.source_mode == "manual"
    assert view.is_active is True


def test_create_category_rank_kind(db):
    data = ServiceCategoryCreate(
        name="TOP10",
        category_type="top10",
        platform="iptv",
        position=0,
    )
    view = svc.create_category(db, data)
    node = db.query(ProgrammingNode).filter(ProgrammingNode.id == view.id).first()
    assert node.kind == NodeKind.rank


def test_create_category_manual_kind(db):
    data = ServiceCategoryCreate(
        name="신작 드라마",
        category_type="new_release",
        platform="ott",
        position=0,
    )
    view = svc.create_category(db, data)
    node = db.query(ProgrammingNode).filter(ProgrammingNode.id == view.id).first()
    assert node.kind == NodeKind.manual


def test_create_category_meta_roundtrip(db):
    data = ServiceCategoryCreate(
        name="큐레이션 A",
        category_type="recommendation",
        platform="iptv_genie",
        position=5,
        source_mode="ai_proposed",
        reference_external_id="ext_123",
        headline_copy="헤드라인",
        sub_copy="서브카피",
    )
    view = svc.create_category(db, data)
    assert view.platform == "iptv_genie"
    assert view.category_type == "recommendation"
    assert view.position == 5
    assert view.source_mode == "ai_proposed"
    assert view.reference_external_id == "ext_123"
    assert view.headline_copy == "헤드라인"
    assert view.sub_copy == "서브카피"


# ── 목록 조회 + 필터 ──────────────────────────────────────────────────────────

def test_get_categories_empty(db):
    assert svc.get_categories(db) == []


def test_get_categories_returns_curation_nodes(db):
    svc.create_category(db, ServiceCategoryCreate(
        name="A", category_type="recommendation", platform="ott", position=0,
    ))
    svc.create_category(db, ServiceCategoryCreate(
        name="B", category_type="rank", platform="iptv", position=1,
    ))
    result = svc.get_categories(db)
    assert len(result) == 2


def test_get_categories_filter_platform(db):
    svc.create_category(db, ServiceCategoryCreate(
        name="IPTV 추천", category_type="recommendation", platform="iptv_genie", position=0,
    ))
    svc.create_category(db, ServiceCategoryCreate(
        name="OTT TOP10", category_type="top10", platform="ott_watcha", position=1,
    ))
    result = svc.get_categories(db, platform="iptv_genie")
    assert len(result) == 1
    assert result[0].platform == "iptv_genie"


def test_get_categories_filter_is_active(db):
    svc.create_category(db, ServiceCategoryCreate(
        name="활성", category_type="recommendation", platform="ott", position=0, is_active=True,
    ))
    svc.create_category(db, ServiceCategoryCreate(
        name="비활성", category_type="recommendation", platform="ott", position=1, is_active=False,
    ))
    active = svc.get_categories(db, is_active=True)
    inactive = svc.get_categories(db, is_active=False)
    assert len(active) == 1
    assert len(inactive) == 1


def test_get_categories_sorted_by_position(db):
    svc.create_category(db, ServiceCategoryCreate(name="C", category_type="recommendation", platform="ott", position=10))
    svc.create_category(db, ServiceCategoryCreate(name="A", category_type="recommendation", platform="ott", position=1))
    svc.create_category(db, ServiceCategoryCreate(name="B", category_type="recommendation", platform="ott", position=5))
    result = svc.get_categories(db)
    assert [v.name for v in result] == ["A", "B", "C"]


# ── 수정 / 삭제 ───────────────────────────────────────────────────────────────

def test_update_category_name_and_meta(db):
    view = svc.create_category(db, ServiceCategoryCreate(
        name="원래 이름", category_type="recommendation", platform="ott", position=0,
    ))
    updated = svc.update_category(db, view.id, ServiceCategoryUpdate(
        name="바뀐 이름", platform="iptv", position=3,
    ))
    assert updated.name == "바뀐 이름"
    assert updated.platform == "iptv"
    assert updated.position == 3


def test_update_category_type_changes_kind(db):
    view = svc.create_category(db, ServiceCategoryCreate(
        name="TOP", category_type="recommendation", platform="ott", position=0,
    ))
    node = db.query(ProgrammingNode).filter(ProgrammingNode.id == view.id).first()
    assert node.kind == NodeKind.manual

    svc.update_category(db, view.id, ServiceCategoryUpdate(category_type="top10"))
    db.refresh(node)
    assert node.kind == NodeKind.rank


def test_delete_category(db):
    view = svc.create_category(db, ServiceCategoryCreate(
        name="삭제대상", category_type="recommendation", platform="ott", position=0,
    ))
    result = svc.delete_category(db, view.id)
    assert result["deleted"] is True
    assert svc.get_categories(db) == []


def test_get_category_or_404_missing(db):
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        svc.get_category_or_404(db, 9999)
    assert exc_info.value.status_code == 404


# ── items CRUD (rank↔sort_order, score↔confidence) ───────────────────────────

def test_add_and_get_item(db, content):
    cat = svc.create_category(db, ServiceCategoryCreate(
        name="큐레이션", category_type="recommendation", platform="ott", position=0,
    ))
    item = svc.add_item(db, cat.id, ServiceCategoryItemCreate(
        content_id=content.id, rank=1, score=0.95,
    ))
    assert item.content_id == content.id
    assert item.rank == 1
    assert item.score == pytest.approx(0.95)
    assert item.content_title == "테스트 영화"


def test_get_category_with_items(db, content):
    cat = svc.create_category(db, ServiceCategoryCreate(
        name="큐레이션", category_type="recommendation", platform="ott", position=0,
    ))
    svc.add_item(db, cat.id, ServiceCategoryItemCreate(content_id=content.id, rank=1))
    detail = svc.get_category_with_items(db, cat.id)
    assert len(detail.items) == 1
    assert detail.items[0].content_id == content.id


def test_add_item_duplicate_raises_409(db, content):
    from fastapi import HTTPException
    cat = svc.create_category(db, ServiceCategoryCreate(
        name="큐레이션", category_type="recommendation", platform="ott", position=0,
    ))
    svc.add_item(db, cat.id, ServiceCategoryItemCreate(content_id=content.id, rank=1))
    with pytest.raises(HTTPException) as exc_info:
        svc.add_item(db, cat.id, ServiceCategoryItemCreate(content_id=content.id, rank=2))
    assert exc_info.value.status_code == 409


def test_remove_item(db, content):
    cat = svc.create_category(db, ServiceCategoryCreate(
        name="큐레이션", category_type="recommendation", platform="ott", position=0,
    ))
    item = svc.add_item(db, cat.id, ServiceCategoryItemCreate(content_id=content.id, rank=1))
    result = svc.remove_item(db, cat.id, item.id)
    assert result["deleted"] is True
    detail = svc.get_category_with_items(db, cat.id)
    assert len(detail.items) == 0


def test_reorder_items(db, content, content2):
    cat = svc.create_category(db, ServiceCategoryCreate(
        name="큐레이션", category_type="recommendation", platform="ott", position=0,
    ))
    item1 = svc.add_item(db, cat.id, ServiceCategoryItemCreate(content_id=content.id, rank=1))
    item2 = svc.add_item(db, cat.id, ServiceCategoryItemCreate(content_id=content2.id, rank=2))

    result = svc.reorder_items(db, cat.id, ReorderRequest(items=[
        ReorderItem(id=item1.id, rank=5),
        ReorderItem(id=item2.id, rank=3),
    ]))
    assert result["updated"] == 2

    detail = svc.get_category_with_items(db, cat.id)
    ranks = {i.content_id: i.rank for i in detail.items}
    assert ranks[content.id] == 5
    assert ranks[content2.id] == 3


# ── compose_theme_text: _curation 제외 확인 ──────────────────────────────────

def test_compose_theme_text_excludes_curation_meta(db):
    node = ProgrammingNode(
        kind=NodeKind.manual,
        name="노드 이름",
        headline_copy="헤드라인",
        theme_features={
            "genres": ["드라마"],
            "_curation": {"platform": "ott", "category_type": "recommendation"},
        },
        is_active=True,
        is_draft=False,
    )
    text = compose_theme_text(node)
    assert "ott" not in text
    assert "recommendation" not in text
    assert "드라마" in text
    assert "노드 이름" in text
    assert "헤드라인" in text


def test_compose_theme_text_no_underscore_keys_in_output(db):
    node = ProgrammingNode(
        kind=NodeKind.manual,
        name="테스트",
        theme_features={"_curation": {"platform": "x"}, "_internal": "hidden"},
        is_active=True,
        is_draft=False,
    )
    text = compose_theme_text(node)
    assert "x" not in text
    assert "hidden" not in text
