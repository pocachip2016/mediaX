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
import difflib
import imaplib
import email
import logging
import os
import httpx
from email.header import decode_header
from datetime import datetime, timedelta

from workers.celery_app import celery_app
from shared.database import SessionLocal
from shared.config import settings
from shared.quota_manager import QuotaManager

logger = logging.getLogger(__name__)

_quota = QuotaManager()


def _kobis_rate_allowed() -> bool:
    """일일 KOBIS API 호출 횟수를 Redis로 추적. 한도 초과 시 False."""
    return _quota.is_allowed("kobis", 2900)


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
        from api.programming.metadata.models.content import IntakeChannel, PipelineStage, StageEventType
        from api.programming.metadata.stage_events import record_stage_event
        content = Content(
            title=title,
            content_type=ContentType.movie,
            status=ContentStatus.waiting,
            cp_name=extracted.get("cp_name"),
            production_year=extracted.get("year"),
            cp_email_id=log.id,
            intake_channel=IntakeChannel.EMAIL_POLL,
        )
        db.add(content)
        db.flush()
        record_stage_event(db, content.id, PipelineStage.S1_INTAKE, StageEventType.ENTERED,
                           source="email_poll", actor="email_poller")
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
def sync_kobis(target_date: str | None = None):
    """영진위 KOBIS 일일 동기화 (매일 03:00) — 전일 개봉 영화 → ExternalMetaSource + external_sync_log"""
    if not getattr(settings, "KOBIS_API_KEY", ""):
        logger.warning("[kobis] KOBIS_API_KEY 없음. 스킵.")
        return {"skipped": True}

    from api.programming.metadata.models import (
        Content, ContentMetadata, ContentType,
        ExternalSourceType, TmdbSyncLog, TmdbSyncSource, TmdbSyncStatus,
    )
    from api.programming.metadata.ai_engine import _upsert_external_source

    db = SessionLocal()
    date_str = target_date or (datetime.utcnow() - timedelta(days=1)).strftime("%Y%m%d")

    log = TmdbSyncLog(
        source=TmdbSyncSource.kobis_daily,
        external_source=ExternalSourceType.kobis,
        target_date=datetime.strptime(date_str, "%Y%m%d").date(),
        status=TmdbSyncStatus.running,
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    inserted = updated = errors = 0
    try:
        if not _kobis_rate_allowed():
            log.status = TmdbSyncStatus.failed
            log.error_sample = ["일일 한도 초과"]
            log.finished_at = datetime.utcnow()
            db.commit()
            return {"skipped": True, "reason": "daily_limit_exceeded"}
        resp = httpx.get(
            "http://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json",
            params={
                "key": settings.KOBIS_API_KEY,
                "targetDt": date_str,
            },
            timeout=15.0,
        )
        movies = resp.json().get("boxOfficeResult", {}).get("dailyBoxOfficeList", [])
        log.items_fetched = len(movies)

        for movie in movies:
            movie_nm = movie.get("movieNm", "")
            movie_cd = movie.get("movieCd", "")
            if not movie_nm or not movie_cd:
                continue
            # DB-레벨 제목 매칭 (O(N) — 전체 루프 제거)
            content = (
                db.query(Content)
                .filter(Content.title == movie_nm, Content.content_type == ContentType.movie)
                .first()
            )
            fuzzy_confidence: float | None = None
            if not content:
                # fuzzy fallback: 같은 연도 영화에서 ratio >= 0.85 탐색
                prdtYear = movie.get("prdtYear", "")
                if prdtYear and prdtYear.isdigit():
                    candidates = (
                        db.query(Content)
                        .filter(
                            Content.content_type == ContentType.movie,
                            Content.production_year == int(prdtYear),
                        )
                        .all()
                    )
                    best_ratio, best_cand = 0.0, None
                    for cand in candidates:
                        ratio = difflib.SequenceMatcher(None, movie_nm, cand.title).ratio()
                        if ratio > best_ratio:
                            best_ratio, best_cand = ratio, cand
                    if best_ratio >= 0.85:
                        content = best_cand
                        fuzzy_confidence = round(best_ratio, 4)
            if not content:
                continue
            try:
                from api.programming.metadata.models import ExternalMetaSource
                prev = (
                    db.query(ExternalMetaSource)
                    .filter(
                        ExternalMetaSource.content_id == content.id,
                        ExternalMetaSource.source_type == ExternalSourceType.kobis,
                    )
                    .first()
                )
                _upsert_external_source(db, content.id, ExternalSourceType.kobis, movie_cd, movie)
                if fuzzy_confidence is not None:
                    src = (
                        db.query(ExternalMetaSource)
                        .filter(
                            ExternalMetaSource.content_id == content.id,
                            ExternalMetaSource.source_type == ExternalSourceType.kobis,
                        )
                        .first()
                    )
                    if src:
                        src.match_confidence = fuzzy_confidence
                if prev:
                    updated += 1
                else:
                    inserted += 1
            except Exception as exc:
                logger.warning(f"[kobis] content_id={content.id} 처리 실패: {exc}")
                errors += 1

        db.commit()
        log.items_inserted = inserted
        log.items_updated = updated
        log.errors = errors
        log.status = TmdbSyncStatus.completed
        log.finished_at = datetime.utcnow()
        db.commit()

        logger.info(f"[kobis] inserted={inserted} updated={updated} errors={errors} total={len(movies)}")
        return {"inserted": inserted, "updated": updated, "errors": errors, "total_from_kobis": len(movies)}
    except Exception as exc:
        log.status = TmdbSyncStatus.failed
        log.error_sample = [str(exc)]
        log.finished_at = datetime.utcnow()
        db.commit()
        logger.error(f"[kobis] 동기화 실패: {exc}")
        return {"error": str(exc)}
    finally:
        db.close()


@celery_app.task(name="workers.tasks.metadata.sync_tmdb")
def sync_tmdb():
    """TMDB 주간 동기화 (매일 02:00) — tmdb_id 미매핑 콘텐츠 일괄 보강"""
    api_key = getattr(settings, "TMDB_API_KEY", "")
    if not api_key:
        logger.warning("[tmdb] TMDB_API_KEY 없음. 스킵.")
        return {"skipped": True}

    db = SessionLocal()
    try:
        stats = asyncio.run(_async_sync_tmdb(db, api_key))
        logger.info(f"[tmdb] 동기화 완료: {stats}")
        return stats
    except Exception as exc:
        logger.error(f"[tmdb] 동기화 실패: {exc}")
        return {"error": str(exc)}
    finally:
        db.close()


async def _async_sync_tmdb(db, api_key: str) -> dict:
    """TMDB 미매핑 콘텐츠 일괄 보강 — 비동기"""
    from api.programming.metadata.models import (
        Content, ContentType, ContentStatus,
        ExternalMetaSource, ExternalSourceType,
    )

    BATCH_LIMIT = 50

    unmapped = (
        db.query(Content)
        .outerjoin(
            ExternalMetaSource,
            (ExternalMetaSource.content_id == Content.id) &
            (ExternalMetaSource.source_type == ExternalSourceType.tmdb),
        )
        .filter(
            ExternalMetaSource.id.is_(None),
            Content.content_type.in_([ContentType.movie, ContentType.series]),
            Content.status != ContentStatus.waiting,
        )
        .limit(BATCH_LIMIT)
        .all()
    )

    updated = skipped = failed = 0
    for content in unmapped:
        try:
            result = await _tmdb_search_and_save(content, db, api_key)
            if result and result.get("id"):
                meta = content.metadata_record
                if meta:
                    meta.tmdb_data = result
                db.commit()
                updated += 1
                logger.info(f"[tmdb] content_id={content.id} '{content.title}' 매핑 완료 (tmdb_id={result['id']})")
            else:
                skipped += 1
                logger.debug(f"[tmdb] content_id={content.id} '{content.title}' TMDB 검색 결과 없음")
        except Exception as exc:
            logger.warning(f"[tmdb] content_id={content.id} 처리 실패: {exc}")
            db.rollback()
            failed += 1

    return {"total": len(unmapped), "updated": updated, "skipped": skipped, "failed": failed}


@celery_app.task(name="workers.tasks.metadata.backfill_tmdb_details")
def backfill_tmdb_details(batch: int = 100):
    """기존 TMDB 매핑 레코드의 runtime/country/credits 백필 (TMDB detail 재조회)"""
    db = SessionLocal()
    try:
        api_key = os.environ.get("TMDB_API_KEY", "")
        if not api_key:
            logger.warning("[backfill_tmdb] TMDB_API_KEY 없음")
            return {"error": "no api key"}
        stats = asyncio.run(_async_backfill_tmdb(db, api_key, batch))
        logger.info(f"[backfill_tmdb] 완료: {stats}")
        return stats
    finally:
        db.close()


async def _async_backfill_tmdb(db, api_key: str, batch: int) -> dict:
    from api.programming.metadata.models import (
        Content, ContentType, ExternalMetaSource, ExternalSourceType,
    )

    targets = (
        db.query(Content, ExternalMetaSource)
        .join(
            ExternalMetaSource,
            (ExternalMetaSource.content_id == Content.id) &
            (ExternalMetaSource.source_type == ExternalSourceType.tmdb),
        )
        .filter(Content.content_type.in_([ContentType.movie, ContentType.series]))
        .filter(Content.runtime_minutes.is_(None))
        .limit(batch)
        .all()
    )

    updated = failed = 0
    async with httpx.AsyncClient(timeout=15.0) as client:
        for content, ext_src in targets:
            try:
                tmdb_id = ext_src.external_id
                from api.programming.metadata.content_kind import is_tv_type
                is_series = is_tv_type(content)
                detail_url = (
                    f"https://api.themoviedb.org/3/tv/{tmdb_id}"
                    if is_series
                    else f"https://api.themoviedb.org/3/movie/{tmdb_id}"
                )
                resp = await client.get(
                    detail_url,
                    params={"api_key": api_key, "language": "ko-KR", "append_to_response": "credits"},
                )
                if resp.status_code != 200:
                    logger.warning(f"[backfill_tmdb] content_id={content.id} TMDB {resp.status_code}")
                    failed += 1
                    continue
                detail = resp.json()

                if not content.runtime_minutes:
                    runtime = (
                        detail.get("runtime")
                        or (detail.get("episode_run_time") or [None])[0]
                    )
                    if runtime:
                        content.runtime_minutes = int(runtime)

                if not content.country:
                    countries = (
                        [c.get("iso_3166_1") for c in detail.get("production_countries", [])]
                        or detail.get("origin_country", [])
                    )
                    if countries:
                        content.country = countries[0]

                ext_src.raw_json = detail
                _save_credits(content.id, detail.get("credits", {}), db)

                db.commit()
                updated += 1
                await asyncio.sleep(0.1)  # TMDB rate limit
            except Exception as exc:
                logger.warning(f"[backfill_tmdb] content_id={content.id} 실패: {exc}")
                db.rollback()
                failed += 1

    return {"total": len(targets), "updated": updated, "failed": failed}


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
    에이전틱 멀티소스 검색 태스크 — meta_core.enrich 위임.
    candidate/suggestion 흐름으로 외부 소스 호출.
    ContentMetadata 직접 쓰기 없음 (Aggregator step7 책임).
    """
    from api.meta_core.enrich import enrich_content as _enrich_content
    from api.programming.metadata.models.content import PipelineStage, StageEventType
    from api.programming.metadata.stage_events import record_stage_event
    db = SessionLocal()
    try:
        record_stage_event(db, content_id, PipelineStage.S3_LLM_EXTRACT, StageEventType.ENTERED,
                           source="ollama", actor="system")
        result = _enrich_content(content_id, db)
        db.commit()
        record_stage_event(db, content_id, PipelineStage.S3_LLM_EXTRACT, StageEventType.COMPLETED,
                           source="ollama", actor="system")
        logger.info(
            "[enrich] content_id=%d candidates=%d edges=%d suggestions=%d skipped=%s",
            content_id, result.candidates_upserted, result.match_edges_created,
            result.suggestions_created, result.sources_skipped,
        )
    except Exception as exc:
        logger.error(f"[enrich] content_id={content_id} 실패: {exc}")
        try:
            record_stage_event(db, content_id, PipelineStage.S3_LLM_EXTRACT, StageEventType.FAILED,
                               source="ollama", error=str(exc)[:500], actor="system")
            db.commit()
        except Exception:
            pass
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

    from api.programming.metadata.models.content import PipelineStage, StageEventType
    from api.programming.metadata.stage_events import record_stage_event

    # ── TMDB 검색 ──────────────────────────────────────────
    if tmdb_key:
        record_stage_event(db, content_id, PipelineStage.S4_SOURCE_MATCH, StageEventType.ENTERED,
                           source="tmdb", actor="system")
        tmdb_result = await _tmdb_search_and_save(content, db, tmdb_key)
        _tmdb_et = StageEventType.COMPLETED if tmdb_result else StageEventType.SKIPPED
        record_stage_event(db, content_id, PipelineStage.S4_SOURCE_MATCH, _tmdb_et,
                           source="tmdb", actor="system")

    # ── KOBIS 검색 ─────────────────────────────────────────
    if kobis_key and content.content_type == ContentType.movie:
        record_stage_event(db, content_id, PipelineStage.S4_SOURCE_MATCH, StageEventType.ENTERED,
                           source="kobis", actor="system")
        kobis_result = await _kobis_search_and_save(content, db, kobis_key)
        _kobis_et = StageEventType.COMPLETED if kobis_result else StageEventType.SKIPPED
        record_stage_event(db, content_id, PipelineStage.S4_SOURCE_MATCH, _kobis_et,
                           source="kobis", actor="system")

    # ── ContentMetadata 업데이트 ───────────────────────────
    meta = content.metadata_record
    if not meta:
        meta = ContentMetadata(content_id=content_id)
        db.add(meta)
        db.flush()

    if tmdb_result and tmdb_result.get("id"):
        meta.tmdb_data = tmdb_result


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

    from api.programming.metadata.content_kind import is_tv_type, external_lookup_target
    is_series = is_tv_type(content)
    lookup = external_lookup_target(content, db)

    # 영화/시리즈 구분 검색
    if is_series:
        search_url = "https://api.themoviedb.org/3/search/tv"
        params = {"api_key": api_key, "query": lookup.title, "language": "ko-KR"}
        if lookup.production_year:
            params["first_air_date_year"] = lookup.production_year
    else:
        search_url = "https://api.themoviedb.org/3/search/movie"
        params = {"api_key": api_key, "query": lookup.title, "language": "ko-KR"}
        if lookup.production_year:
            params["year"] = lookup.production_year

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
                    matched_at=datetime.utcnow(),
                ))

            # Content 필드 보강 (runtime_minutes / country) — 기존 값 우선 보존
            if not content.runtime_minutes:
                runtime = (
                    detail.get("runtime")  # movie
                    or (detail.get("episode_run_time") or [None])[0]  # tv
                )
                if runtime:
                    content.runtime_minutes = int(runtime)

            if not content.country:
                countries = (
                    [c.get("iso_3166_1") for c in detail.get("production_countries", [])]
                    or detail.get("origin_country", [])
                )
                if countries:
                    content.country = countries[0]

            # 포스터 이미지 저장 — service.add_content_image() 와 동일 규약 (멱등 + is_primary)
            # commit 분리: 워커 트랜잭션 원자성을 위해 헬퍼 대신 인라인 처리
            poster_path = detail.get("poster_path")
            if poster_path:
                poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}"
                duplicate = (
                    db.query(ContentImage)
                    .filter(
                        ContentImage.content_id == content.id,
                        ContentImage.image_type == ImageType.poster,
                        ContentImage.url == poster_url,
                    )
                    .first()
                )
                if not duplicate:
                    has_same_type = (
                        db.query(ContentImage)
                        .filter(
                            ContentImage.content_id == content.id,
                            ContentImage.image_type == ImageType.poster,
                        )
                        .first()
                    )
                    db.add(ContentImage(
                        content_id=content.id,
                        image_type=ImageType.poster,
                        url=poster_url,
                        source="tmdb",
                        width=500,
                        is_primary=(has_same_type is None),
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
            person = db.query(PersonMaster).filter(PersonMaster.name_ko == name).first()

        if not person:
            person = PersonMaster(
                name_ko=name,
                tmdb_person_id=tmdb_person_id,
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

    # 이미 저장된 소스가 있으면 API 호출 없이 반환
    existing_src = (
        db.query(ExternalMetaSource)
        .filter(
            ExternalMetaSource.content_id == content.id,
            ExternalMetaSource.source_type == ExternalSourceType.kobis,
        )
        .first()
    )
    if existing_src:
        return existing_src.raw_json

    if not _kobis_rate_allowed():
        return None

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
            db.add(ExternalMetaSource(
                content_id=content.id,
                source_type=ExternalSourceType.kobis,
                external_id=movie_cd,
                raw_json=movie,
                matched_at=datetime.utcnow(),
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
            Content, ContentType,
            ExternalMetaSource, ExternalSourceType,
        )
        # TMDB 매핑된 시리즈 조회 (ExternalMetaSource 기준, 중복 방지)
        rows = (
            db.query(Content, ExternalMetaSource)
            .join(
                ExternalMetaSource,
                (ExternalMetaSource.content_id == Content.id) &
                (ExternalMetaSource.source_type == ExternalSourceType.tmdb),
            )
            .filter(Content.content_type == ContentType.series)
            .limit(50)
            .all()
        )
        seen_ids: set[int] = set()
        for series, ext_source in rows:
            if series.id in seen_ids:
                continue
            seen_ids.add(series.id)
            tmdb_id = ext_source.external_id
            if not tmdb_id:
                continue
            try:
                resp = httpx.get(
                    f"https://api.themoviedb.org/3/tv/{tmdb_id}",
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


# ── KOBIS 소급 백필 ────────────────────────────────────────

@celery_app.task(name="workers.tasks.metadata.backfill_kobis", max_retries=0)
def backfill_kobis(year: int):
    """KOBIS 단일 연도 소급 백필 — quota-aware tick에서 호출.

    한 연도의 영화 목록을 페이지로 순회하면서 ExternalMetaSource 에 upsert.
    일일 한도 도달 시 graceful exit (다음날 tick 이 재개).
    """
    if not getattr(settings, "KOBIS_API_KEY", ""):
        logger.warning("[kobis_backfill] KOBIS_API_KEY 없음. 스킵.")
        return {"skipped": True, "reason": "no_api_key"}

    from datetime import date as date_type

    from api.programming.metadata.models import (
        Content, ContentType, ExternalMetaSource,
        ExternalSourceType, TmdbSyncLog, TmdbSyncSource, TmdbSyncStatus,
    )
    from api.programming.metadata.models.kobis_cache import KobisMovieCache
    from api.programming.metadata.ai_engine import _upsert_external_source

    db = SessionLocal()
    try:
        log = TmdbSyncLog(
            source=TmdbSyncSource.kobis_backfill,
            external_source=ExternalSourceType.kobis,
            target_year=year,
            status=TmdbSyncStatus.running,
        )
        db.add(log)
        db.commit()
        db.refresh(log)

        inserted = updated = unchanged = errors = 0
        cache_ins = cache_upd = 0          # kobis_movie_cache 측 카운터
        quota_hit = False
        page = 1
        date_start = str(year)
        date_end = str(year)

        while True:
            try:
                if not _kobis_rate_allowed():
                    logger.warning(f"[kobis_backfill] 일일 한도 초과. year={year} page={page} 에서 중단.")
                    quota_hit = True
                    break
                resp = httpx.get(
                    "http://www.kobis.or.kr/kobisopenapi/webservice/rest/movie/searchMovieList.json",
                    params={
                        "key": settings.KOBIS_API_KEY,
                        "openStartDt": date_start,
                        "openEndDt": date_end,
                        "itemPerPage": "100",
                        "curPage": str(page),
                    },
                    timeout=20.0,
                )
                result = resp.json().get("movieListResult", {})
                movies = result.get("movieList", [])
                if not movies:
                    break
                log.items_fetched = (log.items_fetched or 0) + len(movies)

                for movie in movies:
                    movie_nm = movie.get("movieNm", "")
                    movie_cd = movie.get("movieCd", "")
                    if not movie_nm or not movie_cd:
                        continue

                    # ── kobis_movie_cache upsert (always, content 매칭과 독립) ──
                    open_dt_raw = movie.get("openDt", "") or ""
                    open_dt = None
                    if len(open_dt_raw) == 8 and open_dt_raw.isdigit():
                        try:
                            open_dt = date_type(int(open_dt_raw[:4]), int(open_dt_raw[4:6]), int(open_dt_raw[6:]))
                        except ValueError:
                            pass
                    prdt_year_raw = movie.get("prdtYear", "") or ""
                    prdt_year = int(prdt_year_raw) if prdt_year_raw and prdt_year_raw.isdigit() else None
                    directors_raw = movie.get("directors") or {}
                    directors_list = directors_raw.get("director", []) if isinstance(directors_raw, dict) else []

                    cache_row = db.get(KobisMovieCache, movie_cd)
                    if cache_row is None:
                        db.add(KobisMovieCache(
                            movie_cd=movie_cd,
                            title=movie_nm,
                            title_en=movie.get("movieNmEn") or None,
                            open_dt=open_dt,
                            prdt_year=prdt_year,
                            type_nm=movie.get("typeNm") or None,
                            prdt_stat_nm=movie.get("prdtStatNm") or None,
                            nation_alt=movie.get("nationAlt") or None,
                            genre_alt=movie.get("genreAlt") or None,
                            rep_nation_nm=movie.get("repNationNm") or None,
                            rep_genre_nm=movie.get("repGenreNm") or None,
                            directors=directors_list,
                            raw_json=movie,
                        ))
                        cache_ins += 1
                    else:
                        cache_row.title = movie_nm
                        cache_row.raw_json = movie
                        cache_upd += 1
                    # ─────────────────────────────────────────────────────────────

                    existing = (
                        db.query(ExternalMetaSource)
                        .filter(
                            ExternalMetaSource.source_type == ExternalSourceType.kobis,
                            ExternalMetaSource.external_id == movie_cd,
                        )
                        .first()
                    )
                    if existing:
                        unchanged += 1
                        continue

                    content = (
                        db.query(Content)
                        .filter(
                            Content.title == movie_nm,
                            Content.content_type == ContentType.movie,
                        )
                        .first()
                    )

                    fuzzy_confidence: float | None = None
                    if not content:
                        prdtYear = movie.get("prdtYear", "")
                        if prdtYear and prdtYear.isdigit():
                            candidates = (
                                db.query(Content)
                                .filter(
                                    Content.content_type == ContentType.movie,
                                    Content.production_year == int(prdtYear),
                                )
                                .all()
                            )
                            best_ratio, best_cand = 0.0, None
                            for cand in candidates:
                                ratio = difflib.SequenceMatcher(None, movie_nm, cand.title).ratio()
                                if ratio > best_ratio:
                                    best_ratio, best_cand = ratio, cand
                            if best_ratio >= 0.85:
                                content = best_cand
                                fuzzy_confidence = round(best_ratio, 4)

                    if not content:
                        continue

                    try:
                        _upsert_external_source(
                            db, content.id, ExternalSourceType.kobis, movie_cd, movie
                        )
                        if fuzzy_confidence is not None:
                            src = (
                                db.query(ExternalMetaSource)
                                .filter(
                                    ExternalMetaSource.content_id == content.id,
                                    ExternalMetaSource.source_type == ExternalSourceType.kobis,
                                )
                                .first()
                            )
                            if src:
                                src.match_confidence = fuzzy_confidence
                        inserted += 1
                    except Exception as exc:
                        logger.warning(f"[kobis_backfill] content_id={content.id} 처리 실패: {exc}")
                        errors += 1

                db.commit()
                page += 1
                total_cnt = int(result.get("totCnt", 0))
                if total_cnt and (page - 1) * 100 >= total_cnt:
                    break
            except Exception as exc:
                logger.error(f"[kobis_backfill] year={year} page={page} 실패: {exc}")
                errors += 1
                break

        log.items_inserted = inserted
        log.items_updated = updated
        log.items_unchanged = unchanged
        log.errors = errors
        log.cache_inserted = cache_ins
        log.cache_updated = cache_upd
        # quota_hit 으로 끝났으면 다음 tick 에서 재개되도록 running 유지하지 않고 failed 로 마킹
        # (completed 만 done_years 에 포함되도록)
        log.status = TmdbSyncStatus.completed if (errors == 0 and not quota_hit) else TmdbSyncStatus.failed
        log.finished_at = datetime.utcnow()
        db.commit()
        logger.info(
            f"[kobis_backfill] year={year} inserted={inserted} updated={updated} "
            f"unchanged={unchanged} errors={errors} cache_ins={cache_ins} quota_hit={quota_hit}"
        )

        return {
            "year": year,
            "inserted": inserted,
            "updated": updated,
            "unchanged": unchanged,
            "errors": errors,
            "quota_hit": quota_hit,
        }
    finally:
        db.close()


# ── KOBIS quota-aware 백필 Beat tick ──────────────────────

_KOBIS_QUOTA_THRESHOLD = 1000   # 잔여 quota < 1000 이면 백필 스킵
_KOBIS_DAILY_LIMIT = 2900       # _kobis_rate_allowed() 와 동일
_KOBIS_BACKFILL_FLOOR_YEAR = 1990


@celery_app.task(name="workers.tasks.metadata.kobis_quota_backfill_tick")
def kobis_quota_backfill_tick():
    """매일 06:30 KST Beat — quota 잔여 확인 후 미백필 연도 1개 비동기 트리거.

    잔여 quota < _KOBIS_QUOTA_THRESHOLD 이면 skip.
    연도 탐색은 current_year → _KOBIS_BACKFILL_FLOOR_YEAR 역순 (최신부터 거슬러).
    """
    from datetime import date
    from api.programming.metadata.models import TmdbSyncSource

    remaining = _quota.daily_remaining("kobis", _KOBIS_DAILY_LIMIT)
    if remaining < _KOBIS_QUOTA_THRESHOLD:
        logger.info("[kobis-tick] quota 잔여 %d < %d — 백필 스킵", remaining, _KOBIS_QUOTA_THRESHOLD)
        return {"skipped": True, "remaining": remaining}

    db = SessionLocal()
    try:
        from sqlalchemy import text
        rows = db.execute(
            text("""
                SELECT DISTINCT target_year FROM external_sync_log
                WHERE source = :src AND status = 'completed' AND target_year IS NOT NULL
            """),
            {"src": TmdbSyncSource.kobis_backfill.value},
        ).fetchall()
        done_years = {r[0] for r in rows}
    finally:
        db.close()

    current_year = date.today().year
    target_year = None
    for y in range(current_year, _KOBIS_BACKFILL_FLOOR_YEAR - 1, -1):
        if y not in done_years:
            target_year = y
            break

    if target_year is None:
        logger.info("[kobis-tick] 모든 연도(%d~%d) 백필 완료", _KOBIS_BACKFILL_FLOOR_YEAR, current_year)
        return {"skipped": True, "reason": "all_done"}

    logger.info("[kobis-tick] quota=%d → year=%d 백필 트리거", remaining, target_year)
    backfill_kobis.delay(year=target_year)
    return {"triggered_year": target_year, "remaining": remaining}


# ── KMDB 캐시 → contents 링크 ────────────────────────────

@celery_app.task(name="workers.tasks.metadata.link_kmdb_cache_to_contents", max_retries=0)
def link_kmdb_cache_to_contents():
    """kmdb_movie_cache 전체를 순회하면서 contents 에 exact/fuzzy 매칭 후 ExternalMetaSource upsert.

    - 이미 external_meta_sources 에 source_type='kmdb' + external_id=docid 로 존재하면 스킵
    - 정확 매칭: Content.title == cache.title (movie 타입)
    - fuzzy 폴백: prod_year 같은 후보군 중 SequenceMatcher ratio >= 0.85
    - 매일 07:00 KST Beat 에서 실행 (idempotent)
    """
    from api.programming.metadata.models import (
        Content, ContentType, ExternalMetaSource,
        ExternalSourceType, TmdbSyncLog, TmdbSyncSource, TmdbSyncStatus,
    )
    from api.programming.metadata.models.kmdb_cache import KmdbMovieCache
    from api.programming.metadata.ai_engine import _upsert_external_source

    db = SessionLocal()
    try:
        log = TmdbSyncLog(
            source=TmdbSyncSource.kmdb_link,
            external_source=ExternalSourceType.kmdb,
            status=TmdbSyncStatus.running,
        )
        db.add(log)
        db.commit()
        db.refresh(log)

        existing_docids = {
            row[0]
            for row in db.query(ExternalMetaSource.external_id)
            .filter(ExternalMetaSource.source_type == ExternalSourceType.kmdb)
            .all()
        }

        caches = db.query(KmdbMovieCache).all()
        log.items_fetched = len(caches)

        inserted = updated = unchanged = errors = 0

        for cache in caches:
            if cache.docid in existing_docids:
                unchanged += 1
                continue

            content = (
                db.query(Content)
                .filter(
                    Content.title == cache.title,
                    Content.content_type == ContentType.movie,
                )
                .first()
            )

            fuzzy_confidence: float | None = None
            if not content and cache.prod_year:
                candidates = (
                    db.query(Content)
                    .filter(
                        Content.content_type == ContentType.movie,
                        Content.production_year == cache.prod_year,
                    )
                    .all()
                )
                best_ratio, best_cand = 0.0, None
                for cand in candidates:
                    ratio = difflib.SequenceMatcher(None, cache.title, cand.title).ratio()
                    if ratio > best_ratio:
                        best_ratio, best_cand = ratio, cand
                if best_ratio >= 0.85:
                    content = best_cand
                    fuzzy_confidence = round(best_ratio, 4)

            if not content:
                continue

            try:
                raw = cache.raw_json or {"docid": cache.docid, "title": cache.title}
                _upsert_external_source(
                    db, content.id, ExternalSourceType.kmdb, cache.docid, raw
                )
                if fuzzy_confidence is not None:
                    src = (
                        db.query(ExternalMetaSource)
                        .filter(
                            ExternalMetaSource.content_id == content.id,
                            ExternalMetaSource.source_type == ExternalSourceType.kmdb,
                        )
                        .first()
                    )
                    if src:
                        src.match_confidence = fuzzy_confidence
                inserted += 1
            except Exception as exc:
                logger.warning(f"[kmdb_link] content_id={content.id} 처리 실패: {exc}")
                errors += 1

        db.commit()

        log.items_inserted = inserted
        log.items_updated = updated
        log.items_unchanged = unchanged
        log.errors = errors
        log.status = TmdbSyncStatus.completed if errors == 0 else TmdbSyncStatus.failed
        log.finished_at = datetime.utcnow()
        db.commit()

        logger.info(
            f"[kmdb_link] inserted={inserted} unchanged={unchanged} errors={errors}"
        )
        return {"inserted": inserted, "unchanged": unchanged, "errors": errors}
    finally:
        db.close()


# ── TMDB 캐시 → contents 링크 ─────────────────────────────

@celery_app.task(name="workers.tasks.metadata.link_tmdb_cache_to_contents", max_retries=0)
def link_tmdb_cache_to_contents():
    """tmdb_movie_cache / tmdb_tv_cache 를 순회, contents 에 title+year 매칭 후
    ExternalMetaSource upsert. 매일 07:30 KST Beat. 멱등.

    - 이미 external_meta_sources 에 source_type='tmdb' + 해당 id 가 있으면 스킵
    - 영화: TmdbMovieCache(id, title, release_date) → ContentType.movie
    - 시리즈: TmdbTvCache(id, name, first_air_date) → ContentType.series
    - 정확 매칭: title == Content.title
    - fuzzy 폴백: prod_year 일치 후보 중 SequenceMatcher >= 0.85
    """
    from datetime import datetime

    from api.programming.metadata.models import (
        Content, ContentType, ExternalMetaSource,
        ExternalSourceType, TmdbSyncLog, TmdbSyncSource, TmdbSyncStatus,
    )
    from api.programming.metadata.models.tmdb_cache import TmdbMovieCache, TmdbTvCache
    from api.programming.metadata.ai_engine import _upsert_external_source

    db = SessionLocal()
    try:
        log = TmdbSyncLog(
            source=TmdbSyncSource.tmdb_link,
            external_source=ExternalSourceType.tmdb,
            status=TmdbSyncStatus.running,
        )
        db.add(log)
        db.commit()
        db.refresh(log)

        # 이미 TMDB가 연결된 content_id 세트 (skip 최적화)
        linked_content_ids = {
            row[0]
            for row in db.query(ExternalMetaSource.content_id)
            .filter(
                ExternalMetaSource.source_type == ExternalSourceType.tmdb,
                ExternalMetaSource.content_id.isnot(None),
            )
            .all()
        }

        inserted = unchanged = errors = 0

        # contents 기준 순회 (캐시 442K 건 전체 로드 대신 contents N건 기준)
        # ── 영화 ─────────────────────────────────────────────────
        movie_q = (
            db.query(Content)
            .filter(Content.content_type == ContentType.movie, Content.is_deleted == False)  # noqa: E712
        )
        log.items_fetched = movie_q.count()
        db.commit()

        for content in movie_q.yield_per(200):
            if content.id in linked_content_ids:
                unchanged += 1
                continue

            # 정확 매칭
            cache = (
                db.query(TmdbMovieCache)
                .filter(TmdbMovieCache.title == content.title)
                .first()
            )

            fuzzy_confidence: float | None = None
            if not cache and content.production_year:
                from sqlalchemy import extract
                candidates = (
                    db.query(TmdbMovieCache)
                    .filter(
                        extract("year", TmdbMovieCache.release_date) == content.production_year
                    )
                    .limit(50)
                    .all()
                )
                best_ratio, best_cache = 0.0, None
                for cand in candidates:
                    ratio = difflib.SequenceMatcher(None, content.title, cand.title).ratio()
                    if ratio > best_ratio:
                        best_ratio, best_cache = ratio, cand
                if best_ratio >= 0.85:
                    cache = best_cache
                    fuzzy_confidence = round(best_ratio, 4)

            if not cache:
                continue

            try:
                raw = cache.raw_json or {"tmdb_id": cache.id, "title": cache.title}
                _upsert_external_source(
                    db, content.id, ExternalSourceType.tmdb, str(cache.id), raw
                )
                if fuzzy_confidence is not None:
                    src = (
                        db.query(ExternalMetaSource)
                        .filter(
                            ExternalMetaSource.content_id == content.id,
                            ExternalMetaSource.source_type == ExternalSourceType.tmdb,
                        )
                        .first()
                    )
                    if src:
                        src.match_confidence = fuzzy_confidence
                inserted += 1
                linked_content_ids.add(content.id)
            except Exception as exc:
                logger.warning(f"[tmdb_link] movie content_id={content.id} 처리 실패: {exc}")
                errors += 1

        # ── 시리즈 ────────────────────────────────────────────────
        tv_q = (
            db.query(Content)
            .filter(Content.content_type == ContentType.series, Content.is_deleted == False)  # noqa: E712
        )
        log.items_fetched += tv_q.count()

        for content in tv_q.yield_per(200):
            if content.id in linked_content_ids:
                unchanged += 1
                continue

            cache_tv = (
                db.query(TmdbTvCache)
                .filter(TmdbTvCache.name == content.title)
                .first()
            )

            fuzzy_confidence = None
            if not cache_tv and content.production_year:
                from sqlalchemy import extract
                candidates = (
                    db.query(TmdbTvCache)
                    .filter(
                        extract("year", TmdbTvCache.first_air_date) == content.production_year
                    )
                    .limit(50)
                    .all()
                )
                best_ratio, best_cache = 0.0, None
                for cand in candidates:
                    ratio = difflib.SequenceMatcher(None, content.title, cand.name).ratio()
                    if ratio > best_ratio:
                        best_ratio, best_cache = ratio, cand
                if best_ratio >= 0.85:
                    cache_tv = best_cache
                    fuzzy_confidence = round(best_ratio, 4)

            if not cache_tv:
                continue

            try:
                raw = cache_tv.raw_json or {"tmdb_id": cache_tv.id, "name": cache_tv.name}
                _upsert_external_source(
                    db, content.id, ExternalSourceType.tmdb, str(cache_tv.id), raw
                )
                if fuzzy_confidence is not None:
                    src = (
                        db.query(ExternalMetaSource)
                        .filter(
                            ExternalMetaSource.content_id == content.id,
                            ExternalMetaSource.source_type == ExternalSourceType.tmdb,
                        )
                        .first()
                    )
                    if src:
                        src.match_confidence = fuzzy_confidence
                inserted += 1
                linked_content_ids.add(content.id)
            except Exception as exc:
                logger.warning(f"[tmdb_link] series content_id={content.id} 처리 실패: {exc}")
                errors += 1

        db.commit()

        log.items_inserted = inserted
        log.items_unchanged = unchanged
        log.errors = errors
        log.status = TmdbSyncStatus.completed if errors == 0 else TmdbSyncStatus.failed
        log.finished_at = datetime.utcnow()
        db.commit()

        logger.info(f"[tmdb_link] inserted={inserted} unchanged={unchanged} errors={errors}")
        return {"inserted": inserted, "unchanged": unchanged, "errors": errors}
    finally:
        db.close()


# ── Dam poster catch-up ───────────────────────────────────

@celery_app.task(name="workers.tasks.metadata.sync_primary_posters_to_dam")
def sync_primary_posters_to_dam():
    """
    Dam 포스터 catch-up Beat task (매일 06:00 KST).
    is_primary=True인 poster 이미지를 전수 조회해 Dam에 재발송.
    Dam 쪽에서 image_id 기준 중복 처리 — 안전하게 여러 번 호출 가능.
    """
    if not settings.DAM_POSTER_INGEST_URL:
        logger.info("[dam_poster_catchup] DAM_POSTER_INGEST_URL 미설정. 스킵.")
        return {"skipped": True}

    from api.programming.metadata.models import ContentImage, ImageType, Content
    db = SessionLocal()
    queued = 0
    try:
        rows = (
            db.query(ContentImage, Content)
            .join(Content, ContentImage.content_id == Content.id)
            .filter(
                ContentImage.image_type == ImageType.poster,
                ContentImage.is_primary == True,  # noqa: E712
                ContentImage.url.isnot(None),
            )
            .all()
        )
        occurred_at = datetime.utcnow().isoformat()
        for image, content in rows:
            send_dam_webhook.delay(
                event_type="poster_primary_set",
                content_id=content.id,
                title=content.title,
                content_type=(
                    content.content_type.value
                    if hasattr(content.content_type, "value")
                    else str(content.content_type)
                ),
                occurred_at=occurred_at,
                poster_url=image.url,
                poster_source=image.source or "tmdb",
                image_id=image.id,
            )
            queued += 1

        logger.info(f"[dam_poster_catchup] {queued}건 Dam 재발송 큐 등록")
        return {"queued": queued}
    except Exception as exc:
        logger.error(f"[dam_poster_catchup] 실패: {exc}")
        return {"error": str(exc)}
    finally:
        db.close()


# ── Dam changefeed webhook ─────────────────────────────────

@celery_app.task(name="workers.tasks.metadata.send_dam_webhook")
def send_dam_webhook(event_type: str, content_id: int, title: str,
                     content_type: str, occurred_at: str,
                     poster_url: str | None = None,
                     poster_source: str | None = None,
                     image_id: int | None = None):
    """Dam에 Content 변경 이벤트 발신 (best-effort).
    poster_primary_set 이벤트 시 DAM_POSTER_INGEST_URL로 포스터 등록 요청.
    """
    if event_type == "poster_primary_set":
        url = settings.DAM_POSTER_INGEST_URL
        if not url:
            return {"skipped": True, "reason": "DAM_POSTER_INGEST_URL not set"}
        try:
            resp = httpx.post(
                url,
                json={
                    "content_id": content_id,
                    "image_id": image_id,
                    "poster_url": poster_url,
                    "poster_source": poster_source or "tmdb",
                    "title": title,
                },
                timeout=10.0,
            )
            logger.info(f"[dam_poster_ingest] content_id={content_id} image_id={image_id} → {resp.status_code}")
            return {"status": resp.status_code}
        except Exception as exc:
            logger.warning(f"[dam_poster_ingest] 발신 실패 content_id={content_id}: {exc}")
            return {"error": str(exc)}

    url = settings.DAM_WEBHOOK_URL
    if not url:
        return {"skipped": True}
    try:
        resp = httpx.post(
            url,
            json={
                "event": event_type,
                "content_id": content_id,
                "title": title,
                "content_type": content_type,
                "occurred_at": occurred_at,
            },
            timeout=5.0,
        )
        logger.info(f"[dam_webhook] {event_type} content_id={content_id} → {resp.status_code}")
        return {"status": resp.status_code}
    except Exception as exc:
        logger.warning(f"[dam_webhook] 발신 실패 content_id={content_id}: {exc}")
        return {"error": str(exc)}


# ── KOBIS 캐시 → contents 링크 ────────────────────────────

@celery_app.task(name="workers.tasks.metadata.link_kobis_cache_to_contents", max_retries=0)
def link_kobis_cache_to_contents():
    """kobis_movie_cache 전체를 contents 에 title+year 매칭 후 ExternalMetaSource upsert.

    - 이미 external_meta_sources 에 source_type='kobis' + external_id=movie_cd 로 존재하면 스킵
    - 정확 매칭: Content.title == cache.title (movie 타입)
    - fuzzy 폴백: prdt_year 같은 후보군 중 SequenceMatcher ratio >= 0.85
    - 매일 07:45 KST Beat 에서 실행 (idempotent)
    """
    from api.programming.metadata.models import (
        Content, ContentType, ExternalMetaSource,
        ExternalSourceType, TmdbSyncLog, TmdbSyncSource, TmdbSyncStatus,
    )
    from api.programming.metadata.models.kobis_cache import KobisMovieCache
    from api.programming.metadata.ai_engine import _upsert_external_source

    db = SessionLocal()
    try:
        log = TmdbSyncLog(
            source=TmdbSyncSource.kobis_link,
            external_source=ExternalSourceType.kobis,
            status=TmdbSyncStatus.running,
        )
        db.add(log)
        db.commit()
        db.refresh(log)

        existing_cds = {
            row[0]
            for row in db.query(ExternalMetaSource.external_id)
            .filter(ExternalMetaSource.source_type == ExternalSourceType.kobis)
            .all()
        }

        caches = db.query(KobisMovieCache).all()
        log.items_fetched = len(caches)

        inserted = unchanged = errors = 0

        for cache in caches:
            if cache.movie_cd in existing_cds:
                unchanged += 1
                continue

            content = (
                db.query(Content)
                .filter(
                    Content.title == cache.title,
                    Content.content_type == ContentType.movie,
                )
                .first()
            )

            fuzzy_confidence: float | None = None
            if not content and cache.prdt_year:
                candidates = (
                    db.query(Content)
                    .filter(
                        Content.content_type == ContentType.movie,
                        Content.production_year == cache.prdt_year,
                    )
                    .all()
                )
                best_ratio, best_cand = 0.0, None
                for cand in candidates:
                    ratio = difflib.SequenceMatcher(None, cache.title, cand.title).ratio()
                    if ratio > best_ratio:
                        best_ratio, best_cand = ratio, cand
                if best_ratio >= 0.85:
                    content = best_cand
                    fuzzy_confidence = round(best_ratio, 4)

            if not content:
                continue

            try:
                raw = cache.raw_json or {"movie_cd": cache.movie_cd, "title": cache.title}
                _upsert_external_source(
                    db, content.id, ExternalSourceType.kobis, cache.movie_cd, raw
                )
                if fuzzy_confidence is not None:
                    src = (
                        db.query(ExternalMetaSource)
                        .filter(
                            ExternalMetaSource.content_id == content.id,
                            ExternalMetaSource.source_type == ExternalSourceType.kobis,
                        )
                        .first()
                    )
                    if src:
                        src.match_confidence = fuzzy_confidence
                inserted += 1
            except Exception as exc:
                logger.warning(f"[kobis_link] content_id={content.id} 처리 실패: {exc}")
                errors += 1

        db.commit()

        log.items_inserted = inserted
        log.items_unchanged = unchanged
        log.errors = errors
        log.status = TmdbSyncStatus.completed if errors == 0 else TmdbSyncStatus.failed
        log.finished_at = datetime.utcnow()
        db.commit()

        logger.info(f"[kobis_link] inserted={inserted} unchanged={unchanged} errors={errors}")
        return {"inserted": inserted, "unchanged": unchanged, "errors": errors}
    finally:
        db.close()
