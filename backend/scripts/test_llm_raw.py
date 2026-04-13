"""Gemini 원본 응답 확인용"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.programming.metadata.llm.gemini import GeminiProvider
from api.programming.metadata.ai_engine import GENRES, MOOD_TAGS, RATING_OPTIONS


async def main():
    p = GeminiProvider()
    system_prompt = (
        "당신은 한국 OTT 플랫폼 지니TV의 콘텐츠 메타데이터 전문가입니다. "
        "주어진 콘텐츠 정보를 바탕으로 정확한 메타데이터를 JSON 형식으로 생성하세요."
    )
    user_prompt = f"""다음 콘텐츠의 메타데이터를 생성해 주세요.

제목: 기생충
제작연도: 2019
CP사: CJ ENM
기존 시놉시스: 전원 백수인 기택 가족이 부유한 박 사장 가족의 집에 하나둘 침투하면서 벌어지는 이야기.

아래 JSON 형식으로만 응답하세요:
```json
{{
  "synopsis": "200자 이상의 상세 시놉시스",
  "genre_primary": "{' | '.join(GENRES[:10])} 중 하나",
  "genre_secondary": "{' | '.join(GENRES[10:])} 중 하나 또는 null",
  "mood_tags": ["태그1", "태그2", "태그3"],
  "rating_suggestion": "{' | '.join(RATING_OPTIONS)} 중 하나"
}}
```

mood_tags는 다음 중에서 3~5개 선택: {', '.join(MOOD_TAGS)}"""

    raw = await p.generate(user_prompt, system_prompt)
    print("=== RAW RESPONSE ===")
    print(repr(raw))
    print()
    print("=== FORMATTED ===")
    print(raw)


if __name__ == "__main__":
    asyncio.run(main())
