"""
카테고리 트리 서비스 단위 테스트 (mock 없음, in-memory SQLite)

검증 케이스:
  - root 노드 depth=0, child 노드 depth=1
  - move 시 서브트리 depth 재계산
  - move-into-descendant → ValueError
  - merge: 자식+매핑 이전, dedupe, source 삭제
  - map_content 멱등 (2회 호출 → 1행)
  - delete 가드: 자식/콘텐츠 있으면 cascade=False 시 ValueError
"""
import pytest

from api.programming.catalog.service import (
    create_category,
    rename_category,
    set_active,
    move_category,
    merge_category,
    delete_category,
    list_tree,
    get_subtree_ids,
    map_content,
    unmap_content,
    category_content_count,
)
from api.programming.catalog.models import Category, ContentCategory
from api.programming.metadata.models import Content, ContentType, ContentStatus


def _make_content(db, title="테스트콘텐츠"):
    c = Content(title=title, content_type=ContentType.movie, cp_name="TEST", status=ContentStatus.raw)
    db.add(c)
    db.flush()
    return c


# ── depth 기본 검증 ───────────────────────────────────────────────────────────

def test_root_depth_zero(db):
    cat = create_category(db, "영화")
    assert cat.depth == 0


def test_child_depth_one(db):
    root = create_category(db, "영화")
    child = create_category(db, "액션", parent_id=root.id)
    assert child.depth == 1
    assert child.parent_id == root.id


def test_grandchild_depth_two(db):
    root = create_category(db, "영화")
    child = create_category(db, "액션", parent_id=root.id)
    grand = create_category(db, "SF", parent_id=child.id)
    assert grand.depth == 2


# ── move + depth 재계산 ───────────────────────────────────────────────────────

def test_move_subtree_depth_recalculated(db):
    """영화(0) > 액션(1) > SF(2) 을 시리즈(0) 아래로 이동 → 액션(1→1), SF(2→2) 재계산."""
    movie = create_category(db, "영화")
    series = create_category(db, "시리즈")
    action = create_category(db, "액션", parent_id=movie.id)
    sf = create_category(db, "SF", parent_id=action.id)

    move_category(db, action.id, new_parent_id=series.id)

    db.refresh(action)
    db.refresh(sf)
    assert action.depth == 1
    assert sf.depth == 2
    assert action.parent_id == series.id


def test_move_to_root(db):
    """자식을 최상위로 이동 → depth=0."""
    root = create_category(db, "영화")
    child = create_category(db, "액션", parent_id=root.id)

    move_category(db, child.id, new_parent_id=None)

    db.refresh(child)
    assert child.depth == 0
    assert child.parent_id is None


# ── 사이클 가드 ───────────────────────────────────────────────────────────────

def test_move_into_self_raises(db):
    cat = create_category(db, "영화")
    with pytest.raises(ValueError, match="self or descendant"):
        move_category(db, cat.id, new_parent_id=cat.id)


def test_move_into_descendant_raises(db):
    root = create_category(db, "영화")
    child = create_category(db, "액션", parent_id=root.id)
    grand = create_category(db, "SF", parent_id=child.id)

    with pytest.raises(ValueError, match="self or descendant"):
        move_category(db, root.id, new_parent_id=grand.id)


# ── merge ─────────────────────────────────────────────────────────────────────

def test_merge_reparents_children(db):
    """source 자식이 target 아래로 이동되고 source 삭제."""
    src = create_category(db, "소스")
    tgt = create_category(db, "타겟")
    child = create_category(db, "자식", parent_id=src.id)

    merge_category(db, src.id, tgt.id)

    db.refresh(child)
    assert child.parent_id == tgt.id
    assert child.depth == tgt.depth + 1
    assert db.query(Category).filter(Category.id == src.id).first() is None


def test_merge_moves_content_mappings(db):
    content = _make_content(db)
    src = create_category(db, "소스")
    tgt = create_category(db, "타겟")
    map_content(db, content.id, [src.id])

    merge_category(db, src.id, tgt.id)

    rows = db.query(ContentCategory).filter(
        ContentCategory.content_id == content.id
    ).all()
    assert len(rows) == 1
    assert rows[0].category_id == tgt.id


def test_merge_deduplicates_content_mappings(db):
    """content가 이미 target에 매핑되어 있으면 중복 제거."""
    content = _make_content(db)
    src = create_category(db, "소스")
    tgt = create_category(db, "타겟")
    map_content(db, content.id, [src.id, tgt.id])

    merge_category(db, src.id, tgt.id)

    rows = db.query(ContentCategory).filter(
        ContentCategory.content_id == content.id,
        ContentCategory.category_id == tgt.id,
    ).all()
    assert len(rows) == 1  # dedupe — 1행만 남아야


# ── map_content 멱등성 ────────────────────────────────────────────────────────

def test_map_content_idempotent(db):
    content = _make_content(db)
    cat = create_category(db, "영화")

    map_content(db, content.id, [cat.id])
    map_content(db, content.id, [cat.id])  # 2회 호출

    count = db.query(ContentCategory).filter(
        ContentCategory.content_id == content.id,
        ContentCategory.category_id == cat.id,
    ).count()
    assert count == 1


def test_unmap_content(db):
    content = _make_content(db)
    cat = create_category(db, "영화")
    map_content(db, content.id, [cat.id])

    unmap_content(db, content.id, cat.id)

    assert db.query(ContentCategory).filter(
        ContentCategory.content_id == content.id
    ).count() == 0


# ── delete 가드 ───────────────────────────────────────────────────────────────

def test_delete_with_children_raises(db):
    parent = create_category(db, "영화")
    create_category(db, "액션", parent_id=parent.id)

    with pytest.raises(ValueError, match="children or contents"):
        delete_category(db, parent.id, cascade=False)


def test_delete_with_contents_raises(db):
    content = _make_content(db)
    cat = create_category(db, "영화")
    map_content(db, content.id, [cat.id])

    with pytest.raises(ValueError, match="children or contents"):
        delete_category(db, cat.id, cascade=False)


def test_delete_empty_succeeds(db):
    cat = create_category(db, "영화")
    delete_category(db, cat.id)
    assert db.query(Category).filter(Category.id == cat.id).first() is None


# ── list_tree / count ─────────────────────────────────────────────────────────

def test_list_tree_structure(db):
    root = create_category(db, "영화")
    child1 = create_category(db, "액션", parent_id=root.id)
    create_category(db, "SF", parent_id=child1.id)
    create_category(db, "드라마", parent_id=root.id)

    tree = list_tree(db)
    assert len(tree) == 1
    assert tree[0]["id"] == root.id
    assert len(tree[0]["children"]) == 2


def test_category_content_count_recursive(db):
    root = create_category(db, "영화")
    child = create_category(db, "액션", parent_id=root.id)
    c1 = _make_content(db, "영화1")
    c2 = _make_content(db, "영화2")
    map_content(db, c1.id, [root.id])
    map_content(db, c2.id, [child.id])

    assert category_content_count(db, root.id, recursive=True) == 2
    assert category_content_count(db, root.id, recursive=False) == 1
    assert category_content_count(db, child.id, recursive=False) == 1


# ── get_subtree_ids ───────────────────────────────────────────────────────────

def test_get_subtree_ids(db):
    root = create_category(db, "영화")
    child = create_category(db, "액션", parent_id=root.id)
    grand = create_category(db, "SF", parent_id=child.id)

    ids = get_subtree_ids(db, root.id)
    assert ids == {root.id, child.id, grand.id}
