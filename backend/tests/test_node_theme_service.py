"""node_theme_service 단위 테스트 — SQLite in-memory + monkeypatch OllamaEmbeddingsProvider."""
import asyncio

import pytest

from api.programming.scheduling.models import NodeKind, ProgrammingNode, ProgrammingNodeSet
from api.programming.scheduling.node_theme_service import (
    build_node_theme_embedding,
    compose_theme_text,
)

_FAKE_VEC = [0.1] * 1024
_FAKE_VEC2 = [0.2] * 1024


def _make_node(db, *, name="테스트 노드", headline_copy=None, sub_copy=None, theme_features=None):
    ns = ProgrammingNodeSet(name="s", status="draft")
    db.add(ns)
    db.flush()
    node = ProgrammingNode(
        set_id=ns.id,
        kind=NodeKind.manual,
        name=name,
        headline_copy=headline_copy,
        sub_copy=sub_copy,
        theme_features=theme_features,
    )
    db.add(node)
    db.flush()
    return node


# ── compose_theme_text ────────────────────────────────────────────────────────

def test_compose_includes_name_headline_sub(db):
    node = _make_node(db, name="여름 드라마", headline_copy="무더위에 시원한", sub_copy="감성 로맨스")
    text = compose_theme_text(node)
    assert "여름 드라마" in text
    assert "무더위에 시원한" in text
    assert "감성 로맨스" in text


def test_compose_skips_none(db):
    node = _make_node(db, name="X", headline_copy=None, sub_copy=None)
    text = compose_theme_text(node)
    assert text == "X"


def test_compose_includes_theme_features_lists(db):
    node = _make_node(db, theme_features={"mood": ["경쾌", "감성"], "tempo": ["빠름"]})
    text = compose_theme_text(node)
    assert "경쾌" in text
    assert "감성" in text
    assert "빠름" in text


def test_compose_flattens_setting(db):
    node = _make_node(db, theme_features={"setting": {"era": ["현대"], "place": ["한국"]}})
    text = compose_theme_text(node)
    assert "현대" in text
    assert "한국" in text


def test_compose_empty_when_all_none(db):
    node = _make_node(db, name="", headline_copy=None, sub_copy=None, theme_features=None)
    text = compose_theme_text(node)
    assert text == ""


# ── build_node_theme_embedding ────────────────────────────────────────────────

def test_build_stores_vector(db, monkeypatch):
    embed_calls = []

    async def _fake_embed(self, text):
        embed_calls.append(text)
        return _FAKE_VEC

    monkeypatch.setattr(
        "api.programming.scheduling.node_theme_service.OllamaEmbeddingsProvider.embed",
        _fake_embed,
    )
    node = _make_node(db, name="가을 편성")
    vec = asyncio.run(build_node_theme_embedding(db, node.id))
    assert vec == _FAKE_VEC
    assert node.embed_theme == _FAKE_VEC
    assert len(embed_calls) == 1


def test_build_idempotent_no_force(db, monkeypatch):
    embed_calls = []

    async def _fake_embed(self, text):
        embed_calls.append(text)
        return _FAKE_VEC2

    monkeypatch.setattr(
        "api.programming.scheduling.node_theme_service.OllamaEmbeddingsProvider.embed",
        _fake_embed,
    )
    node = _make_node(db, name="봄 편성")
    node.embed_theme = _FAKE_VEC  # 이미 캐시된 상태
    db.flush()

    vec = asyncio.run(build_node_theme_embedding(db, node.id))
    assert vec == _FAKE_VEC  # 캐시 반환
    assert len(embed_calls) == 0  # embed 재호출 없음


def test_build_force_reembeds(db, monkeypatch):
    embed_calls = []

    async def _fake_embed(self, text):
        embed_calls.append(text)
        return _FAKE_VEC2

    monkeypatch.setattr(
        "api.programming.scheduling.node_theme_service.OllamaEmbeddingsProvider.embed",
        _fake_embed,
    )
    node = _make_node(db, name="겨울 편성")
    node.embed_theme = _FAKE_VEC
    db.flush()

    vec = asyncio.run(build_node_theme_embedding(db, node.id, force=True))
    assert vec == _FAKE_VEC2
    assert len(embed_calls) == 1


def test_build_empty_text_returns_none(db, monkeypatch):
    async def _fake_embed(self, text):
        return _FAKE_VEC

    monkeypatch.setattr(
        "api.programming.scheduling.node_theme_service.OllamaEmbeddingsProvider.embed",
        _fake_embed,
    )
    node = _make_node(db, name="", headline_copy=None, sub_copy=None, theme_features=None)
    vec = asyncio.run(build_node_theme_embedding(db, node.id))
    assert vec is None
    assert node.embed_theme is None


def test_build_unknown_node_id(db, monkeypatch):
    async def _fake_embed(self, text):
        return _FAKE_VEC

    monkeypatch.setattr(
        "api.programming.scheduling.node_theme_service.OllamaEmbeddingsProvider.embed",
        _fake_embed,
    )
    vec = asyncio.run(build_node_theme_embedding(db, 9999))
    assert vec is None
