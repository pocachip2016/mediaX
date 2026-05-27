"""distribution-step3.0 — services 테이블 모델·seed·API 테스트"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from api.distribution.models import Service
from api.distribution.service import get_services, get_service_by_code
from shared.database import get_db


@pytest.fixture
def client(db):
    from main import app
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def seeded_db(db):
    """5건 seed 데이터 삽입"""
    rows = [
        Service(code="ott_watcha", name="Watcha", kind="ott", position=1),
        Service(code="ott_netflix", name="Netflix", kind="ott", position=2),
        Service(code="ott_wave", name="Wave", kind="ott", position=3),
        Service(code="ott_tving", name="Tving", kind="ott", position=4),
        Service(code="iptv_genie", name="지니TV", kind="iptv", position=5),
    ]
    db.add_all(rows)
    db.commit()
    return db


def test_service_model_fields(db):
    svc = Service(code="ott_test", name="Test OTT", kind="ott", position=99)
    db.add(svc)
    db.commit()
    db.refresh(svc)
    assert svc.id is not None
    assert svc.code == "ott_test"
    assert svc.is_active is True


def test_service_code_unique_constraint(db):
    db.add(Service(code="ott_watcha", name="Watcha", kind="ott", position=1))
    db.commit()
    db.add(Service(code="ott_watcha", name="Watcha2", kind="ott", position=2))
    with pytest.raises(IntegrityError):
        db.commit()


def test_get_services_returns_all(seeded_db):
    result = get_services(seeded_db)
    assert len(result) == 5
    codes = {s.code for s in result}
    assert "ott_watcha" in codes
    assert "iptv_genie" in codes


def test_get_services_kind_filter(seeded_db):
    ott = get_services(seeded_db, kind="ott")
    assert len(ott) == 4
    assert all(s.kind == "ott" for s in ott)

    iptv = get_services(seeded_db, kind="iptv")
    assert len(iptv) == 1
    assert iptv[0].code == "iptv_genie"


def test_get_services_ordered_by_position(seeded_db):
    result = get_services(seeded_db)
    positions = [s.position for s in result]
    assert positions == sorted(positions)


def test_get_service_by_code(seeded_db):
    svc = get_service_by_code(seeded_db, "ott_netflix")
    assert svc is not None
    assert svc.name == "Netflix"

    missing = get_service_by_code(seeded_db, "nonexistent")
    assert missing is None


def test_get_services_api_200(client, seeded_db):
    r = client.get("/api/distribution/services")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 5
    codes = {row["code"] for row in data}
    assert "ott_watcha" in codes
    assert "iptv_genie" in codes


def test_get_services_api_kind_query(client, seeded_db):
    r = client.get("/api/distribution/services?kind=iptv")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["code"] == "iptv_genie"
