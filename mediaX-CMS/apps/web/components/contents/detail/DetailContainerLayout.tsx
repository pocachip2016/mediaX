"use client"

import type { ContentDetail, StagingItem } from "@/lib/api"
import { BreadcrumbNav, type BreadcrumbParent } from "./BreadcrumbNav"
import { LeafMetaHeader, type StatusInfo } from "./LeafMetaHeader"
import { ChildrenTable } from "./ChildrenTable"

interface DetailContainerLayoutProps {
  content: ContentDetail
  contentId: number
  parentChain: BreadcrumbParent[]
  statusInfo: StatusInfo
  qualityScore: number
  childrenItems: StagingItem[]
  childrenLoading: boolean
  onReprocess: () => void
  onLock: () => void
  onPreviewClip: () => void
}

/**
 * Container 상세 — series/season 공용.
 * season 은 parentChain(시리즈)을 받아 브레드크럼 표시.
 * 메타 헤더 + 자식 목록 테이블(series→시즌 / season→에피소드).
 */
export function DetailContainerLayout({
  content, contentId, parentChain, statusInfo, qualityScore,
  childrenItems, childrenLoading, onReprocess, onLock, onPreviewClip,
}: DetailContainerLayoutProps) {
  const parentType = content.content_type === "series" ? "series" : "season"

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="space-y-3">
        {parentChain.length > 0 && (
          <BreadcrumbNav parents={parentChain} backLabel="시리즈로" />
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
        <ChildrenTable
          children={childrenItems}
          parentType={parentType}
          loading={childrenLoading}
        />
      </div>
    </div>
  )
}
