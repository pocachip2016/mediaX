"""
AiTask 추상 기반 클래스 — ADR-007 AI Task 플러그인 프레임워크

신규 AI 기능 추가 방법:
  1. AiTask 상속 + build_input/run/apply 구현
  2. AI_TASK_REGISTRY에 등록

Runner가 활성 task 순회 → input_hash 캐시 → LLM 호출 → apply + 결과 저장
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from api.programming.metadata.models import ContentMetadata


@dataclass
class TaskInput:
    """build_input() 반환값. input_hash 계산의 기반."""
    content_id: int
    task_name: str
    payload: dict[str, Any]  # LLM에 전달될 실제 입력


@dataclass
class TaskOutput:
    """run() 반환값."""
    result: dict[str, Any]
    engine: str


class AiTask(abc.ABC):
    """AI Task 플러그인 인터페이스."""

    #: task_type 값 — AITaskType enum value string (예: "translate_synopsis")
    name: str

    #: False면 Runner가 이 task를 건너뜀 (개별 on/off — B4에서 설정 연동)
    enabled: bool = True

    @abc.abstractmethod
    def build_input(self, meta: "ContentMetadata") -> TaskInput | None:
        """
        ContentMetadata에서 LLM 입력 구성.
        실행 조건 미충족 시 None 반환 → Runner가 skip.
        """

    @abc.abstractmethod
    async def run(self, task_input: TaskInput, provider_chain: list) -> TaskOutput:
        """LLM 호출 → TaskOutput 반환. provider_chain은 AbstractLLMProvider 클래스 목록."""

    @abc.abstractmethod
    def apply(self, meta: "ContentMetadata", output: TaskOutput) -> None:
        """TaskOutput 결과를 ContentMetadata에 반영 (DB flush는 Runner 담당)."""
