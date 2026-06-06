"""
가격 정책 서비스 단위 테스트 (mock 없음, in-memory SQLite)

검증 케이스:
  - set_price upsert: 최초 생성 + PriceChangeLog(old_price=None)
  - set_price 멱등: 동일 값 재호출 시 로그 미생성
  - set_price 변경: old_price 기록
  - get_price_matrix: {purchase_type: {quality: price}} 구조
  - bulk_update: 공통 batch_id, 변경된 행만 로그 생성
  - delete_price: 행 삭제 + 없을 때 ValueError
"""
import pytest

from api.programming.catalog.pricing_service import (
    set_price,
    get_price_matrix,
    bulk_update,
    list_price_changes,
    delete_price,
)
from api.programming.catalog.models import Quality, PurchaseType, Pricing, PriceChangeLog
from api.programming.metadata.models import Content, ContentType, ContentStatus


def _content(db, title="테스트"):
    c = Content(title=title, content_type=ContentType.movie, cp_name="CP_A", status=ContentStatus.raw)
    db.add(c)
    db.flush()
    return c


# ── set_price: 최초 생성 ──────────────────────────────────────────────────────

def test_set_price_creates_row(db):
    c = _content(db)
    row = set_price(db, c.id, Quality.HD, PurchaseType.single, 2000)
    db.commit()
    assert row.id is not None
    assert row.price == 2000
    assert row.currency == "KRW"


def test_set_price_initial_log(db):
    c = _content(db)
    set_price(db, c.id, Quality.HD, PurchaseType.single, 2000, changed_by="admin")
    db.commit()
    logs = list_price_changes(db, c.id)
    assert len(logs) == 1
    assert logs[0].old_price is None
    assert logs[0].new_price == 2000
    assert logs[0].changed_by == "admin"


# ── set_price 멱등 ────────────────────────────────────────────────────────────

def test_set_price_idempotent_no_log(db):
    c = _content(db)
    set_price(db, c.id, Quality.HD, PurchaseType.single, 2000)
    db.commit()
    set_price(db, c.id, Quality.HD, PurchaseType.single, 2000)
    db.commit()
    logs = list_price_changes(db, c.id)
    assert len(logs) == 1  # 첫 생성 시만 로그, 동일값 재호출은 미기록


# ── set_price 변경 ────────────────────────────────────────────────────────────

def test_set_price_change_logs_old_price(db):
    c = _content(db)
    set_price(db, c.id, Quality.HD, PurchaseType.single, 2000)
    db.commit()
    set_price(db, c.id, Quality.HD, PurchaseType.single, 2500, reason="프로모션 종료")
    db.commit()
    logs = list_price_changes(db, c.id)
    assert len(logs) == 2
    latest = logs[0]
    assert latest.old_price == 2000
    assert latest.new_price == 2500
    assert latest.reason == "프로모션 종료"


# ── set_price: str 인자 허용 ──────────────────────────────────────────────────

def test_set_price_accepts_string_enum(db):
    c = _content(db)
    row = set_price(db, c.id, "FHD", "season_package", 9900)
    db.commit()
    assert row.price == 9900


# ── get_price_matrix ──────────────────────────────────────────────────────────

def test_get_price_matrix_structure(db):
    c = _content(db)
    set_price(db, c.id, Quality.SD, PurchaseType.single, 1000)
    set_price(db, c.id, Quality.HD, PurchaseType.single, 2000)
    set_price(db, c.id, Quality.HD, PurchaseType.season_package, 8000)
    db.commit()
    matrix = get_price_matrix(db, c.id)
    assert matrix["single"]["SD"] == 1000
    assert matrix["single"]["HD"] == 2000
    assert matrix["season_package"]["HD"] == 8000


def test_get_price_matrix_empty(db):
    c = _content(db)
    assert get_price_matrix(db, c.id) == {}


# ── bulk_update ───────────────────────────────────────────────────────────────

def test_bulk_update_shares_batch_id(db):
    c1 = _content(db, "콘텐츠1")
    c2 = _content(db, "콘텐츠2")
    items = [
        {"content_id": c1.id, "quality": "HD", "purchase_type": "single", "price": 1500},
        {"content_id": c2.id, "quality": "HD", "purchase_type": "single", "price": 1500},
    ]
    bulk_update(db, items, changed_by="batch_admin", reason="정기 조정")
    db.commit()
    logs1 = list_price_changes(db, c1.id)
    logs2 = list_price_changes(db, c2.id)
    assert len(logs1) == 1
    assert len(logs2) == 1
    assert logs1[0].batch_id == logs2[0].batch_id
    assert logs1[0].batch_id is not None


def test_bulk_update_idempotent_no_extra_log(db):
    c = _content(db)
    items = [{"content_id": c.id, "quality": "HD", "purchase_type": "single", "price": 2000}]
    bulk_update(db, items)
    db.commit()
    bulk_update(db, items)
    db.commit()
    logs = list_price_changes(db, c.id)
    assert len(logs) == 1  # 두 번째 bulk는 동일값 → 로그 없음


# ── delete_price ──────────────────────────────────────────────────────────────

def test_delete_price(db):
    c = _content(db)
    set_price(db, c.id, Quality.HD, PurchaseType.single, 2000)
    db.commit()
    delete_price(db, c.id, Quality.HD, PurchaseType.single)
    db.commit()
    assert db.query(Pricing).filter(Pricing.content_id == c.id).count() == 0


def test_delete_price_not_found(db):
    c = _content(db)
    with pytest.raises(ValueError, match="pricing not found"):
        delete_price(db, c.id, Quality.HD, PurchaseType.single)
