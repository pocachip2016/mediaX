"""
1.1 메타데이터 Celery 태스크

태스크 목록:
  - process_content_metadata  : 콘텐츠 AI 처리 (장르/시놉시스/태그/스코어)
  - poll_cp_emails             : CP 이메일 폴링 (5분 주기 Beat)
  - sync_kobis                 : 영진위 KOBIS 일일 동기화
  - sync_tmdb                  : TMDB 주간 동기화
  - reeval_quality_scores      : 메타 품질 재평가 배치
"""

import asyncio
import imaplib
import email
import logging
from email.header import decode_header
from datetime import datetime

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
    """영진위 KOBIS 일일 동기화 (매일 03:00)"""
    logger.info("[kobis] KOBIS 동기화 시작")
    # TODO: 전일 신규 등록 영화 조회 → 기존 콘텐츠 매핑 업데이트
    return {"status": "ok"}


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
        from api.programming.metadata.models import ContentMetadata, Content, ContentStatus
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
