"""
AI Task 플러그인 레지스트리

AI_TASK_REGISTRY: task_name → AiTask 인스턴스
신규 task는 이 dict에 등록만 하면 Runner가 자동으로 실행.
"""

from api.programming.metadata.ai_tasks.base import AiTask, TaskInput, TaskOutput

AI_TASK_REGISTRY: dict[str, AiTask] = {}


def register_task(task: AiTask) -> None:
    """task를 레지스트리에 등록."""
    AI_TASK_REGISTRY[task.name] = task


# ── Phase1 task 등록 ──────────────────────────────────────
from api.programming.metadata.ai_tasks.translate_synopsis import translate_synopsis_task  # noqa: E402
from api.programming.metadata.ai_tasks.short_synopsis import short_synopsis_task  # noqa: E402
from api.programming.metadata.ai_tasks.genre_normalized import genre_normalized_task  # noqa: E402
from api.programming.metadata.ai_tasks.mood_tags import mood_tags_task  # noqa: E402
from api.programming.metadata.ai_tasks.keywords import keywords_task  # noqa: E402

register_task(translate_synopsis_task)
register_task(short_synopsis_task)
register_task(genre_normalized_task)
register_task(mood_tags_task)
register_task(keywords_task)


__all__ = ["AiTask", "TaskInput", "TaskOutput", "AI_TASK_REGISTRY", "register_task"]
