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


class OttSource(ABC):
    channel: ClassVar[str]
    channel_type: ClassVar[str] = "ott"

    @abstractmethod
    def fetch_top(self, limit: int = 20) -> list[OttItem]: ...
