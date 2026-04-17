# mediaX — Claude Code 효율화 가이드

> 작성일: 2026-04-17  
> 목적: 대규모 프로젝트에서 Claude Code 토큰 소비를 최소화하고 구현 생산성을 극대화하기 위한 체계

---

## 1. 토큰 소비 구조 분석 (이 프로젝트 기준)

| 소비원 | 규모 | 특성 |
|---|---|---|
| CLAUDE.md 17개 | 845줄 | 세션 시작 시 **자동 전부 로드** — 고정 비용 |
| docs/*.md 128개 | 3,651줄 | 참조 시만 소비, 한 번에 여럿 읽히면 큰 비용 |
| research.md (삭제됨) | 29개 | 탐색 시 노이즈 — 삭제 완료 |
| 소스 코드 파일 | service.py 1,100+줄 | 전체 읽기 시 1회에 큰 비용 |
| 대화 기록 | 누적 | 세션이 길수록 기하급수적 증가 |

**핵심 인사이트**: 매 세션마다 "전체 파악 → 해당 부분 찾기 → 구현" 패턴에서 토큰의 60~70%를 탐색에 소비. `plans/` 체계와 `.claudeignore`로 해소.

---

## 2. 모듈 구현 파이프라인

모든 신규 모듈 구현은 이 파이프라인을 따른다.

```
docs/{모듈}/ (설계 확정)
    ↓ [Phase A: 계획]
plans/{모듈}_plan.md 작성 (범위·파일 목록·의존성·세션 분할)
    ↓ [Phase B: 구현 — 모듈당 세션 2~4개]
backend/api/{모듈}/ + mediaX-CMS/apps/web/app/(main)/{모듈}/
    ↓ [Phase C: 테스트]
backend/tests/api/{모듈}/test_service.py
    ↓ [Phase D: 완료]
plans/{모듈}_plan.md 상태 → done
docs/9_todo/9.0_todo.md 갱신
CLAUDE.md 업데이트 (필요 시)
```

---

## 3. plans/ 체계

### 3.1 디렉토리 구조

```
mediaX/plans/
├── README.md               ← 파이프라인 규칙 + 세션 프롬프트 템플릿
├── programming/
│   ├── 1.1_metadata.md     ← ✅ done
│   ├── 1.2_catalog.md      ← 다음 구현 대상
│   └── ...
├── ingest/
├── marketing/
└── common/
```

### 3.2 plan 파일 템플릿

```markdown
# {모듈명} 구현 계획
상태: planning | in-progress | done
마지막 수정: YYYY-MM-DD

## 범위
- 설계 문서: docs/{경로}/
- 핵심 기능 3줄 요약

## 백엔드 파일
- [ ] api/{모듈}/models.py — 테이블 N개
- [ ] api/{모듈}/schemas.py
- [ ] api/{모듈}/service.py — 핵심 비즈니스 로직
- [ ] api/{모듈}/router.py — 엔드포인트 N개
- [ ] alembic/versions/XXXX_{모듈}.py

## 프론트 파일
- [ ] app/(main)/{경로}/page.tsx
- [ ] lib/api.ts 추가 함수 목록

## 의존성
- 선행 모듈: (예: 1.1 metadata — Content 모델 공유)
- 외부 API: 없음 / TMDB / KOBIS

## 테스트
- [ ] tests/api/{모듈}/test_service.py
- 핵심 케이스: (목록)

## 세션 분할 계획
- 세션 1: 모델+서비스 (backend만)
- 세션 2: 라우터+스키마 (backend만)
- 세션 3: 프론트 페이지 (frontend만)
- 세션 4: 테스트+통합 검증

## 완료 기준
- [ ] pytest 4개 이상 PASS
- [ ] Swagger /docs 에서 엔드포인트 확인
- [ ] 프론트 페이지 연동 동작
```

---

## 4. 세션 효율화 패턴

### 4.1 세션 시작 프롬프트 (권장)

```
plans/programming/1.2_catalog.md를 참조해서 세션 1(모델+서비스)을 진행해줘.
backend/api/programming/metadata/service.py 패턴을 재사용.
```

→ 이렇게 하면 plan 파일 1개 + 참조 코드 1개만 읽고 바로 구현 진입 (탐색 최소화).

### 4.2 금지 패턴 (토큰 낭비)

```
# 나쁜 예: 전체 탐색 유발
"카탈로그 모듈 구현해줘"
"이 프로젝트에서 다음에 뭘 해야 해?"

# 좋은 예: 컨텍스트 명시
"plans/programming/1.2_catalog.md 세션 2 진행, router.py 패턴 재사용"
"backend/tests/ 없는 service 함수 중 test_service_readiness_rates 추가"
```

### 4.3 세션 체크리스트

| 시점 | 액션 |
|---|---|
| 세션 시작 | plan 파일 + 대상 코드 파일 명시 |
| Explore 에이전트 3회 이상 | `/compact` 실행 |
| 모듈 전환 | `/clear` 또는 새 세션 |
| 구현 완료 | `pytest` → plan 체크박스 → 9.0_todo 갱신 |

### 4.4 파일 읽기 최적화

```
# 나쁜 패턴 (1,100줄 전체 읽기)
Read: backend/api/programming/metadata/service.py

# 좋은 패턴
Grep: "def suggest_" → 줄 번호 확인 → Read with offset+limit
```

---

## 5. CLAUDE.md 다이어트 원칙

### 5.1 삭제 대상 (코드에서 확인 가능)
- 엔드포인트 전체 목록 → router.py 참조
- 테이블/컬럼 상세 → models/ 참조
- 파일 트리 구조 → `ls` 로 확인
- 코드 패턴 예시 → 실제 코드 참조

### 5.2 유지 대상 (코드에서 추론 불가)
- 함정 주의사항 (예: `ExternalMetaSource.matched_at` — `fetched_at` 아님)
- 자기참조 관계의 특수 설정
- 현재 `.env` 상태 (SQLite vs PostgreSQL 전환)
- 모듈별 구현 상태 ✅/스텁

### 5.3 목표
845줄 → ~300줄 (60% 감소) → 매 세션 ~2,000 토큰 절약

---

## 6. .claudeignore 전략

```
# .claudeignore
**/research.md
docs/2_design/      ← 미구현 모듈
docs/3_ingest/
docs/4_analytics/
docs/5_marketing/
docs/6_monitoring/
docs/10_distribution/
docs/8_architecture/
backend/.venv/
celerybeat-schedule
```

**규칙**: 새 모듈 구현 시작 시 해당 줄만 제거. 작업 완료 후 재추가.

---

## 7. 테스트 인프라

### 7.1 구조

```
backend/tests/
├── conftest.py           ← SQLite in-memory DB 픽스처
├── __init__.py
└── api/
    └── programming/
        └── metadata/
            ├── __init__.py
            └── test_service.py
```

### 7.2 conftest.py 핵심 패턴

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import api.programming.metadata.models  # noqa: 모델 등록
from shared.database import Base

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)
```

### 7.3 테스트 우선순위
1. 서비스 함수 (순수 비즈니스 로직, 가장 효과 큼)
2. 라우터 (FastAPI TestClient)
3. Celery 태스크 (분리 테스트)

### 7.4 효과
테스트가 있으면 "파일 다시 읽고 수동 확인" 패턴 → `pytest` 1회 실행으로 대체.

---

## 8. Todo 관리 — 단일 진실의 원천

**`docs/9_todo/9.0_todo.md`** 를 SSOT로 사용.

모듈별 별도 todo 파일(meta_todo.md 등) 금지. 모든 과제는 9.0_todo.md에.

---

## 9. 적용 로드맵

| 순서 | 작업 | 효과 |
|:---:|---|:---:|
| 1 | `plans/` 체계 구축 | 탐색 시간 40% 절약 |
| 2 | `docs/9_todo/9.0_todo.md` 리디자인 | 단일 추적 |
| 3 | `.claudeignore` + `research.md` 삭제 | 탐색 노이즈 제거 |
| 4 | `backend/tests/` 기반 구축 | 수동 검증 → 자동 |
| 5 | CLAUDE.md 다이어트 (845→300줄) | 매 세션 ~2,000 토큰 절약 |
| 6 | Memory 갱신 | 세션 간 반복 설명 제거 |
