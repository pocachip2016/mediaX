"""ShortSynopsisTask — 줄거리 2~3문장 요약 (ADR-007 Phase1)"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from api.programming.metadata.ai_tasks.base import AiTask, TaskInput, TaskOutput
from api.programming.metadata.ai_tasks._utils import call_with_chain

if TYPE_CHECKING:
    from api.programming.metadata.models import ContentMetadata

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are a professional content summarizer. "
    "Summarize the given synopsis into 2-3 concise sentences in the SAME language as the input. "
    "Output only the summary, no explanation or commentary."
)


def _get_synopsis(meta: "ContentMetadata") -> str | None:
    return meta.synopsis_ko or meta.cp_synopsis or meta.ai_synopsis or meta.synopsis_en or None


class ShortSynopsisTask(AiTask):
    name = "short_synopsis"

    def build_input(self, meta: "ContentMetadata") -> TaskInput | None:
        if meta.short_synopsis:
            return None
        source = _get_synopsis(meta)
        if not source or len(source.strip()) < 20:
            return None
        return TaskInput(
            content_id=meta.content_id,
            task_name=self.name,
            payload={"synopsis": source[:1500]},
        )

    async def run(self, task_input: TaskInput, provider_chain: list) -> TaskOutput:
        prompt = f"Summarize in 2-3 sentences:\n\n{task_input.payload['synopsis']}"
        text, engine = await call_with_chain(prompt, _SYSTEM, provider_chain)
        return TaskOutput(result={"short_synopsis": text}, engine=engine)

    def apply(self, meta: "ContentMetadata", output: TaskOutput) -> None:
        meta.short_synopsis = output.result.get("short_synopsis", "")


short_synopsis_task = ShortSynopsisTask()
