"""
외부 큐레이션 섹션 영속화 — fetch_sections() + ott/matcher content_id resolve.

기존 ott/runner.py(popularity sync)와 같은 인프라를 재사용하되,
ExternalCuration + ExternalCurationItem 테이블에 upsert한다.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from .base import OttSource
from .matcher import match_content
from ..models import ExternalCuration, ExternalCurationItem

logger = logging.getLogger(__name__)


@dataclass
class CurationSyncSummary:
    channel: str
    sections: int = 0
    items_total: int = 0
    items_resolved: int = 0
    errors: list[str] = field(default_factory=list)


def run_curation_source(db: Session, source: OttSource) -> CurationSyncSummary:
    """source.fetch_sections() → ExternalCuration/Item upsert.

    섹션별 (channel, section_id) UNIQUE upsert — 최신 스냅샷만 유지.
    item은 섹션 교체 시 cascade delete 후 재삽입(rank 변동 반영).
    """
    summary = CurationSyncSummary(channel=source.channel)

    try:
        sections = source.fetch_sections()
    except Exception as exc:
        logger.exception("curation_runner: fetch_sections 실패 channel=%s", source.channel)
        summary.errors.append(str(exc))
        return summary

    for sec in sections:
        summary.sections += 1
        try:
            row = (
                db.query(ExternalCuration)
                .filter(
                    ExternalCuration.channel == source.channel,
                    ExternalCuration.section_id == sec.section_id,
                )
                .first()
            )
            if row is None:
                row = ExternalCuration(
                    channel=source.channel,
                    section_id=sec.section_id,
                    section_name=sec.name,
                    category_type=sec.category_type,
                    trend_type="ott",
                    total_count=len(sec.items),
                )
                db.add(row)
                db.flush()
            else:
                row.section_name = sec.name
                row.category_type = sec.category_type
                row.total_count = len(sec.items)
                # 기존 items 삭제 후 재삽입 (rank 변동 반영)
                db.query(ExternalCurationItem).filter(
                    ExternalCurationItem.external_curation_id == row.id
                ).delete()
                db.flush()

            resolved = 0
            for item in sec.items:
                summary.items_total += 1
                content_id = None
                try:
                    content_id = match_content(db, item)
                    if content_id is not None:
                        resolved += 1
                        summary.items_resolved += 1
                except Exception:
                    logger.warning(
                        "curation_runner: match_content 실패 title=%s", item.title
                    )

                db.add(ExternalCurationItem(
                    external_curation_id=row.id,
                    content_id=content_id,
                    external_title=item.title,
                    external_rank=item.rank,
                    production_year=item.production_year,
                ))

            row.matched_count = resolved
            db.commit()

        except Exception as exc:
            db.rollback()
            logger.exception(
                "curation_runner: 섹션 처리 실패 channel=%s section=%s",
                source.channel, sec.section_id,
            )
            summary.errors.append(f"{sec.section_id}: {exc}")

    return summary
