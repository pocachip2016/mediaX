"""
1.1 메타데이터 Celery 태스크

태스크 목록:
  - process_content_metadata    : 콘텐츠 AI 처리 (장르/시놉시스/태그/스코어)
  - enrich_content_metadata     : 에이전틱 멀티소스 검색 (TMDB 시리즈 재귀 + ExternalMetaSource 저장)
  - poll_cp_emails               : CP 이메일 폴링 (5분 주기 Beat)
  - sync_kobis                   : 영진위 KOBIS 일일 동기화
  - sync_tmdb                    : TMDB 주간 동기화
  - reeval_quality_scores        : 메타 품질 재평가 배치
  - check_missing_episodes       : 시리즈 누락 에피소드 체크 (매일 04:00)
  - retry_failed_enrichments     : 실패 항목 재시도 (6시간)
"""

import asyncio
import imaplib
import email
import logging
import httpx
from email.header import decode_header
from datetime import datetime, timedelta

from workers.celery_app import celery_app
from shared.database import SessionLocal
from shared.config import settings

logger = logging.getLogger(__name__)


# ── AI 처리 ───────────────────────────────────────────────

@celery_app.task(bind=True, name="workers.tasks.metadata.process_content_metadata",
                 max_retries=3, default_retry_delay=60)
def process_content_metadata(self, content_id: int):
    """
    콘텐츠 AI 처리 태스크
    - Ollama llama3.2:3b 호출 → 시놉시스/장르/태그 생성
    - 외부 메타 조회 (KOBIS + TMDB)
    - 품질 스코어 산정 → status 자동 설정
    """
    db = SessionLocal()
    try:
        from api.programming.metadata.ai_engine import process_content_ai
        asyncio.run(process_content_ai(content_id, db))
        logger.info(f"[metadata] content_id={content_id} AI 처리 완료")
    except Exception as exc:
        logger.error(f"[metadata] content_id={content_id} 처리 실패: {exc}")
        raise self.retry(exc=exc)
    finally:
        db.close()


# ── CP 이메일 폴링 ─────────────────────────────────────────

@celery_app.task(name="workers.tasks.metadata.poll_cp_emails")
def poll_cp_emails():
    """
    CP사 이메일 폴링 (Celery Beat 5분 주기)
    - IMAP으로 미처리 이메일 수신
    - Ollama로 엔티티 추출 (제목/연도/CP사/수량)
    - CpEmailLog + Content(waiting) DB 저장
    """
    imap_host = getattr(settings, "IMAP_HOST", "")
    imap_user = getattr(settings, "IMAP_USER", "")
    imap_pass = getattr(settings, "IMAP_PASS", "")

    if not all([imap_host, imap_user, imap_pass]):
        logger.warning("[email] IMAP 설정이 없습니다. 스킵합니다.")
        return {"skipped": True, "reason": "IMAP 설정 없음"}

    db = SessionLocal()
    processed_count = 0
    try:
        mail = imaplib.IMAP4_SSL(imap_host)
        mail.login(imap_user, imap_pass)
        mail.select("INBOX")

        # 미처리(UNSEEN) CP 메일 검색 — 발신자 필터는 settings에서 관리
        _, msg_ids = mail.search(None, "UNSEEN")
        for msg_id in msg_ids[0].split():
            _, msg_data = mail.fetch(msg_id, "(RFC822)")
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            subject = _decode_header_value(msg.get("Subject", ""))
            sender = msg.get("From", "")
            message_id = msg.get("Message-ID", "")
            body = _extract_body(msg)

            _save_email_and_extract(db, message_id, subject, sender, body)
            mail.store(msg_id, "+FLAGS", "\\Seen")
            processed_count += 1

        mail.logout()
        logger.info(f"[email] {processed_count}건 처리 완료")
        return {"processed": processed_count}
    except Exception as exc:
        logger.error(f"[email] 폴링 실패: {exc}")
        return {"error": str(exc)}
    finally:
        db.close()


def _save_email_and_extract(db, message_id: str, subject: str, sender: str, body: str):
    """이메일 저장 + Ollama 엔티티 추출 + Content(waiting) 생성"""
    from api.programming.metadata.models import CpEmailLog, Content, ContentStatus, ContentType
    from api.programming.metadata.models import ContentMetadata

    # 중복 체크
    existing = db.query(CpEmailLog).filter(CpEmailLog.message_id == message_id).first()
    if existing:
        return

    # Ollama 엔티티 추출
    extracted = asyncio.run(_extract_entities_from_email(subject, body))

    log = CpEmailLog(
        message_id=message_id,
        subject=subject,
        sender=sender,
        cp_name=extracted.get("cp_name"),
        received_at=datetime.utcnow(),
        extracted_titles=extracted.get("titles", []),
        extracted_year=extracted.get("year"),
        extracted_quantity=extracted.get("quantity"),
        raw_body=body[:5000],
        extraction_confidence=extracted.get("confidence", 0.0),
    )
    db.add(log)
    db.flush()

    # 추출된 제목마다 Content(waiting) 생성
    for title in extracted.get("titles", []):
        content = Content(
            title=title,
            content_type=ContentType.movie,
            status=ContentStatus.waiting,
            cp_name=extracted.get("cp_name"),
            production_year=extracted.get("year"),
            cp_email_id=log.id,
        )
        db.add(content)
        db.flush()
        meta = ContentMetadata(content_id=content.id, quality_score=0.0)
        db.add(meta)

        # 즉시 AI 처리 큐에 등록
        process_content_metadata.delay(content.id)

    log.processed = True
    db.commit()


async def _extract_entities_from_email(subject: str, body: str) -> dict:
    """Ollama로 이메일 본문에서 엔티티 추출"""
    try:
        from api.programming.metadata.ai_engine import call_ollama
        prompt = f"""다음 CP사 이메일에서 콘텐츠 정보를 추출하세요.

제목: {subject}
본문: {body[:2000]}

JSON 형식으로만 응답:
```json
{{
  "cp_name": "CP사명",
  "titles": ["콘텐츠 제목1", "콘텐츠 제목2"],
  "year": 2024,
  "quantity": 1,
  "confidence": 0.9
}}
```"""
        raw = await call_ollama(prompt)
        import json, re
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception as e:
        logger.error(f"[email] 엔티티 추출 실패: {e}")
    return {"titles": [], "confidence": 0.0}


def _decode_header_value(value: str) -> str:
    parts = decode_header(value)
    result = []
    for part, charset in parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(part)
    return "".join(result)


def _extract_body(msg) -> str:
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                charset = part.get_content_charset() or "utf-8"
                body += part.get_payload(decode=True).decode(charset, errors="replace")
                break
    else:
        charset = msg.get_content_charset() or "utf-8"
        body = msg.get_payload(decode=True).decode(charset, errors="replace")
    return body


# ── 외부 메타 동기화 배치 ──────────────────────────────────

@celery_app.task(name="workers.tasks.metadata.sync_kobis")
def sync_kobis():
    """영진위 KOBIS 일일 동기화 (매일 03:00) — 전일 신규 영화 → DB 매핑 업데이트"""
    if not getattr(settings, "KOBIS_API_KEY", ""):
        logger.warning("[kobis] KOBIS_API_KEY 없음. 스킵.")
        return {"skipped": True}

    db = SessionLocal()
    updated = 0
    try:
        from api.programming.metadata.models import ContentMetadata
        yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y%m%d")
        params = {
            "key": settings.KOBIS_API_KEY,
            "openStartDt": yesterday,
            "openEndDt": yesterday,
            "itemPerPage": "100",
        }
        resp = httpx.get(
            "http://www.kobis.or.kr/kobisopenapi/webservice/rest/movie/searchMovieList.json",
            params=params,
            timeout=15.0,
        )
        movies = resp.json().get("movieListResult", {}).get("movieList", [])
        for movie in movies:
            movie_nm = movie.get("movieNm", "")
            movie_cd = movie.get("movieCd", "")
            if not movie_nm or not movie_cd:
                continue
            # 제목 매칭으로 기존 ContentMetadata 업데이트
            rows = (
                db.query(ContentMetadata)
                .join(ContentMetadata.content)
                .filter(ContentMetadata.kobis_movie_cd.is_(None))
                .all()
            )
            for meta in rows:
                if meta.content and meta.content.title == movie_nm:
                    meta.kobis_movie_cd = movie_cd
                    updated += 1
        db.commit()
        logger.info(f"[kobis] {updated}건 kobis_movie_cd 업데이트")
        return {"updated": updated, "total_from_kobis": len(movies)}
    except Exception as exc:
        logger.error(f"[kobis] 동기화 실패: {exc}")
        return {"error": str(exc)}
    finally:
        db.close()


@celery_app.task(name="workers.tasks.metadata.sync_tmdb")
def sync_tmdb():
    """TMDB 주간 동기화 (매주 월 02:00)"""
    logger.info("[tmdb] TMDB 동기화 시작")
    # TODO: 신규 콘텐츠·에피소드 추가분 조회
    return {"status": "ok"}


@celery_app.task(name="workers.tasks.metadata.reeval_quality_scores")
def reeval_quality_scores():
    """메타 품질 재평가 배치 (매일 01:00)"""
    db = SessionLocal()
    try:
        from api.programming.metadata.models import Content, ContentStatus
        # 아직 review 상태인 콘텐츠 재처리
        stale = (
            db.query(Content)
            .filter(Content.status == ContentStatus.review)
            .limit(100)
            .all()
        )
        for c in stale:
            process_content_metadata.delay(c.id)
        logger.info(f"[reeval] {len(stale)}건 재처리 큐 등록")
        return {"queued": len(stale)}
    finally:
        db.close()


# ── 에이전틱 멀티소스 검색 ─────────────────────────────────

@celery_app.task(bind=True, name="workers.tasks.metadata.enrich_content_metadata",
                 max_retries=3, default_retry_delay=120)
def enrich_content_metadata(self, content_id: int):
    """
    에이전틱 멀티소스 검색 태스크
    1. TMDB 검색 → 시리즈면 시즌/에피소드 재귀 수집
    2. KOBIS 검색
    3. ExternalMetaSource, ContentCredit, ContentImage 저장
    4. LLM으로 최종 메타 통합
    5. status → staging
    """
    db = SessionLocal()
    try:
        asyncio.run(_async_enrich_content(content_id, db))
        logger.info(f"[enrich] content_id={content_id} enrichment 완료")
    except Exception as exc:
        logger.error(f"[enrich] content_id={content_id} 실패: {exc}")
        raise self.retry(exc=exc)
    finally:
        db.close()


async def _async_enrich_content(content_id: int, db):
    """에이전틱 멀티소스 검색 비동기 로직"""
    from api.programming.metadata.models import (
        Content, ContentMetadata, ContentStatus, ContentType,
        ExternalMetaSource, ExternalSourceType,
        ContentImage, ImageType,
        ContentCredit, PersonMaster, CreditRole,
        ContentAIResult, AITaskType,
    )

    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise ValueError(f"Content {content_id} not found")

    tmdb_key = getattr(settings, "TMDB_API_KEY", "")
    kobis_key = getattr(settings, "KOBIS_API_KEY", "")

    tmdb_result = None
    kobis_result = None

    # ── TMDB 검색 ──────────────────────────────────────────
    if tmdb_key:
        tmdb_result = await _tmdb_search_and_save(content, db, tmdb_key)

    # ── KOBIS 검색 ─────────────────────────────────────────
    if kobis_key and content.content_type == ContentType.movie:
        kobis_result = await _kobis_search_and_save(content, db, kobis_key)

    # ── ContentMetadata 업데이트 ───────────────────────────
    meta = content.metadata_record
    if not meta:
        meta = ContentMetadata(content_id=content_id)
        db.add(meta)
        db.flush()

    if tmdb_result and tmdb_result.get("id"):
        meta.tmdb_id = tmdb_result["id"]
        meta.tmdb_data = tmdb_result
    if kobis_result and kobis_result.get("movieCd"):
        meta.kobis_movie_cd = kobis_result["movieCd"]
        meta.kobis_data = kobis_result

    # ── status → staging ──────────────────────────────────
    content.status = ContentStatus.staging

    # AI 결과 기록 (enrichment 태스크)
    db.query(ContentAIResult).filter(
        ContentAIResult.content_id == content_id,
        ContentAIResult.task_type == AITaskType.enrichment,
        ContentAIResult.is_final == True,  # noqa: E712
    ).update({"is_final": False})

    db.add(ContentAIResult(
        content_id=content_id,
        engine="tmdb+kobis",
        task_type=AITaskType.enrichment,
        result_json={
            "tmdb": tmdb_result,
            "kobis": kobis_result,
        },
        quality_score=meta.quality_score or 0.0,
        is_final=True,
        processed_at=datetime.utcnow(),
    ))

    db.commit()


async def _tmdb_search_and_save(content, db, api_key: str) -> dict | None:
    """TMDB 검색 → ExternalMetaSource, ContentImage, ContentCredit 저장"""
    from api.programming.metadata.models import (
        ContentType, ExternalMetaSource, ExternalSourceType,
        ContentImage, ImageType, ContentCredit, PersonMaster, CreditRole,
        Content, ContentStatus, ContentMetadata,
    )

    is_series = content.content_type in (ContentType.series,)

    # 영화/시리즈 구분 검색
    search_url = (
        "https://api.themoviedb.org/3/search/tv"
        if is_series
        else "https://api.themoviedb.org/3/search/movie"
    )
    params = {"api_key": api_key, "query": content.title, "language": "ko-KR"}
    if content.production_year:
        params["year"] = content.production_year

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(search_url, params=params)
            results = resp.json().get("results", [])
            if not results:
                return None
            item = results[0]
            tmdb_id = item["id"]

            # 상세 조회
            detail_url = (
                f"https://api.themoviedb.org/3/tv/{tmdb_id}"
                if is_series
                else f"https://api.themoviedb.org/3/movie/{tmdb_id}"
            )
            detail_resp = await client.get(
                detail_url,
                params={"api_key": api_key, "language": "ko-KR", "append_to_response": "credits"},
            )
            detail = detail_resp.json()

            # ExternalMetaSource 저장
            existing_src = (
                db.query(ExternalMetaSource)
                .filter(
                    ExternalMetaSource.content_id == content.id,
                    ExternalMetaSource.source_type == ExternalSourceType.tmdb,
                )
                .first()
            )
            if not existing_src:
                db.add(ExternalMetaSource(
                    content_id=content.id,
                    source_type=ExternalSourceType.tmdb,
                    external_id=str(tmdb_id),
                    raw_json=detail,
                    fetched_at=datetime.utcnow(),
                ))

            # 포스터 이미지 저장
            poster_path = detail.get("poster_path")
            if poster_path:
                existing_img = (
                    db.query(ContentImage)
                    .filter(
                        ContentImage.content_id == content.id,
                        ContentImage.image_type == ImageType.poster,
                    )
                    .first()
                )
                if not existing_img:
                    db.add(ContentImage(
                        content_id=content.id,
                        image_type=ImageType.poster,
                        url=f"https://image.tmdb.org/t/p/w500{poster_path}",
                        source="tmdb",
                        width=500,
                    ))

            # 출연진/감독 저장
            credits = detail.get("credits", {})
            _save_credits(content.id, credits, db)

            # 시리즈라면 시즌/에피소드 재귀 수집
            if is_series:
                await _tmdb_collect_seasons(content, detail, db, api_key, client)

            db.flush()
            return detail
    except Exception as exc:
        logger.warning(f"[tmdb] content_id={content.id} 검색 실패: {exc}")
        return None


def _save_credits(content_id: int, credits: dict, db):
    """TMDB credits → PersonMaster + ContentCredit 저장 (중복 방지)"""
    from api.programming.metadata.models import PersonMaster, ContentCredit, CreditRole

    cast = credits.get("cast", [])[:10]  # 주요 출연진 10명
    crew = credits.get("crew", [])

    # 감독 추출
    directors = [p for p in crew if p.get("job") == "Director"][:3]

    for person_data in (cast + directors):
        tmdb_person_id = person_data.get("id")
        name = person_data.get("name") or person_data.get("original_name", "")
        if not name:
            continue

        # PersonMaster 조회 또는 생성
        person = (
            db.query(PersonMaster)
            .filter(PersonMaster.tmdb_person_id == tmdb_person_id)
            .first()
        ) if tmdb_person_id else None

        if not person:
            person = db.query(PersonMaster).filter(PersonMaster.name == name).first()

        if not person:
            person = PersonMaster(
                name=name,
                tmdb_person_id=tmdb_person_id,
                profile_image_url=(
                    f"https://image.tmdb.org/t/p/w185{person_data['profile_path']}"
                    if person_data.get("profile_path") else None
                ),
            )
            db.add(person)
            db.flush()

        # ContentCredit 중복 체크
        existing_credit = (
            db.query(ContentCredit)
            .filter(
                ContentCredit.content_id == content_id,
                ContentCredit.person_id == person.id,
            )
            .first()
        )
        if not existing_credit:
            is_director = person_data.get("job") == "Director"
            db.add(ContentCredit(
                content_id=content_id,
                person_id=person.id,
                role=CreditRole.director if is_director else CreditRole.actor,
                character_name=person_data.get("character"),
                cast_order=person_data.get("order", 99),
            ))


async def _tmdb_collect_seasons(content, series_detail: dict, db, api_key: str, client):
    """시리즈 시즌/에피소드 재귀 수집 → contents 계층 구성"""
    from api.programming.metadata.models import (
        Content, ContentType, ContentStatus, ContentMetadata,
        ExternalMetaSource, ExternalSourceType,
    )

    tmdb_id = series_detail.get("id")
    seasons = series_detail.get("seasons", [])

    for season_info in seasons:
        season_num = season_info.get("season_number", 0)
        if season_num == 0:  # 특별편 시즌 스킵 옵션 — 일단 포함
            continue

        season_name = season_info.get("name") or f"{content.title} 시즌 {season_num}"

        # 시즌 Content 조회 또는 생성
        season_content = (
            db.query(Content)
            .filter(
                Content.parent_id == content.id,
                Content.content_type == ContentType.season,
                Content.season_number == season_num,
            )
            .first()
        )
        if not season_content:
            season_content = Content(
                title=season_name,
                content_type=ContentType.season,
                status=ContentStatus.staging,
                parent_id=content.id,
                season_number=season_num,
                cp_name=content.cp_name,
            )
            db.add(season_content)
            db.flush()
            db.add(ContentMetadata(content_id=season_content.id, quality_score=0.0))
            db.flush()

        # 시즌 상세 조회 → 에피소드 수집
        try:
            season_resp = await client.get(
                f"https://api.themoviedb.org/3/tv/{tmdb_id}/season/{season_num}",
                params={"api_key": api_key, "language": "ko-KR"},
                timeout=15.0,
            )
            season_data = season_resp.json()
            episodes = season_data.get("episodes", [])

            for ep in episodes:
                ep_num = ep.get("episode_number")
                if not ep_num:
                    continue
                ep_title = ep.get("name") or f"{content.title} S{season_num:02d}E{ep_num:02d}"

                existing_ep = (
                    db.query(Content)
                    .filter(
                        Content.parent_id == season_content.id,
                        Content.episode_number == ep_num,
                    )
                    .first()
                )
                if not existing_ep:
                    ep_content = Content(
                        title=ep_title,
                        content_type=ContentType.episode,
                        status=ContentStatus.staging,
                        parent_id=season_content.id,
                        season_number=season_num,
                        episode_number=ep_num,
                        runtime_minutes=ep.get("runtime"),
                        cp_name=content.cp_name,
                    )
                    db.add(ep_content)
                    db.flush()
                    db.add(ContentMetadata(content_id=ep_content.id, quality_score=0.0))

        except Exception as exc:
            logger.warning(f"[tmdb] 시즌 {season_num} 에피소드 수집 실패: {exc}")

    db.flush()


async def _kobis_search_and_save(content, db, api_key: str) -> dict | None:
    """KOBIS 검색 → ExternalMetaSource 저장"""
    from api.programming.metadata.models import ExternalMetaSource, ExternalSourceType

    params = {
        "key": api_key,
        "movieNm": content.title,
        "itemPerPage": "1",
    }
    if content.production_year:
        params["openStartDt"] = str(content.production_year)
        params["openEndDt"] = str(content.production_year)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "http://www.kobis.or.kr/kobisopenapi/webservice/rest/movie/searchMovieList.json",
                params=params,
            )
            movies = resp.json().get("movieListResult", {}).get("movieList", [])
            if not movies:
                return None
            movie = movies[0]
            movie_cd = movie.get("movieCd", "")

            existing_src = (
                db.query(ExternalMetaSource)
                .filter(
                    ExternalMetaSource.content_id == content.id,
                    ExternalMetaSource.source_type == ExternalSourceType.kobis,
                )
                .first()
            )
            if not existing_src:
                db.add(ExternalMetaSource(
                    content_id=content.id,
                    source_type=ExternalSourceType.kobis,
                    external_id=movie_cd,
                    raw_json=movie,
                    fetched_at=datetime.utcnow(),
                ))
            db.flush()
            return movie
    except Exception as exc:
        logger.warning(f"[kobis] content_id={content.id} 검색 실패: {exc}")
        return None


# ── 누락 에피소드 체크 ─────────────────────────────────────

@celery_app.task(name="workers.tasks.metadata.check_missing_episodes")
def check_missing_episodes():
    """
    시리즈 누락 에피소드 체크 (매일 04:00)
    TMDB 에피소드 수 vs DB 에피소드 수 불일치 → 누락 에피소드 waiting 상태 생성
    """
    if not getattr(settings, "TMDB_API_KEY", ""):
        logger.warning("[check_ep] TMDB_API_KEY 없음. 스킵.")
        return {"skipped": True}

    db = SessionLocal()
    created = 0
    try:
        from api.programming.metadata.models import (
            Content, ContentType, ContentMetadata,
            ExternalMetaSource, ExternalSourceType, ContentStatus,
        )
        # TMDB 매핑된 시리즈 조회
        series_list = (
            db.query(Content)
            .filter(Content.content_type == ContentType.series)
            .join(Content.metadata_record)
            .filter(ContentMetadata.tmdb_id.isnot(None))
            .limit(50)
            .all()
        )
        for series in series_list:
            meta = series.metadata_record
            if not meta or not meta.tmdb_id:
                continue
            try:
                resp = httpx.get(
                    f"https://api.themoviedb.org/3/tv/{meta.tmdb_id}",
                    params={"api_key": settings.TMDB_API_KEY, "language": "ko-KR"},
                    timeout=10.0,
                )
                tmdb_data = resp.json()
                tmdb_ep_count = tmdb_data.get("number_of_episodes", 0)

                db_ep_count = (
                    db.query(Content)
                    .filter(
                        Content.parent_id == series.id,
                        Content.content_type == ContentType.episode,
                    )
                    .count()
                )

                if tmdb_ep_count > db_ep_count:
                    logger.info(
                        f"[check_ep] '{series.title}': TMDB {tmdb_ep_count}화 vs DB {db_ep_count}화 → "
                        f"enrichment 재실행"
                    )
                    enrich_content_metadata.delay(series.id)
                    created += 1
            except Exception as exc:
                logger.warning(f"[check_ep] series_id={series.id} 체크 실패: {exc}")

        logger.info(f"[check_ep] {created}건 재enrichment 큐 등록")
        return {"queued": created}
    finally:
        db.close()


# ── 실패 항목 재시도 ──────────────────────────────────────

@celery_app.task(name="workers.tasks.metadata.retry_failed_enrichments")
def retry_failed_enrichments():
    """
    실패 항목 재시도 (6시간 주기)
    status=processing이고 6시간 이상 경과한 항목 → 재처리
    max_retries=3 초과 항목은 rejected 처리
    """
    db = SessionLocal()
    retried = 0
    rejected_count = 0
    try:
        from api.programming.metadata.models import (
            Content, ContentStatus, ContentAIResult,
        )
        cutoff = datetime.utcnow() - timedelta(hours=6)
        stalled = (
            db.query(Content)
            .filter(
                Content.status == ContentStatus.processing,
                Content.updated_at < cutoff,
            )
            .limit(50)
            .all()
        )
        for c in stalled:
            # 재시도 횟수 확인
            retry_count = (
                db.query(ContentAIResult)
                .filter(ContentAIResult.content_id == c.id)
                .count()
            )
            if retry_count >= 3:
                c.status = ContentStatus.rejected
                rejected_count += 1
                logger.warning(f"[retry] content_id={c.id} max retries 초과 → rejected")
            else:
                enrich_content_metadata.delay(c.id)
                retried += 1

        db.commit()
        logger.info(f"[retry] 재시도 {retried}건, rejected {rejected_count}건")
        return {"retried": retried, "rejected": rejected_count}
    finally:
        db.close()
