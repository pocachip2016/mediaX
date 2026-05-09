"""
meta_core 모델 re-export

물리적 파일은 api.programming.metadata.models.* 에 있으며,
이 패키지는 meta_core 경계에서 canonical 모델만 노출한다.
ContentMetadata·CpEmailLog·ContentBatchJob 은 service_kt 영역이므로 제외.
"""

from api.programming.metadata.models.content import (
    Content,
    ContentType,
    ContentStatus,
    MetaSource,
)
from api.programming.metadata.models.person import (
    PersonMaster,
    ContentCredit,
    CreditRole,
)
from api.programming.metadata.models.taxonomy import (
    GenreCode,
    TagCode,
    ContentGenre,
    ContentTag,
    TagType,
)
from api.programming.metadata.models.image import (
    ContentImage,
    ImageType,
)
from api.programming.metadata.models.external import (
    ExternalMetaSource,
    ExternalSourceType,
    ContentAIResult,
    AITaskType,
)
from api.programming.metadata.models.tmdb_cache import (
    TmdbMovieCache,
    TmdbTvCache,
    TmdbPersonCache,
    TmdbSyncLog,
    TmdbSyncSource,
    TmdbSyncStatus,
    WebSearchCache,
)
from api.meta_core.models.intelligence import (
    MetadataCandidate,
    MatchEdge,
    FieldSuggestion,
    FieldResolution,
    SeedCandidate,
)

__all__ = [
    # content master
    "Content", "ContentType", "ContentStatus", "MetaSource",
    # person
    "PersonMaster", "ContentCredit", "CreditRole",
    # taxonomy
    "GenreCode", "TagCode", "ContentGenre", "ContentTag", "TagType",
    # image
    "ContentImage", "ImageType",
    # external meta source
    "ExternalMetaSource", "ExternalSourceType", "ContentAIResult", "AITaskType",
    # tmdb cache + web search cache
    "TmdbMovieCache", "TmdbTvCache", "TmdbPersonCache",
    "TmdbSyncLog", "TmdbSyncSource", "TmdbSyncStatus",
    "WebSearchCache",
    # meta intelligence
    "MetadataCandidate", "MatchEdge", "FieldSuggestion", "FieldResolution", "SeedCandidate",
]
