$ARGUMENTS CLAUDE.md 파일을 60줄 이하로 다이어트해줘.

삭제 기준 (코드에서 확인 가능 → 삭제):
- 엔드포인트 전체 목록 → router.py 참조
- DB 테이블/컬럼 상세 → models/ 참조
- 파일 트리 구조 → ls/Glob으로 확인 가능
- 코드 패턴 예시 → 실제 코드 참조
- 완료된 구현 이력 → git log로 확인 가능

유지 기준 (코드에서 추론 불가 → 유지):
- 함정 주의사항 (예: matched_at vs fetched_at, remote_side 설정)
- 비직관적 enum 값이나 상태 흐름
- 현재 .env 상태 (SQLite vs PostgreSQL)
- 외부 API 키 발급 링크
- 모듈별 구현 상태 ✅/스텁

진행 방식:
1. 파일 읽기
2. "삭제할 항목: [목록]" 먼저 보여주기
3. 확인 없이 바로 삭제 진행
4. 결과: N줄 → M줄 보고
