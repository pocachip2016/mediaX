"""
홀드백 서비스 단위 테스트 (mock 없음, in-memory SQLite)

검증 케이스:
  - upsert_policy: 생성 + 재호출 시 갱신 (멱등)
  - list_policies: cp_name 필터 + 전체 조회
  - delete_policy: 삭제 + 없을 때 ValueError
  - apply_policy_to_content: offset_days → start/end_date 계산
  - apply_policy_to_content 멱등: 재호출 시 start_date 갱신
  - calendar: 날짜 범위 겹침 조회 + open-ended(end=None) 포함
  - activate_window: status=active 전환 + price 반영
"""
import pytest
from datetime import date, timedelta

from api.programming.catalog.holdback_service import (
    upsert_policy,
    list_policies,
    delete_policy,
    apply_policy_to_content,
    list_schedules,
    calendar,
    activate_window,
)
from api.programming.catalog.models import Quality, PurchaseType, HoldbackSchedule
from api.programming.catalog.pricing_service import get_price_matrix
from api.programming.metadata.models import Content, ContentType, ContentStatus


def _content(db, cp_name="CP_TEST"):
    c = Content(title="홀드백테스트", content_type=ContentType.movie, cp_name=cp_name, status=ContentStatus.raw)
    db.add(c)
    db.flush()
    return c


def _policy(db, cp_name="CP_TEST", window_no=1, offset_start=0, offset_end=90, rule="premium"):
    return upsert_policy(
        db,
        cp_name=cp_name,
        window_no=window_no,
        name=f"윈도우{window_no}",
        offset_days_start=offset_start,
        offset_days_end=offset_end,
        price_rule=rule,
    )


BASE = date(2026, 1, 1)

# ── upsert_policy ─────────────────────────────────────────────────────────────

def test_upsert_policy_creates(db):
    p = _policy(db)
    db.commit()
    assert p.id is not None
    assert p.cp_name == "CP_TEST"
    assert p.window_no == 1


def test_upsert_policy_updates(db):
    _policy(db, rule="premium")
    db.commit()
    p2 = _policy(db, rule="discount")
    db.commit()
    assert p2.price_rule == "discount"
    assert db.query(type(p2)).filter_by(cp_name="CP_TEST", window_no=1).count() == 1


# ── list_policies ─────────────────────────────────────────────────────────────

def test_list_policies_filter_by_cp(db):
    _policy(db, cp_name="CP_A")
    _policy(db, cp_name="CP_B")
    db.commit()
    result = list_policies(db, cp_name="CP_A")
    assert len(result) == 1
    assert result[0].cp_name == "CP_A"


def test_list_policies_all(db):
    _policy(db, cp_name="CP_A")
    _policy(db, cp_name="CP_B")
    db.commit()
    assert len(list_policies(db)) == 2


# ── delete_policy ─────────────────────────────────────────────────────────────

def test_delete_policy(db):
    p = _policy(db)
    db.commit()
    delete_policy(db, p.id)
    db.commit()
    assert list_policies(db, cp_name="CP_TEST") == []


def test_delete_policy_not_found(db):
    with pytest.raises(ValueError, match="holdback_policy not found"):
        delete_policy(db, 9999)


# ── apply_policy_to_content ───────────────────────────────────────────────────

def test_apply_creates_schedules_with_correct_dates(db):
    c = _content(db, cp_name="CP_TEST")
    _policy(db, cp_name="CP_TEST", window_no=1, offset_start=0, offset_end=90)
    _policy(db, cp_name="CP_TEST", window_no=2, offset_start=91, offset_end=180)
    db.commit()
    schedules = apply_policy_to_content(db, c.id, base_date=BASE)
    db.commit()
    assert len(schedules) == 2
    s1 = schedules[0]
    assert s1.start_date == BASE
    assert s1.end_date == BASE + timedelta(days=90)
    s2 = schedules[1]
    assert s2.start_date == BASE + timedelta(days=91)


def test_apply_idempotent_updates_dates(db):
    c = _content(db, cp_name="CP_TEST")
    _policy(db, cp_name="CP_TEST", window_no=1, offset_start=0, offset_end=90)
    db.commit()
    apply_policy_to_content(db, c.id, base_date=BASE)
    db.commit()
    new_base = BASE + timedelta(days=30)
    apply_policy_to_content(db, c.id, base_date=new_base)
    db.commit()
    schedules = list_schedules(db, c.id)
    assert len(schedules) == 1
    assert schedules[0].start_date == new_base


def test_apply_open_ended_window(db):
    c = _content(db, cp_name="CP_TEST")
    upsert_policy(db, cp_name="CP_TEST", window_no=4, name="구독전환",
                  offset_days_start=365, offset_days_end=None, price_rule="subscription")
    db.commit()
    schedules = apply_policy_to_content(db, c.id, base_date=BASE)
    db.commit()
    assert schedules[0].end_date is None


# ── calendar ──────────────────────────────────────────────────────────────────

def test_calendar_returns_overlapping_schedules(db):
    c = _content(db, cp_name="CP_TEST")
    _policy(db, cp_name="CP_TEST", window_no=1, offset_start=0, offset_end=90)
    _policy(db, cp_name="CP_TEST", window_no=2, offset_start=91, offset_end=180)
    db.commit()
    apply_policy_to_content(db, c.id, base_date=BASE)
    db.commit()
    result = calendar(db, start_date=date(2026, 2, 1), end_date=date(2026, 2, 28))
    assert len(result) == 1
    assert result[0].window_no == 1


def test_calendar_includes_open_ended(db):
    c = _content(db, cp_name="CP_TEST")
    upsert_policy(db, cp_name="CP_TEST", window_no=4, name="구독",
                  offset_days_start=0, offset_days_end=None, price_rule="subscription")
    db.commit()
    apply_policy_to_content(db, c.id, base_date=BASE)
    db.commit()
    result = calendar(db, start_date=date(2027, 1, 1), end_date=date(2027, 12, 31))
    assert len(result) == 1


# ── activate_window ───────────────────────────────────────────────────────────

def test_activate_window_changes_status(db):
    c = _content(db, cp_name="CP_TEST")
    _policy(db, cp_name="CP_TEST", window_no=1)
    db.commit()
    apply_policy_to_content(db, c.id, base_date=BASE)
    db.commit()
    s = activate_window(db, c.id, window_no=1)
    db.commit()
    assert s.status == "active"


def test_activate_window_applies_price(db):
    c = _content(db, cp_name="CP_TEST")
    _policy(db, cp_name="CP_TEST", window_no=1)
    db.commit()
    apply_policy_to_content(db, c.id, base_date=BASE)
    db.commit()
    activate_window(
        db, c.id, window_no=1,
        quality=Quality.HD, purchase_type=PurchaseType.single, price=3000,
        changed_by="system",
    )
    db.commit()
    matrix = get_price_matrix(db, c.id)
    assert matrix["single"]["HD"] == 3000


def test_activate_window_not_found(db):
    c = _content(db)
    with pytest.raises(ValueError, match="holdback_schedule not found"):
        activate_window(db, c.id, window_no=99)
