"use client"

import { useEffect, useState } from "react"
import { useParams, usePathname, useRouter, useSearchParams } from "next/navigation"
import { metadataApi, posterRecommendApi, type ContentDetail, type PosterCandidateOut, type RecommendationsOut, type FieldRecommendation, type SourceFieldRec, type StagingItem } from "@/lib/api"
import { DetailContainerLayout } from "@/components/contents/detail/DetailContainerLayout"
import { isLeafType } from "@/components/contents/detail/contentType"
import type { BreadcrumbParent } from "@/components/contents/detail/BreadcrumbNav"
import { ContentShell } from "@/components/contents/shell/ContentShell"
import { PosterPanel } from "@/components/contents/shell/PosterPanel"
import { DetailHeader } from "@/components/contents/shell/DetailHeader"
import { ThreeColumnShell } from "@/components/contents/shell/ThreeColumnShell"
import { EditPane } from "@/components/contents/shell/EditPane"
import { ReviewPane } from "@/components/contents/shell/ReviewPane"
import { AISummaryBottom } from "@/components/contents/recommend/AISummaryBottom"

const STATUS_BADGE: Record<string, { label: string; emoji: string; color: string }> = {
  waiting: { label: "대기", emoji: "⏳", color: "bg-slate-100 text-slate-600" },
  processing: { label: "처리중", emoji: "🔄", color: "bg-blue-100 text-blue-700" },
  staging: { label: "검토대기", emoji: "📋", color: "bg-violet-100 text-violet-700" },
  review: { label: "검수", emoji: "🟧", color: "bg-amber-100 text-amber-700" },
  approved: { label: "승인됨", emoji: "✓", color: "bg-green-100 text-green-700" },
  rejected: { label: "반려됨", emoji: "✗", color: "bg-red-100 text-red-700" },
}

export default function ContentDetailPage() {
  const params = useParams()
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const contentId = Number(params.id)

  const modeParam = searchParams.get("mode")
  const mode: "view" | "edit" | "review" =
    modeParam === "edit" || modeParam === "review" ? modeParam : "view"

  const handleModeChange = (next: "view" | "edit" | "review") => {
    const sp = new URLSearchParams(searchParams.toString())
    if (next === "view") sp.delete("mode")
    else sp.set("mode", next)
    const qs = sp.toString()
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false })
  }

  const [content, setContent] = useState<ContentDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [posterCandidates, setPosterCandidates] = useState<PosterCandidateOut[] | null>(null)

  const [recommendations, setRecommendations] = useState<RecommendationsOut | null>(null)
  const [appliedFields, setAppliedFields] = useState<Set<string>>(new Set())

  const [parentChain, setParentChain] = useState<BreadcrumbParent[]>([])
  const [childrenItems, setChildrenItems] = useState<StagingItem[]>([])
  const [childrenLoading, setChildrenLoading] = useState(false)

  useEffect(() => {
    const fetchContent = async () => {
      try {
        const data = await metadataApi.getContent(contentId)
        setContent(data)
      } catch (error) {
        console.error("Failed to fetch content:", error)
      } finally {
        setLoading(false)
      }
    }
    fetchContent()
  }, [contentId])

  // 부모 체인(브레드크럼) — season: [series], episode: [series, season]
  useEffect(() => {
    if (!content || content.parent_id == null) {
      setParentChain([])
      return
    }
    let cancelled = false
    const buildChain = async () => {
      const chain: BreadcrumbParent[] = []
      try {
        let pid: number | null | undefined = content.parent_id
        let guard = 0
        while (pid != null && guard < 5) {
          const p = await metadataApi.getContent(pid)
          chain.unshift({ id: p.id, title: p.title, content_type: p.content_type })
          pid = p.parent_id
          guard += 1
        }
        if (!cancelled) setParentChain(chain)
      } catch {
        if (!cancelled) setParentChain([])
      }
    }
    void buildChain()
    return () => { cancelled = true }
  }, [content])

  // Container(series/season) 자식 목록 — hierarchy 재사용
  useEffect(() => {
    if (!content || isLeafType(content.content_type)) {
      setChildrenItems([])
      return
    }
    let cancelled = false
    setChildrenLoading(true)
    metadataApi.getHierarchy(content.id)
      .then((item) => { if (!cancelled) setChildrenItems(item.children ?? []) })
      .catch(() => { if (!cancelled) setChildrenItems([]) })
      .finally(() => { if (!cancelled) setChildrenLoading(false) })
    return () => { cancelled = true }
  }, [content])


  // Load poster candidates on mount
  useEffect(() => {
    posterRecommendApi.getCandidates(contentId).then(setPosterCandidates).catch(() => setPosterCandidates(null))
  }, [contentId])

  // Load meta recommendations on mount (mock fallback when backend unavailable)
  useEffect(() => {
    metadataApi.getRecommendations(contentId).then(setRecommendations).catch(() => {
      setRecommendations({
        content_id: contentId,
        missing_fields: ["cast", "synopsis", "runtime", "country"],
        auto_fill: [
          {
            field: "cast",
            status: "auto",
            recommendations: [{ source_type: "watcha", source_id: 1, value: "김설현 · 오정세 · 유재명 외 12명", confidence: 1.0 }],
            ai_synthesis: null,
          },
          {
            field: "runtime",
            status: "auto",
            recommendations: [{ source_type: "tmdb", source_id: 2, value: "132분", confidence: 0.94 }],
            ai_synthesis: null,
          },
          {
            field: "country",
            status: "auto",
            recommendations: [{ source_type: "tmdb", source_id: 2, value: "대한민국", confidence: 0.94 }],
            ai_synthesis: null,
          },
        ],
        conflicts: [
          {
            field: "synopsis",
            status: "conflict",
            recommendations: [
              { source_type: "watcha", source_id: 1, value: "가난한 박씨 가족은 부잣집에 하나 둘씩 취업하며 묘한 공생 관계를 형성해간다.", confidence: 0.5 },
              { source_type: "tmdb", source_id: 2, value: "A poor family schemes to become employed by a wealthy Park family and infiltrates their home.", confidence: 0.94 },
            ],
            ai_synthesis: {
              source_type: "ai", source_id: 99,
              value: "경제적으로 어려운 박씨 일가는 재벌 박 사장 가족의 집에 한 명씩 취업하며 공생 관계를 형성해가지만, 숨겨진 비밀이 드러나면서 예기치 못한 사건이 벌어진다.",
              confidence: 0.79,
            },
          },
        ],
      })
    })
  }, [contentId])

  if (loading) {
    return <div className="p-6 text-center text-slate-600">로드 중...</div>
  }

  if (!content) {
    return <div className="p-6 text-center text-slate-600">콘텐츠를 찾을 수 없습니다.</div>
  }

  // Handler for recommendation apply
  const handleApplyRec = async (rec: FieldRecommendation, sourceRec: SourceFieldRec) => {
    try {
      if (sourceRec.source_type === "ai") {
        await metadataApi.promoteAIResult(contentId, sourceRec.source_id)
      } else {
        await metadataApi.applyExternalFields(contentId, sourceRec.source_id, [rec.field])
      }
      const [updated, updatedRecs] = await Promise.all([
        metadataApi.getContent(contentId),
        metadataApi.getRecommendations(contentId),
      ])
      setContent(updated)
      setRecommendations(updatedRecs)
      setAppliedFields((prev) => new Set([...prev, rec.field]))
    } catch (err) {
      console.error("apply rec failed", err)
    }
  }

  const handleApplyAllAuto = async () => {
    if (!recommendations) return
    for (const rec of recommendations.auto_fill) {
      const top = rec.recommendations[0]
      if (top) await handleApplyRec(rec, top)
    }
  }

  const handleRegenerate = async () => {
    try {
      await metadataApi.triggerEnrich(contentId)
      alert("AI 재분석 요청이 전송됐습니다. 잠시 후 새로고침하세요.")
    } catch {
      alert("재분석 요청에 실패했습니다.")
    }
  }

  // Handler for partialReprocess (AI 재처리)
  const handlePartialReprocess = async () => {
    try {
      await metadataApi.partialReprocess(contentId)
      alert("AI 재처리 요청이 전송되었습니다.")
    } catch (error) {
      console.error("AI 재처리 실패:", error)
      alert("AI 재처리에 실패했습니다.")
    }
  }

  // Handler for lockFields (필드 잠금)
  const handleLockFields = async () => {
    try {
      await metadataApi.lockFields(contentId, ["title", "director"], "품질 검증 완료")
      alert("필드가 잠금 처리되었습니다.")
    } catch (error) {
      console.error("필드 잠금 실패:", error)
      alert("필드 잠금에 실패했습니다.")
    }
  }

  // Handler for requestPreviewClip (Preview clip 요청)
  const handleRequestPreviewClip = async () => {
    try {
      await metadataApi.requestPreviewClip(contentId)
      alert("Preview clip 생성이 요청되었습니다.")
    } catch (error) {
      console.error("Preview clip 요청 실패:", error)
      alert("Preview clip 요청에 실패했습니다.")
    }
  }

  const statusInfo = (STATUS_BADGE[content.status] ?? STATUS_BADGE.waiting)!
  const qualityScore = content.quality_score ?? 0

  // Container(series/season) → 자식 목록 레이아웃으로 디스패치
  if (!isLeafType(content.content_type)) {
    return (
      <DetailContainerLayout
        content={content}
        contentId={contentId}
        parentChain={parentChain}
        statusInfo={statusInfo}
        qualityScore={qualityScore}
        childrenItems={childrenItems}
        childrenLoading={childrenLoading}
        onReprocess={handlePartialReprocess}
        onLock={handleLockFields}
        onPreviewClip={handleRequestPreviewClip}
      />
    )
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <DetailHeader
        content={content}
        contentId={contentId}
        mode={mode}
        parentChain={parentChain}
        statusInfo={statusInfo}
        onModeChange={handleModeChange}
        onReprocess={handlePartialReprocess}
        onLock={handleLockFields}
        onPreviewClip={handleRequestPreviewClip}
      />

      {/* view: 2컬럼 (Poster + 현재상태) / edit·review: 3컬럼 (Step 2에서 전환) */}
      {mode === "view" ? (
        <div className="grid grid-cols-[200px_1fr] gap-4 p-6 max-w-[1200px] mx-auto">
          {/* 포스터 컬럼 */}
          <PosterPanel
            content={content}
            posterCandidates={posterCandidates ?? []}
            primaryId={posterCandidates?.find((c) => c.is_primary)?.id ?? null}
            onSelectPrimary={async (id) => {
              const updated = await posterRecommendApi.selectPrimary(contentId, id)
              setPosterCandidates(updated)
            }}
            onRecommendPoster={async () => {
              const res = await posterRecommendApi.recommend(contentId)
              setPosterCandidates(res.candidates)
            }}
          />
          {/* 중앙 — 현재 상태 */}
          <ContentShell
            content={content}
            contentId={contentId}
            posterCandidates={posterCandidates ?? []}
            primaryId={posterCandidates?.find((c) => c.is_primary)?.id ?? null}
            childrenItems={childrenItems}
            childrenLoading={childrenLoading}
            onSelectPrimary={async (id) => {
              const updated = await posterRecommendApi.selectPrimary(contentId, id)
              setPosterCandidates(updated)
            }}
            onRecommendPoster={async () => {
              const res = await posterRecommendApi.recommend(contentId)
              setPosterCandidates(res.candidates)
            }}
          />
        </div>
      ) : (
      <ThreeColumnShell
        poster={
          <PosterPanel
            content={content}
            posterCandidates={posterCandidates ?? []}
            primaryId={posterCandidates?.find((c) => c.is_primary)?.id ?? null}
            onSelectPrimary={async (id) => {
              const updated = await posterRecommendApi.selectPrimary(contentId, id)
              setPosterCandidates(updated)
            }}
            onRecommendPoster={async () => {
              const res = await posterRecommendApi.recommend(contentId)
              setPosterCandidates(res.candidates)
            }}
          />
        }
        current={
          <ContentShell
            content={content}
            contentId={contentId}
            posterCandidates={posterCandidates ?? []}
            primaryId={posterCandidates?.find((c) => c.is_primary)?.id ?? null}
            childrenItems={childrenItems}
            childrenLoading={childrenLoading}
            onSelectPrimary={async (id) => {
              const updated = await posterRecommendApi.selectPrimary(contentId, id)
              setPosterCandidates(updated)
            }}
            onRecommendPoster={async () => {
              const res = await posterRecommendApi.recommend(contentId)
              setPosterCandidates(res.candidates)
            }}
          />
        }
        right={
          mode === "edit" ? (
            <EditPane
              content={content}
              contentId={contentId}
              posterCandidates={posterCandidates ?? []}
              primaryId={posterCandidates?.find((c) => c.is_primary)?.id ?? null}
              onSelectPrimary={async (id) => {
                const updated = await posterRecommendApi.selectPrimary(contentId, id)
                setPosterCandidates(updated)
              }}
              onSaved={(updated) => {
                setContent(updated)
                handleModeChange("view")
              }}
              onCancel={() => handleModeChange("view")}
            />
          ) : (
            <ReviewPane
              content={content}
              contentId={contentId}
              recommendations={recommendations}
              posterCandidates={posterCandidates ?? []}
              primaryId={posterCandidates?.find((c) => c.is_primary)?.id ?? null}
              appliedFields={appliedFields}
              onSelectPrimary={async (id) => {
                const updated = await posterRecommendApi.selectPrimary(contentId, id)
                setPosterCandidates(updated)
              }}
              onApply={handleApplyRec}
              onApplyAll={handleApplyAllAuto}
              onDecision={() => router.push("/programming/contents/review")}
            />
          )
        }
        footer={
          recommendations && (
            <AISummaryBottom
              recommendations={recommendations}
              appliedFields={appliedFields}
              onApplyAllAuto={handleApplyAllAuto}
              onRegenerate={handleRegenerate}
              onDismiss={() => {}}
            />
          )
        }
      />
      )}
    </div>
  )
}
