$ARGUMENTS 모듈 완료 처리를 진행해줘.

1. cd backend && .venv/bin/python -m pytest tests/ -v 실행
2. pytest 4개 이상 PASS 확인 (실패 시 수정 후 재실행)
3. plans/$ARGUMENTS.md 상태를 "done ✅"으로, 완료된 체크박스 표시
4. docs/9_todo/9.0_todo.md 해당 모듈 행 백엔드/프론트/테스트 ✅ 갱신
5. 수정된 CLAUDE.md 파일들 줄 수 확인 — 60줄 초과 시 다이어트 대상 목록 제시

코드는 읽지 않아도 됨. pytest + plan + todo 3가지만 작업.
