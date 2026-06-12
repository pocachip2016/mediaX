"""
Recommendations + AI Review Queue + Enrich Credits service.

service.py 분할 과정에서 추출 (dev-service-module-split Step 4).
"""

import os
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy.orm import Session, joinedload, selectinload

from api.programming.metadata.models import (
    Content, ContentMetadata, ContentImage,
    ExternalMetaSource, ExternalSourceType,
    ContentStatus, ContentType,
    ContentCredit,
)

logger = logging.getLogger(__name__)

# ── Resolution Service ─────────────────────────────────────

def _source_priority(source_type: str) -> int:
    """소스 우선순위 (높을수록 우선)"""
    return {
        "manual": 100,
        "tmdb": 80,
        "kobis": 70,
        "kmdb": 60,
        "watcha": 50,
        "naver": 40,
        "daum": 30,
        "netflix": 20,
        "bulk_upload": 15,
        "ai": 10,
        "other": 5,
    }.get(source_type, 0)


def _parse_source_fields(source_type: str, raw_json: dict) -> dict:
    """소스별 raw_json에서 표준 필드 추출"""
    fields: dict = {}

    if source_type == "tmdb":
        if raw_json.get("title"):
            fields["title"] = raw_json["title"]
        if raw_json.get("original_title"):
            fields["original_title"] = raw_json["original_title"]
        if raw_json.get("overview"):
            fields["synopsis"] = raw_json["overview"]
        if raw_json.get("genres"):
            fields["genres"] = [g["name"] for g in raw_json["genres"] if g.get("name")]
        credits = raw_json.get("credits", {})
        if credits.get("cast"):
            fields["cast"] = [
                {"name": p["name"], "character": p.get("character", "")}
                for p in credits["cast"][:15]
                if p.get("name")
            ]
        if credits.get("crew"):
            fields["directors"] = [
                p["name"] for p in credits["crew"]
                if p.get("job") == "Director" and p.get("name")
            ]
        if raw_json.get("production_countries"):
            countries = [c["name"] for c in raw_json["production_countries"] if c.get("name")]
            if countries:
                fields["country"] = countries[0]
        if raw_json.get("runtime"):
            fields["runtime"] = int(raw_json["runtime"])
        release = raw_json.get("release_date", "")
        if release and len(release) >= 4 and release[:4].isdigit():
            fields["production_year"] = int(release[:4])

    elif source_type == "kobis":
        movie_info = raw_json.get("movieInfoResult", {}).get("movieInfo", raw_json)
        if movie_info.get("movieNm"):
            fields["title"] = movie_info["movieNm"]
        if movie_info.get("showTm"):
            try:
                fields["runtime"] = int(movie_info["showTm"])
            except (ValueError, TypeError):
                pass
        nations = [n.get("nationNm") for n in movie_info.get("nations", []) if n.get("nationNm")]
        if nations:
            fields["country"] = nations[0]
        genres = [g.get("genreNm") for g in movie_info.get("genres", []) if g.get("genreNm")]
        if genres:
            fields["genres"] = genres
        directors = [d.get("peopleNm") for d in movie_info.get("directors", []) if d.get("peopleNm")]
        if directors:
            fields["directors"] = directors
        actors = [
            {"name": a.get("peopleNm"), "character": a.get("cast", "")}
            for a in movie_info.get("actors", [])[:15]
            if a.get("peopleNm")
        ]
        if actors:
            fields["cast"] = actors
        if movie_info.get("prdtYear"):
            try:
                fields["production_year"] = int(movie_info["prdtYear"])
            except (ValueError, TypeError):
                pass

    else:
        for key in ["title", "synopsis", "country", "rating_age", "poster_url", "original_title"]:
            if raw_json.get(key):
                fields[key] = raw_json[key]

        if raw_json.get("production_year"):
            try:
                fields["production_year"] = int(raw_json["production_year"])
            except (ValueError, TypeError):
                pass

        if raw_json.get("runtime"):
            runtime_raw = raw_json["runtime"]
            if isinstance(runtime_raw, (int, float)):
                fields["runtime"] = int(runtime_raw)
            elif isinstance(runtime_raw, str):
                cleaned = runtime_raw.replace("분", "").strip()
                if cleaned.isdigit():
                    fields["runtime"] = int(cleaned)

        cast_raw = raw_json.get("cast")
        if cast_raw:
            if isinstance(cast_raw, list):
                fields["cast"] = [
                    {"name": c["name"] if isinstance(c, dict) else c,
                     "character": c.get("character", "") if isinstance(c, dict) else ""}
                    for c in cast_raw if c
                ]
            elif isinstance(cast_raw, str):
                fields["cast"] = [{"name": n.strip(), "character": ""} for n in cast_raw.split(",") if n.strip()]

        dirs_raw = raw_json.get("directors")
        if dirs_raw:
            if isinstance(dirs_raw, list):
                fields["directors"] = [d if isinstance(d, str) else d.get("name", "") for d in dirs_raw if d]
            elif isinstance(dirs_raw, str):
                fields["directors"] = [n.strip() for n in dirs_raw.split(",") if n.strip()]

        genres_raw = raw_json.get("genres")
        if genres_raw:
            if isinstance(genres_raw, list):
                fields["genres"] = [g if isinstance(g, str) else g.get("name", "") for g in genres_raw if g]
            elif isinstance(genres_raw, str):
                fields["genres"] = [n.strip().rstrip("/") for n in genres_raw.split(",") if n.strip().strip("/")]

    return {k: v for k, v in fields.items() if v is not None and v != "" and v != []}


def _get_or_create_genre(db: Session, genre_name: str, source: str = "ai") -> Optional[object]:
    """장르명으로 GenreCode 조회 또는 생성"""
    from api.programming.metadata.models.taxonomy import GenreCode

    if not genre_name or not genre_name.strip():
        return None
    genre_name = genre_name.strip()

    existing = db.query(GenreCode).filter(GenreCode.name_ko == genre_name).first()
    if existing:
        return existing

    base_code = "GN_" + "".join(c for c in genre_name if c.isalnum())[:8].upper()
    code = base_code
    if db.query(GenreCode).filter(GenreCode.code == code).first():
        total = db.query(GenreCode).count()
        code = f"{base_code}_{total % 1000}"

    new_genre = GenreCode(code=code, name_ko=genre_name, is_active=True)
    db.add(new_genre)
    db.flush()
    return new_genre


def _get_or_create_person(db: Session, name_ko: str) -> Optional[object]:
    """인물명으로 PersonMaster 조회 또는 생성"""
    from api.programming.metadata.models.person import PersonMaster

    if not name_ko or not name_ko.strip():
        return None
    name_ko = name_ko.strip()

    existing = db.query(PersonMaster).filter(PersonMaster.name_ko == name_ko).first()
    if existing:
        return existing

    new_person = PersonMaster(name_ko=name_ko)
    db.add(new_person)
    db.flush()
    return new_person


def resolve_metadata(db: Session, content_id: int) -> dict:
    """
    content_id의 external_meta_sources를 우선순위 병합해
    Content, ContentMetadata, ContentCredits, ContentGenres에 적용.

    우선순위: manual(100) > tmdb(80) > kobis(70) > watcha(50) > bulk_upload(15) > ai(10)
    멱등: 여러 번 호출해도 같은 결과 (기존 credits/genres는 중복 추가 방지).
    """
    from api.programming.metadata.models.taxonomy import ContentGenre
    from api.programming.metadata.models.person import ContentCredit, CreditRole

    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        return {"error": f"Content {content_id} not found"}

    sources = (
        db.query(ExternalMetaSource)
        .filter(ExternalMetaSource.content_id == content_id)
        .order_by(ExternalMetaSource.matched_at.asc().nullsfirst(), ExternalMetaSource.id.asc())
        .all()
    )
    if not sources:
        return {"status": "no_sources", "content_id": content_id}

    winner: dict[str, dict] = {}
    for src in sources:
        src_name = src.source_type.value if hasattr(src.source_type, "value") else str(src.source_type)
        priority = _source_priority(src_name)
        try:
            fields = _parse_source_fields(src_name, src.raw_json or {})
        except Exception:
            continue
        for field, value in fields.items():
            if field not in winner or winner[field]["priority"] <= priority:
                winner[field] = {"value": value, "source": src_name, "priority": priority}

    if not winner:
        return {"status": "no_fields_extracted", "content_id": content_id}

    locked = set(content.locked_fields or [])

    for field, col_attr in [
        ("title", "title"),
        ("original_title", "original_title"),
        ("country", "country"),
    ]:
        if field in winner and field not in locked:
            setattr(content, col_attr, winner[field]["value"])

    if "production_year" in winner and "production_year" not in locked:
        content.production_year = winner["production_year"]["value"]

    if "runtime" in winner and "runtime" not in locked:
        content.runtime_minutes = winner["runtime"]["value"]

    db.add(content)

    meta = content.metadata_record
    if meta:
        if "synopsis" in winner and "synopsis" not in locked:
            src_name = winner["synopsis"]["source"]
            if src_name in ("manual", "cp", "bulk_upload"):
                meta.cp_synopsis = winner["synopsis"]["value"]
            else:
                meta.ai_synopsis = winner["synopsis"]["value"]

        meta.score_breakdown = {
            f: {"source": info["source"], "confidence": round(info["priority"] / 100, 2)}
            for f, info in winner.items()
        }
        db.add(meta)

    if "genres" in winner:
        genre_list = winner["genres"]["value"] or []
        src_name = winner["genres"]["source"]
        existing_genre_ids = {cg.genre_id for cg in (content.genres or [])}
        for i, genre_name in enumerate(genre_list):
            genre = _get_or_create_genre(db, genre_name, src_name)
            if genre and genre.id not in existing_genre_ids:
                db.add(ContentGenre(
                    content_id=content_id,
                    genre_id=genre.id,
                    is_primary=(i == 0),
                    source=src_name,
                ))
                existing_genre_ids.add(genre.id)

    existing_person_ids = {cc.person_id for cc in (content.credits or [])}

    if "directors" in winner:
        src_name = winner["directors"]["source"]
        for name in (winner["directors"]["value"] or []):
            person = _get_or_create_person(db, name)
            if person and person.id not in existing_person_ids:
                db.add(ContentCredit(
                    content_id=content_id,
                    person_id=person.id,
                    role=CreditRole.director,
                    source=src_name,
                ))
                existing_person_ids.add(person.id)

    if "cast" in winner:
        src_name = winner["cast"]["source"]
        for i, item in enumerate(winner["cast"]["value"] or []):
            name = item.get("name") if isinstance(item, dict) else item
            character = item.get("character", "") if isinstance(item, dict) else ""
            person = _get_or_create_person(db, name)
            if person and person.id not in existing_person_ids:
                db.add(ContentCredit(
                    content_id=content_id,
                    person_id=person.id,
                    role=CreditRole.actor,
                    character_name=character or None,
                    cast_order=i + 1,
                    source=src_name,
                ))
                existing_person_ids.add(person.id)

    db.flush()

    return {
        "status": "resolved",
        "content_id": content_id,
        "filled_fields": list(winner.keys()),
        "source_breakdown": {f: info["source"] for f, info in winner.items()},
    }


# ── 메타 보강 추천 ────────────────────────────────────────

_SOURCE_DEFAULT_CONFIDENCE = {
    "tmdb": 0.94,
    "kobis": 0.87,
    "kmdb": 0.82,
    "watcha": 1.0,
    "manual": 1.0,
    "bulk_upload": 0.15,
    "netflix": 0.80,
    "naver": 0.70,
    "daum": 0.70,
    "omdb": 0.75,
    "other": 0.50,
}

_CAST_ROLES = {"actor", "cast", "주연", "출연", "조연", "단역", "특별출연", "카메오"}
_DIRECTOR_ROLES = {"director", "감독", "연출"}

_STANDARD_RECOMMENDATION_FIELDS = [
    "genres", "cast", "director", "synopsis",
    "runtime", "country", "production_year", "cp_name",
]


def _names_from_list(v) -> str | None:
    """문자열 또는 list[str|dict] 에서 이름을 추출해 ", ".join."""
    if not v:
        return None
    if isinstance(v, str):
        return v
    names: list[str] = []
    for x in v:
        if isinstance(x, dict):
            n = x.get("peopleNm") or x.get("name") or x.get("name_ko") or x.get("name_en")
            if n:
                names.append(str(n))
        else:
            names.append(str(x))
    return ", ".join(names) if names else None


def _extract_field_from_raw(raw: dict, field: str) -> str | None:
    """raw_json에서 field에 해당하는 값을 문자열로 추출."""
    if field == "cast":
        raw_cast = raw.get("cast") or raw.get("actors")
        if isinstance(raw_cast, list):
            raw_cast = raw_cast[:5]
        return _names_from_list(raw_cast)
    if field == "director":
        return _names_from_list(raw.get("directors") or raw.get("director"))
    if field == "synopsis":
        return raw.get("synopsis") or raw.get("cp_synopsis") or raw.get("overview") or raw.get("story") or None
    if field == "runtime":
        v = raw.get("runtime") or raw.get("runtime_minutes")
        return str(v) if v else None
    if field == "country":
        # countries: MediSearch enrich 응답 키
        v = raw.get("country") or raw.get("countries") or raw.get("origin_country") or raw.get("nationAlt") or raw.get("repNationNm")
        if isinstance(v, list):
            return ", ".join(v)
        return str(v) if v else None
    if field == "genres":
        v = raw.get("genres") or raw.get("genreAlt")
        if not v:
            return None
        if isinstance(v, list):
            items = []
            for g in v:
                items.append(g["name"] if isinstance(g, dict) else str(g))
            return ", ".join(items)
        return str(v)
    if field == "production_year":
        v = raw.get("production_year") or raw.get("prdtYear")
        if not v:
            rd = str(raw.get("release_date") or raw.get("openDt") or "")
            digits = rd.replace("-", "")
            v = digits[:4] if len(digits) >= 4 else None
        return str(v) if v else None
    if field == "cp_name":
        v = raw.get("cp_name") or raw.get("studio")
        if not v:
            companys = raw.get("companys") or raw.get("production_companies")
            if isinstance(companys, list) and companys:
                first = companys[0]
                if isinstance(first, dict):
                    v = first.get("companyNm") or first.get("name")
                else:
                    v = str(first)
        return str(v) if v else None
    return None


def get_content_recommendations(db: Session, content_id: int):
    from api.programming.metadata.schemas import SourceFieldRec, FieldRecommendation, RecommendationsOut
    from api.programming.metadata.models.external import ContentAIResult, AITaskType

    content = (
        db.query(Content)
        .options(
            selectinload(Content.credits).joinedload(ContentCredit.person),
            selectinload(Content.genres),
            joinedload(Content.metadata_record),
        )
        .filter(Content.id == content_id)
        .first()
    )
    if not content:
        return RecommendationsOut(content_id=content_id, missing_fields=[], auto_fill=[], conflicts=[])

    meta = content.metadata_record

    missing: list[str] = []
    cast_credits = [c for c in content.credits if c.role.lower() in _CAST_ROLES]
    director_credits = [c for c in content.credits if c.role.lower() in _DIRECTOR_ROLES]
    synopsis_val = (meta.final_synopsis or meta.ai_synopsis or meta.cp_synopsis) if meta else None

    if not cast_credits:
        missing.append("cast")
    if not director_credits:
        missing.append("director")
    if not synopsis_val or not synopsis_val.strip():
        missing.append("synopsis")
    if not content.runtime_minutes:
        missing.append("runtime")
    if not content.country or not content.country.strip():
        missing.append("country")
    if not content.genres:
        missing.append("genres")

    from api.programming.metadata.models.external import ExternalSourceType
    ext_sources = [
        s for s in db.query(ExternalMetaSource)
            .filter(ExternalMetaSource.content_id == content_id)
            .all()
        if s.source_type not in (ExternalSourceType.manual, ExternalSourceType.bulk_upload)
    ]

    field_recs: dict[str, list[SourceFieldRec]] = {f: [] for f in _STANDARD_RECOMMENDATION_FIELDS}
    for src in ext_sources:
        raw = src.raw_json or {}
        conf = src.match_confidence or _SOURCE_DEFAULT_CONFIDENCE.get(src.source_type.value if hasattr(src.source_type, 'value') else str(src.source_type), 0.5)
        for field in _STANDARD_RECOMMENDATION_FIELDS:
            val = _extract_field_from_raw(raw, field)
            if val and val.strip():
                field_recs[field].append(SourceFieldRec(
                    source_type=src.source_type.value if hasattr(src.source_type, 'value') else str(src.source_type),
                    source_id=src.id,
                    value=val.strip(),
                    confidence=round(float(conf), 2),
                ))

    ai_synopsis_result = (
        db.query(ContentAIResult)
        .filter(
            ContentAIResult.content_id == content_id,
            ContentAIResult.task_type == AITaskType.synopsis,
            ContentAIResult.is_final == True,
        )
        .first()
    )
    ai_synopsis_rec: SourceFieldRec | None = None
    if ai_synopsis_result and ai_synopsis_result.result_json:
        ai_val = ai_synopsis_result.result_json.get("synopsis") or ai_synopsis_result.result_json.get("text")
        if ai_val:
            ai_synopsis_rec = SourceFieldRec(
                source_type="ai",
                source_id=ai_synopsis_result.id,
                value=str(ai_val).strip(),
                confidence=round(float(ai_synopsis_result.quality_score or 0.79), 2),
            )

    auto_fill: list[FieldRecommendation] = []
    conflicts: list[FieldRecommendation] = []

    for field, recs in field_recs.items():
        if not recs:
            continue
        synthesis = ai_synopsis_rec if field == "synopsis" else None
        unique_values = {r.value for r in recs}
        if len(recs) == 1 or len(unique_values) == 1:
            auto_fill.append(FieldRecommendation(
                field=field,
                status="auto",
                recommendations=recs,
                ai_synthesis=synthesis,
            ))
        else:
            conflicts.append(FieldRecommendation(
                field=field,
                status="conflict",
                recommendations=recs,
                ai_synthesis=synthesis,
            ))

    return RecommendationsOut(
        content_id=content_id,
        missing_fields=missing,
        auto_fill=auto_fill,
        conflicts=conflicts,
    )


# ── AI Review Queue 분류 헬퍼 ─────────────────────────────────────────────────

def _classify_input_type(external_sources: list[ExternalMetaSource]) -> str:
    types = {s.source_type for s in external_sources}
    if ExternalSourceType.bulk_upload in types:
        return "bulk"
    if ExternalSourceType.manual in types:
        return "manual"
    return "existing"


def _classify_metadata_status(rec) -> str:
    if rec.conflicts:
        return "conflict"
    if rec.missing_fields:
        return "missing"
    if rec.auto_fill:
        return "enhancement"
    return "clean"


def _classify_poster_status(images: list[ContentImage], dam_count: int) -> str:
    if not images:
        return "no_candidate"
    primary = next((img for img in images if img.is_primary), None)
    if primary and primary.source in {"cp", "manual"}:
        return "poster_ok"
    if primary and primary.source == "tmdb":
        return "external_only"
    if not primary and dam_count > 0:
        return "dam_match_found"
    return "needs_selection"


def _risk_level(metadata_status: str, poster_status: str, confidence: float) -> str:
    if metadata_status == "conflict" or poster_status == "no_candidate" or confidence < 0.5:
        return "high"
    if metadata_status == "missing":
        return "medium"
    return "low"


def _fetch_dam_count(content_id: int, dam_url: str) -> tuple[int, int]:
    """(content_id, dam_asset_count) 반환. 실패·타임아웃 시 (content_id, 0)."""
    try:
        resp = httpx.get(
            f"{dam_url}/api/mapping/by-content/{content_id}",
            timeout=2.0,
        )
        if resp.status_code == 200:
            return content_id, len(resp.json().get("assets", []))
        return content_id, 0
    except Exception:
        return content_id, 0


def _fetch_dam_counts(content_ids: list[int]) -> dict[int, int]:
    """DAM에서 content_id별 매칭 에셋 수를 병렬 조회 (max 5 동시)."""
    dam_url = os.environ.get("DAM_API_URL", "http://localhost:18000")
    results: dict[int, int] = {cid: 0 for cid in content_ids}
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(_fetch_dam_count, cid, dam_url): cid
            for cid in content_ids
        }
        for future in as_completed(futures):
            cid, count = future.result()
            results[cid] = count
    return results


def build_ai_review_queue(
    db: Session,
    *,
    status: str | None = None,
    input_type: str | None = None,
    metadata_status: str | None = None,
    poster_status: str | None = None,
    risk_level: str | None = None,
    include_dam: bool = False,
    page: int = 1,
    size: int = 50,
):
    from api.programming.metadata.schemas import (
        AiReviewQueueRow, AiReviewQueueSummary, PaginatedAiReviewQueue,
    )

    query = (
        db.query(Content)
        .options(
            selectinload(Content.images),
            selectinload(Content.external_sources),
        )
        .filter(Content.is_deleted == False)  # noqa: E712
    )
    if status:
        try:
            query = query.filter(Content.status == ContentStatus(status))
        except ValueError:
            pass

    contents = query.all()

    rows: list[AiReviewQueueRow] = []
    content_images_map: dict[int, list] = {}
    for content in contents:
        rec = get_content_recommendations(db, content.id)

        all_source_recs = [
            r
            for field in (rec.auto_fill + rec.conflicts)
            for r in field.recommendations
        ]
        confidence = (
            sum(r.confidence for r in all_source_recs) / len(all_source_recs)
            if all_source_recs
            else 1.0
        )

        it = _classify_input_type(content.external_sources)
        ms = _classify_metadata_status(rec)
        ps = _classify_poster_status(content.images, 0)
        rl = _risk_level(ms, ps, confidence)

        content_images_map[content.id] = list(content.images)
        rows.append(AiReviewQueueRow(
            content_id=content.id,
            title=content.title,
            content_type=content.content_type.value if content.content_type else "",
            input_type=it,
            content_status=content.status.value if content.status else "",
            metadata_status=ms,
            poster_status=ps,
            dam_match_count=0,
            risk_level=rl,
            confidence=round(confidence, 3),
            updated_at=content.updated_at or content.created_at or datetime.utcnow(),
        ))

    if input_type:
        rows = [r for r in rows if r.input_type == input_type]
    if metadata_status:
        rows = [r for r in rows if r.metadata_status == metadata_status]
    if poster_status:
        rows = [r for r in rows if r.poster_status == poster_status]
    if risk_level:
        rows = [r for r in rows if r.risk_level == risk_level]

    if include_dam and rows:
        dam_counts = _fetch_dam_counts([r.content_id for r in rows])
        updated = []
        for r in rows:
            dc = dam_counts.get(r.content_id, 0)
            ps = _classify_poster_status(content_images_map.get(r.content_id, []), dc)
            rl = _risk_level(r.metadata_status, ps, r.confidence)
            updated.append(r.model_copy(update={"dam_match_count": dc, "poster_status": ps, "risk_level": rl}))
        rows = updated

    summary = AiReviewQueueSummary(
        total=len(rows),
        missing=sum(1 for r in rows if r.metadata_status == "missing"),
        conflict=sum(1 for r in rows if r.metadata_status == "conflict"),
        needs_poster=sum(
            1 for r in rows
            if r.poster_status in {"needs_selection", "no_candidate", "external_only"}
        ),
        dam_match=sum(1 for r in rows if r.dam_match_count > 0),
        high_risk=sum(1 for r in rows if r.risk_level == "high"),
    )

    total = len(rows)
    start = (page - 1) * size
    return PaginatedAiReviewQueue(
        items=rows[start:start + size],
        summary=summary,
        total=total,
        page=page,
        size=size,
    )


# ── Enrich External Credits ──────────────────────────────────────────────────

async def _enrich_tmdb_source(
    src: ExternalMetaSource, content: Content, db: Session, api_key: str
) -> str:
    from api.programming.metadata.models import TmdbMovieCache, TmdbTvCache
    from api.programming.metadata.tmdb_client import TmdbClient
    from workers.tasks.tmdb_cache import _upsert_movie, _upsert_tv

    if not src.external_id:
        return "no_id"
    try:
        tmdb_id = int(src.external_id)
    except (ValueError, TypeError):
        return "no_id"

    is_movie = content.content_type == ContentType.movie
    cached = db.get(TmdbMovieCache if is_movie else TmdbTvCache, tmdb_id)

    detail: dict | None = None
    if cached and isinstance(cached.raw_json, dict) and cached.raw_json.get("credits"):
        detail = cached.raw_json
    else:
        try:
            async with TmdbClient(api_key=api_key) as client:
                if is_movie:
                    detail = await client.detail_movie(tmdb_id)
                    _upsert_movie(db, detail)
                else:
                    detail = await client.detail_tv(tmdb_id)
                    _upsert_tv(db, detail)
            db.flush()
        except Exception as exc:
            logger.warning("[enrich_tmdb] error tmdb_id=%s: %s", tmdb_id, exc)
            return "error"

    if not detail:
        return "error"

    credits = detail.get("credits", {})
    raw = dict(src.raw_json or {})
    if "cast" not in raw and credits.get("cast"):
        raw["cast"] = credits["cast"]
    if "crew" not in raw and credits.get("crew"):
        raw["crew"] = credits["crew"]
    if "genres" not in raw and detail.get("genres"):
        raw["genres"] = detail["genres"]
    if "runtime" not in raw:
        rt = detail.get("runtime") or next(iter(detail.get("episode_run_time") or []), None)
        if rt:
            raw["runtime"] = rt
    src.raw_json = raw
    db.flush()
    return "ok"


def _enrich_kobis_source(
    src: ExternalMetaSource, db: Session, api_key: str
) -> str:
    from api.meta_core.clients.kobis_client import KobisClient, KobisApiKeyMissing

    if not src.external_id:
        return "no_id"
    try:
        client = KobisClient(api_key=api_key)
        info = client.movie_info(src.external_id)
    except KobisApiKeyMissing:
        return "no_key"
    except Exception as exc:
        logger.warning("[enrich_kobis] error external_id=%s: %s", src.external_id, exc)
        return "error"

    if not info:
        return "no_id"

    raw = dict(src.raw_json or {})
    if "actors" not in raw and info.get("actors"):
        raw["actors"] = info["actors"]
    if "directors" not in raw and info.get("directors"):
        raw["directors"] = info["directors"]
    if "companys" not in raw and info.get("companys"):
        raw["companys"] = info["companys"]
    if "runtime" not in raw and info.get("showTm"):
        raw["runtime"] = info["showTm"]
    src.raw_json = raw
    db.flush()
    return "ok"


async def enrich_external_credits(content_id: int, db: Session) -> dict:
    """외부 소스(TMDB/KOBIS)에서 credits 보강."""
    content = (
        db.query(Content)
        .options(selectinload(Content.external_sources))
        .filter(Content.id == content_id)
        .first()
    )
    if not content:
        return {"error": f"Content {content_id} not found"}

    tmdb_key = os.getenv("TMDB_API_KEY", "")
    kobis_key = os.getenv("KOBIS_API_KEY", "")
    result: dict[str, str] = {}

    for src in (content.external_sources or []):
        st = src.source_type
        if st == ExternalSourceType.tmdb:
            result["tmdb"] = (
                "no_key" if not tmdb_key
                else await _enrich_tmdb_source(src, content, db, tmdb_key)
            )
        elif st == ExternalSourceType.kobis:
            result["kobis"] = (
                "no_key" if not kobis_key
                else _enrich_kobis_source(src, db, kobis_key)
            )

    db.commit()
    return result
