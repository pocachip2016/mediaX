"use client"

import { useEffect, useState, useCallback, useRef } from "react"
import { RefreshCw, CheckCircle, AlertCircle, Mail, Search, GitMerge, Database, FlaskConical, Trash2, Plus, Upload, Play, Zap, Square, CheckSquare } from "lucide-react"
import {
  metadataApi,
  pipelineTestApi,
  type PipelineStatus,
  type PipelineTestStageSummary,
  type PipelineTestSeedResult,
  type PipelineTestCleanup,
  type ContentOut,
  type ContentTimeline,
  type ContentType,
  type BatchJobOut,
  type BulkActionResponse,
} from "@/lib/api"
import { PipelineBoard } from "@/components/contents/pipeline/PipelineBoard"

const ENABLE_TEST = process.env.NEXT_PUBLIC_ENABLE_PIPELINE_TEST === "true"

// ── Pipeline Test Console 설정 ────────────────────────────

const STAGE_DEFS = [
  { stage: 1, name: "생성",    statusKey: "raw",      colorClass: "bg-yellow-500" },
  { stage: 2, name: "회수",    statusKey: "enriched", colorClass: "bg-blue-500" },
  { stage: 3, name: "AI처리",  statusKey: "ai",       colorClass: "bg-violet-500" },
  { stage: 4, name: "검수",    statusKey: "review",     colorClass: "bg-orange-500" },
  { stage: 5, name: "승인",    statusKey: "approved",   colorClass: "bg-green-500" },
  { stage: 6, name: "게시",    statusKey: "published",  colorClass: "bg-gray-500" },
] as const

// ── Mock 데이터 ──────────────────────────────────────────

const MOCK_PIPELINE: PipelineStatus = {
  waiting_count: 12,
  processing_count: 8,
  staging_count: 41,
  review_count: 23,
  approved_count: 189,
  rejected_count: 17,
  failed_enrichment_count: 2,
  avg_quality_score: 83.4,
  last_email_poll: null,
  tasks_description: "Celery Beat 활성",
}

interface BeatTask {
  name: string
  task_key: string
  schedule: string
  last_run: string
  next_run: string
  status: "ok" | "warning" | "error"
  icon: React.ReactNode
}

const MOCK_BEAT_TASKS: BeatTask[] = [
  {
    name: "이메일 폴링",
    task_key: "poll_cp_emails",
    schedule: "5분",
    last_run: "3분 전",
    next_run: "2분 후",
    status: "ok",
    icon: <Mail className="h-4 w-4" />,
  },
  {
    name: "에이전틱 검색",
    task_key: "enrich_content_metadata",
    schedule: "온디맨드",
    last_run: "방금",
    next_run: "-",
    status: "ok",
    icon: <Search className="h-4 w-4" />,
  },
  {
    name: "누락 에피소드 체크",
    task_key: "check_missing_episodes",
    schedule: "매일 04:00",
    last_run: "6시간 전",
    next_run: "18시간 후",
    status: "ok",
    icon: <GitMerge className="h-4 w-4" />,
  },
  {
    name: "실패 재시도",
    task_key: "retry_failed_enrichments",
    schedule: "6시간",
    last_run: "1시간 전",
    next_run: "5시간 후",
    status: "warning",
    icon: <RefreshCw className="h-4 w-4" />,
  },
  {
    name: "KOBIS 동기화",
    task_key: "sync_kobis",
    schedule: "매일 03:00",
    last_run: "7시간 전",
    next_run: "17시간 후",
    status: "ok",
    icon: <Database className="h-4 w-4" />,
  },
  {
    name: "품질 재평가",
    task_key: "reeval_quality_scores",
    schedule: "매일 01:00",
    last_run: "9시간 전",
    next_run: "15시간 후",
    status: "ok",
    icon: <CheckCircle className="h-4 w-4" />,
  },
]

interface FailedItem {
  id: number
  title: string
  error: string
  retries: number
  max_retries: number
}

const MOCK_FAILED: FailedItem[] = [
  { id: 101, title: "외계+인 2부", error: "TMDB 404 Not Found", retries: 1, max_retries: 3 },
  { id: 202, title: "익명의 드라마", error: "LLM JSON 파싱 실패", retries: 2, max_retries: 3 },
]

// ── Seed 카탈로그 (D2 SSOT) ──────────────────────────────

const SEED_CATALOG = [
  { category: "영화-완전", count: 3, desc: "title/year/synopsis/genre/runtime/director/cast/poster/tmdb_id — enrich no-op 검증" },
  { category: "영화-불완전", count: 5, desc: "title/year 만 — enrich 후보(synopsis/genre/cast/poster/runtime) 발생" },
  { category: "시리즈-완전", count: 2, desc: "시리즈+시즌2+에피4 풀세트 — hierarchy 검증" },
  { category: "시리즈-불완전", count: 3, desc: "시리즈 title만+시즌1 셸 — 상속+enrich" },
  { category: "충돌", count: 2, desc: "year/genre 의도적 오류 — MetadataDiffPanel conflict 검증" },
] as const

// ── 컴포넌트 ─────────────────────────────────────────────

function SampleSeedPanel({
  summary,
  onRefresh,
}: {
  summary: PipelineTestStageSummary | null
  onRefresh: () => void
}) {
  const [seeding, setSeeding] = useState(false)
  const [cleaning, setCleaning] = useState(false)
  const [seedResult, setSeedResult] = useState<PipelineTestSeedResult | null>(null)
  const [cleanupResult, setCleanupResult] = useState<PipelineTestCleanup | null>(null)
  const [cleanupConfirm, setCleanupConfirm] = useState(false)

  const handleSeed = async () => {
    setSeeding(true)
    setSeedResult(null)
    try {
      const r = await pipelineTestApi.seed()
      setSeedResult(r)
      onRefresh()
    } catch (e) {
      console.error("seed failed", e)
    } finally {
      setSeeding(false)
    }
  }

  const handleCleanup = async (dry_run: boolean) => {
    setCleaning(true)
    setCleanupResult(null)
    setCleanupConfirm(false)
    try {
      const r = await pipelineTestApi.cleanup(dry_run)
      setCleanupResult(r)
      if (!dry_run) onRefresh()
    } catch (e) {
      console.error("cleanup failed", e)
    } finally {
      setCleaning(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold">시드 생성</h3>
          <p className="text-xs text-muted-foreground mt-0.5">TEST_PIPELINE 15건 격리 데이터 관리 · cp_name=TEST_PIPELINE + tags=pipeline-test</p>
        </div>
        {summary && summary.total > 0 && (
          <span className="shrink-0 text-xs px-2 py-0.5 rounded-full bg-amber-200 dark:bg-amber-800/40 text-amber-700 dark:text-amber-400 font-medium">
            시드 {summary.total}건 존재
          </span>
        )}
      </div>

      {/* D2 시드 카탈로그 */}
      <div className="rounded-lg border border-border bg-background overflow-hidden">
        <div className="px-3 py-2 bg-muted/40 flex items-center justify-between">
          <span className="text-xs font-semibold text-muted-foreground">시드 카탈로그 (총 15건)</span>
          <span className="text-xs text-muted-foreground">seed 실행 시 매번 동일하게 생성됨</span>
        </div>
        <div className="divide-y divide-border">
          {SEED_CATALOG.map((item) => (
            <div key={item.category} className="flex items-start gap-3 px-3 py-2.5">
              <span className="text-xs font-semibold w-24 shrink-0 pt-0.5">{item.category}</span>
              <span className="text-xs font-bold text-amber-600 dark:text-amber-500 w-6 shrink-0 pt-0.5">{item.count}건</span>
              <span className="text-xs text-muted-foreground leading-relaxed">{item.desc}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 현재 상태 분포 */}
      {summary && summary.total > 0 && (
        <div className="rounded-lg border border-border bg-background p-3 space-y-2">
          <div className="text-xs font-semibold text-muted-foreground">현재 DB 상태 분포</div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(summary.by_status)
              .filter(([, v]) => v > 0)
              .map(([k, v]) => (
                <span key={k} className="text-xs px-2 py-0.5 rounded-full bg-muted font-medium">
                  {k}: <span className="font-bold">{v}</span>
                </span>
              ))}
          </div>
          {summary.last_seeded_at && (
            <div className="text-xs text-muted-foreground">
              최근 시드: {new Date(summary.last_seeded_at).toLocaleString("ko-KR")}
            </div>
          )}
        </div>
      )}

      {/* 결과 피드백 */}
      {seedResult && (
        <div className="rounded-lg border border-green-200 dark:border-green-800/40 bg-green-50 dark:bg-green-900/10 px-3 py-2.5">
          <div className="text-sm font-medium text-green-700 dark:text-green-400">✓ 시드 완료</div>
          <div className="text-xs text-green-600 dark:text-green-500 mt-1 space-y-0.5">
            <div>영화-완전 {seedResult.movie_complete}건 · 영화-불완전 {seedResult.movie_incomplete}건</div>
            <div>시리즈-완전 {seedResult.series_complete}건 · 시리즈-불완전 {seedResult.series_incomplete}건 · 충돌 {seedResult.conflict}건</div>
            <div className="font-medium">합계 {seedResult.total_root}건 (루트 콘텐츠 기준)</div>
          </div>
        </div>
      )}
      {cleanupResult && (
        <div className={`rounded-lg border px-3 py-2.5 ${
          cleanupResult.dry_run
            ? "border-blue-200 dark:border-blue-800/40 bg-blue-50 dark:bg-blue-900/10"
            : "border-red-200 dark:border-red-800/40 bg-red-50 dark:bg-red-900/10"
        }`}>
          <div className={`text-sm font-medium ${
            cleanupResult.dry_run
              ? "text-blue-700 dark:text-blue-400"
              : "text-red-700 dark:text-red-400"
          }`}>
            {cleanupResult.dry_run
              ? `[건식] 삭제 대상 ${cleanupResult.deleted}건 — 실제 삭제되지 않음`
              : `클린업 완료: ${cleanupResult.deleted}건 삭제됨`}
          </div>
        </div>
      )}

      {/* 액션 버튼 */}
      <div className="flex items-center gap-2 flex-wrap">
        <button
          onClick={handleSeed}
          disabled={seeding}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-600 text-white text-sm font-medium disabled:opacity-50 transition-colors"
        >
          <FlaskConical className={`h-3.5 w-3.5 ${seeding ? "animate-pulse" : ""}`} />
          시드 생성 (15건)
        </button>

        <button
          onClick={() => handleCleanup(true)}
          disabled={cleaning || !summary?.total}
          className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-border text-sm hover:bg-accent disabled:opacity-50 transition-colors"
        >
          건식 테스트
        </button>

        {cleanupConfirm ? (
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-red-500 font-medium">TEST_PIPELINE 데이터 전체 삭제. 계속?</span>
            <button
              onClick={() => handleCleanup(false)}
              className="px-3 py-1.5 rounded-lg bg-red-500 hover:bg-red-600 text-white text-xs font-medium transition-colors"
            >
              삭제 확인
            </button>
            <button
              onClick={() => setCleanupConfirm(false)}
              className="px-3 py-1.5 rounded-lg border border-border text-xs hover:bg-accent transition-colors"
            >
              취소
            </button>
          </div>
        ) : (
          <button
            onClick={() => setCleanupConfirm(true)}
            disabled={cleaning || !summary?.total}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-red-200 dark:border-red-800/40 text-red-600 dark:text-red-400 text-sm hover:bg-red-50 dark:hover:bg-red-900/10 disabled:opacity-50 transition-colors"
          >
            {cleaning ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
            클린업
          </button>
        )}
      </div>
    </div>
  )
}

const STATUS_LABEL: Record<string, string> = {
  waiting: "대기", processing: "처리중", staging: "검토", review: "검수", approved: "승인", rejected: "반려", published: "게시",
}
const STATUS_COLOR: Record<string, string> = {
  waiting: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
  processing: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  staging: "bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400",
  review: "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400",
  approved: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  rejected: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  published: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
}
const TYPE_LABEL: Record<string, string> = { movie: "영화", series: "시리즈", season: "시즌", episode: "에피" }

function TestContentList({
  contents,
  loading,
  selectedId,
  onSelect,
}: {
  contents: ContentOut[]
  loading: boolean
  selectedId: number | null
  onSelect: (id: number) => void
}) {
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
  return (
    <div className="rounded-lg border border-border bg-background overflow-hidden">
      <div className="px-3 py-2 bg-muted/40 flex items-center justify-between">
        <span className="text-xs font-semibold text-muted-foreground">TEST_PIPELINE 목록</span>
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

const TIMELINE_STAGES = ["생성", "AI처리", "Enrich", "검수", "승인", "게시"] as const

function ContentPipelineTimeline({
  timeline,
  loading,
}: {
  timeline: ContentTimeline | null
  loading: boolean
}) {
  if (loading) {
    return (
      <div className="mt-3 rounded-lg border border-border bg-background p-4 text-center text-xs text-muted-foreground">
        <RefreshCw className="h-4 w-4 mx-auto mb-1.5 animate-spin opacity-50" />
        타임라인 로딩 중…
      </div>
    )
  }
  if (!timeline) return null

  const stageMap = new Map(timeline.stages.map((s) => [s.stage, s]))

  return (
    <div className="mt-3 rounded-lg border border-border bg-background overflow-hidden">
      {/* 헤더 */}
      <div className="px-3 py-2 bg-muted/40 flex items-center justify-between gap-2">
        <span className="text-xs font-semibold truncate">{timeline.title}</span>
        <span className="text-xs text-muted-foreground shrink-0">#{timeline.content_id}</span>
      </div>

      <div className="px-3 py-3 space-y-3">
        {/* 수평 타임라인 도트 */}
        <div className="overflow-x-auto">
          <div className="min-w-[320px]">
            {/* 도트 + 선 */}
            <div className="flex items-center">
              {TIMELINE_STAGES.map((name, i) => {
                const stage = stageMap.get(i + 1)
                const isDone = stage?.status === "done"
                const isActive = stage?.status === "active"
                return (
                  <div key={name} className="flex items-center flex-1">
                    <div className={`w-4 h-4 rounded-full border-2 shrink-0 flex items-center justify-center ${
                      isDone ? "bg-primary border-primary" : isActive ? "bg-primary/30 border-primary animate-pulse" : "bg-background border-muted-foreground/30"
                    }`}>
                      {isDone && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
                    </div>
                    {i < TIMELINE_STAGES.length - 1 && (
                      <div className={`flex-1 h-0.5 ${isDone ? "bg-primary" : "bg-muted-foreground/20"}`} />
                    )}
                  </div>
                )
              })}
            </div>
            {/* 스테이지 이름 + 시각 */}
            <div className="flex mt-1.5">
              {TIMELINE_STAGES.map((name, i) => {
                const stage = stageMap.get(i + 1)
                const timeStr = stage?.at
                  ? new Date(stage.at).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })
                  : "—"
                return (
                  <div key={name} className="flex-1 text-center">
                    <div className="text-[10px] font-medium text-foreground">{name}</div>
                    <div className="text-[10px] text-muted-foreground">{timeStr}</div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>

        {/* 상세 행 */}
        <div className="border-t border-border pt-2 space-y-1">
          {TIMELINE_STAGES.map((name, i) => {
            const stage = stageMap.get(i + 1)
            if (!stage || (stage.status === "pending" && Object.keys(stage.detail ?? {}).length === 0)) return null
            const detailParts = Object.entries(stage.detail ?? {})
              .filter(([, v]) => v !== null && v !== undefined && v !== "")
              .map(([k, v]) => `${k}=${String(v).slice(0, 20)}`)
              .join(" · ")
            return (
              <div key={name} className="flex items-start gap-2 text-xs">
                <span className="shrink-0 text-muted-foreground w-16">①②③④⑤⑥"[i]"</span>
                <span className={`shrink-0 font-medium ${stage.status === "done" ? "text-primary" : stage.status === "active" ? "text-amber-600" : "text-muted-foreground"}`}>
                  {"①②③④⑤⑥"[i]} {name}
                </span>
                <span className="text-muted-foreground truncate">{detailParts || (stage.status === "pending" ? "대기중" : "—")}</span>
              </div>
            )
          })}
          {timeline.stages.every((s) => s.status === "pending") && (
            <div className="text-xs text-muted-foreground text-center py-1">파이프라인 미시작 — 콘텐츠가 대기 상태</div>
          )}
        </div>
      </div>
    </div>
  )
}

function AddContentInlinePanel({ onRefresh }: { onRefresh: () => void }) {
  const [form, setForm] = useState({ title: "", content_type: "movie" as ContentType, production_year: "" })
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<ContentOut | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [autoEnrich, setAutoEnrich] = useState(false)

  const handleSubmit = async () => {
    if (!form.title.trim()) return
    setSubmitting(true)
    setResult(null)
    setError(null)
    try {
      const c = await metadataApi.createContent({
        title: form.title.trim(),
        content_type: form.content_type,
        cp_name: "TEST_PIPELINE",
        production_year: form.production_year ? Number(form.production_year) : undefined,
      })
      if (autoEnrich) await metadataApi.triggerEnrich(c.id).catch(() => {})
      setResult(c)
      setForm({ title: "", content_type: "movie", production_year: "" })
      onRefresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : "등록 실패")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-semibold">단건 콘텐츠 등록</h3>
        <p className="text-xs text-muted-foreground mt-0.5">TEST_PIPELINE CP 고정 · 파이프라인 생성 단계 검증</p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="col-span-2">
          <label className="block text-xs font-medium mb-1">제목 *</label>
          <input
            type="text"
            placeholder="예: 기생충 (테스트)"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            onKeyDown={(e) => { if (e.key === "Enter") handleSubmit() }}
            className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
        </div>
        <div>
          <label className="block text-xs font-medium mb-1">유형</label>
          <select
            value={form.content_type}
            onChange={(e) => setForm({ ...form, content_type: e.target.value as ContentType })}
            className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary/30"
          >
            <option value="movie">영화</option>
            <option value="series">시리즈</option>
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium mb-1">제작연도</label>
          <input
            type="number"
            placeholder="2024"
            value={form.production_year}
            onChange={(e) => setForm({ ...form, production_year: e.target.value })}
            className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
        </div>
        <div className="col-span-2">
          <label className="block text-xs font-medium mb-1">CP사</label>
          <input type="text" value="TEST_PIPELINE" disabled className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-muted text-muted-foreground" />
        </div>
      </div>

      <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
        <input type="checkbox" checked={autoEnrich} onChange={(e) => setAutoEnrich(e.target.checked)} className="rounded" />
        등록 후 Enrich 자동 트리거
      </label>

      {error && (
        <div className="text-xs text-red-600 dark:text-red-400 px-3 py-2 rounded-lg border border-red-200 dark:border-red-800/40 bg-red-50 dark:bg-red-900/10">{error}</div>
      )}
      {result && (
        <div className="text-xs px-3 py-2 rounded-lg border border-green-200 dark:border-green-800/40 bg-green-50 dark:bg-green-900/10 text-green-700 dark:text-green-400">
          ✓ 등록 완료: #{result.id} {result.title} (상태: {result.status})
        </div>
      )}

      <button
        onClick={handleSubmit}
        disabled={submitting || !form.title.trim()}
        className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground text-sm font-medium disabled:opacity-50 transition-colors"
      >
        {submitting ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
        단건 등록
      </button>
    </div>
  )
}

function BulkUploadEmbed({ onRefresh }: { onRefresh: () => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState<BatchJobOut | null>(null)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    const f = e.dataTransfer.files[0]
    if (f) setFile(f)
  }, [])

  const handleUpload = async () => {
    if (!file) return
    setUploading(true)
    setResult(null)
    setError(null)
    try {
      const formData = new FormData()
      formData.append("file", file)
      const r = await metadataApi.uploadBatch(formData, false)
      setResult(r)
      setFile(null)
      onRefresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : "업로드 실패")
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-semibold">CSV 벌크 업로드</h3>
        <p className="text-xs text-muted-foreground mt-0.5">CSV/Excel → 다수 콘텐츠 일괄 등록 · /upload/batch 재사용</p>
      </div>

      <label
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        className="block border-2 border-dashed border-border rounded-lg p-6 text-center hover:border-primary/40 transition-colors cursor-pointer"
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.xlsx,.xls"
          className="hidden"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) setFile(f); e.target.value = "" }}
        />
        <Upload className="h-6 w-6 text-muted-foreground mx-auto mb-2" />
        {file ? (
          <p className="text-sm font-medium text-primary">{file.name} ({(file.size / 1024).toFixed(1)} KB)</p>
        ) : (
          <>
            <p className="text-sm text-muted-foreground">CSV/Excel 드래그 또는 클릭</p>
            <p className="text-xs text-muted-foreground mt-1">최대 10MB · <span className="font-mono">title</span> 컬럼 필수</p>
          </>
        )}
      </label>

      {error && (
        <div className="text-xs text-red-600 dark:text-red-400 px-3 py-2 rounded-lg border border-red-200 dark:border-red-800/40 bg-red-50 dark:bg-red-900/10">{error}</div>
      )}
      {result && (
        <div className="text-xs px-3 py-2 rounded-lg border border-green-200 dark:border-green-800/40 bg-green-50 dark:bg-green-900/10 text-green-700 dark:text-green-400">
          ✓ 업로드 완료: job #{result.id} · 성공 {result.success_count}건 / 실패 {result.failed_count}건 (총 {result.total_count}건)
        </div>
      )}

      <div className="flex items-center gap-2">
        <button
          onClick={handleUpload}
          disabled={uploading || !file}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground text-sm font-medium disabled:opacity-50 transition-colors"
        >
          {uploading ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
          업로드 시작
        </button>
        {file && (
          <button onClick={() => setFile(null)} className="text-xs text-muted-foreground hover:text-foreground transition-colors">
            취소
          </button>
        )}
      </div>
    </div>
  )
}

const CREATION_TABS = [
  { key: "seed", label: "🧪 시드" },
  { key: "single", label: "➕ 건별" },
  { key: "bulk", label: "📤 대량(CSV)" },
] as const

function CreationTabsPanel({
  summary,
  onRefresh,
}: {
  summary: PipelineTestStageSummary | null
  onRefresh: () => void
}) {
  const [activeTab, setActiveTab] = useState<"seed" | "single" | "bulk">("seed")
  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-semibold">① 생성 — waiting로 투입</h3>
        <p className="text-xs text-muted-foreground mt-0.5">시드 · 건별 · 대량(CSV) 입력으로 waiting 상태 콘텐츠 생성</p>
      </div>
      {/* 탭 바 */}
      <div className="flex gap-4 border-b border-amber-200 dark:border-amber-800/40">
        {CREATION_TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActiveTab(tab.key)}
            className={`pb-2 px-1 text-sm font-medium transition-colors border-b-2 ${
              activeTab === tab.key
                ? "border-amber-500 text-amber-600 dark:text-amber-400"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>
      {/* 탭 본문 */}
      {activeTab === "seed" && <SampleSeedPanel summary={summary} onRefresh={onRefresh} />}
      {activeTab === "single" && <AddContentInlinePanel onRefresh={onRefresh} />}
      {activeTab === "bulk" && <BulkUploadEmbed onRefresh={onRefresh} />}
    </div>
  )
}

function BatchAiTrigger({ onRefresh }: { onRefresh: () => void }) {
  const [items, setItems] = useState<ContentOut[]>([])
  const [loading, setLoading] = useState(false)
  const [triggering, setTriggering] = useState(false)
  const [result, setResult] = useState<BulkActionResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const fetchWaiting = useCallback(async () => {
    setLoading(true)
    try {
      const r = await metadataApi.listContents({ cp_name: "TEST_PIPELINE", status: "raw", size: 50 })
      setItems(r.items)
    } catch { setItems([]) } finally { setLoading(false) }
  }, [])

  useEffect(() => { fetchWaiting() }, [fetchWaiting])

  const handleTrigger = async () => {
    if (!items.length) return
    setTriggering(true)
    setResult(null)
    setError(null)
    try {
      const r = await metadataApi.bulkProcess({ ids: items.map((c) => c.id) })
      setResult(r)
      onRefresh()
      fetchWaiting()
    } catch (e) { setError(e instanceof Error ? e.message : "처리 실패") }
    finally { setTriggering(false) }
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-semibold">S3 — 일괄 AI 처리 트리거</h3>
        <p className="text-xs text-muted-foreground mt-0.5">TEST_PIPELINE 대기 항목 → AI process 일괄 큐잉 · /bulk/process</p>
      </div>

      {loading ? (
        <div className="text-center py-4 text-xs text-muted-foreground">
          <RefreshCw className="h-4 w-4 mx-auto mb-1 animate-spin opacity-50" />로딩 중…
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border p-4 text-center text-xs text-muted-foreground">
          대기(waiting) 상태 TEST_PIPELINE 항목 없음
        </div>
      ) : (
        <div className="rounded-lg border border-border bg-background overflow-hidden">
          <div className="px-3 py-2 bg-muted/40 flex items-center justify-between">
            <span className="text-xs font-semibold text-muted-foreground">대기 항목</span>
            <span className="text-xs text-muted-foreground">{items.length}건</span>
          </div>
          <div className="divide-y divide-border max-h-48 overflow-y-auto">
            {items.map((c) => (
              <div key={c.id} className="flex items-center gap-2 px-3 py-2">
                <span className="text-xs text-muted-foreground shrink-0">{TYPE_LABEL[c.content_type] ?? c.content_type}</span>
                <span className="text-xs font-medium truncate flex-1">{c.title}</span>
                <span className="text-xs text-muted-foreground shrink-0">#{c.id}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {error && (
        <div className="text-xs text-red-600 dark:text-red-400 px-3 py-2 rounded-lg border border-red-200 dark:border-red-800/40 bg-red-50 dark:bg-red-900/10">{error}</div>
      )}
      {result && (
        <div className="rounded-lg border border-blue-200 dark:border-blue-800/40 bg-blue-50 dark:bg-blue-900/10 px-3 py-2.5">
          <div className="text-sm font-medium text-blue-700 dark:text-blue-400">✓ AI 처리 큐잉 완료</div>
          <div className="text-xs text-blue-600 dark:text-blue-500 mt-1">
            수락 {result.ids_accepted}건 · 거부 {result.ids_rejected}건 · job: {result.job_id}
          </div>
        </div>
      )}

      <div className="flex items-center gap-2">
        <button
          onClick={handleTrigger}
          disabled={triggering || !items.length}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium disabled:opacity-50 transition-colors"
        >
          {triggering ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
          AI 처리 트리거 ({items.length}건)
        </button>
        <button
          onClick={fetchWaiting}
          disabled={loading}
          className="p-2 rounded-lg border border-border hover:bg-accent disabled:opacity-50 transition-colors"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>
    </div>
  )
}

function BatchEnrichTrigger({ onRefresh }: { onRefresh: () => void }) {
  const [items, setItems] = useState<ContentOut[]>([])
  const [loading, setLoading] = useState(false)
  const [triggering, setTriggering] = useState(false)
  const [result, setResult] = useState<BulkActionResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const fetchProcessing = useCallback(async () => {
    setLoading(true)
    try {
      const r = await metadataApi.listContents({ cp_name: "TEST_PIPELINE", status: "enriched", size: 50 })
      setItems(r.items)
    } catch { setItems([]) } finally { setLoading(false) }
  }, [])

  useEffect(() => { fetchProcessing() }, [fetchProcessing])

  const handleTrigger = async () => {
    if (!items.length) return
    setTriggering(true)
    setResult(null)
    setError(null)
    try {
      const r = await metadataApi.bulkEnrich({ ids: items.map((c) => c.id) })
      setResult(r)
      onRefresh()
      fetchProcessing()
    } catch (e) { setError(e instanceof Error ? e.message : "처리 실패") }
    finally { setTriggering(false) }
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-semibold">S4 — 일괄 Enrich 트리거</h3>
        <p className="text-xs text-muted-foreground mt-0.5">TEST_PIPELINE 처리중 항목 → 외부 소스 enrich 일괄 큐잉 · /bulk/enrich</p>
      </div>

      {loading ? (
        <div className="text-center py-4 text-xs text-muted-foreground">
          <RefreshCw className="h-4 w-4 mx-auto mb-1 animate-spin opacity-50" />로딩 중…
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border p-4 text-center text-xs text-muted-foreground">
          처리중(processing) 상태 TEST_PIPELINE 항목 없음
        </div>
      ) : (
        <div className="rounded-lg border border-border bg-background overflow-hidden">
          <div className="px-3 py-2 bg-muted/40 flex items-center justify-between">
            <span className="text-xs font-semibold text-muted-foreground">처리중 항목</span>
            <span className="text-xs text-muted-foreground">{items.length}건</span>
          </div>
          <div className="divide-y divide-border max-h-48 overflow-y-auto">
            {items.map((c) => (
              <div key={c.id} className="flex items-center gap-2 px-3 py-2">
                <span className="text-xs text-muted-foreground shrink-0">{TYPE_LABEL[c.content_type] ?? c.content_type}</span>
                <span className="text-xs font-medium truncate flex-1">{c.title}</span>
                <span className="text-xs text-muted-foreground shrink-0">#{c.id}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {error && (
        <div className="text-xs text-red-600 dark:text-red-400 px-3 py-2 rounded-lg border border-red-200 dark:border-red-800/40 bg-red-50 dark:bg-red-900/10">{error}</div>
      )}
      {result && (
        <div className="rounded-lg border border-violet-200 dark:border-violet-800/40 bg-violet-50 dark:bg-violet-900/10 px-3 py-2.5">
          <div className="text-sm font-medium text-violet-700 dark:text-violet-400">✓ Enrich 큐잉 완료</div>
          <div className="text-xs text-violet-600 dark:text-violet-500 mt-1">
            수락 {result.ids_accepted}건 · 거부 {result.ids_rejected}건 · job: {result.job_id}
          </div>
        </div>
      )}

      <div className="flex items-center gap-2">
        <button
          onClick={handleTrigger}
          disabled={triggering || !items.length}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-700 text-white text-sm font-medium disabled:opacity-50 transition-colors"
        >
          {triggering ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Zap className="h-3.5 w-3.5" />}
          Enrich 트리거 ({items.length}건)
        </button>
        <button
          onClick={fetchProcessing}
          disabled={loading}
          className="p-2 rounded-lg border border-border hover:bg-accent disabled:opacity-50 transition-colors"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>
    </div>
  )
}

function TestReviewPanel({ onRefresh }: { onRefresh: () => void }) {
  const [items, setItems] = useState<ContentOut[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [acting, setActing] = useState(false)
  const [resultMsg, setResultMsg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const fetchStaging = useCallback(async () => {
    setLoading(true)
    try {
      const r = await metadataApi.listContents({ cp_name: "TEST_PIPELINE", status: "ai", size: 50 })
      setItems(r.items)
      setSelectedIds(new Set())
    } catch { setItems([]) } finally { setLoading(false) }
  }, [])

  useEffect(() => { fetchStaging() }, [fetchStaging])

  const toggleAll = () => {
    setSelectedIds(selectedIds.size === items.length ? new Set() : new Set(items.map((c) => c.id)))
  }

  const toggleOne = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const handleApprove = async () => {
    if (!selectedIds.size) return
    setActing(true)
    setResultMsg(null)
    setError(null)
    try {
      const r = await metadataApi.bulkApprove({ content_ids: [...selectedIds], reviewer: "test-console" })
      setResultMsg(`✓ ${r.approved}건 승인됨`)
      onRefresh()
      fetchStaging()
    } catch (e) { setError(e instanceof Error ? e.message : "승인 실패") }
    finally { setActing(false) }
  }

  const handleReject = async () => {
    if (!selectedIds.size) return
    setActing(true)
    setResultMsg(null)
    setError(null)
    try {
      const r = await metadataApi.bulkReject({ content_ids: [...selectedIds], reviewer: "test-console" })
      setResultMsg(`✓ ${r.rejected}건 반려됨`)
      onRefresh()
      fetchStaging()
    } catch (e) { setError(e instanceof Error ? e.message : "반려 실패") }
    finally { setActing(false) }
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-semibold">S5 — 검수 큐 (TEST_PIPELINE)</h3>
        <p className="text-xs text-muted-foreground mt-0.5">검토대기(staging) 항목 선택 후 일괄 승인/반려</p>
      </div>

      {loading ? (
        <div className="text-center py-4 text-xs text-muted-foreground">
          <RefreshCw className="h-4 w-4 mx-auto mb-1 animate-spin opacity-50" />로딩 중…
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border p-4 text-center text-xs text-muted-foreground">
          검토대기(staging) 상태 TEST_PIPELINE 항목 없음
        </div>
      ) : (
        <div className="rounded-lg border border-border bg-background overflow-hidden">
          <div className="px-3 py-2 bg-muted/40 flex items-center gap-2">
            <button onClick={toggleAll} className="shrink-0">
              {selectedIds.size === items.length
                ? <CheckSquare className="h-3.5 w-3.5 text-primary" />
                : <Square className="h-3.5 w-3.5 text-muted-foreground" />}
            </button>
            <span className="text-xs font-semibold text-muted-foreground flex-1">검토대기 항목</span>
            <span className="text-xs text-muted-foreground">{selectedIds.size}/{items.length}건 선택</span>
          </div>
          <div className="divide-y divide-border max-h-48 overflow-y-auto">
            {items.map((c) => (
              <button
                key={c.id}
                onClick={() => toggleOne(c.id)}
                className={`w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-accent transition-colors ${
                  selectedIds.has(c.id) ? "bg-primary/5" : ""
                }`}
              >
                {selectedIds.has(c.id)
                  ? <CheckSquare className="h-3.5 w-3.5 text-primary shrink-0" />
                  : <Square className="h-3.5 w-3.5 text-muted-foreground shrink-0" />}
                <span className="text-xs text-muted-foreground shrink-0">{TYPE_LABEL[c.content_type] ?? c.content_type}</span>
                <span className="text-xs font-medium truncate flex-1">{c.title}</span>
                <span className="text-xs text-muted-foreground shrink-0">#{c.id}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {error && (
        <div className="text-xs text-red-600 dark:text-red-400 px-3 py-2 rounded-lg border border-red-200 dark:border-red-800/40 bg-red-50 dark:bg-red-900/10">{error}</div>
      )}
      {resultMsg && (
        <div className="rounded-lg border border-green-200 dark:border-green-800/40 bg-green-50 dark:bg-green-900/10 px-3 py-2.5">
          <div className="text-sm font-medium text-green-700 dark:text-green-400">{resultMsg}</div>
        </div>
      )}

      <div className="flex items-center gap-2">
        <button
          onClick={handleApprove}
          disabled={acting || !selectedIds.size}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-green-600 hover:bg-green-700 text-white text-sm font-medium disabled:opacity-50 transition-colors"
        >
          {acting ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle className="h-3.5 w-3.5" />}
          일괄 승인 ({selectedIds.size}건)
        </button>
        <button
          onClick={handleReject}
          disabled={acting || !selectedIds.size}
          className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-red-200 dark:border-red-800/40 text-red-600 dark:text-red-400 text-sm hover:bg-red-50 dark:hover:bg-red-900/10 disabled:opacity-50 transition-colors"
        >
          반려 ({selectedIds.size}건)
        </button>
        <button
          onClick={fetchStaging}
          disabled={loading}
          className="p-2 rounded-lg border border-border hover:bg-accent disabled:opacity-50 transition-colors"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>
    </div>
  )
}

function StatusDot({ status }: { status: "ok" | "warning" | "error" }) {
  return (
    <span className={`inline-block w-2 h-2 rounded-full ${
      status === "ok" ? "bg-green-500" : status === "warning" ? "bg-yellow-500" : "bg-red-500"
    }`} />
  )
}

function PipelineStageCard({
  stage, name, count, colorClass, active, onClick,
}: {
  stage: number; name: string; count: number; colorClass: string; active: boolean; onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={`flex-1 min-w-[80px] rounded-xl border-2 p-3 text-center transition-all ${
        active ? "border-primary bg-primary/5" : "border-border bg-card hover:bg-accent"
      }`}
    >
      <div className={`text-xs font-bold text-white ${colorClass} rounded px-1.5 py-0.5 inline-block mb-1.5`}>
        S{stage}
      </div>
      <div className="text-xs font-medium text-foreground">{name}</div>
      <div className="text-xl font-bold mt-0.5">{count}</div>
    </button>
  )
}

function PipelineStat({ label, value, color }: { label: string; value: number; color: string }) {
  const colorMap: Record<string, string> = {
    yellow: "text-yellow-600 dark:text-yellow-400",
    blue: "text-blue-600 dark:text-blue-400",
    violet: "text-violet-600 dark:text-violet-400",
    orange: "text-orange-600 dark:text-orange-400",
    green: "text-green-600 dark:text-green-400",
    red: "text-red-600 dark:text-red-400",
    gray: "text-muted-foreground",
  }
  return (
    <div className="text-center">
      <div className={`text-3xl font-bold ${colorMap[color] ?? ""}`}>{value}</div>
      <div className="text-xs text-muted-foreground mt-0.5">{label}</div>
    </div>
  )
}

// ── 메인 페이지 ──────────────────────────────────────────

export default function PipelineMonitoringPage() {
  const [pipeline, setPipeline] = useState<PipelineStatus>(MOCK_PIPELINE)
  const [loading, setLoading] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [failedItems] = useState<FailedItem[]>(MOCK_FAILED)
  const [retrying, setRetrying] = useState<Set<number>>(new Set())

  // Pipeline Test Console 상태
  const [testSummary, setTestSummary] = useState<PipelineTestStageSummary | null>(null)
  const [activeStage, setActiveStage] = useState<number | null>(null)
  const [testContents, setTestContents] = useState<ContentOut[]>([])
  const [testContentsLoading, setTestContentsLoading] = useState(false)
  const [selectedContentId, setSelectedContentId] = useState<number | null>(null)
  const [contentTimeline, setContentTimeline] = useState<ContentTimeline | null>(null)
  const [timelineLoading, setTimelineLoading] = useState(false)

  const fetchPipeline = useCallback(async () => {
    setLoading(true)
    try {
      const p = await metadataApi.getPipelineStatus()
      setPipeline(p)
    } catch {
      // Mock 유지
    } finally {
      setLoading(false)
    }
  }, [])

  // 자동 새로고침 30초
  useEffect(() => {
    fetchPipeline()
    if (!autoRefresh) return
    const id = setInterval(fetchPipeline, 30000)
    return () => clearInterval(id)
  }, [fetchPipeline, autoRefresh])

  const fetchTestContents = useCallback(async () => {
    if (!ENABLE_TEST) return
    setTestContentsLoading(true)
    try {
      const r = await metadataApi.listContents({ cp_name: "TEST_PIPELINE", size: 50 })
      setTestContents(r.items)
    } catch {
      setTestContents([])
    } finally {
      setTestContentsLoading(false)
    }
  }, [])

  const fetchTimeline = useCallback(async (id: number) => {
    setTimelineLoading(true)
    setContentTimeline(null)
    try {
      const t = await metadataApi.getTimeline(id)
      setContentTimeline(t)
    } catch {
      setContentTimeline(null)
    } finally {
      setTimelineLoading(false)
    }
  }, [])

  const handleSelectContent = useCallback((id: number) => {
    setSelectedContentId(id)
    fetchTimeline(id)
  }, [fetchTimeline])

  const refreshTestSummary = useCallback(async () => {
    if (!ENABLE_TEST) return
    try {
      const s = await pipelineTestApi.summary()
      setTestSummary(s)
    } catch {}
    await fetchTestContents()
  }, [fetchTestContents])

  // Test Console 초기 summary 로드
  useEffect(() => {
    refreshTestSummary()
  }, [refreshTestSummary])

  const handleRetry = async (item: FailedItem) => {
    setRetrying((prev) => new Set(prev).add(item.id))
    try {
      await metadataApi.retryFailedJob(item.id)
      setTimeout(() => {
        setRetrying((prev) => { const n = new Set(prev); n.delete(item.id); return n })
      }, 2000)
    } catch {
      setRetrying((prev) => { const n = new Set(prev); n.delete(item.id); return n })
    }
  }

  const totalItems = pipeline.waiting_count + pipeline.processing_count + pipeline.staging_count + pipeline.review_count + pipeline.approved_count + pipeline.rejected_count
  const successRate = totalItems > 0 ? ((pipeline.approved_count / totalItems) * 100).toFixed(1) : "0.0"

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold">파이프라인 모니터링</h1>
          <p className="text-sm text-muted-foreground mt-1">AI VOD 메타데이터 자동화 파이프라인 실시간 현황</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setAutoRefresh((v) => !v)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-sm transition-colors ${
              autoRefresh
                ? "border-green-300 dark:border-green-700 bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400"
                : "border-border text-muted-foreground hover:bg-accent"
            }`}
          >
            <span className={`w-2 h-2 rounded-full ${autoRefresh ? "bg-green-500 animate-pulse" : "bg-gray-400"}`} />
            {autoRefresh ? "자동 새로고침 ON" : "자동 새로고침 OFF"}
          </button>
          <button
            onClick={fetchPipeline}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border text-sm hover:bg-accent"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            수동 새로고침
          </button>
        </div>
      </div>

      {/* ADR-006: 파이프라인 보드 (마스터-디테일) */}
      <PipelineBoard autoRefresh={autoRefresh} />

      {/* 전체 현황 카드 */}
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold">파이프라인 현황</h2>
          <div className="text-sm text-muted-foreground">
            평균 품질 <span className="font-bold text-foreground">{pipeline.avg_quality_score}점</span>
            <span className="mx-2">·</span>
            성공률 <span className="font-bold text-green-600">{successRate}%</span>
          </div>
        </div>
        <div className="grid grid-cols-3 md:grid-cols-6 gap-4">
          <PipelineStat label="수신 대기" value={pipeline.waiting_count} color="yellow" />
          <PipelineStat label="처리 중" value={pipeline.processing_count} color="blue" />
          <PipelineStat label="검토 대기" value={pipeline.staging_count} color="violet" />
          <PipelineStat label="검수 대기" value={pipeline.review_count} color="orange" />
          <PipelineStat label="승인 완료" value={pipeline.approved_count} color="green" />
          <PipelineStat label="반려/실패" value={pipeline.rejected_count} color="red" />
        </div>

        {/* 흐름 바 */}
        <div className="mt-5 flex items-center gap-1 overflow-x-auto pb-1 text-sm">
          {[
            { label: "이메일 수신", val: pipeline.waiting_count, bg: "bg-yellow-500" },
            { label: "AI 처리", val: pipeline.processing_count, bg: "bg-blue-500" },
            { label: "검색 완료", val: pipeline.staging_count, bg: "bg-violet-500" },
            { label: "검수", val: pipeline.review_count, bg: "bg-orange-500" },
            { label: "등록", val: pipeline.approved_count, bg: "bg-green-500" },
          ].map((step, i) => (
            <div key={step.label} className="flex items-center gap-1 shrink-0">
              {i > 0 && <span className="text-muted-foreground text-xs px-0.5">→</span>}
              <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-white text-xs font-medium ${step.bg}`}>
                {step.label}
                <span className="font-bold">{step.val}</span>
              </div>
            </div>
          ))}
          {pipeline.failed_enrichment_count > 0 && (
            <div className="flex items-center gap-1 shrink-0 ml-2">
              <span className="text-muted-foreground text-xs">↘</span>
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-red-500 text-white text-xs font-medium">
                <AlertCircle className="h-3 w-3" />
                실패 {pipeline.failed_enrichment_count}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Beat 스케줄 상태 */}
        <div className="rounded-xl border border-border bg-card overflow-hidden">
          <div className="px-5 py-4 border-b border-border">
            <h2 className="font-semibold">Beat 스케줄 상태</h2>
          </div>
          <div className="divide-y divide-border">
            {MOCK_BEAT_TASKS.map((task) => (
              <div key={task.task_key} className="flex items-center gap-3 px-5 py-3">
                <div className={`p-1.5 rounded-lg ${
                  task.status === "ok" ? "bg-green-100 dark:bg-green-900/20 text-green-600 dark:text-green-400"
                  : task.status === "warning" ? "bg-yellow-100 dark:bg-yellow-900/20 text-yellow-600 dark:text-yellow-400"
                  : "bg-red-100 dark:bg-red-900/20 text-red-600 dark:text-red-400"
                }`}>
                  {task.icon}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{task.name}</span>
                    <StatusDot status={task.status} />
                  </div>
                  <div className="text-xs text-muted-foreground">
                    주기: {task.schedule}
                  </div>
                </div>
                <div className="text-right text-xs">
                  <div className="text-muted-foreground">마지막: <span className="text-foreground">{task.last_run}</span></div>
                  <div className="text-muted-foreground">다음: <span className="text-foreground">{task.next_run}</span></div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 실패 항목 재시도 */}
        <div className="rounded-xl border border-border bg-card overflow-hidden">
          <div className="px-5 py-4 border-b border-border flex items-center justify-between">
            <h2 className="font-semibold">실패 항목</h2>
            {failedItems.length > 0 && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-red-100 dark:bg-red-900/20 text-red-600 dark:text-red-400 font-medium">
                {failedItems.length}건
              </span>
            )}
          </div>
          <div className="divide-y divide-border">
            {failedItems.length === 0 ? (
              <div className="px-5 py-8 text-center text-muted-foreground text-sm">
                <CheckCircle className="h-8 w-8 mx-auto mb-2 text-green-500 opacity-60" />
                실패 항목 없음
              </div>
            ) : (
              failedItems.map((item) => (
                <div key={item.id} className="px-5 py-3.5 flex items-start gap-3">
                  <AlertCircle className="h-4 w-4 text-red-500 mt-0.5 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium">{item.title}</div>
                    <div className="text-xs text-muted-foreground mt-0.5">{item.error}</div>
                    <div className="flex items-center gap-1.5 mt-1">
                      <div className="flex gap-0.5">
                        {Array.from({ length: item.max_retries }, (_, i) => (
                          <div
                            key={i}
                            className={`w-3 h-1.5 rounded-sm ${i < item.retries ? "bg-red-400" : "bg-muted"}`}
                          />
                        ))}
                      </div>
                      <span className="text-xs text-muted-foreground">{item.retries}/{item.max_retries}회</span>
                    </div>
                  </div>
                  <button
                    onClick={() => handleRetry(item)}
                    disabled={retrying.has(item.id) || item.retries >= item.max_retries}
                    className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg border border-border hover:bg-accent disabled:opacity-50 shrink-0"
                  >
                    <RefreshCw className={`h-3 w-3 ${retrying.has(item.id) ? "animate-spin" : ""}`} />
                    {item.retries >= item.max_retries ? "한도초과" : "재시도"}
                  </button>
                </div>
              ))
            )}
          </div>

          {/* 24시간 통계 */}
          <div className="px-5 py-4 border-t border-border bg-muted/20">
            <div className="text-xs font-medium text-muted-foreground mb-2">최근 24시간 통계</div>
            <div className="grid grid-cols-3 gap-3 text-center text-sm">
              <div>
                <div className="font-bold text-foreground">{pipeline.waiting_count + pipeline.processing_count + pipeline.staging_count + pipeline.approved_count}</div>
                <div className="text-xs text-muted-foreground">수신</div>
              </div>
              <div>
                <div className="font-bold text-green-600">{pipeline.approved_count}</div>
                <div className="text-xs text-muted-foreground">완료</div>
              </div>
              <div>
                <div className="font-bold text-red-500">{pipeline.failed_enrichment_count}</div>
                <div className="text-xs text-muted-foreground">실패</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 알림 패널 */}
      {pipeline.failed_enrichment_count > 0 && (
        <div className="rounded-xl border border-yellow-200 dark:border-yellow-800/40 bg-yellow-50 dark:bg-yellow-900/10 px-5 py-4">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-yellow-600" />
            <div>
              <div className="text-sm font-medium text-yellow-700 dark:text-yellow-400">
                {pipeline.failed_enrichment_count}건의 콘텐츠가 6시간 이상 처리 중 상태입니다.
              </div>
              <div className="text-xs text-yellow-600 dark:text-yellow-500 mt-0.5">
                다음 재시도 배치(6시간 주기)에서 자동 처리됩니다.
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Pipeline Test Console (dev only — NEXT_PUBLIC_ENABLE_PIPELINE_TEST=true) */}
      {ENABLE_TEST && (
        <div className="rounded-xl border border-amber-200 dark:border-amber-800/40 bg-amber-50 dark:bg-amber-900/10">
          <div className="px-5 py-4 border-b border-amber-200 dark:border-amber-800/40 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FlaskConical className="h-4 w-4 text-amber-600" />
              <h2 className="font-semibold text-amber-800 dark:text-amber-300">Pipeline Test Console</h2>
              <span className="text-xs px-2 py-0.5 rounded-full bg-amber-200 dark:bg-amber-800/40 text-amber-700 dark:text-amber-400 font-medium">
                DEV ONLY
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-amber-600 dark:text-amber-500">
                {testSummary ? `TEST_PIPELINE 총 ${testSummary.total}건` : "데이터 없음 (시드 필요)"}
              </span>
              <button
                onClick={refreshTestSummary}
                className="flex items-center gap-1 px-2 py-1 rounded-md border border-amber-200 dark:border-amber-800/40 text-amber-600 dark:text-amber-500 text-xs hover:bg-amber-100 dark:hover:bg-amber-900/20 transition-colors"
              >
                <RefreshCw className="h-3 w-3" />
                새로고침
              </button>
            </div>
          </div>

          <div className="px-5 py-4 space-y-4">
            {/* 6단계 스트립 */}
            <div className="flex gap-2 overflow-x-auto pb-1">
              {STAGE_DEFS.map((s) => (
                <PipelineStageCard
                  key={s.stage}
                  stage={s.stage}
                  name={s.name}
                  count={testSummary?.by_status[s.statusKey] ?? 0}
                  colorClass={s.colorClass}
                  active={activeStage === s.stage}
                  onClick={() => setActiveStage(activeStage === s.stage ? null : s.stage)}
                />
              ))}
            </div>

            {/* 좌3/우2 그리드 */}
            <div className="grid grid-cols-5 gap-4 items-start">
              {/* 좌측 — ActiveStagePanel */}
              <div className="col-span-3">
                {activeStage !== null ? (
                  <div className="rounded-lg border border-amber-200 dark:border-amber-700/50 bg-background p-4">
                    {activeStage === 1 ? (
                      <CreationTabsPanel summary={testSummary} onRefresh={refreshTestSummary} />
                    ) : activeStage === 2 ? (
                      <BatchAiTrigger onRefresh={refreshTestSummary} />
                    ) : activeStage === 3 ? (
                      <BatchEnrichTrigger onRefresh={refreshTestSummary} />
                    ) : activeStage === 4 ? (
                      <TestReviewPanel onRefresh={refreshTestSummary} />
                    ) : activeStage === 5 || activeStage === 6 ? (
                      <div className="text-center text-xs text-muted-foreground py-8">
                        {activeStage === 5 ? "승인" : "게시"} 단계 패널 준비 중 — 검수 통과 후 자동 전이 현황을 우측 목록·타임라인에서 확인하세요
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <div className="rounded-lg border border-dashed border-amber-200 dark:border-amber-800/30 p-6 text-center text-xs text-amber-600/60 dark:text-amber-500/60">
                    스테이지 카드를 클릭해 패널을 열어주세요
                  </div>
                )}
              </div>

              {/* 우측 — TestContentList + Timeline */}
              <div className="col-span-2">
                <TestContentList
                  contents={testContents}
                  loading={testContentsLoading}
                  selectedId={selectedContentId}
                  onSelect={handleSelectContent}
                />
                <ContentPipelineTimeline
                  timeline={contentTimeline}
                  loading={timelineLoading}
                />
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
