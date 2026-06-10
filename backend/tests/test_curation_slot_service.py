"""test_curation_slot_service.py — HomeSlot CRUD + resolve 검증."""
import pytest
from api.programming.curation import slot_service as svc
from api.programming.curation.models import Device, SlotCode, SlotType, TimeBand
from api.programming.scheduling.models import ProgrammingNodeSet


# ── helpers ───────────────────────────────────────────────────────────────────

@pytest.fixture
def node_set(db):
    ns = ProgrammingNodeSet(name="테스트 세트", status="draft")
    db.add(ns)
    db.commit()
    db.refresh(ns)
    return ns


# ── CRUD ──────────────────────────────────────────────────────────────────────

def test_create_and_get_slot(db):
    slot = svc.create_slot(db, SlotCode.A, SlotType.banner)
    db.commit()
    fetched = svc.get_slot(db, slot.id)
    assert fetched is not None
    assert fetched.slot_code == SlotCode.A
    assert fetched.slot_type == SlotType.banner
    assert fetched.device == Device.all
    assert fetched.time_band == TimeBand.all
    assert fetched.is_active is True


def test_list_slots_active_only(db):
    svc.create_slot(db, SlotCode.A, SlotType.banner)
    s2 = svc.create_slot(db, SlotCode.B, SlotType.theme)
    db.flush()
    svc.update_slot(db, s2.id, is_active=False)
    db.commit()
    active = svc.list_slots(db, active_only=True)
    assert len(active) == 1
    assert active[0].slot_code == SlotCode.A


def test_bind_and_unbind_node_set(db, node_set):
    slot = svc.create_slot(db, SlotCode.C, SlotType.genre)
    db.commit()
    svc.bind_node_set(db, slot.id, node_set.id)
    db.commit()
    assert svc.get_slot(db, slot.id).node_set_id == node_set.id

    svc.bind_node_set(db, slot.id, None)
    db.commit()
    assert svc.get_slot(db, slot.id).node_set_id is None


def test_delete_slot(db):
    slot = svc.create_slot(db, SlotCode.D, SlotType.ranking)
    db.commit()
    svc.delete_slot(db, slot.id)
    db.commit()
    assert svc.get_slot(db, slot.id) is None


def test_delete_nonexistent_raises(db):
    with pytest.raises(ValueError, match="not found"):
        svc.delete_slot(db, 99999)


# ── resolve ───────────────────────────────────────────────────────────────────

def test_resolve_returns_generic_when_no_specific(db):
    svc.create_slot(db, SlotCode.A, SlotType.banner, Device.all, TimeBand.all)
    db.commit()
    result = svc.resolve_slots(db, Device.tv, TimeBand.evening)
    assert len(result) == 1
    assert result[0].slot_code == SlotCode.A


def test_resolve_prefers_specific_over_all(db):
    svc.create_slot(db, SlotCode.A, SlotType.banner, Device.all, TimeBand.all, position=0)
    svc.create_slot(db, SlotCode.A, SlotType.banner, Device.tv, TimeBand.evening, position=0)
    db.commit()
    result = svc.resolve_slots(db, Device.tv, TimeBand.evening)
    assert len(result) == 1
    assert result[0].device == Device.tv
    assert result[0].time_band == TimeBand.evening


def test_resolve_excludes_inactive(db):
    s = svc.create_slot(db, SlotCode.B, SlotType.theme, Device.all, TimeBand.all)
    db.flush()
    svc.update_slot(db, s.id, is_active=False)
    db.commit()
    result = svc.resolve_slots(db, Device.mobile, TimeBand.morning)
    assert all(r.slot_code != SlotCode.B for r in result)


def test_resolve_slot_order_follows_slot_code(db):
    for code in (SlotCode.C, SlotCode.A, SlotCode.B):
        svc.create_slot(db, code, SlotType.genre)
    db.commit()
    result = svc.resolve_slots(db, Device.all, TimeBand.all)
    codes = [r.slot_code for r in result]
    assert codes == sorted(codes, key=lambda c: c.value)


def test_resolve_no_match_returns_empty(db):
    svc.create_slot(db, SlotCode.A, SlotType.banner, Device.tv, TimeBand.evening)
    db.commit()
    result = svc.resolve_slots(db, Device.mobile, TimeBand.morning)
    assert result == []
