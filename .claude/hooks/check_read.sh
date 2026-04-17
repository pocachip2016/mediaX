#!/bin/bash
# PreToolUse hook (Read) — 150줄 이상 파일 전체 읽기 시 경고
# STDIN: JSON {"tool_name": "Read", "tool_input": {"file_path": "...", ...}}

INPUT=$(cat)

FILE=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('file_path', ''))
except:
    print('')
" 2>/dev/null)

LIMIT=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    v = d.get('tool_input', {}).get('limit', '')
    print(v if v is not None else '')
except:
    print('')
" 2>/dev/null)

OFFSET=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    v = d.get('tool_input', {}).get('offset', '')
    print(v if v is not None else '')
except:
    print('')
" 2>/dev/null)

# limit/offset 없이 읽으려는 경우만 체크
if [ -n "$FILE" ] && [ -z "$LIMIT" ] && [ -z "$OFFSET" ] && [ -f "$FILE" ]; then
    LINE_COUNT=$(wc -l < "$FILE" 2>/dev/null || echo 0)
    if [ "$LINE_COUNT" -gt 150 ]; then
        echo "⚠️ [Read 경고] ${FILE##*/}은 ${LINE_COUNT}줄입니다."
        echo "   권장 패턴: Grep \"^def 함수명\" → 줄번호 확인 → Read offset=N limit=30"
        # exit 0 = 경고만, 실행 허용
        # exit 2 = 차단 (엄격 모드)
    fi
fi

exit 0
