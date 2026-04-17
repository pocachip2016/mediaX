# mediaX — Claude Code 프롬프트 효율화 가이드
> 작성일: 2026-04-17
> 목적: 매번 기억하지 않아도 자동으로 토큰을 아끼는 3-레이어 시스템

---

## 자동화 레이어 개요

```
레이어 1: CLAUDE.md 행동 규칙    ← 매 세션 자동 적용, 프롬프트 불필요
레이어 2: Hooks                  ← 나쁜 패턴 실시간 차단/경고
레이어 3: Custom Slash Commands  ← 단계별 세션 템플릿 1단어 호출
```

---

## 레이어 1 — CLAUDE.md 행동 규칙

루트 CLAUDE.md에 아래 섹션을 추가해 매 세션 자동 적용.

```markdown
## Claude 자동 행동 규칙

### 파일 읽기
- 100줄 이상 파일: Read 전 Grep으로 줄번호 확인 후 offset+limit 사용
- 전체 파일 Read 금지 (50줄 이하 또는 신규 파일 예외)
- service.py 탐색: `Grep "^def "` → 줄번호 → 필요한 함수만 읽기

### 세션 진입
- plans/{모듈}.md 존재 시 반드시 먼저 읽고 시작 (docs/ 탐색 금지)
- 선언한 세션 범위 외 파일 수정 금지
- Explore 에이전트 3회 이상 → /compact 제안

### 완료 보고
- "완료" 보고 전 pytest 또는 python import 체크 실행 필수
- plan 체크박스 + 9.0_todo.md 갱신이 완료 처리의 일부

### CLAUDE.md 관리
- 각 CLAUDE.md 60줄 이하 유지
- 추가 전 자문: "코드에서 확인 가능한가?" → 가능하면 추가 금지
- 엔드포인트 목록·테이블 컬럼 상세·파일 트리는 CLAUDE.md에 쓰지 않음
```

---

## 레이어 2 — Hooks

### 파일 위치
```
.claude/
├── settings.json
└── hooks/
    ├── prompt_check.sh       ← UserPromptSubmit: 나쁜 프롬프트 경고
    ├── check_read.sh         ← PreToolUse(Read): 대형 파일 전체 읽기 경고
    └── check_claudemd_size.sh ← PostToolUse(Write/Edit): CLAUDE.md 비대화 경고
```

### prompt_check.sh — 나쁜 프롬프트 패턴 감지

```bash
#!/bin/bash
PROMPT="$CLAUDE_USER_PROMPT"
warn() { echo "⚠️ [토큰 효율] $1"; }

# plan 없이 구현 요청
if echo "$PROMPT" | grep -qE "(구현해줘|만들어줘|작성해줘)" && \
   ! echo "$PROMPT" | grep -q "plans/"; then
    warn "plan 파일 경로를 명시하면 탐색 없이 바로 진행 가능합니다."
    echo "  예) plans/1.2_catalog.md 세션 1 진행해줘"
fi

# 전체 파일 읽기 유발
if echo "$PROMPT" | grep -qE "전체.*(읽어|확인해|파악해)|다 읽어"; then
    warn "전체 파일 읽기는 큰 토큰을 소비합니다."
    echo "  → Grep으로 줄번호 확인 후 offset+limit 사용을 권장합니다."
fi

# 광범위 탐색 유발
if echo "$PROMPT" | grep -qE "이 프로젝트에서|전체적으로|구조가 어때|어떻게 돼 있어"; then
    warn "전체 탐색 대신 plans/ 또는 CLAUDE.md를 참조하면 빠릅니다."
fi

# 모듈 전환인데 세션 분리 없음
if echo "$PROMPT" | grep -qE "1\.[2-9]|catalog|curation|approval|iam" && \
   ! echo "$PROMPT" | grep -qE "plans/|세션"; then
    warn "새 모듈은 /clear 후 새 세션에서 시작하면 컨텍스트 누적을 방지합니다."
fi

exit 0
```

### check_read.sh — 대형 파일 전체 읽기 경고

```bash
#!/bin/bash
INPUT=$(cat)
FILE=$(echo "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(d.get('tool_input', {}).get('file_path', ''))
" 2>/dev/null)
LIMIT=$(echo "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(d.get('tool_input', {}).get('limit', ''))
" 2>/dev/null)

if [ -n "$FILE" ] && [ -z "$LIMIT" ] && [ -f "$FILE" ]; then
    LINE_COUNT=$(wc -l < "$FILE")
    if [ "$LINE_COUNT" -gt 150 ]; then
        echo "⚠️ [Read 경고] ${FILE##*/}은 ${LINE_COUNT}줄입니다."
        echo "   Grep → 줄번호 → Read offset=N limit=30 패턴을 사용하세요."
    fi
fi
exit 0
```

### check_claudemd_size.sh — CLAUDE.md 비대화 감지

```bash
#!/bin/bash
INPUT=$(cat)
FILE=$(echo "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
inp = d.get('tool_input', {})
print(inp.get('file_path', ''))
" 2>/dev/null)

if echo "$FILE" | grep -q "CLAUDE.md" && [ -f "$FILE" ]; then
    LINE_COUNT=$(wc -l < "$FILE")
    if [ "$LINE_COUNT" -gt 60 ]; then
        echo "⚠️ [CLAUDE.md] ${FILE##*/}이 ${LINE_COUNT}줄입니다 (권장: 60줄 이하)."
        echo "   /diet-claudemd 커맨드로 정리하세요."
    fi
fi
exit 0
```

### settings.json — hooks 등록

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [{"type": "command", "command": "bash .claude/hooks/prompt_check.sh"}]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Read",
        "hooks": [{"type": "command", "command": "bash .claude/hooks/check_read.sh"}]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [{"type": "command", "command": "bash .claude/hooks/check_claudemd_size.sh"}]
      }
    ]
  }
}
```

---

## 레이어 3 — Custom Slash Commands

`.claude/commands/` 폴더의 `.md` 파일이 자동으로 슬래시 커맨드가 됨.

### /start-module

```
/start-module 1.2_catalog 세션1
```

plans/$ARGUMENTS.md 를 읽고 진행:
1. plans/$ARGUMENTS.md 만 읽기 (docs/ 탐색 금지)
2. 세션 범위 확인 후 패턴 참조 파일을 Grep → offset+limit으로 읽기
3. 선언 범위 외 파일 수정 금지
4. 완료 후 pytest 또는 import 체크

### /complete-module

```
/complete-module 1.2_catalog
```

1. pytest 실행 → 4개 이상 PASS 확인
2. plans/$ARGUMENTS.md 상태 "done ✅" + 체크박스 완료
3. docs/9_todo/9.0_todo.md 해당 모듈 행 ✅ 갱신
4. CLAUDE.md 크기 점검 (60줄 초과 시 다이어트 목록 제시)

### /diet-claudemd

```
/diet-claudemd backend/api/programming/metadata/CLAUDE.md
```

삭제 대상 (코드에서 확인 가능):
- 엔드포인트 전체 목록 → router.py
- DB 테이블/컬럼 상세 → models/
- 파일 트리 → ls/Glob
- 코드 패턴 예시 → 실제 코드

유지 대상 (코드에서 추론 불가):
- 함정 주의사항 (예: matched_at vs fetched_at)
- 비직관적 enum 값
- 환경 변수 현재 상태

### /check-session

세션 상태 점검:
1. 읽은 파일 수 (5개 이상이면 /compact 권장)
2. 현재 모듈 plan 완료 여부
3. 미실행 pytest 여부
4. 수정된 CLAUDE.md 크기

---

## 단계별 개선 프롬프트

### STAGE 0 — Plan 파일 작성
```
plans/1.2_catalog.md 를 새로 작성해줘.
읽을 파일: docs/1_programming/1.2_catalog/CLAUDE.md + plans/1.1_metadata.md
포함: 범위/의존성/백엔드파일/프론트파일/테스트4케이스/세션분할/완료기준
구현은 하지 마.
```

### STAGE 1 — 모델 + 서비스
```
plans/1.2_catalog.md 세션 1(모델+서비스) 진행.
패턴: models/content.py 1~80줄 + service.py create_content(34줄)/get_service_readiness(888줄)
만들 파일: catalog/models/catalog.py + catalog/service.py
router/schemas/프론트 건드리지 마.
```

### STAGE 2 — 라우터 + 스키마
```
plans/1.2_catalog.md 세션 2(라우터+스키마) 진행.
읽을 파일:
- catalog/service.py (Grep "^def " → 시그니처만)
- metadata/router.py 50~120줄
- metadata/schemas.py 1~60줄
만들 파일: catalog/schemas.py + catalog/router.py
등록: api/programming/router.py include 추가
```

### STAGE 3 — 프론트엔드
```
plans/1.2_catalog.md 세션 3(프론트) 진행.
패턴: metadata/page.tsx 1~80줄 (Grep으로 api 함수 위치 확인)
만들 파일: app/(main)/programming/catalog/page.tsx
lib/api.ts: catalogApi.list/get 추가
규칙: "use client" + Mock fallback, 새 컴포넌트 파일 금지, @/ 절대경로
```

### STAGE 4 — 테스트
```
plans/1.2_catalog.md 세션 4(테스트) 진행.
인프라 준비됨 (읽지 않아도 됨): tests/conftest.py + tests/api/programming/metadata/test_service.py
만들 파일: tests/api/programming/catalog/__init__.py + test_service.py
service.py: Grep "^def " → 시그니처(5줄)만 읽기
완료: cd backend && .venv/bin/python -m pytest tests/api/programming/catalog/ -v
```

### STAGE 5 — 완료 처리
```
1.2 카탈로그 완료 처리:
1. plans/1.2_catalog.md → done ✅ + 체크박스
2. docs/9_todo/9.0_todo.md → 1.2 행 ✅
파일 2개만. 코드 읽지 마.
```

---

## 세션 간 컨텍스트 전달 패턴

새 세션 시작 시 이전 결과를 말로 설명하지 않고 파일 경로로 전달.

```
[세션 2 시작]
세션 1 완료:
- backend/api/programming/catalog/models/catalog.py — CatalogItem, CatalogStatus
- backend/api/programming/catalog/service.py — create/list/get/update 4개 함수

세션 2(라우터+스키마) 진행. service.py는 함수 시그니처만 확인 후 router 작성 시작.
```

---

## 프롬프트 자가 진단 체크리스트

```
□ 읽을 파일을 경로+줄범위로 명시했는가?
□ 이번 세션 범위 외 작업을 금지했는가?
□ 패턴 참조는 파일 경로로 대체했는가? (설명 X)
□ 큰 파일은 Grep → 줄번호 → offset+limit을 명시했는가?
□ 이전 세션 결과를 파일 경로로 전달했는가?
□ 완료 검증 명령어를 포함했는가?
```

---

## 토큰 절감 효과

| 단계 | 나쁜 프롬프트 | 개선 프롬프트 | 절감 |
|---|---|---|---|
| Plan 작성 | docs/ 전체 탐색 ~8,000 tok | plan 2개 읽기 ~1,500 tok | ~80% |
| 모델+서비스 | service.py 전체 ~4,000 tok | 함수 2개 ~300 tok | ~92% |
| 라우터+스키마 | 재탐색 ~3,000 tok | 줄번호 지정 ~800 tok | ~73% |
| 프론트 | app/ 탐색 ~5,000 tok | 1페이지 80줄 ~600 tok | ~88% |
| 테스트 | service.py 재읽기 ~4,000 tok | Grep+시그니처 ~400 tok | ~90% |

---

## 사용 방법 — 실제 예시

### Hooks (레이어 2) — 자동 동작, 별도 조작 불필요

세션을 시작하면 `.claude/settings.json`에 등록된 hooks가 자동 활성화됨.

#### 나쁜 프롬프트 입력 시

```
사용자 입력: "카탈로그 라우터 만들어줘"

↓ UserPromptSubmit hook 자동 실행

⚠️ [토큰 효율] plan 파일 경로를 명시하면 탐색 없이 바로 진행 가능합니다.
  예) plans/1.2_catalog.md 세션 1 진행해줘
---

Claude: plans/1.2_catalog.md를 먼저 확인하겠습니다...
```

경고를 보고 프롬프트를 수정하거나, 그냥 진행해도 됨 (차단이 아니라 경고).

#### 대형 파일 전체 읽기 시도 시

```
Claude가 service.py 전체 Read를 시도하면:

⚠️ [Read 경고] service.py은 1169줄입니다.
   권장 패턴: Grep "^def 함수명" → 줄번호 확인 → Read offset=N limit=30

→ Claude가 자동으로 Grep 먼저 사용하도록 유도됨
```

#### CLAUDE.md 비대화 시

```
Claude가 CLAUDE.md를 수정해서 60줄 초과가 되면:

⚠️ [CLAUDE.md 경고] metadata/CLAUDE.md이 87줄입니다 (권장: 60줄 이하).
   /diet-claudemd 커맨드로 코드에서 확인 가능한 항목을 삭제하세요.
```

---

### /start-module — 모듈 구현 세션 시작

**형식:**
```
/start-module {plan파일명} {세션번호}
```

**예시 1: 새 모듈 1번 세션**
```
/start-module 1.2_catalog 세션1
```
→ `plans/1.2_catalog.md` 읽기 → 세션 1 범위(모델+서비스) 확인 → 패턴 파일만 읽기 → 구현 시작

**예시 2: 이어서 2번 세션**
```
/start-module 1.2_catalog 세션2
```
→ plan 재확인 → 세션 2 범위(라우터+스키마) → 세션 1 결과 파일 시그니처만 확인 → router 작성

**예시 3: 테스트 세션**
```
/start-module 1.2_catalog 세션4
```
→ plan 확인 → conftest.py는 이미 있으니 읽지 않음 → test_service.py 작성 → pytest 실행

> plan 파일이 없으면 먼저 STAGE 0 프롬프트로 plan 파일을 만들어야 함.

---

### /complete-module — 모듈 완료 처리

**형식:**
```
/complete-module {plan파일명}
```

**예시:**
```
/complete-module 1.2_catalog
```

**Claude가 자동으로 하는 것:**
1. `cd backend && .venv/bin/python -m pytest tests/ -v` 실행
2. `plans/1.2_catalog.md` 상태 → `done ✅`, 체크박스 완료 표시
3. `docs/9_todo/9.0_todo.md` 1.2 카탈로그 행 ✅ 갱신
4. 관련 CLAUDE.md 줄 수 점검 후 60줄 초과 항목 목록 출력

**pytest 실패 시:**
```
/complete-module 1.2_catalog
→ pytest 3 failed, 1 passed
→ Claude가 실패한 테스트 수정 후 재실행
→ 4 passed 확인 후 plan/todo 갱신
```

---

### /diet-claudemd — CLAUDE.md 다이어트

**형식:**
```
/diet-claudemd {CLAUDE.md 경로}
```

**예시 1: 메타데이터 모듈 정리**
```
/diet-claudemd backend/api/programming/metadata/CLAUDE.md
```

**Claude 동작:**
```
현재 87줄 → 목표 60줄 이하

삭제할 항목:
- 엔드포인트 전체 목록 25개 (router.py에 있음) → 12줄 삭제
- DB 테이블 컬럼 상세 (models/에 있음) → 8줄 삭제
- 파일 트리 구조 (ls로 확인 가능) → 5줄 삭제

진행 후: 87줄 → 52줄 ✅
```

**예시 2: 여러 파일 순서대로**
```
/diet-claudemd backend/CLAUDE.md
/diet-claudemd backend/workers/CLAUDE.md
```

---

### /check-session — 세션 상태 점검

**언제 사용:** 탐색이 많아졌다 싶을 때, 혹은 세션 중간 점검 시

**예시:**
```
/check-session
```

**출력 예시:**
```
- 세션 상태: 파일 7개 읽음 → /compact 권장
- 미완료 과제: pytest 미실행, 9.0_todo.md 갱신 필요
- CLAUDE.md 경고: metadata/CLAUDE.md 87줄 초과
- 다음 권장 액션: /compact 실행 후 pytest 실행
```

---

### 신규 모듈 전체 흐름 예시 (1.2 카탈로그 기준)

#### 세션 A — Plan 작성 (새 세션에서)

```
plans/1.2_catalog.md 를 새로 작성해줘.
읽을 파일:
- docs/1_programming/1.2_catalog/CLAUDE.md
- plans/1.1_metadata.md (완료 모듈 패턴)
포함: 범위/의존성/백엔드파일목록/프론트파일목록/테스트4케이스/세션분할/완료기준
구현은 하지 마.
```

#### 세션 B — 모델+서비스 (/clear 후 새 세션)

```
/start-module 1.2_catalog 세션1
```

#### 세션 C — 라우터+스키마 (/clear 후 새 세션)

```
[세션 1 완료]
- backend/api/programming/catalog/models/catalog.py 생성됨
- backend/api/programming/catalog/service.py — list/get/create/update 4개 함수

/start-module 1.2_catalog 세션2
```

#### 세션 D — 프론트엔드 (/clear 후 새 세션)

```
/start-module 1.2_catalog 세션3
```

#### 세션 E — 테스트 (/clear 후 새 세션)

```
/start-module 1.2_catalog 세션4
```

#### 완료 처리 (세션 E 마지막)

```
/complete-module 1.2_catalog
```

---

### 기존 모듈 보완 예시

#### 특정 기능만 추가할 때

```
plans/1.1_metadata.md 의 잔여 과제 중 Excel 업로드 기능 추가해줘.
대상 함수: backend/api/programming/metadata/service.py의 process_batch_rows
참조: Grep "def process_batch" service.py → 줄번호 확인 후 해당 블록만 읽기
openpyxl 이미 설치됨. router.py 수정 없음.
```

#### CLAUDE.md만 정리할 때

```
/diet-claudemd backend/api/programming/metadata/CLAUDE.md
```

#### 테스트만 추가할 때

```
plans/1.1_metadata.md 테스트 케이스 추가:
- test_suggest_image_meta_missing_type
대상: service.py의 suggest_image_meta 함수
Grep으로 줄번호 확인 후 해당 함수만 읽기.
conftest.py는 이미 있음 (읽지 않아도 됨).
```

---

### hooks 설치 확인 방법

새 Claude Code 세션 시작 후 아래 프롬프트로 hooks 작동 여부 확인:

```
카탈로그 구현해줘
```

→ `⚠️ [토큰 효율]` 경고가 뜨면 hooks 정상 작동 중.
→ 경고가 안 뜨면 `.claude/settings.json` 경로 확인 필요.

```bash
# 수동 테스트
CLAUDE_USER_PROMPT="카탈로그 만들어줘" bash .claude/hooks/prompt_check.sh
echo '{"tool_name":"Read","tool_input":{"file_path":"backend/api/programming/metadata/service.py"}}' \
  | bash .claude/hooks/check_read.sh
```
