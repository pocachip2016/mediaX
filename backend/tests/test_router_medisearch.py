"""tests/test_router_medisearch.py — router_medisearch 헬퍼 단위 테스트."""
from unittest.mock import MagicMock, patch

import pytest


class TestCallMedisearchEvaluateRaw:
    """_call_medisearch_evaluate_raw가 payload를 MediSearch로 정확히 전달하는지 검증."""

    def _call(self, payload: dict):
        from api.programming.metadata.router_medisearch import _call_medisearch_evaluate_raw
        return _call_medisearch_evaluate_raw(payload)

    def test_content_type_included_when_present(self):
        """content_type=series → evaluate payload에 포함."""
        captured = {}

        def fake_post(url, json):
            captured["json"] = json
            resp = MagicMock()
            resp.is_success = True
            resp.json.return_value = {"facet": {}, "source_count": 1}
            return resp

        with patch("api.programming.metadata.router_medisearch.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = lambda s: s
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = fake_post
            mock_client_cls.return_value = mock_client

            result = self._call({
                "title": "오징어 게임",
                "production_year": 2021,
                "content_type": "series",
                "imdb_id": "tt10919420",
            })

        assert result is not None
        assert captured["json"]["content_type"] == "series"
        assert captured["json"].get("require_namu") is False

    def test_content_type_omitted_when_absent(self):
        """content_type 없으면 payload에 포함 안 됨."""
        captured = {}

        def fake_post(url, json):
            captured["json"] = json
            resp = MagicMock()
            resp.is_success = True
            resp.json.return_value = {"facet": {}, "source_count": 1}
            return resp

        with patch("api.programming.metadata.router_medisearch.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = lambda s: s
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = fake_post
            mock_client_cls.return_value = mock_client

            self._call({"title": "기생충", "production_year": 2019})

        assert "content_type" not in captured["json"]

    def test_require_namu_always_false(self):
        """require_namu는 항상 False — 외부 payload 값 무시."""
        captured = {}

        def fake_post(url, json):
            captured["json"] = json
            resp = MagicMock()
            resp.is_success = True
            resp.json.return_value = {}
            return resp

        with patch("api.programming.metadata.router_medisearch.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = lambda s: s
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = fake_post
            mock_client_cls.return_value = mock_client

            self._call({"title": "기생충", "require_namu": True})

        assert captured["json"]["require_namu"] is False
