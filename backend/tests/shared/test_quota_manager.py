import redis
from unittest.mock import MagicMock
from shared.quota_manager import QuotaManager


def _mgr(incr_return: int = 1) -> QuotaManager:
    mock = MagicMock(spec=redis.Redis)
    mock.incr.return_value = incr_return
    return QuotaManager(redis_client=mock)


def test_is_allowed_below_limit():
    assert _mgr(incr_return=1).is_allowed("kobis", 2900) is True


def test_is_allowed_at_limit():
    assert _mgr(incr_return=2900).is_allowed("kobis", 2900) is True


def test_is_not_allowed_above_limit():
    assert _mgr(incr_return=2901).is_allowed("kobis", 2900) is False


def test_fail_open_on_redis_error():
    mock = MagicMock(spec=redis.Redis)
    mock.incr.side_effect = redis.exceptions.RedisError("connection refused")
    assert QuotaManager(redis_client=mock).is_allowed("kobis", 2900) is True


def test_current_count_returns_value():
    mock = MagicMock(spec=redis.Redis)
    mock.get.return_value = "42"
    assert QuotaManager(redis_client=mock).current_count("kobis") == 42


def test_current_count_returns_zero_when_missing():
    mock = MagicMock(spec=redis.Redis)
    mock.get.return_value = None
    assert QuotaManager(redis_client=mock).current_count("kobis") == 0
