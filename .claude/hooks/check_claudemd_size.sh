#!/bin/bash
# PostToolUse hook (Write/Edit) — CLAUDE.md 파일이 60줄 초과 시 경고

INPUT=$(cat)

FILE=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    inp = d.get('tool_input', {})
    # Write는 file_path, Edit도 file_path
    print(inp.get('file_path', ''))
except:
    print('')
" 2>/dev/null)

if echo "$FILE" | grep -q "CLAUDE.md" && [ -f "$FILE" ]; then
    LINE_COUNT=$(wc -l < "$FILE" 2>/dev/null || echo 0)
    if [ "$LINE_COUNT" -gt 60 ]; then
        echo "⚠️ [CLAUDE.md 경고] ${FILE##*/}이 ${LINE_COUNT}줄입니다 (권장: 60줄 이하)."
        echo "   /diet-claudemd 커맨드로 코드에서 확인 가능한 항목을 삭제하세요."
        echo "   삭제 대상: 엔드포인트 목록, 테이블 컬럼 상세, 파일 트리, 코드 패턴 예시"
    fi
fi

exit 0
