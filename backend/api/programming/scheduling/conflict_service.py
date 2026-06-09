"""conflict_service.py — 자동편성 노출 충돌 탐지 (ADR-012 P5).

NodeSet 내 active content 링크를 대상으로 두 종류의 충돌을 탐지한다:
- window_overlap: 동일 content_id 가 겹치는 노출 window 에 2회+ 편성 → 동시 노출 중복(발행 차단 대상)
- duplicate_content: 동일 content_id 가 겹치지 않는 window 로 2회+ 편성 → 중복 편성 dedup 후보(권고)

read-time 순수 함수 — 저장하지 않는다. P5 단계 평가 + P6 발행 가드 + 콘솔 충돌 패널 공용.
"""
from __future__ import annotations

from datetime import date
from typing import Optional, TypedDict

from sqlalchemy.orm import Session

from .models import LinkStatus, ProgrammingLink, ProgrammingNode


class ConflictItem(TypedDict):
    type: str             # "window_overlap" | "duplicate_content"
    content_id: int
    link_ids: list[int]
    node_ids: list[int]
    detail: str


class ConflictReport(TypedDict):
    set_id: int
    conflict_count: int           # 전체 충돌 항목 수 (양 종류 합)
    blocking_count: int           # 발행 차단 대상 수 (= window_overlap_count)
    window_overlap_count: int
    duplicate_content_count: int
    conflicts: list[ConflictItem]


def _overlaps(
    s1: Optional[date], e1: Optional[date],
    s2: Optional[date], e2: Optional[date],
) -> bool:
    """두 노출 window 가 겹치는가.

    None start = -∞, None end = +∞ (상시 노출). 표준 구간 겹침: s1 ≤ e2 AND s2 ≤ e1.
    """
    if e1 is not None and s2 is not None and s2 > e1:
        return False
    if e2 is not None and s1 is not None and s1 > e2:
        return False
    return True


def detect_conflicts(db: Session, set_id: int) -> ConflictReport:
    """set_id 의 active content 링크 충돌 리포트.

    동일 content_id 의 active 링크 쌍을 검사:
      - 겹치는 window → window_overlap (blocking)
      - 안 겹치는 window → duplicate_content (advisory)
    멱등/read-time — DB 변경 없음.
    """
    rows = (
        db.query(ProgrammingLink, ProgrammingNode.id)
        .join(ProgrammingNode, ProgrammingLink.parent_node_id == ProgrammingNode.id)
        .filter(
            ProgrammingNode.set_id == set_id,
            ProgrammingLink.status == LinkStatus.active,
            ProgrammingLink.child_content_id.isnot(None),
        )
        .all()
    )

    # content_id → [(link_id, node_id, window_start, window_end), …]
    by_content: dict[int, list[tuple[int, int, Optional[date], Optional[date]]]] = {}
    for link, node_id in rows:
        by_content.setdefault(link.child_content_id, []).append(
            (link.id, node_id, link.window_start, link.window_end)
        )

    conflicts: list[ConflictItem] = []
    window_overlap = 0
    duplicate = 0

    for content_id, entries in by_content.items():
        if len(entries) < 2:
            continue
        for i in range(len(entries)):
            for j in range(i + 1, len(entries)):
                li, ni, ws1, we1 = entries[i]
                lj, nj, ws2, we2 = entries[j]
                node_ids = sorted({ni, nj})
                if _overlaps(ws1, we1, ws2, we2):
                    window_overlap += 1
                    conflicts.append(ConflictItem(
                        type="window_overlap",
                        content_id=content_id,
                        link_ids=[li, lj],
                        node_ids=node_ids,
                        detail=f"콘텐츠 {content_id} 노출 window 겹침 (링크 {li}↔{lj})",
                    ))
                else:
                    duplicate += 1
                    conflicts.append(ConflictItem(
                        type="duplicate_content",
                        content_id=content_id,
                        link_ids=[li, lj],
                        node_ids=node_ids,
                        detail=f"콘텐츠 {content_id} 중복 편성 (링크 {li}, {lj} — window 분리)",
                    ))

    return ConflictReport(
        set_id=set_id,
        conflict_count=len(conflicts),
        blocking_count=window_overlap,
        window_overlap_count=window_overlap,
        duplicate_content_count=duplicate,
        conflicts=conflicts,
    )
