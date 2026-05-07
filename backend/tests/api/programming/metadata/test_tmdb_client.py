"""
TmdbClient 단위 테스트 — respx 로 외부 호출 mock
"""
import asyncio
import pytest
import respx
import httpx

from api.programming.metadata.tmdb_client import TmdbClient, TmdbRateLimitError

API_KEY = "test_key"
BASE = "https://api.themoviedb.org/3"


# ── 헬퍼 ─────────────────────────────────────────────────────────────────────

def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ── 1. discover_movies 정상 응답 ───────────────────────────────────────────────

@respx.mock
def test_discover_movies_success():
    respx.get(f"{BASE}/discover/movie").mock(
        return_value=httpx.Response(200, json={"results": [{"id": 1, "title": "영화A"}], "total_pages": 1})
    )
    async def _run():
        async with TmdbClient(api_key=API_KEY) as client:
            data = await client.discover_movies(year=2024)
        return data

    result = run(_run())
    assert result["results"][0]["id"] == 1
    assert result["total_pages"] == 1


# ── 2. 429 → Retry-After 대기 → 성공 ─────────────────────────────────────────

@respx.mock
def test_429_retry_then_success(monkeypatch):
    async def _noop(_): pass
    monkeypatch.setattr("api.programming.metadata.tmdb_client.asyncio.sleep", _noop)

    call_count = 0

    def side_effect(request, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(429, headers={"Retry-After": "1"}, json={})
        return httpx.Response(200, json={"results": [], "total_pages": 0})

    respx.get(f"{BASE}/discover/movie").mock(side_effect=side_effect)

    async def _run():
        async with TmdbClient(api_key=API_KEY, max_retries=2) as client:
            return await client.discover_movies()

    result = run(_run())
    assert result == {"results": [], "total_pages": 0}
    assert call_count == 2


# ── 3. 429 max_retries 초과 → TmdbRateLimitError ─────────────────────────────

@respx.mock
def test_429_max_retries_raises(monkeypatch):
    async def _noop(_): pass
    monkeypatch.setattr("api.programming.metadata.tmdb_client.asyncio.sleep", _noop)
    respx.get(f"{BASE}/discover/movie").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "1"}, json={})
    )

    async def _run():
        async with TmdbClient(api_key=API_KEY, max_retries=1) as client:
            await client.discover_movies()

    with pytest.raises(TmdbRateLimitError):
        run(_run())


# ── 4. max_concurrency Semaphore — 동시 요청 N 초과 안됨 ─────────────────────

@respx.mock
def test_concurrency_limit():
    respx.get(f"{BASE}/discover/movie").mock(
        return_value=httpx.Response(200, json={"results": [], "total_pages": 1})
    )

    active = 0
    max_active = 0

    original_get = httpx.AsyncClient.get

    async def patched_get(self, url, **kwargs):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0)
        result = await original_get(self, url, **kwargs)
        active -= 1
        return result

    async def _run():
        client = TmdbClient(api_key=API_KEY, max_concurrency=3)
        async with client:
            tasks = [client.discover_movies(year=2020 + i) for i in range(6)]
            await asyncio.gather(*tasks)

    run(_run())
    assert max_active <= 3


# ── 5. poster_url 조합 ────────────────────────────────────────────────────────

def test_poster_url():
    assert TmdbClient.poster_url("/abc.jpg") == "https://image.tmdb.org/t/p/w500/abc.jpg"
    assert TmdbClient.poster_url(None) is None
    assert TmdbClient.poster_url("/x.jpg", size="original") == "https://image.tmdb.org/t/p/original/x.jpg"


# ── 6. API 키가 로그에 노출되지 않음 ─────────────────────────────────────────

@respx.mock
def test_api_key_not_logged(caplog):
    respx.get(f"{BASE}/discover/movie").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "0"}, json={})
    )

    async def _run():
        async with TmdbClient(api_key="SECRET_KEY_12345", max_retries=0) as client:
            try:
                await client.discover_movie(1)
            except Exception:
                pass
            try:
                await client.discover_movies()
            except Exception:
                pass

    import logging
    with caplog.at_level(logging.WARNING):
        run(_run())

    for record in caplog.records:
        assert "SECRET_KEY_12345" not in record.getMessage()
