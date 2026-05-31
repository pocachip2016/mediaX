"""
reference_extract — Wikidata/Wikipedia RAG 기반 빈 필드 보강 (Step 3)

content_id 를 받아 Wikidata 구조화 fact + Wikipedia intro 텍스트를 조회하고
ExternalMetaSource(wikidata/wikipedia)로 upsert 후 결과를 반환.

Wikipedia 텍스트는 CC BY-SA → 직접 synopsis 저장 금지.
호출부(FE 또는 LLM step)에서 요약 후 반영.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from api.meta_core.clients.wikidata_client import WikidataClient
from api.meta_core.clients.wikipedia_client import WikipediaClient
from api.programming.metadata.models.content import Content
from api.programming.metadata.models.external import ExternalMetaSource, ExternalSourceType

logger = logging.getLogger(__name__)


@dataclass
class ReferenceExtractResult:
    content_id: int
    title_used: str
    year_used: int | None
    wikidata_facts: dict = field(default_factory=dict)
    wikidata_url: str | None = None
    wikipedia_text: str | None = None
    wikipedia_url: str | None = None
    wikipedia_lang: str | None = None
    sources_hit: list[str] = field(default_factory=list)
    sources_skipped: list[str] = field(default_factory=list)


def reference_extract(content_id: int, db: Session) -> ReferenceExtractResult:
    """Wikidata + Wikipedia를 조회해 ExternalMetaSource에 upsert.

    wikipedia 텍스트는 raw_json["text"]에만 저장(synopsis 직접 쓰기 금지).
    """
    content = db.query(Content).filter(Content.id == content_id, Content.is_deleted.is_(False)).first()
    if not content:
        raise ValueError(f"Content {content_id} not found")

    title = content.title or ""
    year: int | None = content.production_year

    result = ReferenceExtractResult(
        content_id=content_id,
        title_used=title,
        year_used=year,
    )

    if not title:
        logger.warning("[reference_extract] content_id=%d 제목 없음 — skip", content_id)
        result.sources_skipped = ["wikidata", "wikipedia"]
        return result

    # ── Wikidata ──────────────────────────────────────────────────────────────
    try:
        wd_client = WikidataClient()
        facts = wd_client.fetch_facts(title, year=year)
        if facts:
            wd_url = facts.pop("_url", None)
            result.wikidata_facts = facts
            result.wikidata_url = wd_url
            _upsert_source(
                db, content_id, ExternalSourceType.wikidata,
                external_id=wd_url or title,
                raw_json={"facts": facts, "url": wd_url},
            )
            result.sources_hit.append("wikidata")
        else:
            result.sources_skipped.append("wikidata")
    except Exception as exc:
        logger.warning("[reference_extract] wikidata 실패 content_id=%d: %s", content_id, exc)
        result.sources_skipped.append("wikidata")

    # ── Wikipedia ─────────────────────────────────────────────────────────────
    try:
        wp_client = WikipediaClient()
        wp = wp_client.fetch(title)
        if wp:
            result.wikipedia_text = wp["text"]
            result.wikipedia_url = wp["url"]
            result.wikipedia_lang = wp.get("lang")
            _upsert_source(
                db, content_id, ExternalSourceType.wikipedia,
                external_id=wp["url"],
                raw_json={"text": wp["text"], "url": wp["url"], "lang": wp.get("lang")},
            )
            result.sources_hit.append("wikipedia")
        else:
            result.sources_skipped.append("wikipedia")
    except Exception as exc:
        logger.warning("[reference_extract] wikipedia 실패 content_id=%d: %s", content_id, exc)
        result.sources_skipped.append("wikipedia")

    db.commit()
    return result


def _upsert_source(
    db: Session,
    content_id: int,
    source_type: ExternalSourceType,
    external_id: str,
    raw_json: dict,
) -> None:
    """ExternalMetaSource upsert — 동일 content_id + source_type 이면 raw_json 갱신."""
    existing = (
        db.query(ExternalMetaSource)
        .filter(
            ExternalMetaSource.content_id == content_id,
            ExternalMetaSource.source_type == source_type,
        )
        .first()
    )
    now = datetime.now(timezone.utc)
    if existing:
        existing.raw_json = raw_json
        existing.external_id = external_id
        existing.matched_at = now
    else:
        db.add(ExternalMetaSource(
            content_id=content_id,
            source_type=source_type,
            external_id=external_id,
            raw_json=raw_json,
            match_confidence=1.0,
            matched_at=now,
        ))
