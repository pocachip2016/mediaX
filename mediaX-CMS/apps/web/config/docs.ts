export type NavItem = {
  title: string
  href?: string
  /** href 없이 그룹 레이블만 있는 경우 true */
  heading?: boolean
  /** 외부 링크 여부 */
  external?: boolean
  /** 뱃지 텍스트 (예: "LIVE", "NEW") */
  label?: string
  /** 하위 항목 */
  items?: NavItem[]
  /** 비활성화 */
  disabled?: boolean
}

export type NavSection = {
  title: string
  /** 섹션 루트 경로 — startsWith 매칭에 사용 */
  base: string
  items: NavItem[]
}

export const docsNav: NavSection[] = [
  {
    title: "편성 기획 AX",
    base: "/programming",
    items: [
      {
        title: "콘텐츠 관리",
        href: "/programming/contents",
        items: [],
      },
      {
        title: "편성 스케줄",
        href: "/programming/schedule",
        items: [],
      },
      {
        title: "TMDB 탐색",
        href: "/programming/tmdb",
        items: [],
      },
    ],
  },
  {
    title: "디자인 AX",
    base: "/design",
    items: [
      {
        title: "에셋 관리 (DAM)",
        href: "/design/assets",
        items: [],
      },
      {
        title: "AI 이미지 생성",
        href: "/design/generate",
        items: [],
      },
      {
        title: "배치 작업",
        href: "/design/batch",
        items: [],
      },
    ],
  },
  {
    title: "인제스트 AX",
    base: "/ingest",
    items: [
      {
        title: "수신 현황",
        href: "/ingest/receive",
        items: [],
      },
      {
        title: "인코딩 작업",
        href: "/ingest/encoding",
        items: [],
      },
      {
        title: "QC 대시보드",
        href: "/ingest/qc",
        items: [],
      },
    ],
  },
  {
    title: "통계 AX",
    base: "/analytics",
    items: [
      {
        title: "시청 통계",
        href: "/analytics/viewing",
        items: [],
      },
      {
        title: "매출 분석",
        href: "/analytics/revenue",
        items: [],
      },
      {
        title: "CP 정산",
        href: "/analytics/settlement",
        items: [],
      },
    ],
  },
  {
    title: "마케팅 AX",
    base: "/marketing",
    items: [
      {
        title: "프로모션",
        href: "/marketing/promotion",
        items: [],
      },
      {
        title: "CRM / 푸시",
        href: "/marketing/crm",
        items: [],
      },
      {
        title: "광고 상품",
        href: "/marketing/ad",
        items: [],
      },
    ],
  },
  {
    title: "모니터링 AX",
    base: "/monitoring",
    items: [
      {
        title: "장애 현황",
        href: "/monitoring/incidents",
        label: "LIVE",
        items: [],
      },
      {
        title: "품질 감시",
        href: "/monitoring/quality",
        items: [],
      },
      {
        title: "보안 로그",
        href: "/monitoring/security",
        items: [],
      },
    ],
  },
]

/** href → { section, item } 역방향 조회 맵 */
export const navItemMap = new Map<
  string,
  { section: NavSection; item: NavItem }
>(
  docsNav.flatMap((section) =>
    section.items
      .flatMap((item) => [item, ...(item.items ?? [])])
      .filter((item): item is NavItem & { href: string } => !!item.href)
      .map((item) => [item.href, { section, item }])
  )
)
