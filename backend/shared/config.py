from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://media_ax:media_ax@localhost:5432/media_ax"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Elasticsearch
    ELASTICSEARCH_URL: str = "http://localhost:9200"

    # AI APIs
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "ap-northeast-2"

    # External APIs
    TMDB_API_KEY: str = ""
    KOBIS_API_KEY: str = ""
    KMDB_API_KEY: str = ""        # 영화상세정보 (kmdb_new2 컬렉션)
    KMDB_KOFA_API_KEY: str = ""   # 시네마테크KOFA 상영일정 (별도 공공데이터포털 API)
    OMDB_API_KEY: str = ""

    # Phase D — WebSearch keys
    BRAVE_SEARCH_API_KEY: str = ""
    SERPAPI_KEY: str = ""

    # Phase D — WebSearch control
    WEBSEARCH_ENABLED: bool = True
    WEBSEARCH_BULK_ALLOWED: bool = False
    WEBSEARCH_PROVIDERS: str = "brave,serpapi,gemini,ollama"  # CSV
    WEBSEARCH_BRAVE_DAILY: int = 60
    WEBSEARCH_SERPAPI_DAILY: int = 3
    WEBSEARCH_GEMINI_DAILY: int = 200
    WEBSEARCH_TRENDING_ENABLED: bool = False

    # Ollama
    OLLAMA_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2:3b"
    # AI Task(번역/요약/분류) 전용 경량 instruct 모델 — reasoning 모델(qwen3) 회피
    OLLAMA_TASK_MODEL: str = "qwen2.5:3b"

    # Multi-provider LLM
    AI_ENGINE: str = "gemini"      # gemini | groq | ollama
    GOOGLE_API_KEY: str = ""
    GROQ_API_KEY: str = ""

    # MediSearch facet 배치 통합
    MEDISEARCH_URL: str = "http://medisearch-api:8000"
    MEDISEARCH_TIMEOUT_S: int = 420       # 콘텐츠 1건 평가 최악 ~5분 + 여유
    FACET_BATCH_ENABLED: bool = False     # beat 야간 배치 opt-in (수동 트리거는 무관)
    FACET_BATCH_SIZE: int = 100           # run당 처리 상한
    FACET_STALENESS_DAYS: int = 180       # final facet이 이보다 오래되면 재평가 대상

    # Dam integration
    DAM_WEBHOOK_URL: str = ""
    DAM_POSTER_INGEST_URL: str = ""

    # IMAP (CP 이메일 폴링)
    IMAP_HOST: str = ""
    IMAP_USER: str = ""
    IMAP_PASS: str = ""

    # Auth
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8

    # Pipeline Test Console (dev only)
    ENABLE_PIPELINE_TEST: bool = False
    PIPELINE_TEST_ADMIN_KEY: str = ""   # 비어 있으면 토큰 검증 스킵 (ENABLE_PIPELINE_TEST=True 시만 유효)

    class Config:
        env_file = ".env"


settings = Settings()
