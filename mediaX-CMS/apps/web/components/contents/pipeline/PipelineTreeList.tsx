"use client"

import { useState, useMemo } from "react"
import { ChevronRight, ChevronDown, RefreshCw } from "lucide-react"
import { TypeIcon } from "@/components/contents/detail/contentType"
import type { ContentOut } from "@/lib/api"

// ── 상수 (pipeline/page.tsx 와 동기) ─────────────────────────────────────────

const STATUS_LABEL: Record<string, string> = {
  raw: "RAW", enriched: "Enrich완료", ai: "AI처리완료",
  review: "검수", approved: "승인", rejected: "반려", published: "게시",
}
const STATUS_COLOR: Record<string, string> = {
  raw: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
  enriched: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  ai: "bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400",
  review: "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400",
  approved: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  rejected: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  published: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
}
const TYPE_LABEL: Record<string, string> = { movie: "영화", series: "시리즈", season: "시즌", episode: "에피" }

// ── 트리 그룹핑 ───────────────────────────────────────────────────────────────

interface TreeNode {
  item: ContentOut
  children: TreeNode[]
}

function buildTree(contents: ContentOut[]): { roots: TreeNode[]; idMap: Map<number, TreeNode> } {
  const idMap = new Map<number, TreeNode>()
  for (const c of contents) idMap.set(c.id, { item: c, children: [] })

  const roots: TreeNode[] = []
  for (const c of contents) {
    const node = idMap.get(c.id)!
    const parentNode = c.parent_id != null ? idMap.get(c.parent_id) : undefined
    if (parentNode) {
      parentNode.children.push(node)
    } else {
      roots.push(node)
    }
  }

  // series > season > episode 순으로 정렬
  const typeOrder: Record<string, number> = { series: 0, season: 1, episode: 2, movie: 3 }
  const sort = (nodes: TreeNode[]) => {
    nodes.sort((a, b) => {
      const to = (typeOrder[a.item.content_type] ?? 9) - (typeOrder[b.item.content_type] ?? 9)
      if (to !== 0) return to
      const sn = (a.item.season_number ?? 0) - (b.item.season_number ?? 0)
      if (sn !== 0) return sn
      return (a.item.episode_number ?? 0) - (b.item.episode_number ?? 0)
    })
    nodes.forEach((n) => sort(n.children))
  }
  sort(roots)
  return { roots, idMap }
}

function countDescendants(node: TreeNode): number {
  return node.children.reduce((acc, c) => acc + 1 + countDescendants(c), 0)
}

// ── 행 컴포넌트 ───────────────────────────────────────────────────────────────

function TreeRow({
  node,
  depth,
  selectedId,
  onSelect,
  expanded,
  onToggle,
}: {
  node: TreeNode
  depth: number
  selectedId: number | null
  onSelect: (id: number) => void
  expanded: boolean
  onToggle: () => void
}) {
  const c = node.item
  const hasChildren = node.children.length > 0
  const isSelected = selectedId === c.id
  const descCount = useMemo(() => countDescendants(node), [node])

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onSelect(c.id)}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onSelect(c.id) }}
      className={`w-full flex items-center gap-1.5 px-2 py-1.5 text-left hover:bg-accent transition-colors cursor-pointer ${
        isSelected ? "bg-primary/5 border-l-2 border-primary" : ""
      }`}
      style={{ paddingLeft: `${8 + depth * 16}px` }}
    >
      {/* 접이식 토글 */}
      <span
        className="shrink-0 w-4 h-4 flex items-center justify-center text-muted-foreground"
        onClick={(e) => { if (hasChildren) { e.stopPropagation(); onToggle() } }}
      >
        {hasChildren
          ? (expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />)
          : <span className="w-3" />
        }
      </span>

      {/* 타입 아이콘 */}
      <span className="shrink-0 text-muted-foreground">
        <TypeIcon type={c.content_type as "movie" | "series" | "season" | "episode"} className="h-3 w-3" />
      </span>

      {/* 상태 배지 */}
      <span className={`shrink-0 text-[10px] px-1.5 py-0.5 rounded font-medium ${STATUS_COLOR[c.status] ?? ""}`}>
        {STATUS_LABEL[c.status] ?? c.status}
      </span>

      {/* 타입 레이블 */}
      <span className="text-xs text-muted-foreground shrink-0">{TYPE_LABEL[c.content_type] ?? c.content_type}</span>

      {/* 제목 */}
      <span className="text-xs font-medium truncate flex-1">{c.title}</span>

      {/* roll-up 칩 — 자손 수 */}
      {hasChildren && (
        <span className="shrink-0 text-[10px] bg-muted text-muted-foreground px-1.5 py-0.5 rounded-full">
          {descCount}건
        </span>
      )}

      {/* ID */}
      <span className="text-xs text-muted-foreground shrink-0">#{c.id}</span>
    </div>
  )
}

function TreeNodes({
  nodes,
  depth,
  selectedId,
  onSelect,
  expandedSet,
  onToggle,
}: {
  nodes: TreeNode[]
  depth: number
  selectedId: number | null
  onSelect: (id: number) => void
  expandedSet: Set<number>
  onToggle: (id: number) => void
}) {
  return (
    <>
      {nodes.map((node) => (
        <div key={node.item.id}>
          <TreeRow
            node={node}
            depth={depth}
            selectedId={selectedId}
            onSelect={onSelect}
            expanded={expandedSet.has(node.item.id)}
            onToggle={() => onToggle(node.item.id)}
          />
          {expandedSet.has(node.item.id) && node.children.length > 0 && (
            <TreeNodes
              nodes={node.children}
              depth={depth + 1}
              selectedId={selectedId}
              onSelect={onSelect}
              expandedSet={expandedSet}
              onToggle={onToggle}
            />
          )}
        </div>
      ))}
    </>
  )
}

// ── 메인 컴포넌트 ─────────────────────────────────────────────────────────────

export interface PipelineTreeListProps {
  contents: ContentOut[]
  loading: boolean
  selectedId: number | null
  onSelect: (id: number) => void
  viewMode: "flat" | "tree"
}

export function PipelineTreeList({ contents, loading, selectedId, onSelect, viewMode }: PipelineTreeListProps) {
  const { roots } = useMemo(() => buildTree(contents), [contents])

  // 최상위 series/season 노드를 기본 펼침
  const [expandedSet, setExpandedSet] = useState<Set<number>>(() => {
    const s = new Set<number>()
    for (const c of contents) {
      if (c.content_type === "series" || c.content_type === "season") s.add(c.id)
    }
    return s
  })

  const toggleNode = (id: number) => {
    setExpandedSet((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  if (loading) {
    return (
      <div className="rounded-lg border border-border bg-background p-4 text-center text-xs text-muted-foreground">
        <RefreshCw className="h-4 w-4 mx-auto mb-1.5 animate-spin opacity-50" />
        목록 로딩 중…
      </div>
    )
  }

  if (contents.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border bg-background p-4 text-center text-xs text-muted-foreground">
        시드 데이터 없음 — S0 패널에서 시드 생성 후 새로고침
      </div>
    )
  }

  if (viewMode === "flat") {
    // 기존 TestContentList 동작 그대로 유지
    return (
      <div className="rounded-lg border border-border bg-background overflow-hidden">
        <div className="px-3 py-2 bg-muted/40 flex items-center justify-between">
          <span className="text-xs font-semibold text-muted-foreground">콘텐츠/시리즈 목록</span>
          <span className="text-xs text-muted-foreground">{contents.length}건</span>
        </div>
        <div className="divide-y divide-border max-h-64 overflow-y-auto">
          {contents.map((c) => (
            <button
              key={c.id}
              onClick={() => onSelect(c.id)}
              className={`w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-accent transition-colors ${
                selectedId === c.id ? "bg-primary/5 border-l-2 border-primary" : ""
              }`}
            >
              <span className={`shrink-0 text-[10px] px-1.5 py-0.5 rounded font-medium ${STATUS_COLOR[c.status] ?? ""}`}>
                {STATUS_LABEL[c.status] ?? c.status}
              </span>
              <span className="text-xs text-muted-foreground shrink-0">{TYPE_LABEL[c.content_type] ?? c.content_type}</span>
              <span className="text-xs font-medium truncate flex-1">{c.title}</span>
              <span className="text-xs text-muted-foreground shrink-0">#{c.id}</span>
            </button>
          ))}
        </div>
      </div>
    )
  }

  // tree 모드
  return (
    <div className="rounded-lg border border-border bg-background overflow-hidden">
      <div className="px-3 py-2 bg-muted/40 flex items-center justify-between">
        <span className="text-xs font-semibold text-muted-foreground">콘텐츠/시리즈 목록</span>
        <span className="text-xs text-muted-foreground">{contents.length}건</span>
      </div>
      <div className="divide-y divide-border max-h-64 overflow-y-auto">
        <TreeNodes
          nodes={roots}
          depth={0}
          selectedId={selectedId}
          onSelect={onSelect}
          expandedSet={expandedSet}
          onToggle={toggleNode}
        />
      </div>
    </div>
  )
}
