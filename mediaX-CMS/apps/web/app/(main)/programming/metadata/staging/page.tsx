"use client"

import { useEffect, useState, useCallback } from "react"
import {
  CheckCircle, XCircle, RefreshCw, ChevronLeft, ChevronRight,
  ChevronDown, ChevronRight as ChevronRightIcon, ExternalLink,
  GitCompare, ArrowLeft,
} from "lucide-react"
import Link from "next/link"
import { metadataApi, type StagingItem, type ContentOut } from "@/lib/api"

// ── Mock 데이터 ──────────────────────────────────────────

const MOCK_STAGING: StagingItem[] = [
  {
    content: {
      id: 1, title: "기생충", original_title: "Parasite", content_type: "movie",
      status: "staging", cp_name: "CJ ENM", production_year: 2019, runtime_minutes: 132,
      created_at: new Date().toISOString(), quality_score: 96,
    },
    metadata: {
      id: 1, content_id: 1,
      cp_synopsis: "전원 백수인 기택 가족이 부유한 박 사장 가족 집에 침투하면서 벌어지는 이야기.",
      cp_genre: "드라마",
      cp_tags: ["가족", "스릴러"],
      ai_synopsis: "전원 백수인 기택 가족이 부유한 IT기업 CEO 박 사장의 고급 저택에 하나씩 스며들면서 두 계층의 예상치 못한 충돌이 빚어지는 블랙코미디 스릴러. 봉준호 감독의 사회 비판적 시각이 빛나는 작품으로, 계층 간 불평등을 유머와 공포로 버무린 독창적 서사.",
      ai_genre_primary: "스릴러", ai_genre_secondary: "드라마",
      ai_mood_tags: ["긴장감", "반전있음", "사회비판"],
      ai_rating_suggestion: "15세이상관람가",
      final_synopsis: null, final_genre: null, final_tags: null,
      quality_score: 96, score_breakdown: null,
      ai_processed_at: new Date().toISOString(), reviewed_at: null,
    },
    diff: {
      synopsis: { cp: "전원 백수인 기택 가족이 부유한 박 사장 가족 집에 침투하면서 벌어지는 이야기.", ai: "전원 백수인 기택 가족이 부유한 IT기업 CEO 박 사장의 고급 저택에 하나씩 스며들면서 두 계층의 예상치 못한 충돌이 빚어지는 블랙코미디 스릴러." },
      genre: { cp: "드라마", ai: "스릴러" },
    },
    external_sources: [
      { id: 1, source_type: "tmdb", external_id: "496243", fetched_at: new Date().toISOString() },
      { id: 2, source_type: "kobis", external_id: "20199023", fetched_at: new Date().toISOString() },
    ],
    children: [],
  },
  {
    content: {
      id: 2, title: "오징어 게임", original_title: "Squid Game", content_type: "series",
      status: "staging", cp_name: "넷플릭스", production_year: 2021, runtime_minutes: null,
      created_at: new Date().toISOString(), quality_score: 88,
    },
    metadata: {
      id: 2, content_id: 2,
      cp_synopsis: "456억 원의 상금을 건 생존 게임 서바이벌.",
      cp_genre: "드라마",
      cp_tags: ["서바이벌"],
      ai_synopsis: "456억 원의 상금을 걸고 벌어지는 극한의 생존 게임에 참가한 456명의 이야기. 빚에 쫓기는 사람들이 어린 시절 놀이를 패러디한 게임에서 목숨을 건다. 사회적 불평등과 자본주의의 어두운 단면을 날카롭게 비판하는 넷플릭스 오리지널 시리즈.",
      ai_genre_primary: "스릴러", ai_genre_secondary: "드라마",
      ai_mood_tags: ["긴장감", "반전있음", "심야감성", "사회비판"],
      ai_rating_suggestion: "청소년관람불가",
      final_synopsis: null, final_genre: null, final_tags: null,
      quality_score: 88, score_breakdown: null,
      ai_processed_at: new Date().toISOString(), reviewed_at: null,
    },
    diff: {
      genre: { cp: "드라마", ai: "스릴러" },
    },
    external_sources: [
      { id: 3, source_type: "tmdb", external_id: "93405", fetched_at: new Date().toISOString() },
    ],
    children: [
      {
        content: {
          id: 20, title: "오징어 게임 시즌 1", original_title: null, content_type: "season",
          status: "staging", cp_name: "넷플릭스", production_year: 2021, runtime_minutes: null,
          created_at: new Date().toISOString(), quality_score: 88,
        },
        metadata: null, diff: {}, external_sources: [],
        children: Array.from({ length: 9 }, (_, i) => ({
          content: {
            id: 200 + i, title: `에피소드 ${i + 1}`, original_title: null, content_type: "episode" as const,
            status: "staging" as const, cp_name: "넷플릭스", production_year: 2021, runtime_minutes: 55,
            created_at: new Date().toISOString(), quality_score: 0,
          },
          metadata: null, diff: {}, external_sources: [], children: [],
        })),
      },
    ],
  },
]

// ── 유틸 ─────────────────────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
  movie: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
  series: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300",
  season: "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300",
  episode: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
}
const TYPE_KO: Record<string, string> = {
  movie: "영화", series: "시리즈", season: "시즌", episode: "에피소드",
}

function QualityBadge({ score }: { score: number | null }) {
  if (score === null) return <span className="text-xs text-muted-foreground">-</span>
  const color = score >= 90 ? "text-green-600" : score >= 70 ? "text-yellow-600" : "text-orange-600"
  return <span className={`text-sm font-bold ${color}`}>{score.toFixed(0)}점</span>
}

function DiffField({ label, cp, ai }: { label: string; cp: string | null; ai: string | null }) {
  const changed = cp !== ai && cp && ai
  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{label}</span>
        {changed && <GitCompare className="h-3 w-3 text-yellow-500" />}
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div className="rounded-lg bg-yellow-50 dark:bg-yellow-900/10 border border-yellow-200 dark:border-yellow-800/30 p-2.5 text-sm">
          <div className="text-xs text-muted-foreground mb-1">CP 원본</div>
          <div className="text-foreground">{cp ?? <span className="italic text-muted-foreground">없음</span>}</div>
        </div>
        <div className="rounded-lg bg-green-50 dark:bg-green-900/10 border border-green-200 dark:border-green-800/30 p-2.5 text-sm">
          <div className="text-xs text-muted-foreground mb-1">AI 생성</div>
          <div className="text-foreground">{ai ?? <span className="italic text-muted-foreground">없음</span>}</div>
        </div>
      </div>
    </div>
  )
}

function HierarchyTree({ item, depth = 0 }: { item: StagingItem; depth?: number }) {
  const [expanded, setExpanded] = useState(depth === 0)
  const hasChildren = item.children.length > 0

  return (
    <div>
      <div
        className="flex items-center gap-2 py-1.5 px-2 rounded hover:bg-accent/50 cursor-pointer"
        style={{ paddingLeft: `${(depth + 1) * 12}px` }}
        onClick={() => hasChildren && setExpanded((e) => !e)}
      >
        {hasChildren ? (
          expanded
            ? <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            : <ChevronRightIcon className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
        ) : (
          <span className="w-3.5 h-3.5 shrink-0" />
        )}
        <span className={`text-xs px-1.5 py-0.5 rounded ${STATUS_COLORS[item.content.content_type] ?? ""}`}>
          {TYPE_KO[item.content.content_type]}
        </span>
        <span className="text-sm truncate">{item.content.title}</span>
        {item.content.quality_score != null && item.content.quality_score > 0 && (
          <QualityBadge score={item.content.quality_score} />
        )}
      </div>
      {expanded && hasChildren && (
        <div>
          {item.children.map((child) => (
            <HierarchyTree key={child.content.id} item={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  )
}

// ── 메인 페이지 ──────────────────────────────────────────

export default function StagingPage() {
  const [items, setItems] = useState<StagingItem[]>(MOCK_STAGING)
  const [selected, setSelected] = useState<StagingItem | null>(null)
  const [checkedIds, setCheckedIds] = useState<Set<number>>(new Set())
  const [loading, setLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(MOCK_STAGING.length)
  const [reviewer, setReviewer] = useState("담당자")
  const [filterType, setFilterType] = useState<string>("")
  const [showHierarchy, setShowHierarchy] = useState(false)

  const fetchStaging = useCallback(async () => {
    setLoading(true)
    try {
      const res = await metadataApi.getStaging({
        content_type: filterType || undefined,
        page,
        size: 15,
      })
      setItems(res.items)
      setTotal(res.total)
    } catch {
      // Mock 유지
    } finally {
      setLoading(false)
    }
  }, [page, filterType])

  useEffect(() => { fetchStaging() }, [fetchStaging])

  const toggleCheck = (id: number) => {
    setCheckedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleAll = () => {
    if (checkedIds.size === items.length) {
      setCheckedIds(new Set())
    } else {
      setCheckedIds(new Set(items.map((i) => i.content.id)))
    }
  }

  const handleBulkAction = async (action: "approve" | "reject") => {
    const ids = Array.from(checkedIds)
    if (ids.length === 0) return
    if (!reviewer.trim()) { alert("검수자 이름을 입력하세요"); return }
    setActionLoading(true)
    try {
      if (action === "approve") {
        await metadataApi.bulkApprove({ content_ids: ids, reviewer })
      } else {
        await metadataApi.bulkReject({ content_ids: ids, reviewer })
      }
      setItems((prev) => prev.filter((i) => !ids.includes(i.content.id)))
      setCheckedIds(new Set())
      if (selected && ids.includes(selected.content.id)) setSelected(null)
    } catch {
      // Mock: 그냥 제거
      setItems((prev) => prev.filter((i) => !ids.includes(i.content.id)))
      setCheckedIds(new Set())
    } finally {
      setActionLoading(false)
    }
  }

  const handleSingleAction = async (action: "approve" | "reject") => {
    if (!selected) return
    setCheckedIds(new Set([selected.content.id]))
    await handleBulkAction(action)
  }

  const meta = selected?.metadata
  const diff = selected?.diff ?? {}

  return (
    <div className="space-y-4">
      {/* 헤더 */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <Link href="/programming/metadata" className="p-1.5 rounded-lg hover:bg-accent">
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold">검토 대기풀</h1>
            <p className="text-sm text-muted-foreground mt-1">
              에이전틱 검색 완료 — 운영자 검토 대기 ({total}건)
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <input
            className="rounded-lg border border-border px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary w-28"
            placeholder="검수자"
            value={reviewer}
            onChange={(e) => setReviewer(e.target.value)}
          />
          <select
            className="rounded-lg border border-border px-2 py-1.5 text-sm bg-background focus:outline-none focus:ring-1 focus:ring-primary"
            value={filterType}
            onChange={(e) => { setFilterType(e.target.value); setPage(1) }}
          >
            <option value="">전체</option>
            <option value="movie">영화</option>
            <option value="series">시리즈</option>
          </select>
          {checkedIds.size > 0 && (
            <>
              <button
                onClick={() => handleBulkAction("approve")}
                disabled={actionLoading}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-green-600 text-white text-sm font-medium hover:bg-green-700 disabled:opacity-50"
              >
                <CheckCircle className="h-4 w-4" /> 선택 승인 ({checkedIds.size})
              </button>
              <button
                onClick={() => handleBulkAction("reject")}
                disabled={actionLoading}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50"
              >
                <XCircle className="h-4 w-4" /> 반려
              </button>
            </>
          )}
          <button
            onClick={fetchStaging}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border text-sm hover:bg-accent"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4 min-h-[620px]">
        {/* 좌측: 목록 */}
        <div className="lg:col-span-2 rounded-xl border border-border bg-card overflow-hidden flex flex-col">
          {/* 전체선택 헤더 */}
          <div className="px-4 py-2.5 border-b border-border bg-muted/30 flex items-center gap-2">
            <input
              type="checkbox"
              className="rounded"
              checked={checkedIds.size === items.length && items.length > 0}
              onChange={toggleAll}
            />
            <span className="text-xs font-medium text-muted-foreground">
              전체선택 {checkedIds.size > 0 ? `(${checkedIds.size}개 선택)` : ""}
            </span>
          </div>

          <div className="flex-1 overflow-y-auto divide-y divide-border">
            {items.length === 0 && (
              <div className="p-8 text-center text-muted-foreground text-sm">
                검토 대기 항목이 없습니다
              </div>
            )}
            {items.map((item) => {
              const c = item.content
              const isSelected = selected?.content.id === c.id
              const isChecked = checkedIds.has(c.id)
              return (
                <div
                  key={c.id}
                  className={`flex items-center gap-2 px-3 py-2.5 hover:bg-accent/40 transition-colors cursor-pointer ${isSelected ? "bg-accent" : ""}`}
                  onClick={() => setSelected(item)}
                >
                  <input
                    type="checkbox"
                    className="rounded shrink-0"
                    checked={isChecked}
                    onChange={(e) => { e.stopPropagation(); toggleCheck(c.id) }}
                    onClick={(e) => e.stopPropagation()}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5 mb-0.5">
                      <span className={`text-xs px-1.5 py-0.5 rounded ${STATUS_COLORS[c.content_type] ?? ""}`}>
                        {TYPE_KO[c.content_type]}
                      </span>
                      <span className="font-medium text-sm truncate">{c.title}</span>
                    </div>
                    <div className="text-xs text-muted-foreground flex items-center gap-1.5">
                      <span>{c.cp_name ?? "-"}</span>
                      <span>·</span>
                      <span>{c.production_year ?? "-"}년</span>
                      {item.children.length > 0 && (
                        <>
                          <span>·</span>
                          <span className="text-blue-500">
                            {item.children.length}개 하위
                          </span>
                        </>
                      )}
                    </div>
                  </div>
                  <QualityBadge score={c.quality_score} />
                </div>
              )
            })}
          </div>

          {/* 페이지네이션 */}
          <div className="px-4 py-2.5 border-t border-border flex items-center justify-between text-sm">
            <span className="text-muted-foreground text-xs">총 {total}건</span>
            <div className="flex gap-1">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="p-1 rounded hover:bg-accent disabled:opacity-40"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="px-2 py-0.5 text-xs">{page}</span>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={items.length < 15}
                className="p-1 rounded hover:bg-accent disabled:opacity-40"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>

        {/* 우측: 상세 비교 */}
        <div className="lg:col-span-3 rounded-xl border border-border bg-card overflow-hidden flex flex-col">
          {!selected ? (
            <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
              왼쪽에서 콘텐츠를 선택하세요
            </div>
          ) : (
            <>
              {/* 헤더 */}
              <div className="px-5 py-4 border-b border-border">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h2 className="font-bold text-lg truncate">{selected.content.title}</h2>
                      <span className={`text-xs px-1.5 py-0.5 rounded ${STATUS_COLORS[selected.content.content_type] ?? ""}`}>
                        {TYPE_KO[selected.content.content_type]}
                      </span>
                    </div>
                    <div className="text-sm text-muted-foreground mt-0.5">
                      {selected.content.cp_name} · {selected.content.production_year ?? "-"}년
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <QualityBadge score={selected.content.quality_score} />
                    <div className="text-xs text-muted-foreground mt-0.5">품질 스코어</div>
                  </div>
                </div>

                {/* 외부 소스 뱃지 */}
                {selected.external_sources.length > 0 && (
                  <div className="flex gap-2 mt-2">
                    {selected.external_sources.map((src) => (
                      <span
                        key={src.id}
                        className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-muted border border-border"
                      >
                        <ExternalLink className="h-3 w-3" />
                        {src.source_type.toUpperCase()} #{src.external_id}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* 본문 */}
              <div className="flex-1 overflow-y-auto p-5 space-y-5">
                {/* 계층 트리 (시리즈인 경우) */}
                {selected.children.length > 0 && (
                  <div className="space-y-1">
                    <button
                      className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground uppercase tracking-wide hover:text-foreground"
                      onClick={() => setShowHierarchy((v) => !v)}
                    >
                      {showHierarchy ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRightIcon className="h-3.5 w-3.5" />}
                      계층 구조 ({selected.children.length}개 시즌)
                    </button>
                    {showHierarchy && (
                      <div className="rounded-lg border border-border bg-muted/20 py-2">
                        <HierarchyTree item={selected} />
                      </div>
                    )}
                  </div>
                )}

                {/* Diff 필드 */}
                {Object.keys(diff).length === 0 && !meta && (
                  <div className="text-sm text-muted-foreground italic">메타데이터 정보 없음</div>
                )}

                {diff.synopsis && (
                  <DiffField
                    label="시놉시스"
                    cp={diff.synopsis.cp}
                    ai={diff.synopsis.ai ?? meta?.ai_synopsis ?? null}
                  />
                )}

                {!diff.synopsis && meta?.ai_synopsis && (
                  <div className="space-y-1.5">
                    <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide">AI 시놉시스</div>
                    <div className="rounded-lg bg-green-50 dark:bg-green-900/10 border border-green-200 dark:border-green-800/30 p-3 text-sm">
                      {meta.ai_synopsis}
                    </div>
                  </div>
                )}

                {diff.genre && (
                  <DiffField label="장르" cp={diff.genre.cp} ai={diff.genre.ai} />
                )}

                {/* 태그 */}
                {meta?.ai_mood_tags && meta.ai_mood_tags.length > 0 && (
                  <div className="space-y-1.5">
                    <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide">AI 태그</div>
                    <div className="flex flex-wrap gap-1.5">
                      {meta.ai_mood_tags.map((tag) => (
                        <span
                          key={tag}
                          className="text-xs px-2 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20"
                        >
                          #{tag}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* 등급 */}
                {meta?.ai_rating_suggestion && (
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">등급 제안</span>
                    <span className="text-sm px-2 py-0.5 rounded bg-orange-100 dark:bg-orange-900/20 text-orange-700 dark:text-orange-300 border border-orange-200 dark:border-orange-800/30">
                      {meta.ai_rating_suggestion}
                    </span>
                  </div>
                )}
              </div>

              {/* 액션 버튼 */}
              <div className="px-5 py-4 border-t border-border flex items-center gap-2 flex-wrap">
                <button
                  onClick={() => handleSingleAction("approve")}
                  disabled={actionLoading}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-green-600 text-white text-sm font-medium hover:bg-green-700 disabled:opacity-50"
                >
                  <CheckCircle className="h-4 w-4" /> 승인
                </button>
                <button
                  onClick={() => handleSingleAction("reject")}
                  disabled={actionLoading}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg border border-red-300 dark:border-red-700 text-red-600 dark:text-red-400 text-sm font-medium hover:bg-red-50 dark:hover:bg-red-900/20 disabled:opacity-50"
                >
                  <XCircle className="h-4 w-4" /> 반려
                </button>
                <div className="flex-1" />
                <button
                  onClick={async () => {
                    try {
                      await metadataApi.triggerEnrich(selected.content.id)
                      alert("에이전틱 재검색 큐에 등록되었습니다")
                    } catch {
                      alert("재검색 요청 실패")
                    }
                  }}
                  className="text-xs px-3 py-1.5 rounded-lg border border-border text-muted-foreground hover:bg-accent"
                >
                  재검색
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
