"use client"

import type { ContentDetail } from "@/lib/api"
import { BreadcrumbNav, type BreadcrumbParent } from "./BreadcrumbNav"
import { LeafMetaHeader, type StatusInfo } from "./LeafMetaHeader"

interface DetailLeafLayoutProps {
  content: ContentDetail
  contentId: number
  parentChain: BreadcrumbParent[]
  statusInfo: StatusInfo
  qualityScore: number
  onReprocess: () => void
  onLock: () => void
  onPreviewClip: () => void
}

/**
 * Leaf 상세 상단 섹션 — movie/episode 공용.
 * episode 는 parentChain(시리즈›시즌)을 받아 브레드크럼 표시, movie 는 빈 배열.
 * 하단 3탭(글자/이미지/영상) 등 무거운 영역은 page.tsx 가 그대로 보유.
 */
export function DetailLeafLayout({
  content, contentId, parentChain, statusInfo, qualityScore,
  onReprocess, onLock, onPreviewClip,
}: DetailLeafLayoutProps) {
  return (
    <div className="space-y-3">
      {parentChain.length > 0 && (
        <BreadcrumbNav parents={parentChain} backLabel="시즌으로" />
      )}
      <LeafMetaHeader
        content={content}
        contentId={contentId}
        statusInfo={statusInfo}
        qualityScore={qualityScore}
        onReprocess={onReprocess}
        onLock={onLock}
        onPreviewClip={onPreviewClip}
      />
    </div>
  )
}
