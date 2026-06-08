"""semantic_profile.py — Content Understanding Profile Beat 태스크.

build_semantic_profiles: 신규/변경 콘텐츠에 대해 profile_service.build_profile 실행.
  - 이미 최신 model_version인 콘텐츠는 건너뜀 (멱등)
  - BATCH_SIZE씩 처리, 커밋
  - off-peak Beat (매일 03:30 KST) 등록
"""
import logging

from celery import shared_task

from shared.database import SessionLocal

logger = logging.getLogger(__name__)

BATCH_SIZE = 50


@shared_task(name="workers.tasks.semantic_profile.build_semantic_profiles", bind=True, max_retries=0)
def build_semantic_profiles(self):
    """신규/model_version 미일치 콘텐츠 프로파일 일괄 생성."""
    import asyncio
    from api.programming.metadata.models.content import Content
    from api.programming.scheduling.profile_models import ContentSemanticProfile
    from api.programming.scheduling.profile_service import MODEL_VERSION, build_profile

    db = SessionLocal()
    inserted = updated = skipped = errors = 0
    try:
        # 프로파일 없거나 model_version 구버전인 content_id
        profiled_current = (
            db.query(ContentSemanticProfile.content_id)
            .filter(ContentSemanticProfile.model_version == MODEL_VERSION)
            .subquery()
        )
        target_ids = [
            row.id
            for row in db.query(Content.id)
            .filter(Content.id.notin_(profiled_current))
            .limit(BATCH_SIZE)
            .all()
        ]

        if not target_ids:
            logger.info("[semantic_profile] 갱신 대상 없음")
            return {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}

        for content_id in target_ids:
            try:
                existing_before = (
                    db.query(ContentSemanticProfile)
                    .filter(ContentSemanticProfile.content_id == content_id)
                    .first()
                )
                profile = asyncio.run(build_profile(db, content_id))
                if profile is None:
                    skipped += 1
                    continue
                if existing_before is None:
                    inserted += 1
                else:
                    updated += 1
                db.commit()
            except Exception as e:
                db.rollback()
                errors += 1
                logger.warning("[semantic_profile] content_id=%s 실패: %s", content_id, e)

        result = {"inserted": inserted, "updated": updated, "skipped": skipped, "errors": errors}
        logger.info("[semantic_profile] 완료: %s", result)
        return result
    finally:
        db.close()
