"""MoodTagsTask — 감성 태그 분류 (ADR-007 Phase1)"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from api.programming.metadata.ai_tasks.base import AiTask, TaskInput, TaskOutput
from api.programming.metadata.ai_tasks._utils import call_with_chain, extract_json

if TYPE_CHECKING:
    from api.programming.metadata.models import ContentMetadata

logger = logging.getLogger(__name__)

# ai_engine.py의 MOOD_TAGS와 동기화 유지
MOOD_TAGS = [
    "따뜻한", "긴장감", "가족과함께", "심야감성", "액션몰입", "힐링",
    "웃음보장", "눈물주의", "반전있음", "실화기반", "청춘", "성장",
    "복수극", "사랑이야기", "인간드라마",
]

_SYSTEM = "You are a content mood tagger. Output only a valid JSON array, no explanation."

_PROMPT_TMPL = """\
Select 3-5 mood tags for this content.

Available tags: {tags}

Title: {title}
Synopsis: {synopsis}

Output JSON array of 3-5 tags: ["tag1", "tag2", ...]"""


class MoodTagsTask(AiTask):
    name = "mood_tags"

    def build_input(self, meta: "ContentMetadata") -> TaskInput | None:
        if meta.ai_mood_tags:
            return None
        synopsis = meta.synopsis_ko or meta.cp_synopsis or meta.ai_synopsis or ""
        if not synopsis:
            return None
        title = getattr(meta, "content", None) and meta.content.title or ""
        return TaskInput(
            content_id=meta.content_id,
            task_name=self.name,
            payload={"title": title, "synopsis": synopsis[:1000]},
        )

    async def run(self, task_input: TaskInput, provider_chain: list) -> TaskOutput:
        payload = task_input.payload
        prompt = _PROMPT_TMPL.format(
            tags=", ".join(MOOD_TAGS),
            title=payload.get("title", ""),
            synopsis=payload.get("synopsis", ""),
        )
        text, engine = await call_with_chain(prompt, _SYSTEM, provider_chain)
        tags = extract_json(text)
        if not isinstance(tags, list):
            tags = []
        # 정의된 태그만 허용
        tags = [t for t in tags if t in MOOD_TAGS][:5]

        return TaskOutput(result={"mood_tags": tags}, engine=engine)

    def apply(self, meta: "ContentMetadata", output: TaskOutput) -> None:
        if not meta.ai_mood_tags:
            meta.ai_mood_tags = output.result.get("mood_tags", [])


mood_tags_task = MoodTagsTask()
