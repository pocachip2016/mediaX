"""suggest_service.py — Tier2 매칭 결과를 suggested 링크로 저장 + 확정/반려.

설계 원칙:
  - 멱등: 동일 (node, content) 쌍이 이미 suggested 링크로 존재하면 confidence/reason 갱신.
  - 임계 자동제외: confidence < threshold 인 후보는 저장하지 않음.
  - reason 저장: copy_override["_ai_reason"] 에 기록 (별도 컬럼 불필요).
  - read-time 가드: compute_members 에서 suggested 제외는 node_service 담당(기존 구현).
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from .link_service import add_link
from .match_service import match_node_to_contents
from .models import ChildType, LinkSource, LinkStatus, ProgrammingLink, ProgrammingNode


@dataclass
class SuggestResult:
    saved: list[ProgrammingLink]
    skipped_count: int   # threshold 미달로 제외된 수


def suggest_links(
    db: Session,
    node: ProgrammingNode,
    *,
    threshold: float = 0.3,
    limit: int = 50,
) -> SuggestResult:
    """Tier2 매칭 후 suggested 링크 upsert.

    threshold 미만 → 저장 제외.
    기존 suggested 링크(same parent+child) → confidence/reason 갱신(멱등).
    이미 active/rejected 인 링크 → 건드리지 않음.
    """
    match_results = match_node_to_contents(db, node, limit=limit)

    saved: list[ProgrammingLink] = []
    skipped = 0

    for mr in match_results:
        if mr.confidence < threshold:
            skipped += 1
            continue

        # 기존 링크 탐색 (status 무관 — active/rejected 포함)
        existing = (
            db.query(ProgrammingLink)
            .filter(
                ProgrammingLink.parent_node_id == node.id,
                ProgrammingLink.child_content_id == mr.content_id,
                ProgrammingLink.child_type == ChildType.content,
            )
            .first()
        )

        if existing is not None:
            if existing.status == LinkStatus.suggested:
                # 멱등 갱신
                existing.confidence = mr.confidence
                existing.copy_override = {
                    **(existing.copy_override or {}),
                    "_ai_reason": mr.reason,
                }
                db.flush()
                saved.append(existing)
            # active/rejected 는 건드리지 않음
            continue

        lnk = add_link(
            db,
            node.id,
            child_content_id=mr.content_id,
            source=LinkSource.ai,
            confidence=mr.confidence,
            status=LinkStatus.suggested,
            copy_override={"_ai_reason": mr.reason},
        )
        saved.append(lnk)

    return SuggestResult(saved=saved, skipped_count=skipped)


def confirm_link(db: Session, link_id: int) -> ProgrammingLink:
    """suggested → active."""
    lnk = db.query(ProgrammingLink).filter(ProgrammingLink.id == link_id).first()
    if lnk is None:
        raise ValueError(f"link {link_id} not found")
    if lnk.status != LinkStatus.suggested:
        raise ValueError(
            f"link {link_id} status={lnk.status.value!r} — confirmed 는 suggested 링크에만 가능"
        )
    lnk.status = LinkStatus.active
    db.flush()
    return lnk


def reject_link(db: Session, link_id: int) -> ProgrammingLink:
    """suggested → rejected."""
    lnk = db.query(ProgrammingLink).filter(ProgrammingLink.id == link_id).first()
    if lnk is None:
        raise ValueError(f"link {link_id} not found")
    if lnk.status != LinkStatus.suggested:
        raise ValueError(
            f"link {link_id} status={lnk.status.value!r} — reject 는 suggested 링크에만 가능"
        )
    lnk.status = LinkStatus.rejected
    db.flush()
    return lnk
