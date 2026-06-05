"use client"

import { useEffect, useState } from "react"
import { RefreshCw } from "lucide-react"
import { metadataApi, type ContentDetail, type StagingItem } from "@/lib/api"
import { isLeafType } from "@/components/contents/detail/contentType"
import { ChildrenTable } from "@/components/contents/detail/ChildrenTable"
import type { BreadcrumbParent } from "@/components/contents/detail/BreadcrumbNav"

// ── 상수 (pipeline/page.tsx 와 동기) ─────────────────────────────────────────

const STATUS_COLOR: Record<string, string> = {
  raw: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
  enriched: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  ai: "bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400",
  review: "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400",
  approved: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  rejected: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  published: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
}
const STATUS_LABEL: Record<string, string> = {
  raw: "RAW", enriched: "Enrich완료", ai: "AI처리완료",
  review: "검수", approved: "승인", rejected: "반려", published: "게시",
}
const TYPE_LABEL: Record<string, string> = { movie: "영화", series: "시리즈", season: "시즌", episode: "에피" }

// ── 브레드크럼 (파이프라인용 — router.push 없이 onSelect 사용) ─────────────────

function PipelineBreadcrumb({
  parents,
  onSelect,
}: {
  parents: BreadcrumbParent[]
  onSelect: (id: number) => void
}) {
  if (parents.length === 0) return null
  return (
    <div className="flex items-center gap-1 text-xs text-muted-foreground flex-wrap px-3 pt-2">
      {parents.map((p, i) => (
        <span key={p.id} className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => onSelect(p.id)}
            className="hover:text-foreground hover:underline transition-colors"
            title={p.title}
          >
            {p.title}
          </button>
          {i < parents.length - 1 && <span className="text-border">›</span>}
        </span>
      ))}
    </div>
  )
}

// ── 메인 컴포넌트 ─────────────────────────────────────────────────────────────

export interface PipelineDrilldownDetailProps {
  contentId: number | null
  refreshKey?: number
  onSelect: (id: number) => void
}

export function PipelineDrilldownDetail({ contentId, refreshKey = 0, onSelect }: PipelineDrilldownDetailProps) {
  const [detail, setDetail] = useState<ContentDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [hierarchy, setHierarchy] = useState<StagingItem | null>(null)
  const [hierarchyLoading, setHierarchyLoading] = useState(false)
  const [parents, setParents] = useState<BreadcrumbParent[]>([])

  useEffect(() => {
    if (contentId === null) { setDetail(null); setHierarchy(null); setParents([]); return }
    let alive = true
    setLoading(true)
    metadataApi.getContent(contentId)
      .then((d) => { if (alive) setDetail(d) })
      .catch(() => { if (alive) setDetail(null) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [contentId, refreshKey])

  // 컨테이너 타입이면 hierarchy + parentChain 로드
  useEffect(() => {
    if (!detail || isLeafType(detail.content_type)) {
      setHierarchy(null)
      setParents([])
      return
    }
    let alive = true
    setHierarchyLoading(true)
    metadataApi.getHierarchy(detail.id)
      .then((h) => { if (alive) setHierarchy(h) })
      .catch(() => { if (alive) setHierarchy(null) })
      .finally(() => { if (alive) setHierarchyLoading(false) })

    // parentChain — series는 부모 없음, season은 series 부모 1단계
    if (detail.parent_id != null) {
      metadataApi.getContent(detail.parent_id)
        .then((p) => {
          if (alive) setParents([{ id: p.id, title: p.title, content_type: p.content_type }])
        })
        .catch(() => { if (alive) setParents([]) })
    } else {
      setParents([])
    }
    return () => { alive = false }
  }, [detail])

  if (contentId === null) {
    return (
      <div className="rounded-lg border border-dashed border-border bg-background p-4 text-center text-xs text-muted-foreground">
        목록에서 콘텐츠를 선택하면 메타 정보가 표시됩니다
      </div>
    )
  }

  if (loading) {
    return (
      <div className="rounded-lg border border-border bg-background p-4 text-center text-xs text-muted-foreground">
        <RefreshCw className="h-4 w-4 mx-auto mb-1.5 animate-spin opacity-50" />
        메타 로딩 중…
      </div>
    )
  }

  if (!detail) return null

  // ── Leaf (movie / episode) — 기존 SelectedContentMeta 스타일 유지 ──────────
  if (isLeafType(detail.content_type)) {
    const fields: Array<[string, string | null]> = [
      ["제작연도", detail.production_year != null ? String(detail.production_year) : null],
      ["국가", detail.country ?? null],
      ["장르", (detail.genres ?? []).map((g) => g.genre.name_ko).join(", ") || null],
      ["러닝타임", detail.runtime_minutes != null ? `${detail.runtime_minutes}분` : null],
      ["출연", (detail.credits ?? []).filter((c) => /actor|cast|주연|출연/i.test(c.role)).map((c) => c.person.name_ko).join(", ") || null],
      ["감독", (detail.credits ?? []).filter((c) => /director|감독/i.test(c.role)).map((c) => c.person.name_ko).join(", ") || null],
    ]
    const synopsis = detail.metadata_record?.final_synopsis ?? detail.metadata_record?.ai_synopsis ?? detail.metadata_record?.cp_synopsis ?? null
    return (
      <div className="rounded-lg border border-border bg-background overflow-hidden">
        <div className="px-3 py-2 bg-muted/40 flex items-center justify-between gap-2">
          <span className="text-xs font-semibold truncate">{detail.title}</span>
          <span className="text-xs text-muted-foreground shrink-0">#{detail.id}</span>
        </div>
        <div className="p-3 flex gap-3">
          {detail.poster_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={detail.poster_url} alt={detail.title} className="w-16 h-24 object-cover rounded border border-border shrink-0" />
          ) : (
            <div className="w-16 h-24 rounded border border-dashed border-border flex items-center justify-center text-[10px] text-muted-foreground shrink-0">No Img</div>
          )}
          <div className="flex-1 min-w-0 space-y-1.5">
            <div className="flex items-center gap-1.5">
              <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${STATUS_COLOR[detail.status] ?? ""}`}>{STATUS_LABEL[detail.status] ?? detail.status}</span>
              <span className="text-[10px] text-muted-foreground">{TYPE_LABEL[detail.content_type] ?? detail.content_type}</span>
            </div>
            <div className="space-y-0.5 text-xs">
              {fields.map(([label, value]) => (
                <div key={label} className="flex gap-2">
                  <span className="text-muted-foreground w-14 shrink-0">{label}</span>
                  <span className="truncate flex-1">{value ?? "—"}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
        {synopsis && (
          <div className="px-3 pb-3 -mt-1">
            <p className="text-xs text-muted-foreground line-clamp-4">{synopsis}</p>
          </div>
        )}
      </div>
    )
  }

  // ── Container (series / season) — 계층 드릴다운 ─────────────────────────────
  const parentType = detail.content_type === "series" ? "series" : "season"
  const children = hierarchy?.children ?? []

  return (
    <div className="rounded-lg border border-border bg-background overflow-hidden space-y-0">
      <div className="px-3 py-2 bg-muted/40 flex items-center justify-between gap-2">
        <span className="text-xs font-semibold truncate">{detail.title}</span>
        <div className="flex items-center gap-2 shrink-0">
          <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${STATUS_COLOR[detail.status] ?? ""}`}>{STATUS_LABEL[detail.status] ?? detail.status}</span>
          <span className="text-xs text-muted-foreground">#{detail.id}</span>
        </div>
      </div>
      {parents.length > 0 && (
        <PipelineBreadcrumb parents={parents} onSelect={onSelect} />
      )}
      <div className="p-3">
        <ChildrenTable
          children={children}
          parentType={parentType}
          loading={hierarchyLoading}
          onItemClick={onSelect}
        />
      </div>
    </div>
  )
}
