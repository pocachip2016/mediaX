"""
Batch upload service — CSV/Excel import processing.

service.py 분할 과정에서 추출 (dev-service-module-split Step 5).
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from api.programming.metadata.models import (
    Content, ContentMetadata, ContentBatchJob,
    ContentStatus, ContentType,
    ExternalMetaSource,
)


def create_batch_job(
    db: Session,
    file_name: str,
    cp_name: Optional[str],
    created_by: Optional[str],
    file_size: Optional[int] = None,
) -> ContentBatchJob:
    job = ContentBatchJob(
        job_name=f"배치업로드_{file_name}",
        cp_name=cp_name,
        file_name=file_name,
        file_size_bytes=file_size,
        status="pending",
        created_by=created_by,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _process_movie_row(
    db: Session,
    row: dict,
    job: "ContentBatchJob",
    idx: int,
    errors: list,
    auto_process: bool = True,
) -> str:
    """단건 movie 행 → Content(raw) 평면 insert.

    반환: 'success' | 'skipped' (dedup 중복) | 'failed'
    runtime 컬럼 값이 양의 정수이면 Content.runtime_minutes에 매핑한다.
    """
    from api.programming.metadata.models.external import ExternalSourceType
    from api.programming.metadata.service_recommendations import resolve_metadata
    from api.programming.metadata.service_meta import add_content_image
    from workers.tasks.metadata import process_content_metadata

    try:
        title = (row.get("title") or "").strip()
        if not title:
            raise ValueError("제목 없음")

        cp_name = row.get("cp_name") or job.cp_name
        production_year = row.get("production_year")
        runtime_raw = row.get("runtime")
        runtime_val = runtime_raw if isinstance(runtime_raw, int) and runtime_raw > 0 else None
        raw_json = {k: v for k, v in {
            "title": title,
            "synopsis": row.get("synopsis") or row.get("cp_synopsis"),
            "cast": row.get("cast"),
            "directors": row.get("directors"),
            "genres": row.get("genres"),
            "country": row.get("country"),
            "runtime": runtime_val,
            "rating_age": row.get("rating_age"),
            "poster_url": row.get("poster_url"),
            "production_year": production_year,
            "audio_channels": row.get("audio_channels"),
            "video_resolution": row.get("video_resolution"),
            "extra_metadata": row.get("extra_metadata"),
        }.items() if v}

        row_content_type = ContentType(row.get("content_type") or "movie")
        existing = (
            db.query(Content)
            .filter(
                Content.title == title,
                Content.production_year == production_year,
                Content.cp_name == cp_name,
                Content.content_type == row_content_type,
            )
            .first()
        )

        if existing:
            ext_src = (
                db.query(ExternalMetaSource)
                .filter(
                    ExternalMetaSource.content_id == existing.id,
                    ExternalMetaSource.source_type == ExternalSourceType.bulk_upload,
                )
                .first()
            )
            if ext_src:
                merged = dict(ext_src.raw_json or {})
                for k, v in raw_json.items():
                    if v and not merged.get(k):
                        merged[k] = v
                ext_src.raw_json = merged
                ext_src.matched_at = datetime.utcnow()
            else:
                db.add(ExternalMetaSource(
                    content_id=existing.id,
                    source_type=ExternalSourceType.bulk_upload,
                    raw_json=raw_json,
                    matched_at=datetime.utcnow(),
                ))
            db.flush()
            return "skipped"

        content = Content(
            title=title,
            content_type=row_content_type,
            status=ContentStatus.raw,
            cp_name=cp_name,
            production_year=production_year,
            runtime_minutes=runtime_val,
        )
        db.add(content)
        db.flush()

        meta = ContentMetadata(
            content_id=content.id,
            quality_score=0.0,
            audio_channels=row.get("audio_channels") or None,
            video_resolution=row.get("video_resolution") or None,
            extra_metadata=row.get("extra_metadata") or None,
        )
        db.add(meta)
        db.flush()

        ext_src = ExternalMetaSource(
            content_id=content.id,
            source_type=ExternalSourceType.bulk_upload,
            raw_json=raw_json,
            matched_at=datetime.utcnow(),
        )
        db.add(ext_src)
        db.flush()

        resolve_metadata(db, content.id)

        if row.get("poster_url"):
            add_content_image(db, content.id, "poster", row["poster_url"], source="cp")

        if auto_process:
            process_content_metadata.delay(content.id)
        return "success"

    except Exception as exc:
        errors.append({"row": idx + 1, "title": row.get("title", ""), "error": str(exc)})
        return "failed"


def _process_series_rows(
    db: Session,
    job: "ContentBatchJob",
    rows: list[dict],
    errors: list,
    auto_process: bool = True,
) -> dict:
    """series 계층 bulk insert.

    rows의 series_title(없으면 title) 기준 그룹핑 후 series→season→episode upsert.
    parent_id 자동 링크. 메타는 raw_json에만 저장, read-time 상속(D3)으로 해석.
    Celery 트리거는 series 노드만 (episode 개별 외부조회 폭주 방지).
    """
    from collections import defaultdict
    from api.programming.metadata.models.external import ExternalSourceType
    from api.programming.metadata.service_recommendations import resolve_metadata
    from workers.tasks.metadata import process_content_metadata

    success = 0
    failed = 0
    skipped_duplicates = 0

    groups: dict[str, list[dict]] = defaultdict(list)
    for i, row in enumerate(rows):
        series_title = (row.get("series_title") or row.get("title") or "").strip()
        if not series_title:
            errors.append({"row": i + 1, "title": "", "error": "series_title 없음"})
            failed += 1
            continue
        groups[series_title].append(row)

    for series_title, group_rows in groups.items():
        try:
            cp_name = next(
                (r.get("cp_name") for r in group_rows if r.get("cp_name")), None
            ) or job.cp_name
            production_year = next(
                (r.get("production_year") for r in group_rows if r.get("production_year")), None
            )

            series_meta_row = next(
                (r for r in group_rows
                 if not r.get("season_number") and not r.get("episode_number")),
                group_rows[0],
            )
            series_raw_json = {k: v for k, v in {
                "title": series_title,
                "synopsis": series_meta_row.get("synopsis") or series_meta_row.get("cp_synopsis"),
                "cast": series_meta_row.get("cast"),
                "directors": series_meta_row.get("directors"),
                "genres": series_meta_row.get("genres"),
                "country": series_meta_row.get("country"),
                "rating_age": series_meta_row.get("rating_age"),
                "poster_url": series_meta_row.get("poster_url"),
                "production_year": production_year,
            }.items() if v}

            series = (
                db.query(Content)
                .filter(
                    Content.title == series_title,
                    Content.cp_name == cp_name,
                    Content.content_type == ContentType.series,
                )
                .first()
            )
            if not series:
                series = Content(
                    title=series_title,
                    content_type=ContentType.series,
                    status=ContentStatus.raw,
                    cp_name=cp_name,
                    production_year=production_year,
                )
                db.add(series)
                db.flush()
                db.add(ContentMetadata(content_id=series.id, quality_score=0.0))
                db.add(ExternalMetaSource(
                    content_id=series.id,
                    source_type=ExternalSourceType.bulk_upload,
                    raw_json=series_raw_json,
                    matched_at=datetime.utcnow(),
                ))
                db.flush()
                resolve_metadata(db, series.id)
                if auto_process:
                    process_content_metadata.delay(series.id)
                success += 1
            else:
                skipped_duplicates += 1

            for row in group_rows:
                season_num_raw = row.get("season_number")
                ep_num_raw = row.get("episode_number")
                if not season_num_raw:
                    continue

                try:
                    season_num = int(season_num_raw)
                    ep_num = int(ep_num_raw) if ep_num_raw else None

                    season = (
                        db.query(Content)
                        .filter(
                            Content.parent_id == series.id,
                            Content.content_type == ContentType.season,
                            Content.season_number == season_num,
                        )
                        .first()
                    )
                    if not season:
                        season_title = (
                            row.get("title") if not ep_num else None
                        ) or f"{series_title} 시즌 {season_num}"
                        season = Content(
                            title=season_title,
                            content_type=ContentType.season,
                            status=ContentStatus.raw,
                            parent_id=series.id,
                            season_number=season_num,
                            cp_name=cp_name,
                        )
                        db.add(season)
                        db.flush()
                        db.add(ContentMetadata(content_id=season.id, quality_score=0.0))
                        db.flush()
                        success += 1

                    if not ep_num:
                        continue

                    episode = (
                        db.query(Content)
                        .filter(
                            Content.parent_id == season.id,
                            Content.content_type == ContentType.episode,
                            Content.episode_number == ep_num,
                        )
                        .first()
                    )
                    if not episode:
                        ep_title = (
                            row.get("title")
                            or f"{series_title} S{season_num:02d}E{ep_num:02d}"
                        )
                        runtime_raw = row.get("runtime")
                        ep_runtime = (
                            runtime_raw
                            if isinstance(runtime_raw, int) and runtime_raw > 0
                            else None
                        )
                        ep_raw_json = {k: v for k, v in {
                            "title": ep_title,
                            "synopsis": row.get("synopsis"),
                            "runtime": ep_runtime,
                        }.items() if v}
                        episode = Content(
                            title=ep_title,
                            content_type=ContentType.episode,
                            status=ContentStatus.raw,
                            parent_id=season.id,
                            season_number=season_num,
                            episode_number=ep_num,
                            cp_name=cp_name,
                            runtime_minutes=ep_runtime,
                        )
                        db.add(episode)
                        db.flush()
                        db.add(ContentMetadata(content_id=episode.id, quality_score=0.0))
                        if ep_raw_json:
                            db.add(ExternalMetaSource(
                                content_id=episode.id,
                                source_type=ExternalSourceType.bulk_upload,
                                raw_json=ep_raw_json,
                                matched_at=datetime.utcnow(),
                            ))
                        db.flush()
                        success += 1

                except Exception as exc:
                    errors.append({
                        "row": 0,
                        "title": row.get("title", series_title),
                        "error": str(exc),
                    })
                    failed += 1

        except Exception as exc:
            errors.append({"row": 0, "title": series_title, "error": str(exc)})
            failed += 1

    return {"success": success, "failed": failed, "skipped_duplicates": skipped_duplicates}


def process_batch_rows(
    db: Session,
    job: ContentBatchJob,
    rows: list[dict],
    auto_process: bool = True,
) -> dict:
    """파싱된 배치 행 → movie/series 경로 분리 후 처리.

    movie: _process_movie_row 평면 insert + runtime_minutes 매핑.
    series/season/episode: _process_series_rows 위임 (Step 9 구현).
    Dedup 키: (title, production_year, cp_name, content_type).
    """
    from api.programming.metadata.content_kind import is_tv_type

    job.status = "processing"
    job.total_count = len(rows)
    db.flush()

    success = 0
    failed = 0
    skipped_duplicates = 0
    errors = []

    movie_rows = [(i, row) for i, row in enumerate(rows)
                  if not is_tv_type(row.get("content_type") or "movie")]
    tv_rows = [row for row in rows
               if is_tv_type(row.get("content_type") or "movie")]

    for i, row in movie_rows:
        result = _process_movie_row(db, row, job, i, errors, auto_process=auto_process)
        if result == "success":
            success += 1
        elif result == "skipped":
            skipped_duplicates += 1
        else:
            failed += 1

    if tv_rows:
        tv_result = _process_series_rows(db, job, tv_rows, errors, auto_process=auto_process)
        success += tv_result["success"]
        failed += tv_result["failed"]
        skipped_duplicates += tv_result["skipped_duplicates"]

    job.success_count = success
    job.failed_count = failed
    job.error_log = errors
    job.status = "done"
    job.finished_at = datetime.utcnow()
    job.parsed_count = len(rows)
    db.commit()

    return {
        "success": success,
        "failed": failed,
        "skipped_duplicates": skipped_duplicates,
        "job_id": job.id,
    }
