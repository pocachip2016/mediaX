#!/bin/bash
# UserPromptSubmit hook — 토큰 낭비 패턴 감지 후 경고 출력
# Claude Code는 이 스크립트의 stdout을 프롬프트 컨텍스트에 주입

PROMPT="$CLAUDE_USER_PROMPT"
WARNED=0

warn() {
    echo "⚠️ [토큰 효율] $1"
    WARNED=1
}

# 패턴 1: plan 파일 없이 모듈 구현 요청
if echo "$PROMPT" | grep -qE "(구현해줘|만들어줘|작성해줘)" && \
   ! echo "$PROMPT" | grep -q "plans/"; then
    warn "plan 파일 경로를 명시하면 탐색 없이 바로 진행 가능합니다."
    echo "  예) plans/1.2_catalog.md 세션 1 진행해줘"
fi

# 패턴 2: 전체 파일 읽기 유발 표현
if echo "$PROMPT" | grep -qE "전체.*(읽어|확인해|파악해)|다 읽어|전부 읽어"; then
    warn "전체 파일 읽기는 큰 토큰을 소비합니다."
    echo "  → Grep으로 줄번호 확인 후 offset+limit 사용을 권장합니다."
fi

# 패턴 3: 광범위 탐색 유발
if echo "$PROMPT" | grep -qE "이 프로젝트에서|전체적으로|어떻게 돼 있어|구조가 어때|다음에 뭘 해야"; then
    warn "전체 탐색 대신 plans/ 또는 CLAUDE.md를 참조하면 빠릅니다."
    echo "  → docs/9_todo/9.0_todo.md 또는 plans/ 파일 확인을 권장합니다."
fi

# 패턴 4: 새 모듈인데 세션 분리 없이 진행
if echo "$PROMPT" | grep -qE "1\.[2-9]|2\.[0-9]|catalog|curation|approval|cp.supply|iam" && \
   ! echo "$PROMPT" | grep -qE "plans/|세션|/clear"; then
    warn "새 모듈 작업은 /clear 후 새 세션에서 시작하면 컨텍스트 누적을 방지합니다."
fi

# 경고가 있었으면 구분선 출력
if [ "$WARNED" -eq 1 ]; then
    echo "---"
fi

exit 0
