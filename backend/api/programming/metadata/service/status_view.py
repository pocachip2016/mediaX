"""ADR-006 status ↔ stage 동기 보장 헬퍼.

derive_status_from_stage(stage) → ContentStatus | None 는 stage_events.py에 SSOT로 정의됨.
이 모듈은 서비스 레이어에서 직접 임포트할 수 있는 진입점 역할.

규칙 (D3):
  - current_stage 갱신 = record_stage_event() 경유 (SSOT)
  - 직접 Content.status 수동 변경 금지 (cutover 이후)
  - 예외: staging/review 단계에서 승인/반려 액션은 service.py 유지
"""

from api.programming.metadata.stage_events import (  # noqa: F401  re-export
    derive_status_from_stage,
    record_stage_event,
)
