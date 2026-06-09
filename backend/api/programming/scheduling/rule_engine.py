"""Tier 0 규칙 필터 엔진 — rule_query(JSON) → 설명가능 콘텐츠 후보.

rule_query 지원 필드:
  genre       : str | list[str]  — GenreCode.code 기준 (예: "ACT", ["DRM", "ROM"])
  year_gte    : int              — production_year >= N
  year_lte    : int              — production_year <= N
  country     : str              — 국가 부분 일치 (ilike)
  content_type: str              — "movie" | "series" | "season" | "episode"
  tags        : str | list[str]  — TagCode.name 기준 (AND가 아닌 OR 포함)
  approved_only: bool            — True이면 status=approved 콘텐츠만 (기본 False)
  limit       : int              — 최대 반환 수 (기본 200)

설계 원칙:
  - 결과는 read-time 계산, DB에 링크로 저장하지 않는다.
  - 각 결과에 reason 문자열 첨부(어떤 규칙에 걸렸는지 설명가능성 보장).
  - 필터 없는 빈 rule_query는 approved 콘텐츠 전체를 반환한다.
"""
from dataclasses import dataclass, field

from sqlalchemy import distinct
from sqlalchemy.orm import Session

from api.programming.metadata.models.content import Content, ContentStatus, ContentType
from api.programming.metadata.models.taxonomy import ContentGenre, ContentTag, GenreCode, TagCode


@dataclass
class RuleResult:
    content_id: int
    reason: str


def apply_rule_query(
    db: Session,
    rule_query: dict,
    limit: int = 200,
) -> list[RuleResult]:
    """rule_query 딕셔너리를 실행해 매칭 콘텐츠 목록 + reason을 반환한다."""

    genre = rule_query.get("genre")
    year_gte = rule_query.get("year_gte")
    year_lte = rule_query.get("year_lte")
    country = rule_query.get("country")
    content_type = rule_query.get("content_type")
    tags = rule_query.get("tags")
    approved_only = rule_query.get("approved_only", False)
    query_limit = rule_query.get("limit", limit)

    # reason 구성에 사용할 규칙 설명 목록
    applied_rules: list[str] = []

    q = db.query(distinct(Content.id), Content).filter(Content.id == Content.id)

    # ── genre 필터 ─────────────────────────────────────────────────────────────
    if genre:
        genre_list = [genre] if isinstance(genre, str) else list(genre)
        q = (
            q.join(ContentGenre, ContentGenre.content_id == Content.id)
            .join(GenreCode, GenreCode.id == ContentGenre.genre_id)
            .filter(GenreCode.code.in_(genre_list))
        )
        applied_rules.append(f"genre∈{genre_list}")

    # ── tag 필터 ──────────────────────────────────────────────────────────────
    if tags:
        tag_list = [tags] if isinstance(tags, str) else list(tags)
        tag_subq = (
            db.query(distinct(ContentTag.content_id))
            .join(TagCode, TagCode.id == ContentTag.tag_id)
            .filter(TagCode.name.in_(tag_list))
            .scalar_subquery()
        )
        q = q.filter(Content.id.in_(tag_subq))
        applied_rules.append(f"tags∈{tag_list}")

    # ── year 필터 ─────────────────────────────────────────────────────────────
    if year_gte is not None:
        q = q.filter(Content.production_year >= int(year_gte))
        applied_rules.append(f"year≥{year_gte}")
    if year_lte is not None:
        q = q.filter(Content.production_year <= int(year_lte))
        applied_rules.append(f"year≤{year_lte}")

    # ── country 필터 ──────────────────────────────────────────────────────────
    if country:
        q = q.filter(Content.country.ilike(f"%{country}%"))
        applied_rules.append(f"country≈{country}")

    # ── content_type 필터 ─────────────────────────────────────────────────────
    if content_type:
        try:
            ct_enum = ContentType(content_type)
            q = q.filter(Content.content_type == ct_enum)
            applied_rules.append(f"type={content_type}")
        except ValueError:
            pass  # 알 수 없는 타입은 무시

    # ── approved_only 필터 ────────────────────────────────────────────────────
    if approved_only:
        q = q.filter(Content.status == ContentStatus.approved)
        applied_rules.append("approved_only")

    reason = "rule:" + (", ".join(applied_rules) if applied_rules else "all")

    rows = q.limit(int(query_limit)).all()
    return [RuleResult(content_id=row[0], reason=reason) for row in rows]
