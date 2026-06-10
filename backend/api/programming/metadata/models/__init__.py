"""
metadata models 패키지

기존 코드에서 `from api.programming.metadata.models import Content` 등으로
import 하던 것이 변경 없이 동작하도록 모든 모델을 re-export.
"""

# 콘텐츠 핵심 모델
from api.programming.metadata.models.content import (
    Content,
    ContentMetadata,
    CpEmailLog,
    ContentBatchJob,
    ContentActionLog,
    ContentAuditLog,
    ContentType,
    ContentStatus,
    MetaSource,
    PipelineStage,
    IntakeChannel,
    StageEventType,
    FailureCode,
)

# 파이프라인 이벤트 (ADR-006)
from api.programming.metadata.models.stage_event import StageEvent

# 분류 체계
from api.programming.metadata.models.taxonomy import (
    GenreCode,
    TagCode,
    ContentGenre,
    ContentTag,
    TagType,
)

# 인물
from api.programming.metadata.models.person import (
    PersonMaster,
    ContentCredit,
    CreditRole,
)

# 이미지
from api.programming.metadata.models.image import (
    ContentImage,
    ImageType,
)

# 외부 메타 소스 & AI 결과
from api.programming.metadata.models.external import (
    ExternalMetaSource,
    ContentAIResult,
    ExternalSourceType,
    AITaskType,
    AiTaskSetting,
    EnrichPolicy,
    StageAutoPolicy,
    FacetBatchRun,
    FacetEvent,
    FacetPolicy,
)

# TMDB 로컬 캐시
from api.programming.metadata.models.tmdb_cache import (
    TmdbMovieCache,
    TmdbTvCache,
    TmdbPersonCache,
    TmdbSyncLog,
    TmdbSyncSource,
    TmdbSyncStatus,
)

# KMDB 로컬 캐시
from api.programming.metadata.models.kmdb_cache import (
    KmdbMovieCache,
)

__all__ = [
    # content
    "Content", "ContentMetadata", "CpEmailLog", "ContentBatchJob", "ContentActionLog", "ContentAuditLog",
    "ContentType", "ContentStatus", "MetaSource",
    "PipelineStage", "IntakeChannel", "StageEventType", "FailureCode",
    # stage event
    "StageEvent",
    # taxonomy
    "GenreCode", "TagCode", "ContentGenre", "ContentTag", "TagType",
    # person
    "PersonMaster", "ContentCredit", "CreditRole",
    # image
    "ContentImage", "ImageType",
    # external
    "ExternalMetaSource", "ContentAIResult", "ExternalSourceType", "AITaskType", "AiTaskSetting", "EnrichPolicy", "StageAutoPolicy", "FacetBatchRun", "FacetEvent", "FacetPolicy",
    # tmdb cache
    "TmdbMovieCache", "TmdbTvCache", "TmdbPersonCache", "TmdbSyncLog",
    "TmdbSyncSource", "TmdbSyncStatus",
    # kmdb cache
    "KmdbMovieCache",
]
