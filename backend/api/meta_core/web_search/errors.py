class QuotaExhaustedError(Exception):
    """Quota exhausted for provider."""
    def __init__(self, provider: str, remaining: int = 0):
        self.provider = provider
        self.remaining = remaining
        super().__init__(f"Quota exhausted for {provider} (remaining: {remaining})")


class ProviderUnavailableError(Exception):
    """Provider unavailable (API error, network issue, etc.)."""
    def __init__(self, provider: str, detail: str = ""):
        self.provider = provider
        self.detail = detail
        super().__init__(f"Provider {provider} unavailable: {detail}")


class BulkQuotaError(Exception):
    """Bulk operation rejected by quota guard."""
    def __init__(self, expected: int, remaining: int, detail: str = ""):
        self.expected = expected
        self.remaining = remaining
        self.detail = detail
        msg = f"Bulk rejected: expected={expected} > remaining={remaining} * 0.5"
        if detail:
            msg += f" ({detail})"
        super().__init__(msg)
