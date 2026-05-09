"""
Gap Analyzer — 콘텐츠별 누락 필드 탐지

analyze_gap(content_id, db) → GapReport
analyze_gap_batch(db, **filters) → list[GapReport]

외부 API 호출 없음. 내부 DB 만 조회.
다음 step(enrich) 의 입력으로 사용됨.
참조: docs/dev/meta-intelligence.md §2
"""

from dataclasses import dataclass, field
from sqlalchemy.orm import Session

from api.programming.metadata.models.content import Content, ContentMetadata
from api.programming.metadata.models.external import ExternalMetaSource
from api.programming.metadata.models.image import ContentImage, ImageType
from api.programming.metadata.models.person import ContentCredit, CreditRole
from api.programming.metadata.models.taxonomy import ContentGenre

# 소스 추천 (필드 → 우선 소스 목록)
_SOURCE_MAP: dict[str, list[str]] = {
    "external_id": ["tmdb", "kobis", "kmdb"],
    "poster":      ["tmdb", "kmdb"],
    "synopsis":    ["tmdb", "kmdb", "websearch"],
    "cast":        ["tmdb", "kmdb", "kobis"],
    "director":    ["tmdb", "kmdb", "kobis"],
    "primary_genre": ["tmdb", "kobis"],
}

# 필드별 우선순위 (1=긴급 ~ 3=낮음)
_PRIORITY: dict[str, int] = {
    "external_id":    1,
    "poster":         1,
    "synopsis":       2,
    "cast":           2,
    "director":       2,
    "primary_genre":  3,
}

SYNOPSIS_MIN_LEN = 50  # 이 미만이면 "too_short"


@dataclass
class FieldGap:
    field_name: str
    reason: str                    # "empty" | "too_short" | "no_primary" | "no_match"
    recommended_sources: list[str]
    priority: int                  # 1(긴급) ~ 3(낮음)


@dataclass
class GapReport:
    content_id: int
    title: str
    content_type: str
    missing_fields: list[FieldGap] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return len(self.missing_fields) == 0

    @property
    def min_priority(self) -> int:
        """가장 긴급한 필드의 priority (낮을수록 먼저 처리)."""
        if not self.missing_fields:
            return 99
        return min(f.priority for f in self.missing_fields)


def _gap(field_name: str, reason: str) -> FieldGap:
    return FieldGap(
        field_name=field_name,
        reason=reason,
        recommended_sources=_SOURCE_MAP[field_name],
        priority=_PRIORITY[field_name],
    )


def analyze_gap(content_id: int, db: Session) -> GapReport:
    """콘텐츠 1건의 누락 필드를 분석해 GapReport 반환."""
    content = db.query(Content).filter(Content.id == content_id).first()
    if content is None:
        raise ValueError(f"Content {content_id} not found")

    meta: ContentMetadata | None = (
        db.query(ContentMetadata)
        .filter(ContentMetadata.content_id == content_id)
        .first()
    )
    gaps: list[FieldGap] = []

    # 1. external_id — ExternalMetaSource 가 없으면 갭
    ext_count = (
        db.query(ExternalMetaSource)
        .filter(ExternalMetaSource.content_id == content_id)
        .count()
    )
    if ext_count == 0:
        gaps.append(_gap("external_id", "no_match"))

    # 2. poster — is_primary=True 포스터가 없으면 갭
    has_poster = (
        db.query(ContentImage)
        .filter(
            ContentImage.content_id == content_id,
            ContentImage.image_type == ImageType.poster,
            ContentImage.is_primary.is_(True),
        )
        .first()
    ) is not None
    if not has_poster:
        gaps.append(_gap("poster", "no_primary"))

    # 3. synopsis — cp_synopsis + ai_synopsis 모두 50자 미만이면 갭
    cp_syn = (meta.cp_synopsis or "") if meta else ""
    ai_syn = (meta.ai_synopsis or "") if meta else ""
    if len(cp_syn) < SYNOPSIS_MIN_LEN and len(ai_syn) < SYNOPSIS_MIN_LEN:
        reason = "too_short" if (cp_syn or ai_syn) else "empty"
        gaps.append(_gap("synopsis", reason))

    # 4. cast — ContentCredit(actor) 없고 cp_cast JSON도 비어있으면 갭
    actor_count = (
        db.query(ContentCredit)
        .filter(
            ContentCredit.content_id == content_id,
            ContentCredit.role == CreditRole.actor,
        )
        .count()
    )
    if actor_count == 0:
        cp_cast = (meta.cp_cast or []) if meta else []
        if not cp_cast:
            gaps.append(_gap("cast", "empty"))

    # 5. director — ContentCredit(director) 없으면 갭
    dir_count = (
        db.query(ContentCredit)
        .filter(
            ContentCredit.content_id == content_id,
            ContentCredit.role == CreditRole.director,
        )
        .count()
    )
    if dir_count == 0:
        gaps.append(_gap("director", "empty"))

    # 6. primary_genre — is_primary=True 장르가 없으면 갭
    has_primary_genre = (
        db.query(ContentGenre)
        .filter(
            ContentGenre.content_id == content_id,
            ContentGenre.is_primary.is_(True),
        )
        .first()
    ) is not None
    if not has_primary_genre:
        gaps.append(_gap("primary_genre", "no_primary"))

    return GapReport(
        content_id=content_id,
        title=content.title,
        content_type=content.content_type.value if content.content_type else "unknown",
        missing_fields=gaps,
    )


def analyze_gap_batch(
    db: Session,
    *,
    status: str | None = None,
    content_type: str | None = None,
    limit: int = 100,
) -> list[GapReport]:
    """여러 콘텐츠의 갭을 일괄 분석. 대시보드 및 enrich 스케줄링용."""
    q = db.query(Content)
    if status:
        q = q.filter(Content.status == status)
    if content_type:
        q = q.filter(Content.content_type == content_type)
    contents = q.limit(limit).all()
    return [analyze_gap(c.id, db) for c in contents]
