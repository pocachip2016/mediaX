import logging
import redis
from datetime import datetime, timezone, timedelta

from shared.config import settings

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))

_client: "redis.Redis | None" = None


def _get_client() -> "redis.Redis":
    global _client
    if _client is None:
        _client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _client


def _midnight_ttl() -> int:
    """Seconds until next KST midnight + 1h buffer."""
    now = datetime.now(KST)
    tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return int((tomorrow - now).total_seconds()) + 3600


class QuotaManager:
    def __init__(self, redis_client: "redis.Redis | None" = None) -> None:
        self._redis = redis_client or _get_client()

    def _key(self, api: str) -> str:
        return f"{api}:daily:{datetime.now(KST).strftime('%Y%m%d')}"

    def is_allowed(self, api: str, daily_limit: int) -> bool:
        key = self._key(api)
        try:
            count = self._redis.incr(key)
            self._redis.expire(key, _midnight_ttl())
            if count > daily_limit:
                logger.warning(f"[{api}] 일일 한도 초과 (count={count}/{daily_limit}). 호출 스킵.")
                return False
            return True
        except redis.RedisError as exc:
            logger.warning(f"[{api}] quota-check Redis 오류, fail-open: {exc}")
            return True

    def current_count(self, api: str) -> int:
        try:
            val = self._redis.get(self._key(api))
            return int(val) if val else 0
        except redis.RedisError:
            return 0

    def daily_remaining(self, api: str, daily_limit: int) -> int:
        """오늘 남은 quota 수 반환 (음수가 되면 0으로 clamp)."""
        return max(0, daily_limit - self.current_count(api))
