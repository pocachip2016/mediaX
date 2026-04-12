export type SiteConfig = typeof siteConfig

export const siteConfig = {
  name: "MediaX",
  description: "KT 지니TV VOD AI Transformation Platform — 편성·디자인·인제스트·통계·마케팅·모니터링을 하나의 플랫폼에서.",
  version: "0.1.0",
  stage: "MVP" as const,

  /** 브라우저 <title> 템플릿 */
  titleTemplate: "%s | MediaX",

  /** 진입점 (루트 / 리다이렉트 대상) */
  defaultPath: "/programming/contents",

  /** 외부 링크 */
  links: {
    github: "https://github.com/kt-genie/mediaX-CMS",
    docs: "/docs",
  },

  /** 헤더에 노출되는 최상위 메뉴 (main-nav 용) */
  mainNav: [
    { title: "대시보드", href: "/programming/contents" },
    { title: "문서", href: "/docs" },
  ],
} as const
