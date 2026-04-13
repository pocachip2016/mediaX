# apps/web/app/ — Next.js App Router 페이지

## 레이아웃 계층

```
app/
├── layout.tsx          # 루트: Geist 폰트, ThemeProvider, globals.css import
├── page.tsx            # / → /programming/contents 리다이렉트
└── (main)/             # 라우트 그룹: AppSidebar + Header 레이아웃
    ├── layout.tsx      # SidebarProvider + AppSidebar + SidebarInset
    ├── programming/    # 편성 기획 AX
    ├── design/         # 디자인 AX
    ├── ingest/         # 인제스트 AX
    ├── analytics/      # 통계 AX
    ├── marketing/      # 마케팅 AX
    └── monitoring/     # 모니터링 AX
```

## 구현된 페이지

| 경로 | 상태 | 주요 기능 |
|------|------|-----------|
| `/programming/metadata` | ✅ 구현 완료 | 서비스 준비 현황(KPI) 최상단, AI 파이프라인 접기 섹션, 최근 콘텐츠 접기+상세 이동 |
| `/programming/metadata/staging` | ✅ 구현 완료 | 체크박스 벌크 승인/반려, CP↔AI diff 비교, 시리즈 계층 트리 |
| `/programming/metadata/upload` | ✅ 구현 완료 | CSV/Excel 드래그&드롭, 파싱 미리보기, 템플릿 다운로드 |
| `/programming/metadata/queue` | ✅ 구현 완료 | 70~89점 검수 큐, 시놉시스 수정 후 승인 |
| `/programming/metadata/create` | ✅ 구현 완료 | 실시간 AI 메타 생성 |
| `/monitoring/pipeline` | ✅ 구현 완료 | Beat 스케줄 상태, 실패 항목 재시도, 30초 자동 새로고침 |
| `/programming/contents` | ✅ 구현 완료 | 다중 조건 검색(제목/CP/유형/상태/연도), 행 클릭 → 상세 이동 |
| `/programming/contents/[id]` | ✅ 구현 완료 | 콘텐츠 상세 (영화/에피소드: 이미지+메타, 시리즈: 시즌 목록, 시즌: 에피소드 목록) |
| `/programming/schedule` | 스텁 | |
| `/programming/tmdb` | 스텁 | |
| `/design/assets`, `/design/generate`, `/design/batch` | 스텁 | |
| `/ingest/receive`, `/ingest/encoding`, `/ingest/qc` | 스텁 | |
| `/analytics/viewing`, `/analytics/revenue`, `/analytics/settlement` | 스텁 | |
| `/marketing/promotion`, `/marketing/crm`, `/marketing/ad` | 스텁 | |
| `/monitoring/incidents`, `/monitoring/quality`, `/monitoring/security` | 스텁 | |

## 새 페이지 추가 패턴

1. `config/docs.ts`의 `NavSection[]`에 항목 등록
2. `app/(main)/<섹션>/<항목>/page.tsx` 파일 생성
3. 사이드바는 자동으로 반영됨 (별도 sidebar 수정 불필요)

## 주의
- `(main)` 라우트 그룹은 URL에 포함되지 않음
- 모든 페이지에 Mock 데이터 폴백 포함 — 백엔드 없이 UI 확인 가능
- API 연결: `lib/api.ts` 참조
