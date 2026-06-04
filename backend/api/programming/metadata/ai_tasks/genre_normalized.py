"""GenreNormalizedTask — 표준 장르 분류 (ADR-007 Phase1)"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from api.programming.metadata.ai_tasks.base import AiTask, TaskInput, TaskOutput
from api.programming.metadata.ai_tasks._utils import call_with_chain, extract_json

if TYPE_CHECKING:
    from api.programming.metadata.models import ContentMetadata

logger = logging.getLogger(__name__)

# ai_engine.py의 GENRES와 동기화 유지
GENRES = [
    "액션", "드라마", "코미디", "로맨스", "스릴러", "공포", "SF", "판타지",
    "애니메이션", "다큐멘터리", "예능", "키즈", "교육", "스포츠", "음악",
    "역사", "범죄", "미스터리", "어드벤처", "전쟁",
]

_SYSTEM = "You are a content genre classifier. Output only valid JSON, no explanation."

_PROMPT_TMPL = """\
Classify this content into genres from the list below.

Available genres: {genres}

Title: {title}
Synopsis: {synopsis}

Output JSON:
{{"genre_primary": "<one genre from the list>", "genre_secondary": "<one genre or null>"}}"""


class GenreNormalizedTask(AiTask):
    name = "genre_normalized"

    def build_input(self, meta: "ContentMetadata") -> TaskInput | None:
        if meta.ai_genre_primary and meta.ai_genre_secondary:
            return None
        synopsis = meta.synopsis_ko or meta.cp_synopsis or meta.ai_synopsis or ""
        if not synopsis and not meta.ai_genre_primary:
            return None
        return TaskInput(
            content_id=meta.content_id,
            task_name=self.name,
            payload={
                "title": getattr(meta, "content", None) and meta.content.title or "",
                "synopsis": synopsis[:1000],
                "cp_genre": meta.cp_genre or "",
            },
        )

    async def run(self, task_input: TaskInput, provider_chain: list) -> TaskOutput:
        payload = task_input.payload
        synopsis = payload.get("synopsis") or payload.get("cp_genre") or ""
        prompt = _PROMPT_TMPL.format(
            genres=", ".join(GENRES),
            title=payload.get("title", ""),
            synopsis=synopsis,
        )
        text, engine = await call_with_chain(prompt, _SYSTEM, provider_chain)
        data = extract_json(text) or {}
        genre_primary = data.get("genre_primary", "") if isinstance(data, dict) else ""
        genre_secondary = data.get("genre_secondary") if isinstance(data, dict) else None

        # 유효성 검사: 정의된 장르 목록에 없으면 무시
        if genre_primary not in GENRES:
            genre_primary = GENRES[0]
        if genre_secondary and genre_secondary not in GENRES:
            genre_secondary = None

        return TaskOutput(
            result={"genre_primary": genre_primary, "genre_secondary": genre_secondary},
            engine=engine,
        )

    def apply(self, meta: "ContentMetadata", output: TaskOutput) -> None:
        result = output.result
        if not meta.ai_genre_primary:
            meta.ai_genre_primary = result.get("genre_primary", "")
        if not meta.ai_genre_secondary and result.get("genre_secondary"):
            meta.ai_genre_secondary = result["genre_secondary"]


genre_normalized_task = GenreNormalizedTask()
