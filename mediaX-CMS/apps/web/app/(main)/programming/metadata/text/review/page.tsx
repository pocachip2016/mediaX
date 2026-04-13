"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import {
  ArrowLeft, Check, X, RefreshCw, ChevronDown, ChevronRight, CheckCircle, AlertCircle,
} from "lucide-react"
import { textMetaApi, type TextMetaOut } from "@/lib/api"

const MOCK_INCOMPLETE: TextMetaOut[] = [
  {
    id: 2, title: "오징어 게임 시즌2", content_type: "series", cp_name: "넷플릭스", production_year: 2024,
    season_number: null, episode_number: null, parent_id: null,
    synopsis: "생존을 건 게임이 다시 시작된다.", genre_primary: "스릴러", genre_secondary: "드라마",
    mood_tags: ["긴장감", "심야감성"], rating_suggestion: "18세이상관람가",
    text_meta_completed: false, episode_completed_count: 3, episode_total_count: 7,
    children: [
      {
        id: 20, title: "시즌 2", content_type: "season", cp_name: null, production_year: 2024,
        season_number: 2, episode_number: null, parent_id: 2,
        synopsis: null, genre_primary: null, genre_secondary: null, mood_tags: null,
        rating_suggestion: null, text_meta_completed: false,
        episode_completed_count: 3, episode_total_count: 7,
        children: [
          { id: 204, title: "EP.04", content_type: "episode", cp_name: null, production_year: 2024, season_number: null, episode_number: 4, parent_id: 20, synopsis: null, genre_primary: null, genre_secondary: null, mood_tags: null, rating_suggestion: null, text_meta_completed: false, episode_completed_count: 0, episode_total_count: 0, children: [] },
          { id: 205, title: "EP.05", content_type: "episode", cp_name: null, production_year: 2024, season_number: null, episode_number: 5, parent_id: 20, synopsis: null, genre_primary: null, genre_secondary: null, mood_tags: null, rating_suggestion: null, text_meta_completed: false, episode_completed_count: 0, episode_total_count: 0, children: [] },
          { id: 206, title: "EP.06", content_type: "episode", cp_name: null, production_year: 2024, season_number: null, episode_number: 6, parent_id: 20, synopsis: null, genre_primary: null, genre_secondary: null, mood_tags: null, rating_suggestion: null, text_meta_completed: false, episode_completed_count: 0, episode_total_count: 0, children: [] },
          { id: 207, title: "EP.07", content_type: "episode", cp_name: null, production_year: 2024, season_number: null, episode_number: 7, parent_id: 20, synopsis: null, genre_primary: null, genre_secondary: null, mood_tags: null, rating_suggestion: null, text_meta_completed: false, episode_completed_count: 0, episode_total_count: 0, children: [] },
        ],
      },
    ],
  },
  {
    id: 4, title: "외계+인 2부", content_type: "movie", cp_name: "CJ ENM", production_year: 2024,
    season_number: null, episode_number: null, parent_id: null,
    synopsis: null, genre_primary: "SF", genre_secondary: "액션",
    mood_tags: null, rating_suggestion: null, text_meta_completed: false,
    episode_completed_count: 0, episode_total_count: 0, children: [],
  },
]

function collectAllIds(item: TextMetaOut): number[] {
  const ids = [item.id]
  for (const season of item.children) {
    ids.push(season.id)
    for (const ep of season.children) ids.push(ep.id)
  }
  return ids
}

export default function TextReviewPage() {
  const [items, setItems] = useState<TextMetaOut[]>(MOCK_INCOMPLETE)
  const [selected, setSelected] = useState<TextMetaOut | null>(null)
  const [checkedIds, setCheckedIds] = useState<Set<number>>(new Set())
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set())
  const [loading, setLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)
  const [editSynopsis, setEditSynopsis] = useState("")
  const [editGenre, setEditGenre] = useState("")

  const fetchItems = async () => {
    setLoading(true)
    try {
      const res = await textMetaApi.list({ completed: false })
      setItems(res.items)
    } catch {
      // Mock 유지
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchItems() }, [])

  const selectItem = (item: TextMetaOut) => {
    setSelected(item)
    setEditSynopsis(item.synopsis ?? "")
    setEditGenre(item.genre_primary ?? "")
  }

  const handleComplete = async (complete: boolean) => {
    if (!selected) return
    setActionLoading(true)
    try {
      await textMetaApi.update(selected.id, {
        synopsis: editSynopsis,
        genre_primary: editGenre,
        completed: complete,
      })
      setItems((prev) => prev.filter((i) => i.id !== selected.id))
      setSelected(null)
    } catch {
      setItems((prev) => prev.filter((i) => i.id !== selected.id))
      setSelected(null)
    } finally {
      setActionLoading(false)
    }
  }

  const handleBulkComplete = async () => {
    if (checkedIds.size === 0) return
    setActionLoading(true)
    try {
      await textMetaApi.bulkComplete(Array.from(checkedIds))
      setItems((prev) => prev.filter((i) => !checkedIds.has(i.id)))
      setCheckedIds(new Set())
    } catch {
      setItems((prev) => prev.filter((i) => !checkedIds.has(i.id)))
      setCheckedIds(new Set())
    } finally {
      setActionLoading(false)
    }
  }

  const toggleCheck = (id: number, allIds: number[]) => {
    setCheckedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        allIds.forEach((i) => next.delete(i))
      } else {
        allIds.forEach((i) => next.add(i))
      }
      return next
    })
  }

  const toggleExpand = (id: number) => {
    setExpandedIds((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  function renderItem(item: TextMetaOut, depth: number) {
    const isExpanded = expandedIds.has(item.id)
    const hasChildren = item.children.length > 0
    const indentPx = depth * 20

    return (
      <div key={item.id}>
        <div
          className={`flex items-center gap-2 px-3 py-2.5 hover:bg-accent/50 border-b border-border/50 transition-colors cursor-pointer ${selected?.id === item.id ? "bg-accent" : ""}`}
          style={{ paddingLeft: `${12 + indentPx}px` }}
          onClick={() => selectItem(item)}
        >
          <input
            type="checkbox"
            checked={checkedIds.has(item.id)}
            onChange={() => toggleCheck(item.id, collectAllIds(item))}
            onClick={(e) => e.stopPropagation()}
            className="rounded shrink-0"
          />
          {hasChildren ? (
            <button
              onClick={(e) => { e.stopPropagation(); toggleExpand(item.id) }}
              className="shrink-0"
            >
              {isExpanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
            </button>
          ) : <span className="w-4 shrink-0" />}

          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium truncate">{item.title}</div>
            {depth === 0 && (
              <div className="text-xs text-muted-foreground truncate">{item.cp_name} · {item.production_year}</div>
            )}
          </div>

          {item.episode_total_count > 0 ? (
            <span className="text-xs text-orange-500 font-medium shrink-0">
              {item.episode_completed_count}/{item.episode_total_count}화
            </span>
          ) : (
            <AlertCircle className="h-4 w-4 text-orange-500 shrink-0" />
          )}
        </div>
        {hasChildren && isExpanded && item.children.map((child) => renderItem(child, depth + 1))}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/programming/metadata/text" className="p-1.5 rounded-lg hover:bg-accent">
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold">글자메타 검수</h1>
            <p className="text-sm text-muted-foreground mt-1">미완료 항목 검수 · 총 {items.length}건</p>
          </div>
        </div>
        <div className="flex gap-2">
          {checkedIds.size > 0 && (
            <button
              onClick={handleBulkComplete}
              disabled={actionLoading}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-green-600 text-white text-sm font-medium hover:bg-green-700 disabled:opacity-50"
            >
              <CheckCircle className="h-4 w-4" /> 일괄 완료 ({checkedIds.size}건)
            </button>
          )}
          <button onClick={fetchItems} className="p-2 rounded-lg border border-border hover:bg-accent">
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4 min-h-[600px]">
        {/* 좌: 미완료 목록 */}
        <div className="lg:col-span-2 rounded-xl border border-border bg-card overflow-hidden flex flex-col">
          <div className="px-4 py-3 border-b border-border bg-muted/30 text-sm font-medium text-muted-foreground">
            미완료 목록
          </div>
          <div className="flex-1 overflow-y-auto">
            {items.length === 0 ? (
              <div className="p-8 text-center text-muted-foreground text-sm">모든 글자메타가 완료되었습니다</div>
            ) : (
              items.map((item) => renderItem(item, 0))
            )}
          </div>
        </div>

        {/* 우: 상세 + 편집 */}
        <div className="lg:col-span-3 rounded-xl border border-border bg-card overflow-hidden flex flex-col">
          {!selected ? (
            <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
              왼쪽에서 항목을 선택하세요
            </div>
          ) : (
            <>
              <div className="px-5 py-4 border-b border-border">
                <h2 className="font-bold">{selected.title}</h2>
                <p className="text-sm text-muted-foreground">{selected.cp_name} · {selected.production_year}</p>
              </div>

              <div className="flex-1 overflow-y-auto p-5 space-y-5">
                {/* 시놉시스 diff */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <div className="text-xs font-medium text-muted-foreground uppercase">CP 원본</div>
                    <div className="rounded-lg bg-muted/50 p-3 text-sm min-h-[80px] text-muted-foreground italic">
                      {selected.synopsis ?? "없음"}
                    </div>
                  </div>
                  <div className="space-y-1">
                    <div className="text-xs font-medium text-primary uppercase">AI 수정</div>
                    <textarea
                      className="w-full rounded-lg border border-primary/30 bg-primary/5 p-3 text-sm min-h-[80px] resize-none focus:outline-none focus:ring-1 focus:ring-primary"
                      value={editSynopsis}
                      onChange={(e) => setEditSynopsis(e.target.value)}
                      placeholder="시놉시스를 입력하거나 수정하세요..."
                    />
                  </div>
                </div>

                {/* 장르 */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <div className="text-xs font-medium text-muted-foreground uppercase">장르</div>
                    <div className="rounded-lg bg-muted/50 px-3 py-2 text-sm">{selected.genre_primary ?? "-"}</div>
                  </div>
                  <div className="space-y-1">
                    <div className="text-xs font-medium text-primary uppercase">수정 장르</div>
                    <input
                      className="w-full rounded-lg border border-primary/30 bg-primary/5 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                      value={editGenre}
                      onChange={(e) => setEditGenre(e.target.value)}
                    />
                  </div>
                </div>

                {/* 감성 태그 */}
                {selected.mood_tags && selected.mood_tags.length > 0 && (
                  <div className="space-y-1">
                    <div className="text-xs font-medium text-muted-foreground uppercase">감성 태그</div>
                    <div className="flex flex-wrap gap-1.5">
                      {selected.mood_tags.map((t) => (
                        <span key={t} className="text-xs px-2 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20">
                          #{t}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <div className="px-5 py-4 border-t border-border flex gap-2">
                <button
                  onClick={() => handleComplete(true)}
                  disabled={actionLoading}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-green-600 text-white text-sm font-medium hover:bg-green-700 disabled:opacity-50"
                >
                  <Check className="h-4 w-4" /> 완료 처리
                </button>
                <button
                  onClick={() => handleComplete(false)}
                  disabled={actionLoading}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg border border-border text-sm hover:bg-accent disabled:opacity-50"
                >
                  저장만
                </button>
                <button
                  onClick={() => setSelected(null)}
                  disabled={actionLoading}
                  className="ml-auto flex items-center gap-1.5 px-4 py-2 rounded-lg bg-red-100 text-red-700 dark:bg-red-900/20 dark:text-red-400 text-sm hover:bg-red-200 dark:hover:bg-red-900/40 disabled:opacity-50"
                >
                  <X className="h-4 w-4" /> 닫기
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
