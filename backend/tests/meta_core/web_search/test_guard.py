import pytest
from unittest.mock import MagicMock

from api.meta_core.web_search.guard import check_bulk_allowed
from api.meta_core.web_search.errors import BulkQuotaError


@pytest.fixture
def mock_quota_manager():
    """Mock QuotaManager."""
    manager = MagicMock()
    return manager


def test_bulk_allowed_sufficient_quota(mock_quota_manager):
    """Bulk allowed when expected <= remaining * 0.5."""
    # Brave: limit 60, used 40, remaining 20
    # Expected 8 calls: 8 <= 20 * 0.5 (10) → ALLOW
    mock_quota_manager.current_count.return_value = 40

    result = check_bulk_allowed(
        expected_calls=8,
        provider="brave",
        daily_limit=60,
        quota_manager=mock_quota_manager,
    )

    assert result is True


def test_bulk_rejected_insufficient_quota(mock_quota_manager):
    """Bulk rejected when expected > remaining * 0.5."""
    # Brave: limit 60, used 50, remaining 10
    # Expected 20 calls: 20 > 10 * 0.5 (5) → REJECT
    mock_quota_manager.current_count.return_value = 50

    with pytest.raises(BulkQuotaError) as exc_info:
        check_bulk_allowed(
            expected_calls=20,
            provider="brave",
            daily_limit=60,
            quota_manager=mock_quota_manager,
        )

    assert exc_info.value.expected == 20
    assert exc_info.value.remaining == 10


def test_bulk_edge_case_exactly_at_threshold(mock_quota_manager):
    """Edge case: expected == remaining * 0.5 → ALLOW."""
    # Brave: limit 60, used 40, remaining 20
    # Expected 10 calls: 10 <= 20 * 0.5 (10) → ALLOW (equality)
    mock_quota_manager.current_count.return_value = 40

    result = check_bulk_allowed(
        expected_calls=10,
        provider="brave",
        daily_limit=60,
        quota_manager=mock_quota_manager,
    )

    assert result is True


def test_bulk_rejected_over_threshold_by_one(mock_quota_manager):
    """Edge case: expected == remaining * 0.5 + 1 → REJECT."""
    # Brave: limit 60, used 40, remaining 20
    # Expected 11 calls: 11 > 20 * 0.5 (10) → REJECT
    mock_quota_manager.current_count.return_value = 40

    with pytest.raises(BulkQuotaError):
        check_bulk_allowed(
            expected_calls=11,
            provider="brave",
            daily_limit=60,
            quota_manager=mock_quota_manager,
        )


def test_bulk_multiple_providers(mock_quota_manager):
    """Bulk check works for different providers."""
    # SerpAPI: limit 3, used 1, remaining 2
    # Expected 5 calls: 5 > 2 * 0.5 (1) → REJECT
    mock_quota_manager.current_count.return_value = 1

    with pytest.raises(BulkQuotaError) as exc_info:
        check_bulk_allowed(
            expected_calls=5,
            provider="serpapi",
            daily_limit=3,
            quota_manager=mock_quota_manager,
        )

    assert exc_info.value.remaining == 2
