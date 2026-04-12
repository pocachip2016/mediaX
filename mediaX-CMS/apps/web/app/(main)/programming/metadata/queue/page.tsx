"use client"

import { useEffect, useState } from "react"
import { CheckCircle, XCircle, RefreshCw, ChevronLeft, ChevronRight } from "lucide-react"
import { metadataApi, type ContentOut, type ContentDetail } from "@/lib/api"

const MOCK_QUEUE: ContentOut[] = [
  { id: 2, title: "오징어 게임 시즌2", original_title: null, content_type: "series", status: "review", cp_name: "JTBC스튜디오", production_year: 2024, runtime_minutes: null, created_at: new Date().toISOString(), quality_score: 78 },
  { id: 6, title: "콘크리트 유토피아", original_title: null, content_type: "movie", status: "review", cp_name: "롯데엔터테인먼트", production_year: 2023, runtime_minutes: 130, created_at: new Date().toISOString(), quality_score: 82 },
  { id: 7, title: "외계+인 2부", original_title: null, content_type: "movie", status: "review", cp_name: "CJ ENM", production_year: 2024, runtime_minutes: 122, created_at: new Date().toISOString(), quality_score: 71 },
]

const MOCK_DETAIL: Record<number, ContentDetail> = {
  2: {
    id: 2, title: "오징어 게임 시즌2", original_title: null, content_type: "series", status: "review",
    cp_name: "JTBC스튜디오", production_year: 2024, runtime_minutes: null,
    created_at: new Date().toISOString(), quality_score: 78,
    metadata_record: {
      id: 2, content_id: 2,
      cp_synopsis: "456억 원의 상금을 건 생존 게임 두 번째 시즌.",
      cp_genre: "드라마",
      ai_synopsis: "2024년 공개된 넷플릭스 오리지널 시리즈 오징어 게임의 두 번째 시즌. 생존을 건 극한의 게임이 다시 시작되며, 전작의 유일한 생존자가 다시 게임에 뛰어드는 이야기를 담는다. 사회적 불평등과 생존 본능을 다룬 극적 서사.",
      ai_genre_primary: "스릴러", ai_genre_secondary: "드라마",
      ai_mood_tags: ["긴장감", "반전있음", "심야감성"],
      ai_rating_suggestion: "15세이상관람가",
      final_synopsis: null, final_genre: null, final_tags: null,
      quality_score: 78,
      score_breakdown: { synopsis_quality: 20, genre_confidence: 20, tag_coverage: 9, external_meta: 20, field_coverage: 15 },
      ai_processed_at: new Date().toISOString(), reviewed_at: null,
    },
  },
}

function ScoreBar({ label, value, max = 30 }: { label: string; value: number; max?: number }) {
  const pct = Math.round((value / max) * 100)
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium">{value}/{max}</span>
      </div>
      <div className="h-1.5 rounded-full bg-muted overflow-hidden">
        <div className="h-full bg-primary rounded-full transition-all" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export default function ReviewQueuePage() {
  const [queue, setQueue] = useState<ContentOut[]>(MOCK_QUEUE)
  const [selected, setSelected] = useState<ContentDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(MOCK_QUEUE.length)
  const [reviewer, setReviewer] = useState("담당자")
  const [actionLoading, setActionLoading] = useState(false)
  const [editSynopsis, setEditSynopsis] = useState("")
  const [editGenre, setEditGenre] = useState("")

  const fetchQueue = async () => {
    setLoading(true)
    try {
      const res = await metadataApi.getQueue({ page, size: 10 })
      setQueue(res.items)
      setTotal(res.total)
    } catch {
      // Mock 유지
    } finally {
      setLoading(false)
    }
  }

  const selectContent = async (c: ContentOut) => {
    const detail = MOCK_DETAIL[c.id] ?? { ...c, metadata_record: null }
    setSelected(detail)
    setEditSynopsis(detail.metadata_record?.ai_synopsis ?? "")
    setEditGenre(detail.metadata_record?.ai_genre_primary ?? "")
    try {
      const d = await metadataApi.getContent(c.id)
      setSelected(d)
      setEditSynopsis(d.metadata_record?.ai_synopsis ?? "")
      setEditGenre(d.metadata_record?.ai_genre_primary ?? "")
    } catch {}
  }

  const handleAction = async (action: "approve" | "reject" | "modify") => {
    if (!selected) return
    setActionLoading(true)
    try {
      await metadataApi.reviewAction(selected.id, {
        action,
        reviewer,
        final_synopsis: editSynopsis,
        final_genre: editGenre,
      })
      setQueue((q) => q.filter((c) => c.id !== selected.id))
      setSelected(null)
    } catch {
      // Mock: 그냥 제거
      setQueue((q) => q.filter((c) => c.id !== selected.id))
      setSelected(null)
    } finally {
      setActionLoading(false)
    }
  }

  useEffect(() => { fetchQueue() }, [page])

  const meta = selected?.metadata_record
  const breakdown = meta?.score_breakdown

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">검수 큐</h1>
          <p className="text-sm text-muted-foreground mt-1">AI 처리 완료 — 담당자 리뷰 대기 ({total}건)</p>
        </div>
        <button onClick={fetchQueue} className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border text-sm hover:bg-accent">
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /> 새로고침
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4 min-h-[600px]">
        {/* 목록 */}
        <div className="lg:col-span-2 rounded-xl border border-border bg-card overflow-hidden flex flex-col">
          <div className="px-4 py-3 border-b border-border bg-muted/30 text-sm font-medium text-muted-foreground">
            콘텐츠 목록 (우선순위: 낮은 점수)
          </div>
          <div className="flex-1 overflow-y-auto divide-y divide-border">
            {queue.length === 0 && (
              <div className="p-8 text-center text-muted-foreground text-sm">검수 대기 항목이 없습니다</div>
            )}
            {queue.map((c) => (
              <button
                key={c.id}
                onClick={() => selectContent(c)}
                className={`w-full text-left px-4 py-3 hover:bg-accent/50 transition-colors ${selected?.id === c.id ? "bg-accent" : ""}`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="font-medium text-sm truncate">{c.title}</div>
                    <div className="text-xs text-muted-foreground mt-0.5">{c.cp_name} · {c.production_year ?? "-"}</div>
                  </div>
                  <span className={`text-xs font-bold shrink-0 ${(c.quality_score ?? 0) >= 80 ? "text-yellow-600" : "text-orange-600"}`}>
                    {c.quality_score?.toFixed(0)}점
                  </span>
                </div>
              </button>
            ))}
          </div>
          {/* 페이지네이션 */}
          <div className="px-4 py-3 border-t border-border flex items-center justify-between text-sm">
            <span className="text-muted-foreground">총 {total}건</span>
            <div className="flex gap-1">
              <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1} className="p-1 rounded hover:bg-accent disabled:opacity-40">
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="px-2 py-0.5">{page}</span>
              <button onClick={() => setPage((p) => p + 1)} disabled={queue.length < 10} className="p-1 rounded hover:bg-accent disabled:opacity-40">
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>

        {/* 상세 diff */}
        <div className="lg:col-span-3 rounded-xl border border-border bg-card overflow-hidden flex flex-col">
          {!selected ? (
            <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
              왼쪽에서 콘텐츠를 선택하세요
            </div>
          ) : (
            <>
              <div className="px-5 py-4 border-b border-border">
                <div className="flex items-start justify-between">
                  <div>
                    <h2 className="font-bold text-lg">{selected.title}</h2>
                    <div className="text-sm text-muted-foreground">{selected.cp_name} · {selected.production_year}</div>
                  </div>
                  <div className="text-right">
                    <div className={`text-2xl font-bold ${(meta?.quality_score ?? 0) >= 80 ? "text-yellow-600" : "text-orange-600"}`}>
                      {meta?.quality_score?.toFixed(0)}점
                    </div>
                    <div className="text-xs text-muted-foreground">품질 스코어</div>
                  </div>
                </div>
              </div>

              <div className="flex-1 overflow-y-auto p-5 space-y-5">
                {/* 시놉시스 diff */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide">CP 원본</div>
                    <div className="rounded-lg bg-muted/50 p-3 text-sm min-h-[80px]">
                      {meta?.cp_synopsis ?? <span className="text-muted-foreground italic">없음</span>}
                    </div>
                  </div>
                  <div className="space-y-1">
                    <div className="text-xs font-medium text-primary uppercase tracking-wide">AI 생성</div>
                    <textarea
                      className="w-full rounded-lg border border-border bg-primary/5 p-3 text-sm min-h-[80px] resize-none focus:outline-none focus:ring-1 focus:ring-primary"
                      value={editSynopsis}
                      onChange={(e) => setEditSynopsis(e.target.value)}
                    />
                  </div>
                </div>

                {/* 장르 */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide">CP 장르</div>
                    <div className="rounded-lg bg-muted/50 px-3 py-2 text-sm">{meta?.cp_genre ?? "-"}</div>
                  </div>
                  <div className="space-y-1">
                    <div className="text-xs font-medium text-primary uppercase tracking-wide">AI 장르</div>
                    <input
                      className="w-full rounded-lg border border-border bg-primary/5 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                      value={editGenre}
                      onChange={(e) => setEditGenre(e.target.value)}
                    />
                  </div>
                </div>

                {/* 감성 태그 */}
                {meta?.ai_mood_tags && (
                  <div className="space-y-1">
                    <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide">AI 태그</div>
                    <div className="flex flex-wrap gap-1.5">
                      {meta.ai_mood_tags.map((t) => (
                        <span key={t} className="text-xs px-2 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20">
                          #{t}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* 점수 분석 */}
                {breakdown && (
                  <div className="space-y-2">
                    <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide">점수 분석</div>
                    <div className="rounded-lg border border-border p-3 space-y-2">
                      <ScoreBar label="시놉시스 품질" value={breakdown.synopsis_quality} max={30} />
                      <ScoreBar label="장르 신뢰도" value={breakdown.genre_confidence} max={20} />
                      <ScoreBar label="태그 커버리지" value={breakdown.tag_coverage} max={15} />
                      <ScoreBar label="외부 메타 매핑" value={breakdown.external_meta} max={20} />
                      <ScoreBar label="필드 충족률" value={breakdown.field_coverage} max={15} />
                    </div>
                  </div>
                )}
              </div>

              {/* 액션 버튼 */}
              <div className="px-5 py-4 border-t border-border flex items-center gap-2">
                <input
                  className="flex-1 rounded-lg border border-border px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                  placeholder="검수자 이름"
                  value={reviewer}
                  onChange={(e) => setReviewer(e.target.value)}
                />
                <button
                  onClick={() => handleAction("approve")}
                  disabled={actionLoading}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-green-600 text-white text-sm font-medium hover:bg-green-700 disabled:opacity-50"
                >
                  <CheckCircle className="h-4 w-4" /> 승인
                </button>
                <button
                  onClick={() => handleAction("modify")}
                  disabled={actionLoading}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
                >
                  수정 후 승인
                </button>
                <button
                  onClick={() => handleAction("reject")}
                  disabled={actionLoading}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50"
                >
                  <XCircle className="h-4 w-4" /> 반려
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
