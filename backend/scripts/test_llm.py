"""LLM 엔진 테스트 스크립트"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.programming.metadata.ai_engine import _generate_metadata_with_engine
from api.programming.metadata.schemas import AIGenerateRequest
from shared.database import SessionLocal


async def main():
    req = AIGenerateRequest(
        title="기생충",
        production_year=2019,
        cp_name="CJ ENM",
        cp_synopsis="전원 백수인 기택 가족이 부유한 박 사장 가족의 집에 하나둘 침투하면서 벌어지는 이야기.",
    )
    db = SessionLocal()
    try:
        result, engine = await _generate_metadata_with_engine(req, db)
        print(f"사용 엔진: {engine}")
        print(f"장르: {result.genre_primary} / {result.genre_secondary}")
        print(f"태그: {result.mood_tags}")
        print(f"등급: {result.rating_suggestion}")
        print(f"품질: {result.quality_score}점")
        print(f"시놉시스({len(result.synopsis)}자): {result.synopsis[:150]}")
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
