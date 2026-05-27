from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar


@dataclass
class OttItem:
    title: str
    rank: int
    production_year: int | None = None
    external_id: str | None = None
    raw: dict = field(default_factory=dict)


@dataclass
class OttSection:
    """OTT 1-Depth 섹션. section_name이 큐레이션 카피 후보로 사용된다."""
    section_id: str          # 채널+섹션 식별자 (예: "ott_watcha:top")
    name: str                # 섹션명 → 카피 후보 (예: "이번 주 TOP10")
    category_type: str       # ranking | genre | recommendation | mood
    items: list[OttItem] = field(default_factory=list)


class OttSource(ABC):
    channel: ClassVar[str]
    channel_type: ClassVar[str] = "ott"

    @abstractmethod
    def fetch_top(self, limit: int = 20) -> list[OttItem]: ...

    def fetch_sections(self) -> list[OttSection]:
        """기본 구현: fetch_top() 결과를 단일 'TOP' 섹션으로 래핑.
        소스별로 multi-section override 가능."""
        items = self.fetch_top()
        return [OttSection(
            section_id=f"{self.channel}:top",
            name="TOP",
            category_type="ranking",
            items=items,
        )]
