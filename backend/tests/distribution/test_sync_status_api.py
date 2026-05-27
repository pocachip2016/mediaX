"""distribution-step2.5 — sync/status API 테스트"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from api.distribution.models import ContentDistribution
from api.programming.metadata.models.content import Content
from shared.database import get_db


@pytest.fixture
def client(db):
    from main import app
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_sync_status_empty_db_returns_4_channels(client):
    r = client.get("/api/distribution/sync/status")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 4
    channels = {row["channel"] for row in data}
    assert channels == {"ott_watcha", "ott_netflix", "ott_wave", "ott_tving"}
    for row in data:
        assert row["total_rows"] == 0
        assert row["last_synced_at"] is None


def test_sync_status_with_data_correct_count(client, db):
    now = datetime.now(timezone.utc)
    for i in range(3):
        c = Content(title=f"영화{i}")
        db.add(c)
        db.flush()
        db.add(ContentDistribution(
            content_id=c.id,
            channel="ott_watcha",
            channel_type="ott",
            popularity_rank=i + 1,
            synced_at=now,
        ))
    db.commit()

    r = client.get("/api/distribution/sync/status")
    assert r.status_code == 200
    data = {row["channel"]: row for row in r.json()}
    assert data["ott_watcha"]["total_rows"] == 3
    assert data["ott_netflix"]["total_rows"] == 0


def test_sync_status_returns_200(client):
    r = client.get("/api/distribution/sync/status")
    assert r.status_code == 200
