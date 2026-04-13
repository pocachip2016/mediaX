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
    ContentType,
    ContentStatus,
    MetaSource,
)

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
)

__all__ = [
    # content
    "Content", "ContentMetadata", "CpEmailLog", "ContentBatchJob",
    "ContentType", "ContentStatus", "MetaSource",
    # taxonomy
    "GenreCode", "TagCode", "ContentGenre", "ContentTag", "TagType",
    # person
    "PersonMaster", "ContentCredit", "CreditRole",
    # image
    "ContentImage", "ImageType",
    # external
    "ExternalMetaSource", "ContentAIResult", "ExternalSourceType", "AITaskType",
]
