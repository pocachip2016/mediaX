"""
dev-curation-workbench Step 3 — curations API 엔드포인트 테스트
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.programming.metadata.models.content import Content, ContentType
from api.distribution.ott.base import OttItem, OttSection
from shared.database import get_db


@pytest.fixture
def client(db):
    from main import app
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _make_section(channel: str, name: str, items: list[OttItem] | None = None) -> OttSection:
    return OttSection(
        section_id=f"{channel}:{name}",
        name=name,
        category_type="ranking",
        items=items or [OttItem(title="영화A", rank=1)],
    )


def _empty_ott_mock(channel: str) -> MagicMock:
    m = MagicMock()
    m.channel = channel
    m.fetch_sections.return_value = []
    return m


# ── POST /api/distribution/curations/match-contents ──────────────────────────

def test_match_contents_empty_db(client):
    r = client.post(
        "/api/distribution/curations/match-contents",
        json={"theme_features": {"genres": ["드라마"]}, "limit": 10},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert "genres" in data["theme_features"]


def test_match_contents_returns_candidates(client, db):
    db.add(Content(title="기생충", content_type=ContentType.movie, production_year=2019, is_deleted=False))
    db.add(Content(title="버닝",   content_type=ContentType.movie, production_year=2018, is_deleted=False))
    db.commit()

    r = client.post(
        "/api/distribution/curations/match-contents",
        json={"theme_features": {}, "limit": 10},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    for item in data["items"]:
        assert "content_id" in item
        assert "title" in item
        assert "score" in item
        assert "score_breakdown" in item


def test_match_contents_limit_honored(client, db):
    for i in range(5):
        db.add(Content(title=f"영화{i}", content_type=ContentType.movie, is_deleted=False))
    db.commit()

    r = client.post(
        "/api/distribution/curations/match-contents",
        json={"theme_features": {}, "limit": 2},
    )
    assert r.status_code == 200
    assert len(r.json()["items"]) == 2


def test_match_contents_external_titles_bonus(client, db):
    db.add(Content(title="기생충", content_type=ContentType.movie, production_year=2019, is_deleted=False))
    db.add(Content(title="버닝",   content_type=ContentType.movie, production_year=2018, is_deleted=False))
    db.commit()

    r = client.post(
        "/api/distribution/curations/match-contents",
        json={
            "theme_features": {},
            "external_titles": ["기생충"],
            "limit": 10,
        },
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert items[0]["title"] == "기생충"
    assert items[0]["score_breakdown"]["external"] > 0.0


def test_match_contents_sorted_by_score_desc(client, db):
    db.add(Content(
        title="신작",
        content_type=ContentType.movie,
        production_year=2024,
        runtime_minutes=100,
        is_deleted=False,
    ))
    db.add(Content(
        title="구작",
        content_type=ContentType.movie,
        production_year=1980,
        runtime_minutes=200,
        is_deleted=False,
    ))
    db.commit()

    r = client.post(
        "/api/distribution/curations/match-contents",
        json={
            "theme_features": {
                "era_from": 2020,
                "era_to": 2026,
                "runtime_min": 80,
                "runtime_max": 120,
            },
            "limit": 10,
        },
    )
    assert r.status_code == 200
    items = r.json()["items"]
    scores = [i["score"] for i in items]
    assert scores == sorted(scores, reverse=True)


def test_match_contents_skips_deleted(client, db):
    db.add(Content(title="삭제됨", content_type=ContentType.movie, is_deleted=True))
    db.add(Content(title="활성",   content_type=ContentType.movie, is_deleted=False))
    db.commit()

    r = client.post(
        "/api/distribution/curations/match-contents",
        json={"theme_features": {}, "limit": 10},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "활성"


def test_match_contents_theme_features_echoed(client):
    tf = {"genres": ["코미디"], "era_from": 2000}
    r = client.post(
        "/api/distribution/curations/match-contents",
        json={"theme_features": tf},
    )
    assert r.status_code == 200
    assert r.json()["theme_features"] == tf


# ── GET /api/distribution/curations/external-references ──────────────────────
# 주의: router 함수 내 lazy import 이므로 소스 모듈 위치를 패치함

_PATCH_WATCHA  = "api.distribution.ott.watcha.WatchaTopSource"
_PATCH_NETFLIX = "api.distribution.ott.netflix.NetflixTudumSource"
_PATCH_WAVE    = "api.distribution.ott.wave.WaveTopSource"
_PATCH_TVING   = "api.distribution.ott.tving.TvingTopSource"


def test_external_references_returns_sections(client):
    mock_w = _empty_ott_mock("ott_watcha")
    mock_w.fetch_sections.return_value = [
        _make_section("ott_watcha", "TOP10"),
        _make_section("ott_watcha", "신작"),
    ]
    mock_n = _empty_ott_mock("ott_netflix")
    mock_n.fetch_sections.return_value = [_make_section("ott_netflix", "오늘의 추천")]

    with (
        patch(_PATCH_WATCHA,  return_value=mock_w),
        patch(_PATCH_NETFLIX, return_value=mock_n),
        patch(_PATCH_WAVE,    return_value=_empty_ott_mock("ott_wave")),
        patch(_PATCH_TVING,   return_value=_empty_ott_mock("ott_tving")),
    ):
        r = client.get("/api/distribution/curations/external-references")

    assert r.status_code == 200
    data = r.json()
    assert data["total_sections"] == 3
    names = [s["name"] for s in data["sections"]]
    assert "TOP10" in names
    assert "신작" in names
    assert "오늘의 추천" in names


def test_external_references_section_fields(client):
    mock_w = _empty_ott_mock("ott_watcha")
    mock_w.fetch_sections.return_value = [
        OttSection(
            section_id="ott_watcha:top10",
            name="이번 주 TOP10",
            category_type="ranking",
            items=[OttItem(title="기생충", rank=1, production_year=2019, external_id="abc123")],
        )
    ]

    with (
        patch(_PATCH_WATCHA,  return_value=mock_w),
        patch(_PATCH_NETFLIX, return_value=_empty_ott_mock("ott_netflix")),
        patch(_PATCH_WAVE,    return_value=_empty_ott_mock("ott_wave")),
        patch(_PATCH_TVING,   return_value=_empty_ott_mock("ott_tving")),
    ):
        r = client.get("/api/distribution/curations/external-references")

    assert r.status_code == 200
    section = r.json()["sections"][0]
    assert section["section_id"] == "ott_watcha:top10"
    assert section["name"] == "이번 주 TOP10"
    assert section["category_type"] == "ranking"
    assert section["channel"] == "ott_watcha"
    assert section["item_count"] == 1
    assert section["items"][0]["title"] == "기생충"
    assert section["items"][0]["rank"] == 1


def test_external_references_channel_filter(client):
    mock_w = _empty_ott_mock("ott_watcha")
    mock_w.fetch_sections.return_value = [_make_section("ott_watcha", "TOP10")]
    mock_n = _empty_ott_mock("ott_netflix")
    mock_n.fetch_sections.return_value = [_make_section("ott_netflix", "추천")]

    with (
        patch(_PATCH_WATCHA,  return_value=mock_w),
        patch(_PATCH_NETFLIX, return_value=mock_n),
        patch(_PATCH_WAVE,    return_value=_empty_ott_mock("ott_wave")),
        patch(_PATCH_TVING,   return_value=_empty_ott_mock("ott_tving")),
    ):
        r = client.get("/api/distribution/curations/external-references?channel=ott_watcha")

    assert r.status_code == 200
    data = r.json()
    assert data["total_sections"] == 1
    assert data["sections"][0]["channel"] == "ott_watcha"


def test_external_references_source_failure_graceful(client):
    mock_w = _empty_ott_mock("ott_watcha")
    mock_w.fetch_sections.side_effect = Exception("크롤링 실패")

    with (
        patch(_PATCH_WATCHA,  return_value=mock_w),
        patch(_PATCH_NETFLIX, return_value=_empty_ott_mock("ott_netflix")),
        patch(_PATCH_WAVE,    return_value=_empty_ott_mock("ott_wave")),
        patch(_PATCH_TVING,   return_value=_empty_ott_mock("ott_tving")),
    ):
        r = client.get("/api/distribution/curations/external-references")

    assert r.status_code == 200  # 예외가 500으로 전파되지 않음
    assert r.json()["total_sections"] == 0
