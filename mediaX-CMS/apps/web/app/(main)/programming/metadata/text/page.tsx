"use client"

import { useEffect, useState, useCallback } from "react"
import Link from "next/link"
import {
  ArrowLeft, ChevronDown, ChevronRight, CheckCircle, AlertCircle,
  RefreshCw, Film, Tv, Check, Sparkles,
} from "lucide-react"
import { textMetaApi, type TextMetaOut, type TextMetaSuggestion } from "@/lib/api"

// ── Mock 데이터 ───────────────────────────────────────────────
const MOCK_ITEMS: TextMetaOut[] = [
  {
    id: 1, title: "기생충", content_type: "movie", cp_name: "CJ ENM", production_year: 2019,
    season_number: null, episode_number: null, parent_id: null,
    synopsis: "두 가족의 계층 갈등을 다룬 블랙 코미디 스릴러.", genre_primary: "드라마",
    genre_secondary: "스릴러", mood_tags: ["긴장감", "반전있음", "실화기반"],
    rating_suggestion: "15세이상관람가", text_meta_completed: true,
    episode_completed_count: 0, episode_total_count: 0, children: [],
  },
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
          { id: 201, title: "EP.01 — 무궁화 꽃이 피었습니다", content_type: "episode", cp_name: null, production_year: 2024, season_number: null, episode_number: 1, parent_id: 20, synopsis: "기훈이 다시 게임에 참가한다.", genre_primary: "스릴러", genre_secondary: null, mood_tags: ["긴장감"], rating_suggestion: "18세이상관람가", text_meta_completed: true, episode_completed_count: 0, episode_total_count: 0, children: [] },
          { id: 202, title: "EP.02 — 지옥의 문", content_type: "episode", cp_name: null, production_year: 2024, season_number: null, episode_number: 2, parent_id: 20, synopsis: "두 번째 게임이 시작된다.", genre_primary: "스릴러", genre_secondary: null, mood_tags: ["긴장감"], rating_suggestion: "18세이상관람가", text_meta_completed: true, episode_completed_count: 0, episode_total_count: 0, children: [] },
          { id: 203, title: "EP.03 — 마지막 게임", content_type: "episode", cp_name: null, production_year: 2024, season_number: null, episode_number: 3, parent_id: 20, synopsis: "세 번째 게임.", genre_primary: "스릴러", genre_secondary: null, mood_tags: [], rating_suggestion: null, text_meta_completed: true, episode_completed_count: 0, episode_total_count: 0, children: [] },
          { id: 204, title: "EP.04", content_type: "episode", cp_name: null, production_year: 2024, season_number: null, episode_number: 4, parent_id: 20, synopsis: null, genre_primary: null, genre_secondary: null, mood_tags: null, rating_suggestion: null, text_meta_completed: false, episode_completed_count: 0, episode_total_count: 0, children: [] },
          { id: 205, title: "EP.05", content_type: "episode", cp_name: null, production_year: 2024, season_number: null, episode_number: 5, parent_id: 20, synopsis: null, genre_primary: null, genre_secondary: null, mood_tags: null, rating_suggestion: null, text_meta_completed: false, episode_completed_count: 0, episode_total_count: 0, children: [] },
          { id: 206, title: "EP.06", content_type: "episode", cp_name: null, production_year: 2024, season_number: null, episode_number: 6, parent_id: 20, synopsis: null, genre_primary: null, genre_secondary: null, mood_tags: null, rating_suggestion: null, text_meta_completed: false, episode_completed_count: 0, episode_total_count: 0, children: [] },
          { id: 207, title: "EP.07", content_type: "episode", cp_name: null, production_year: 2024, season_number: null, episode_number: 7, parent_id: 20, synopsis: null, genre_primary: null, genre_secondary: null, mood_tags: null, rating_suggestion: null, text_meta_completed: false, episode_completed_count: 0, episode_total_count: 0, children: [] },
        ],
      },
    ],
  },
  {
    id: 3, title: "서울의 봄", content_type: "movie", cp_name: "플러스엠 엔터테인먼트", production_year: 2023,
    season_number: null, episode_number: null, parent_id: null,
    synopsis: "1979년 12월 12일 군사 반란을 막으려는 자들의 이야기.", genre_primary: "드라마",
    genre_secondary: "역사", mood_tags: ["긴장감", "실화기반"],
    rating_suggestion: "12세이상관람가", text_meta_completed: true,
    episode_completed_count: 0, episode_total_count: 0, children: [],
  },
]

const CONTENT_TYPE_LABEL: Record<string, string> = {
  movie: "영화", series: "시리즈", season: "시즌", episode: "에피소드",
}

function CompletionBadge({ completed, episodeDone, episodeTotal }: {
  completed: boolean; episodeDone?: number; episodeTotal?: number
}) {
  if (episodeTotal && episodeTotal > 0) {
    const pct = Math.round((episodeDone! / episodeTotal) * 100)
    const color = episodeDone === episodeTotal ? "text-green-600" : "text-orange-500"
    return <span className={`text-xs font-medium ${color}`}>{episodeDone}/{episodeTotal}화</span>
  }
  return completed
    ? <span className="flex items-center gap-1 text-xs text-green-600 font-medium"><CheckCircle className="h-3.5 w-3.5" />완료</span>
    : <span className="flex items-center gap-1 text-xs text-orange-500 font-medium"><AlertCircle className="h-3.5 w-3.5" />미완료</span>
}

function ContentTypeIcon({ type }: { type: string }) {
  return type === "movie"
    ? <Film className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
    : <Tv className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
}

interface EditPanelProps {
  item: TextMetaOut
  onSaved: () => void
}

const SOURCE_LABEL: Record<string, string> = { tmdb: "TMDB", kobis: "KOBIS", ai: "AI" }
const SOURCE_COLOR: Record<string, string> = {
  tmdb: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400",
  kobis: "bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-400",
  ai: "bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-400",
}

function EditPanel({ item, onSaved }: EditPanelProps) {
  const [synopsis, setSynopsis] = useState(item.synopsis ?? "")
  const [genre, setGenre] = useState(item.genre_primary ?? "")
  const [tags, setTags] = useState((item.mood_tags ?? []).join(", "))
  const [rating, setRating] = useState(item.rating_suggestion ?? "")
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  const [suggestion, setSuggestion] = useState<TextMetaSuggestion | null>(null)
  const [loadingSuggest, setLoadingSuggest] = useState(false)
  const [showSuggest, setShowSuggest] = useState(false)

  const handleSuggest = async () => {
    setLoadingSuggest(true)
    setShowSuggest(true)
    try {
      const data = await textMetaApi.suggest(item.id)
      setSuggestion(data)
    } catch {
      setSuggestion(null)
    } finally {
      setLoadingSuggest(false)
    }
  }

  const applyField = (field: "synopsis" | "genre" | "tags" | "rating") => {
    if (!suggestion) return
    if (field === "synopsis" && suggestion.synopsis) setSynopsis(suggestion.synopsis)
    if (field === "genre" && suggestion.genre_primary) setGenre(suggestion.genre_primary)
    if (field === "tags" && suggestion.mood_tags) setTags(suggestion.mood_tags.join(", "))
    if (field === "rating" && suggestion.rating_suggestion) setRating(suggestion.rating_suggestion)
  }

  const applyAll = () => {
    if (!suggestion) return
    if (suggestion.synopsis) setSynopsis(suggestion.synopsis)
    if (suggestion.genre_primary) setGenre(suggestion.genre_primary)
    if (suggestion.mood_tags) setTags(suggestion.mood_tags.join(", "))
    if (suggestion.rating_suggestion) setRating(suggestion.rating_suggestion)
    setShowSuggest(false)
  }

  const handleSave = async (complete: boolean) => {
    setSaving(true)
    try {
      await textMetaApi.update(item.id, {
        synopsis,
        genre_primary: genre,
        mood_tags: tags.split(",").map((t) => t.trim()).filter(Boolean),
        rating_suggestion: rating,
        completed: complete,
      })
      setSaved(true)
      onSaved()
    } catch {
      setSaved(true) // Mock
      onSaved()
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="h-full flex flex-col">
      <div className="px-5 py-4 border-b border-border">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <ContentTypeIcon type={item.content_type} />
            <div className="min-w-0">
              <h3 className="font-bold truncate">{item.title}</h3>
              <p className="text-xs text-muted-foreground">{CONTENT_TYPE_LABEL[item.content_type]} · {item.cp_name ?? "-"} · {item.production_year ?? "-"}</p>
            </div>
          </div>
          <button
            onClick={handleSuggest}
            disabled={loadingSuggest}
            className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-violet-300 dark:border-violet-700 text-violet-700 dark:text-violet-400 text-xs font-medium hover:bg-violet-50 dark:hover:bg-violet-900/20 disabled:opacity-50 transition-colors"
          >
            <Sparkles className="h-3.5 w-3.5" />
            {loadingSuggest ? "조회 중..." : "AI 제안"}
          </button>
        </div>
      </div>

      {/* AI 제안 패널 */}
      {showSuggest && (
        <div className="mx-4 mt-3 rounded-xl border border-violet-200 dark:border-violet-800 bg-violet-50/60 dark:bg-violet-900/20 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-violet-500" />
              <span className="text-sm font-medium text-violet-700 dark:text-violet-400">
                {suggestion ? `${SOURCE_LABEL[suggestion.source] ?? suggestion.source} 제안` : "제안 없음"}
              </span>
              {suggestion && (
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${SOURCE_COLOR[suggestion.source] ?? ""}`}>
                  {SOURCE_LABEL[suggestion.source] ?? suggestion.source}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              {suggestion && (
                <button
                  onClick={applyAll}
                  className="text-xs px-2.5 py-1 rounded-lg bg-violet-600 text-white hover:bg-violet-700 transition-colors font-medium"
                >
                  전체 반영
                </button>
              )}
              <button onClick={() => setShowSuggest(false)} className="text-muted-foreground hover:text-foreground p-0.5">
                <span className="text-xs">✕</span>
              </button>
            </div>
          </div>

          {!suggestion && !loadingSuggest && (
            <p className="text-xs text-muted-foreground">TMDB/KOBIS 동기화 또는 AI 처리 후 제안이 가능합니다.</p>
          )}

          {suggestion && (
            <div className="space-y-2 text-xs">
              {suggestion.synopsis && (
                <div className="flex gap-2">
                  <div className="flex-1 text-muted-foreground line-clamp-2">{suggestion.synopsis}</div>
                  <button onClick={() => applyField("synopsis")}
                    className="shrink-0 px-2 py-1 rounded border border-violet-300 dark:border-violet-700 text-violet-600 dark:text-violet-400 hover:bg-violet-100 dark:hover:bg-violet-900/40 transition-colors">
                    반영
                  </button>
                </div>
              )}
              {suggestion.genre_primary && (
                <div className="flex items-center gap-2">
                  <span className="text-muted-foreground">장르: <strong className="text-foreground">{suggestion.genre_primary}</strong>{suggestion.genre_secondary && ` / ${suggestion.genre_secondary}`}</span>
                  <button onClick={() => applyField("genre")}
                    className="px-2 py-1 rounded border border-violet-300 dark:border-violet-700 text-violet-600 dark:text-violet-400 hover:bg-violet-100 dark:hover:bg-violet-900/40 transition-colors">
                    반영
                  </button>
                </div>
              )}
              {suggestion.mood_tags && suggestion.mood_tags.length > 0 && (
                <div className="flex items-center gap-2">
                  <span className="text-muted-foreground">태그: <strong className="text-foreground">{suggestion.mood_tags.join(", ")}</strong></span>
                  <button onClick={() => applyField("tags")}
                    className="px-2 py-1 rounded border border-violet-300 dark:border-violet-700 text-violet-600 dark:text-violet-400 hover:bg-violet-100 dark:hover:bg-violet-900/40 transition-colors">
                    반영
                  </button>
                </div>
              )}
              {suggestion.rating_suggestion && (
                <div className="flex items-center gap-2">
                  <span className="text-muted-foreground">등급: <strong className="text-foreground">{suggestion.rating_suggestion}</strong></span>
                  <button onClick={() => applyField("rating")}
                    className="px-2 py-1 rounded border border-violet-300 dark:border-violet-700 text-violet-600 dark:text-violet-400 hover:bg-violet-100 dark:hover:bg-violet-900/40 transition-colors">
                    반영
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-5 space-y-4">
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">시놉시스</label>
          <textarea
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary resize-none"
            rows={5}
            value={synopsis}
            onChange={(e) => setSynopsis(e.target.value)}
            placeholder="시놉시스를 입력하세요..."
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">장르</label>
            <input
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
              value={genre}
              onChange={(e) => setGenre(e.target.value)}
              placeholder="예: 드라마"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">시청 등급</label>
            <select
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
              value={rating}
              onChange={(e) => setRating(e.target.value)}
            >
              <option value="">선택</option>
              <option value="전체관람가">전체관람가</option>
              <option value="7세이상관람가">7세이상관람가</option>
              <option value="12세이상관람가">12세이상관람가</option>
              <option value="15세이상관람가">15세이상관람가</option>
              <option value="18세이상관람가">18세이상관람가</option>
            </select>
          </div>
        </div>
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            감성 태그 <span className="normal-case font-normal">(쉼표로 구분)</span>
          </label>
          <input
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
            value={tags}
            onChange={(e) => setTags(e.target.value)}
            placeholder="따뜻한, 가족과함께, 눈물주의"
          />
        </div>
      </div>

      <div className="px-5 py-4 border-t border-border flex gap-2">
        <button
          onClick={() => handleSave(false)}
          disabled={saving}
          className="flex-1 px-3 py-2 rounded-lg border border-border text-sm hover:bg-accent disabled:opacity-50 transition-colors"
        >
          {saving ? "저장 중..." : "저장"}
        </button>
        <button
          onClick={() => handleSave(true)}
          disabled={saving || saved}
          className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-green-600 text-white text-sm font-medium hover:bg-green-700 disabled:opacity-60 transition-colors"
        >
          <Check className="h-4 w-4" />
          {saved ? "완료 처리됨" : "완료 처리"}
        </button>
      </div>
    </div>
  )
}

interface TreeRowProps {
  item: TextMetaOut
  depth: number
  selectedId: number | null
  checkedIds: Set<number>
  expandedIds: Set<number>
  onSelect: (item: TextMetaOut) => void
  onToggleCheck: (id: number, descendants: number[]) => void
  onToggleExpand: (id: number) => void
}

function collectDescendantIds(item: TextMetaOut): number[] {
  const ids: number[] = []
  for (const season of item.children) {
    ids.push(season.id)
    for (const ep of season.children) {
      ids.push(ep.id)
    }
  }
  return ids
}

function TreeRow({
  item, depth, selectedId, checkedIds, expandedIds,
  onSelect, onToggleCheck, onToggleExpand,
}: TreeRowProps) {
  const isExpanded = expandedIds.has(item.id)
  const hasChildren = item.children.length > 0
  const isSelected = selectedId === item.id

  const indentClass = depth === 0 ? "" : depth === 1 ? "pl-6" : "pl-12"

  return (
    <>
      <div
        className={`flex items-center gap-2 px-4 py-2.5 hover:bg-accent/50 cursor-pointer transition-colors border-b border-border/50 ${isSelected ? "bg-accent" : ""}`}
      >
        {/* 체크박스 (에피소드만) */}
        <input
          type="checkbox"
          checked={checkedIds.has(item.id)}
          onChange={() => onToggleCheck(item.id, collectDescendantIds(item))}
          className="rounded shrink-0"
          onClick={(e) => e.stopPropagation()}
        />

        {/* 들여쓰기 */}
        <div className={`flex items-center gap-1.5 flex-1 min-w-0 ${indentClass}`}>
          {/* 펼치기/접기 */}
          {hasChildren ? (
            <button
              onClick={(e) => { e.stopPropagation(); onToggleExpand(item.id) }}
              className="shrink-0 p-0.5 hover:bg-accent rounded"
            >
              {isExpanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
            </button>
          ) : (
            <span className="w-5 shrink-0" />
          )}

          <ContentTypeIcon type={item.content_type} />

          <button
            onClick={() => onSelect(item)}
            className="flex-1 text-left min-w-0"
          >
            <div className="text-sm font-medium truncate">{item.title}</div>
            {depth === 0 && (
              <div className="text-xs text-muted-foreground truncate">
                {item.cp_name ?? "-"} · {item.production_year ?? "-"}
              </div>
            )}
          </button>
        </div>

        <CompletionBadge
          completed={item.text_meta_completed}
          episodeDone={item.episode_total_count > 0 ? item.episode_completed_count : undefined}
          episodeTotal={item.episode_total_count > 0 ? item.episode_total_count : undefined}
        />
      </div>

      {/* 하위 항목 */}
      {hasChildren && isExpanded && item.children.map((child) => (
        <TreeRow
          key={child.id}
          item={child}
          depth={depth + 1}
          selectedId={selectedId}
          checkedIds={checkedIds}
          expandedIds={expandedIds}
          onSelect={onSelect}
          onToggleCheck={onToggleCheck}
          onToggleExpand={onToggleExpand}
        />
      ))}
    </>
  )
}

export default function TextMetaPage() {
  const [items, setItems] = useState<TextMetaOut[]>(MOCK_ITEMS)
  const [total, setTotal] = useState(MOCK_ITEMS.length)
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState<TextMetaOut | null>(null)
  const [checkedIds, setCheckedIds] = useState<Set<number>>(new Set())
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set([2])) // 시리즈 기본 펼침
  const [tabFilter, setTabFilter] = useState<"all" | "completed" | "incomplete">("all")
  const [typeFilter, setTypeFilter] = useState<"all" | "movie" | "series">("all")
  const [bulkLoading, setBulkLoading] = useState(false)

  const fetchItems = useCallback(async () => {
    setLoading(true)
    try {
      const params: { completed?: boolean; content_type?: string } = {}
      if (tabFilter === "completed") params.completed = true
      if (tabFilter === "incomplete") params.completed = false
      if (typeFilter !== "all") params.content_type = typeFilter
      const res = await textMetaApi.list(params)
      setItems(res.items)
      setTotal(res.total)
    } catch {
      // Mock 유지
    } finally {
      setLoading(false)
    }
  }, [tabFilter, typeFilter])

  useEffect(() => { fetchItems() }, [fetchItems])

  const handleToggleCheck = (id: number, descendants: number[]) => {
    setCheckedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
        descendants.forEach((d) => next.delete(d))
      } else {
        next.add(id)
        descendants.forEach((d) => next.add(d))
      }
      return next
    })
  }

  const handleToggleExpand = (id: number) => {
    setExpandedIds((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const handleBulkComplete = async () => {
    if (checkedIds.size === 0) return
    setBulkLoading(true)
    try {
      await textMetaApi.bulkComplete(Array.from(checkedIds))
      setCheckedIds(new Set())
      fetchItems()
    } catch {
      setCheckedIds(new Set())
      fetchItems()
    } finally {
      setBulkLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/programming/metadata" className="p-1.5 rounded-lg hover:bg-accent">
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold">글자메타 관리</h1>
            <p className="text-sm text-muted-foreground mt-1">
              텍스트 메타데이터 완성도 관리 — 총 {total}건
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {checkedIds.size > 0 && (
            <button
              onClick={handleBulkComplete}
              disabled={bulkLoading}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-green-600 text-white text-sm font-medium hover:bg-green-700 disabled:opacity-50"
            >
              <Check className="h-4 w-4" />
              선택 완료 처리 ({checkedIds.size}건)
            </button>
          )}
          <button onClick={fetchItems} className="p-2 rounded-lg border border-border hover:bg-accent">
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* 필터 */}
      <div className="flex items-center gap-3">
        <div className="flex rounded-lg border border-border overflow-hidden text-sm">
          {(["all", "completed", "incomplete"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setTabFilter(f)}
              className={`px-3 py-1.5 transition-colors ${tabFilter === f ? "bg-primary text-primary-foreground" : "hover:bg-accent"}`}
            >
              {f === "all" ? "전체" : f === "completed" ? "완료" : "미완료"}
            </button>
          ))}
        </div>
        <div className="flex rounded-lg border border-border overflow-hidden text-sm">
          {(["all", "movie", "series"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setTypeFilter(f)}
              className={`px-3 py-1.5 transition-colors ${typeFilter === f ? "bg-primary text-primary-foreground" : "hover:bg-accent"}`}
            >
              {f === "all" ? "전체" : f === "movie" ? "단편" : "시리즈"}
            </button>
          ))}
        </div>
      </div>

      {/* 메인 레이아웃 */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4 min-h-[600px]">
        {/* 좌: 트리 목록 */}
        <div className="lg:col-span-2 rounded-xl border border-border bg-card overflow-hidden flex flex-col">
          <div className="px-4 py-3 border-b border-border bg-muted/30 flex items-center justify-between">
            <span className="text-sm font-medium text-muted-foreground">콘텐츠 목록</span>
            <button
              onClick={() => {
                const allIds = new Set<number>()
                items.forEach((item) => {
                  allIds.add(item.id)
                  collectDescendantIds(item).forEach((id) => allIds.add(id))
                })
                setCheckedIds(allIds.size === checkedIds.size ? new Set() : allIds)
              }}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              전체 선택
            </button>
          </div>
          <div className="flex-1 overflow-y-auto">
            {items.length === 0 && (
              <div className="p-8 text-center text-muted-foreground text-sm">항목이 없습니다</div>
            )}
            {items.map((item) => (
              <TreeRow
                key={item.id}
                item={item}
                depth={0}
                selectedId={selected?.id ?? null}
                checkedIds={checkedIds}
                expandedIds={expandedIds}
                onSelect={setSelected}
                onToggleCheck={handleToggleCheck}
                onToggleExpand={handleToggleExpand}
              />
            ))}
          </div>
        </div>

        {/* 우: 편집 패널 */}
        <div className="lg:col-span-3 rounded-xl border border-border bg-card overflow-hidden flex flex-col">
          {!selected ? (
            <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground gap-3">
              <Sparkles className="h-8 w-8 opacity-30" />
              <p className="text-sm">왼쪽에서 콘텐츠를 선택하세요</p>
            </div>
          ) : (
            <EditPanel
              key={selected.id}
              item={selected}
              onSaved={() => {
                fetchItems()
                setSelected(null)
              }}
            />
          )}
        </div>
      </div>
    </div>
  )
}
