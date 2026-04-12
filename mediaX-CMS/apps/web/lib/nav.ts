import { docsNav, navItemMap, type NavItem, type NavSection } from "@/config/docs"

/**
 * 현재 pathname에 해당하는 section과 item을 반환합니다.
 * 정확히 일치하는 href가 없으면 startsWith 기반으로 section만 반환합니다.
 */
export function getActiveNav(pathname: string): {
  section: NavSection | undefined
  item: NavItem | undefined
} {
  // 1) 정확히 일치하는 항목
  const exact = navItemMap.get(pathname)
  if (exact) return exact

  // 2) 섹션 base로 prefix 매칭
  const section = docsNav.find((s) => pathname.startsWith(s.base))
  return { section, item: undefined }
}

/**
 * pathname에서 breadcrumb 배열을 생성합니다.
 * 반환: [{ title, href }, ...]  (루트 → 현재 페이지 순)
 */
export function getBreadcrumbs(
  pathname: string
): { title: string; href: string }[] {
  const { section, item } = getActiveNav(pathname)
  const crumbs: { title: string; href: string }[] = []

  if (section) {
    // section 자체는 href가 없으므로 첫 번째 child를 링크로 사용
    const sectionHref = section.items[0]?.href ?? section.base
    crumbs.push({ title: section.title, href: sectionHref })
  }

  // item href가 section의 첫 번째 href와 동일하면 중복이므로 추가하지 않음
  if (item?.href && item.href !== crumbs[0]?.href) {
    crumbs.push({ title: item.title, href: item.href })
  }

  return crumbs
}

/**
 * 현재 section 안에서 이전/다음 페이지를 반환합니다.
 * 페이지 하단 prev/next 네비게이션에 활용합니다.
 */
export function getPagerLinks(pathname: string): {
  prev: NavItem | undefined
  next: NavItem | undefined
} {
  const { section } = getActiveNav(pathname)
  if (!section) return { prev: undefined, next: undefined }

  const flat = section.items.flatMap((item) =>
    item.href ? [item, ...(item.items ?? [])] : (item.items ?? [])
  )
  const idx = flat.findIndex((item) => item.href === pathname)

  return {
    prev: idx > 0 ? flat[idx - 1] : undefined,
    next: idx < flat.length - 1 ? flat[idx + 1] : undefined,
  }
}

/**
 * 전체 docsNav를 평탄화한 목록 (검색 인덱스 구성 등에 활용)
 */
export function getFlatNav(): (NavItem & { href: string })[] {
  return docsNav.flatMap((section) =>
    section.items
      .flatMap((item) => [item, ...(item.items ?? [])])
      .filter((item): item is NavItem & { href: string } => !!item.href)
  )
}
