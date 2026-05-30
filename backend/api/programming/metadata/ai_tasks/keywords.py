"""KeywordsTask — 키워드 추출 (ADR-007 Phase1)"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from api.programming.metadata.ai_tasks.base import AiTask, TaskInput, TaskOutput
from api.programming.metadata.ai_tasks._utils import call_with_chain, extract_json

if TYPE_CHECKING:
    from api.programming.metadata.models import ContentMetadata

logger = logging.getLogger(__name__)

_SYSTEM = "You are a keyword extractor. Output only a valid JSON array of keywords, no explanation."

_PROMPT_TMPL = """\
Extract 5-10 important keywords from this content. Use the same language as the synopsis.

Title: {title}
Synopsis: {synopsis}

Output JSON array: ["keyword1", "keyword2", ...]"""


class KeywordsTask(AiTask):
    name = "keywords"

    def build_input(self, meta: "ContentMetadata") -> TaskInput | None:
        if meta.ai_keywords:
            return None
        synopsis = meta.synopsis_ko or meta.cp_synopsis or meta.ai_synopsis or ""
        if not synopsis or len(synopsis.strip()) < 20:
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
            title=payload.get("title", ""),
            synopsis=payload.get("synopsis", ""),
        )
        text, engine = await call_with_chain(prompt, _SYSTEM, provider_chain)
        keywords = extract_json(text)
        if not isinstance(keywords, list):
            keywords = []
        # 문자열만, 최대 10개
        keywords = [str(k).strip() for k in keywords if k and isinstance(k, str)][:10]

        return TaskOutput(result={"keywords": keywords}, engine=engine)

    def apply(self, meta: "ContentMetadata", output: TaskOutput) -> None:
        if not meta.ai_keywords:
            meta.ai_keywords = output.result.get("keywords", [])


keywords_task = KeywordsTask()
