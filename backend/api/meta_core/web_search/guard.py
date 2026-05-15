"""
Bulk query guard — prevent quota exhaustion on bulk operations.

Rule: expected > remaining_quota * 0.5 → reject

Example:
  - Brave daily limit: 60
  - Current used: 45 (remaining: 15)
  - Expected bulk calls: 20
  - Check: 20 > 15 * 0.5 (7.5)? → YES → REJECT
  - Safety margin: 50% of remaining quota protected for other ops
"""

import logging
from shared.quota_manager import QuotaManager
from api.meta_core.web_search.errors import BulkQuotaError

logger = logging.getLogger(__name__)


def check_bulk_allowed(
    expected_calls: int,
    provider: str,
    daily_limit: int,
    quota_manager: QuotaManager,
) -> bool:
    """
    Check if bulk operation is allowed.

    Args:
        expected_calls: Number of queries expected (e.g., 100 records × 1 provider)
        provider: Provider identifier (e.g., 'brave', 'serpapi')
        daily_limit: Daily quota limit
        quota_manager: QuotaManager instance

    Returns:
        True if bulk allowed, False otherwise

    Raises:
        BulkQuotaError: If bulk would exceed quota guard rule
    """
    quota_key = f"websearch:{provider}"
    used = quota_manager.current_count(quota_key)
    remaining = daily_limit - used

    # Guard rule: expected > remaining * 0.5 → reject
    if expected_calls > remaining * 0.5:
        logger.warning(
            f"[bulk-guard] {provider} rejected: "
            f"expected={expected_calls} > remaining={remaining} * 0.5={remaining * 0.5}"
        )
        raise BulkQuotaError(
            expected=expected_calls,
            remaining=remaining,
            detail=f"{provider} quota too low for bulk operation",
        )

    logger.info(
        f"[bulk-guard] {provider} allowed: "
        f"expected={expected_calls} <= remaining={remaining} * 0.5={remaining * 0.5}"
    )
    return True
