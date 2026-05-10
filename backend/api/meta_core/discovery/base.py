"""
DiscoverySource 추상 인터페이스 + DiscoveryResult 데이터 클래스

참조: docs/dev/phase-c/sources.md, docs/dev/phase-c/lifecycle.md
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator


@dataclass
class DiscoveryResult:
    source_type: str
    external_id: str
    title: str
    content_type: str          # movie | series
    original_title: str | None = None
    production_year: int | None = None
    poster_url: str | None = None
    synopsis: str | None = None
    raw: dict = field(default_factory=dict)


class DiscoverySource(ABC):
    """발굴 소스 추상 인터페이스. 각 소스(TMDB/KOBIS/KMDB/OMDb)는 이를 구현한다."""

    source_type: str  # 구현 클래스에서 클래스 변수로 정의

    @abstractmethod
    def discover(self, mode: str, **kwargs) -> Iterator[DiscoveryResult]:
        """mode 에 따라 외부 API 를 호출하고 DiscoveryResult 를 yield 한다."""

    def log_run(
        self,
        db,
        mode: str,
        total: int,
        new_seeds: int,
        matched_existing: int,
        duplicates: int,
        errors: int,
        duration_ms: int,
        discovery_params: dict | None = None,
    ) -> None:
        """SeedDiscoveryLog 1건 기록."""
        from api.meta_core.models.seed import SeedDiscoveryLog

        entry = SeedDiscoveryLog(
            source_type=self.source_type,
            discovery_mode=mode,
            total_fetched=total,
            new_seeds=new_seeds,
            matched_existing=matched_existing,
            duplicates=duplicates,
            errors=errors,
            duration_ms=duration_ms,
            discovery_params=discovery_params,
        )
        db.add(entry)
        db.commit()
