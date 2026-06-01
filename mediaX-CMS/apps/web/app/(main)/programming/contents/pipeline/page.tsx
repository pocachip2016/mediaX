"use client"

import { useEffect, useState, useCallback, useRef, type ReactNode } from "react"
import { RefreshCw, CheckCircle, AlertCircle, Mail, Search, GitMerge, Database, FlaskConical, Trash2, Plus, Upload, Zap } from "lucide-react"
import {
  metadataApi,
  pipelineTestApi,
  type PipelineStatus,
  type PipelineTestStageSummary,
  type PipelineTestSeedResult,
  type PipelineTestCleanup,
  type ContentOut,
  type ContentDetail,
  type ContentType,
  type BatchJobOut,
  type BulkActionResponse,
  type AiTaskSetting,
  type AiTaskResponse,
  type ContentAIResult,
  type PipelineEventLog,
  type StageAutoPolicy,
  type RecommendationsOut,
  type FieldRecommendation,
  type EnrichPolicy,
  type ReferenceExtractResponse,
  type ContentStatus,
  type ReviewActionResponse,
} from "@/lib/api"
import { PipelineBoard } from "@/components/contents/pipeline/PipelineBoard"

const ENABLE_TEST = process.env.NEXT_PUBLIC_ENABLE_PIPELINE_TEST === "true"

// ── Pipeline Test Console 설정 ────────────────────────────

const STAGE_DEFS = [
  { stage: 1, name: "생성",    statusKey: "raw",      colorClass: "bg-yellow-500" },
  { stage: 2, name: "Enrich",  statusKey: "enriched", colorClass: "bg-blue-500" },
  { stage: 3, name: "AI처리",  statusKey: "ai",       colorClass: "bg-violet-500" },
  { stage: 4, name: "검수",    statusKey: "review",     colorClass: "bg-orange-500" },
  { stage: 5, name: "승인",    statusKey: "approved",   colorClass: "bg-green-500" },
  { stage: 6, name: "반려/실패", statusKey: "rejected",  colorClass: "bg-red-500" },
] as const

// current_stage(위치) → 콘솔 카드 bucket. 백엔드 pipeline_router._STAGE_BUCKET와 일치.
const STAGE_TO_BUCKET: Record<string, number> = {
  s1_intake: 1,
  s2_normalize: 2, s3_source_match: 2, s4_gap_detect: 2, s5_websearch_fill: 2,
  s6_llm_extract: 3, s7_staging: 3,
  s8_review: 4, s9_publish: 5,
}
// 콘텐츠의 위치 bucket — current_stage 없으면(시드 직후/레거시) bucket 1.
function stageBucket(c: { current_stage?: string | null }): number {
  return c.current_stage ? (STAGE_TO_BUCKET[c.current_stage] ?? 1) : 1
}
// 반려 항목은 위치와 무관하게 bucket 6(반려/실패)으로 분기. BE pipeline_summary와 일치.
function contentBucket(c: { current_stage?: string | null; status?: string | null }): number {
  return c.status === "rejected" ? 6 : stageBucket(c)
}

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
  const [seedResult, setSeedResult] = useState<PipelineTestSeedResult | null>(null)

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


      {/* 결과 피드백 */}
      {seedResult && (
        <div className="rounded-lg border border-green-200 dark:border-green-800/40 bg-green-50 dark:bg-green-900/10 px-3 py-2.5">
          <div className="text-sm font-medium text-green-700 dark:text-green-400">✓ 시드 완료</div>
          <div className="text-xs text-green-600 dark:text-green-500 mt-1 space-y-0.5">
            <div>영화-완전 {seedResult.movie_complete}건 · 영화-불완전 {seedResult.movie_incomplete}건</div>
            <div>시리즈-완전 {seedResult.series_complete}건 · 시리즈-불완전 {seedResult.series_incomplete}건 · 충돌 {seedResult.conflict}건</div>
            <div className="font-medium">합계 {seedResult.total_root}건 (루트 콘텐츠 기준)</div>
            {(seedResult.skipped_in_pipeline > 0 || seedResult.skipped_registered > 0) && (
              <div className="text-amber-600 dark:text-amber-400">
                스킵 — 진행중 {seedResult.skipped_in_pipeline}건 · 등록완료 {seedResult.skipped_registered}건 (중복)
              </div>
            )}
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
      </div>
    </div>
  )
}

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
        <span className="text-xs font-semibold text-muted-foreground">콘텐츠 목록</span>
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

// 단계별 전이 라벨 (advance API는 라벨 무관·status 1칸 진행)
const STAGE_TRANSITION: Record<number, [string, string]> = {
  1: ["생성", "Enrich"], 2: ["Enrich", "AI처리"], 3: ["AI처리", "검수"],
  4: ["검수", "승인"], 5: ["승인", "게시"],
}

// 선택 콘텐츠의 메타 정보 카드 (타임라인 대체)
function SelectedContentMeta({ contentId }: { contentId: number | null }) {
  const [detail, setDetail] = useState<ContentDetail | null>(null)
  const [loading, setLoading] = useState(false)
  useEffect(() => {
    if (contentId === null) { setDetail(null); return }
    let alive = true
    setLoading(true)
    metadataApi.getContent(contentId)
      .then((d) => { if (alive) setDetail(d) })
      .catch(() => { if (alive) setDetail(null) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [contentId])

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

  const fields: Array<[string, string | null]> = [
    ["제작연도", currentFieldValue(detail, "production_year")],
    ["국가", currentFieldValue(detail, "country")],
    ["장르", currentFieldValue(detail, "genres")],
    ["러닝타임", currentFieldValue(detail, "runtime")],
    ["출연", currentFieldValue(detail, "cast")],
    ["감독", currentFieldValue(detail, "director")],
  ]
  const synopsis = currentFieldValue(detail, "synopsis")

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

// 메타 상세 밑 — 선택 콘텐츠 단건 다음단계로 / 삭제
function SingleAdvanceDeleteBar({ contentId, activeStage, onDone, onDeleted }: {
  contentId: number | null; activeStage: number | null; onDone: () => void; onDeleted: () => void
}) {
  const [busy, setBusy] = useState(false)
  const [confirmDel, setConfirmDel] = useState(false)
  const [result, setResult] = useState<string | null>(null)
  if (contentId === null) return null
  const [from, to] = STAGE_TRANSITION[activeStage ?? 0] ?? ["현재", "다음"]

  const handleAdvance = async () => {
    setBusy(true); setResult(null)
    try {
      const r = await pipelineTestApi.advance([contentId])
      setResult(`✓ ${r.advanced}건 ${from}→${to}`)
      onDone()
    } catch (e) { setResult(`오류: ${e instanceof Error ? e.message : "advance 실패"}`) }
    finally { setBusy(false) }
  }
  const handleDelete = async () => {
    setBusy(true); setResult(null); setConfirmDel(false)
    try {
      const r = await pipelineTestApi.cleanupStage([contentId])
      setResult(`삭제 완료 (${r.deleted}건)`)
      onDeleted()
    } catch (e) { setResult(`오류: ${e instanceof Error ? e.message : "삭제 실패"}`) }
    finally { setBusy(false) }
  }

  return (
    <div className="mt-2 flex items-center gap-2 flex-wrap">
      <button onClick={() => void handleAdvance()} disabled={busy}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-medium disabled:opacity-50 transition-colors">
        {busy ? <RefreshCw className="h-3 w-3 animate-spin" /> : <span>→</span>}
        다음 단계로 (1건) · {from}→{to}
      </button>
      {confirmDel ? (
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] text-red-500 font-medium">이 콘텐츠 삭제. 계속?</span>
          <button onClick={() => void handleDelete()} className="px-2.5 py-1 rounded-lg bg-red-500 hover:bg-red-600 text-white text-[11px] font-medium transition-colors">삭제 확인</button>
          <button onClick={() => setConfirmDel(false)} className="px-2.5 py-1 rounded-lg border border-border text-[11px] hover:bg-accent transition-colors">취소</button>
        </div>
      ) : (
        <button onClick={() => setConfirmDel(true)} disabled={busy}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-red-200 dark:border-red-800/40 text-red-600 dark:text-red-400 text-xs font-medium hover:bg-red-50 dark:hover:bg-red-900/10 disabled:opacity-50 transition-colors">
          <Trash2 className="h-3 w-3" /> 삭제
        </button>
      )}
      {result && <span className={`text-[11px] ${result.startsWith("오류") ? "text-red-500" : "text-muted-foreground"}`}>{result}</span>}
    </div>
  )
}

// S1 전용 — 다음단계(?건) + 클린업(?건) 한 줄 버튼 (advance + cleanup)
function S1BulkActionBar({ stageContents, activeStage, onDone, onDeleted }: {
  stageContents: ContentOut[]; activeStage: number | null; onDone: () => void; onDeleted?: () => void
}) {
  const ids = stageContents.map((c) => c.id)
  const [from, to] = STAGE_TRANSITION[activeStage ?? 0] ?? ["현재", "다음"]
  const [advBusy, setAdvBusy] = useState(false)
  const [cleanBusy, setCleanBusy] = useState(false)
  const [cleanConfirm, setCleanConfirm] = useState(false)
  const [result, setResult] = useState<string | null>(null)

  const handleAdvance = async () => {
    setAdvBusy(true); setResult(null)
    try {
      const r = await pipelineTestApi.advance(ids)
      setResult(`✓ ${r.advanced}건 ${from}→${to}`)
      onDone()
    } catch (e) { setResult(`오류: ${e instanceof Error ? e.message : "실패"}`) }
    finally { setAdvBusy(false) }
  }
  const handleCleanup = async () => {
    setCleanBusy(true); setResult(null); setCleanConfirm(false)
    try {
      const r = await pipelineTestApi.cleanupStage(ids)
      setResult(`삭제 ${r.deleted}건`)
      onDeleted ? onDeleted() : onDone()
    } catch (e) { setResult(`오류: ${e instanceof Error ? e.message : "실패"}`) }
    finally { setCleanBusy(false) }
  }

  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-2">
        <button onClick={() => void handleAdvance()} disabled={advBusy || !ids.length}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-medium disabled:opacity-50 transition-colors">
          {advBusy ? <RefreshCw className="h-3 w-3 animate-spin" /> : <span>→</span>}
          다음단계 ({ids.length}건)
        </button>
        {cleanConfirm ? (
          <>
            <span className="text-[11px] text-red-500 font-medium">{ids.length}건 삭제?</span>
            <button onClick={() => void handleCleanup()} className="px-2.5 py-1.5 rounded-lg bg-red-500 hover:bg-red-600 text-white text-[11px] font-medium transition-colors">확인</button>
            <button onClick={() => setCleanConfirm(false)} className="px-2.5 py-1.5 rounded-lg border border-border text-[11px] hover:bg-accent transition-colors">취소</button>
          </>
        ) : (
          <button onClick={() => setCleanConfirm(true)} disabled={cleanBusy || !ids.length}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-red-200 dark:border-red-800/40 text-red-600 dark:text-red-400 text-xs font-medium hover:bg-red-50 dark:hover:bg-red-900/10 disabled:opacity-50 transition-colors">
            {cleanBusy ? <RefreshCw className="h-3 w-3 animate-spin" /> : <Trash2 className="h-3 w-3" />}
            클린업 ({ids.length}건)
          </button>
        )}
      </div>
      {result && <p className={`text-[11px] ${result.startsWith("오류") ? "text-red-500" : "text-muted-foreground"}`}>{result}</p>}
    </div>
  )
}

// 콘텐츠 목록 밑 — 해당 단계 전체 다음단계로 / 클린업 (S2~6 용)
function StageBulkBar({ stageContents, activeStage, onDone }: {
  stageContents: ContentOut[]; activeStage: number | null; onDone: () => void
}) {
  const ids = stageContents.map((c) => c.id)
  const [from, to] = STAGE_TRANSITION[activeStage ?? 0] ?? ["현재", "다음"]
  return (
    <div className="rounded-lg border border-border bg-background px-3 py-1">
      <StageAdvanceBar ids={ids} fromStatus={`${from} 전체 (${ids.length}건)`} toStatus={to} onDone={onDone} />
      <StageControlBar stageContents={stageContents} onDone={onDone} showPrev={false} />
    </div>
  )
}

// ── 공유 컴포넌트 ────────────────────────────────────────────────────────────

function InlineWebSearch({ defaultQuery = "" }: { defaultQuery?: string }) {
  const [query, setQuery] = useState(defaultQuery)
  const [results, setResults] = useState<{ title: string; url: string; domain: string; snippet: string }[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const handleSearch = async () => {
    if (!query.trim()) return
    setLoading(true); setError(null)
    try {
      const data = await metadataApi.websearchQuery(query.trim())
      setResults(data)
    } catch (e) { setError(e instanceof Error ? e.message : "검색 실패"); setResults([]) }
    finally { setLoading(false) }
  }
  return (
    <div className="space-y-2">
      <div className="flex gap-1.5">
        <input type="text" value={query} onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") void handleSearch() }}
          placeholder="검색어 입력" className="flex-1 text-xs px-2.5 py-1.5 rounded border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary/30" />
        <button onClick={() => void handleSearch()} disabled={loading || !query.trim()}
          className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 shrink-0">
          {loading ? <RefreshCw className="h-3 w-3 animate-spin" /> : <Search className="h-3 w-3" />} 검색
        </button>
      </div>
      {error && <p className="text-xs text-red-600 dark:text-red-400">{error}</p>}
      {results.length > 0 && (
        <div className="border border-border rounded-lg overflow-hidden divide-y divide-border">
          {results.map((r, i) => (
            <a key={i} href={r.url} target="_blank" rel="noopener noreferrer"
              className="flex items-start gap-2 px-3 py-2 hover:bg-accent transition-colors group">
              <div className="flex-1 min-w-0 space-y-0.5">
                <div className="flex items-center gap-1">
                  <span className="text-xs font-medium text-primary truncate">{r.title}</span>
                </div>
                <p className="text-[10px] text-muted-foreground line-clamp-2">{r.snippet}</p>
                <p className="text-[10px] text-slate-400">{r.domain}</p>
              </div>
            </a>
          ))}
        </div>
      )}
      <p className="text-[10px] text-muted-foreground">결과 클릭 시 새 탭에서 원문 확인 후 수동 입력.</p>
    </div>
  )
}

function StageAdvanceBar({ ids, fromStatus, toStatus, onDone, disabled }: {
  ids: number[]; fromStatus: string; toStatus: string; onDone: () => void; disabled?: boolean
}) {
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<string | null>(null)
  const handleAdvance = async () => {
    if (!ids.length) return
    setBusy(true); setResult(null)
    try {
      const r = await pipelineTestApi.advance(ids)
      setResult(`✓ ${r.advanced}건 ${fromStatus}→${toStatus}`)
      onDone()
    } catch (e) { setResult(`오류: ${e instanceof Error ? e.message : "advance 실패"}`) }
    finally { setBusy(false) }
  }
  return (
    <div className="mt-4 pt-4 border-t border-border space-y-1.5">
      <div className="flex items-center gap-2">
        <button onClick={handleAdvance} disabled={busy || disabled || !ids.length}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium disabled:opacity-50 transition-colors">
          {busy ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <span>→</span>}
          다음단계로 ({ids.length}건) · {fromStatus} → {toStatus}
        </button>
        {result && <span className={`text-xs ${result.startsWith("✓") ? "text-emerald-600" : "text-red-600"}`}>{result}</span>}
      </div>
      <p className="text-[10px] text-muted-foreground">내부처리 없이 status만 1칸 진행.</p>
    </div>
  )
}

function StageControlBar({
  stageContents,
  onDone,
  showPrev = true,
}: {
  stageContents: ContentOut[]
  onDone: () => void
  showPrev?: boolean
}) {
  const [cleanupConfirm, setCleanupConfirm] = useState(false)
  const [cleaning, setCleaning] = useState(false)
  const [reverting, setReverting] = useState(false)
  const [result, setResult] = useState<string | null>(null)

  const ids = stageContents.map((c) => c.id)

  const handleCleanup = async (dry_run: boolean) => {
    setCleaning(true)
    setResult(null)
    setCleanupConfirm(false)
    try {
      const r = await pipelineTestApi.cleanupStage(ids, dry_run)
      setResult(
        dry_run
          ? `[건식] 삭제 대상 ${r.deleted}건 — 실제 삭제되지 않음`
          : `클린업 완료: ${r.deleted}건 삭제됨`
      )
      if (!dry_run) onDone()
    } catch (e) {
      setResult(`오류: ${e instanceof Error ? e.message : "클린업 실패"}`)
    } finally {
      setCleaning(false)
    }
  }

  const handleRevert = async () => {
    if (!ids.length) return
    setReverting(true)
    setResult(null)
    try {
      const r = await pipelineTestApi.revert(ids)
      setResult(`↩ ${r.reverted}건 이전단계 복귀`)
      onDone()
    } catch (e) {
      setResult(`오류: ${e instanceof Error ? e.message : "이전단계 실패"}`)
    } finally {
      setReverting(false)
    }
  }

  return (
    <div className="mt-3 pt-3 border-t border-dashed border-border/60 flex items-center gap-2 flex-wrap">
      {showPrev && (
        <button
          onClick={() => void handleRevert()}
          disabled={reverting || !ids.length}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-600 text-slate-600 dark:text-slate-400 text-xs font-medium hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50 transition-colors"
        >
          {reverting ? <RefreshCw className="h-3 w-3 animate-spin" /> : <span>↩</span>}
          이전단계 ({ids.length}건)
        </button>
      )}

      {cleanupConfirm ? (
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] text-red-500 font-medium">이 단계 {ids.length}건 삭제. 계속?</span>
          <button
            onClick={() => void handleCleanup(false)}
            className="px-2.5 py-1 rounded-lg bg-red-500 hover:bg-red-600 text-white text-[11px] font-medium transition-colors"
          >
            삭제 확인
          </button>
          <button
            onClick={() => setCleanupConfirm(false)}
            className="px-2.5 py-1 rounded-lg border border-border text-[11px] hover:bg-accent transition-colors"
          >
            취소
          </button>
        </div>
      ) : (
        <button
          onClick={() => setCleanupConfirm(true)}
          disabled={cleaning || !ids.length}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-red-200 dark:border-red-800/40 text-red-600 dark:text-red-400 text-xs font-medium hover:bg-red-50 dark:hover:bg-red-900/10 disabled:opacity-50 transition-colors"
        >
          {cleaning ? <RefreshCw className="h-3 w-3 animate-spin" /> : <Trash2 className="h-3 w-3" />}
          클린업 ({ids.length}건)
        </button>
      )}

      {result && (
        <span className={`text-[11px] ${result.startsWith("오류") ? "text-red-500" : "text-muted-foreground"}`}>
          {result}
        </span>
      )}
    </div>
  )
}

const ENRICH_FIELD_LABELS: Record<string, string> = {
  synopsis: "줄거리", poster: "포스터", cast: "출연", director: "감독",
  primary_genre: "장르", genres: "장르", runtime: "러닝타임", country: "국가",
  external_id: "외부ID", production_year: "제작연도",
}


// STEP A에 항상 표시할 필드 고정 목록 (순서 = 중요도)
const ALL_ENRICH_FIELDS = [
  "genres", "cast", "director", "runtime", "country", "production_year", "synopsis",
]

// 선택 콘텐츠(ContentDetail)에서 필드별 현재값을 문자열로 추출 — 적용 후 재조회 시 갱신됨
function currentFieldValue(c: ContentDetail | null, field: string): string | null {
  if (!c) return null
  const join = (xs: (string | null | undefined)[]) => {
    const v = xs.filter(Boolean).join(", ")
    return v || null
  }
  switch (field) {
    case "synopsis":
      return c.metadata_record?.final_synopsis || c.metadata_record?.ai_synopsis || c.metadata_record?.cp_synopsis || null
    case "synopsis_ko":
      return c.metadata_record?.synopsis_ko || null
    case "synopsis_en":
      return c.metadata_record?.synopsis_en || null
    case "runtime":
      return c.runtime_minutes ? `${c.runtime_minutes}분` : null
    case "country":
      return c.country || null
    case "production_year":
      return c.production_year ? String(c.production_year) : null
    case "poster":
      return c.poster_url || null
    case "cast":
      return join(c.credits.filter((cr) => /actor|cast|주연|출연|조연|단역/i.test(cr.role)).map((cr) => cr.person.name_ko))
    case "director":
      return join(c.credits.filter((cr) => /director|감독|연출/i.test(cr.role)).map((cr) => cr.person.name_ko))
    case "genres":
    case "primary_genre":
      return join(c.genres.map((g) => g.genre.name_ko))
    default:
      return null
  }
}

function EnrichFieldRow({ field, rec, contentId, currentValue, applied, onApplied }: {
  field: string; rec: FieldRecommendation | null; contentId: number; currentValue: string | null; applied: boolean; onApplied: (field: string) => void
}) {
  const label = ENRICH_FIELD_LABELS[field] ?? field
  const recs = rec?.recommendations ?? []
  const best = recs[0] ?? null
  const alreadyCurrent = !!(best && currentValue && best.value.trim() === currentValue.trim())
  const [busy, setBusy] = useState(false)

  const handleApply = async () => {
    if (!best) return
    setBusy(true)
    try { await metadataApi.applyExternalFields(contentId, best.source_id, [field]); onApplied(field) }
    catch (e) { console.error("apply field failed", e) }
    finally { setBusy(false) }
  }

  // 소스별로 그룹화: 같은 값이면 배지만 추가, 다른 값이면 별도 줄
  const grouped: { value: string; sources: string[] }[] = []
  for (const r of recs) {
    const existing = grouped.find((g) => g.value.trim().toLowerCase() === r.value.trim().toLowerCase())
    if (existing) existing.sources.push(r.source_type.toUpperCase())
    else grouped.push({ value: r.value, sources: [r.source_type.toUpperCase()] })
  }

  const sourceColor = (src: string) =>
    src === "TMDB" ? "bg-blue-100 text-blue-600 dark:bg-blue-900/40 dark:text-blue-300"
    : src === "KMDB" ? "bg-orange-100 text-orange-600 dark:bg-orange-900/40 dark:text-orange-300"
    : "bg-muted text-muted-foreground"

  return (
    <div className="grid grid-cols-[4.5rem_1fr_1fr_4rem] items-stretch border-b border-border last:border-0 text-[10px]">
      <div className="flex items-center px-2 py-1.5 font-medium text-muted-foreground">{label}</div>
      <div className={`px-2 py-1.5 border-l border-border ${currentValue ? "text-foreground" : "text-muted-foreground/50"}`}>
        {currentValue ? <span>{currentValue}</span> : "(없음)"}
      </div>
      <div className="px-2 py-1.5 border-l border-border space-y-0.5">
        {grouped.length > 0 ? grouped.map((g, i) => (
          <div key={i} className="flex items-baseline gap-1 flex-wrap">
            <span className="text-foreground">{g.value}</span>
            {g.sources.map((s) => (
              <span key={s} className={`text-[9px] font-medium px-1 py-0.5 rounded ${sourceColor(s)}`}>{s}</span>
            ))}
          </div>
        )) : (
          <span className="text-muted-foreground/40">—</span>
        )}
      </div>
      <div className="flex items-center justify-center border-l border-border px-1">
        {applied || alreadyCurrent ? (
          <span className="text-[9px] font-medium text-emerald-600">✓</span>
        ) : best ? (
          <button onClick={() => void handleApply()} disabled={busy}
            className="text-[10px] px-1.5 py-0.5 rounded bg-blue-600 hover:bg-blue-700 text-white font-medium disabled:opacity-50">
            {busy ? <RefreshCw className="h-3 w-3 animate-spin" /> : "적용"}
          </button>
        ) : null}
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

function CreationTabsPanel({ summary, onRefresh, selectedContentId: _sel, stageContents }: {
  summary: PipelineTestStageSummary | null; onRefresh: () => void; selectedContentId: number | null; stageContents: ContentOut[]
}) {
  const [activeTab, setActiveTab] = useState<"seed" | "single" | "bulk">("seed")
  const rawIds = stageContents.map((c) => c.id)
  return (
    <div className="space-y-4">
      <div className="flex gap-4 border-b border-amber-200 dark:border-amber-800/40">
        {CREATION_TABS.map((tab) => (
          <button key={tab.key} type="button" onClick={() => setActiveTab(tab.key)}
            className={`pb-2 px-1 text-sm font-medium transition-colors border-b-2 ${activeTab === tab.key ? "border-amber-500 text-amber-600 dark:text-amber-400" : "border-transparent text-muted-foreground hover:text-foreground"}`}>
            {tab.label}
          </button>
        ))}
      </div>
      {activeTab === "seed" && <SampleSeedPanel summary={summary} onRefresh={onRefresh} />}
      {activeTab === "single" && <AddContentInlinePanel onRefresh={onRefresh} />}
      {activeTab === "bulk" && <BulkUploadEmbed onRefresh={onRefresh} />}
    </div>
  )
}

// ── EnrichBoostPanel — S3 전체 필드 보강 ─────────────────────

// 필드별 의미상 동일 여부 — 현재값과 RAG 추천값이 실질적으로 같으면 적용 불필요
function isBoostValueSimilar(field: string, current: string, suggest: string): boolean {
  if (current.trim().toLowerCase() === suggest.trim().toLowerCase()) return true
  if (field === "runtime") {
    const cn = parseInt(current)
    const sn = parseInt(suggest)
    return !isNaN(cn) && !isNaN(sn) && cn === sn
  }
  if (field === "country") {
    const norm = (v: string) => {
      const s = v.trim().toLowerCase()
      if (["kr", "korea", "대한민국", "south korea", "한국"].includes(s)) return "kr"
      if (["us", "usa", "united states", "미국", "america"].includes(s)) return "us"
      if (["jp", "japan", "일본"].includes(s)) return "jp"
      if (["cn", "china", "중국"].includes(s)) return "cn"
      if (["gb", "uk", "united kingdom", "영국"].includes(s)) return "gb"
      if (["fr", "france", "프랑스"].includes(s)) return "fr"
      if (["de", "germany", "독일"].includes(s)) return "de"
      return s
    }
    return norm(current) === norm(suggest)
  }
  if (field === "cast" || field === "genres") {
    const toSet = (v: string) => new Set(v.split(",").map((s) => s.trim().toLowerCase()).filter(Boolean))
    const cSet = toSet(current)
    const sSet = toSet(suggest)
    if (cSet.size === 0) return false
    const intersection = [...cSet].filter((x) => sSet.has(x)).length
    // 현재값의 80% 이상이 RAG 추천에 포함되면 유사한 것으로 판단
    return intersection / cSet.size >= 0.8
  }
  return false
}

// 표준 필드 디스크립터: 항상 표시, 현재값·보완값 채움
const BOOST_STANDARD_FIELDS: Array<{
  field: string        // canonical key (= currentFieldValue 키)
  label: string
  ragKey?: string      // wikidata_facts 키 (있으면 RAG 보완 대상)
  ragContentField?: string  // updateContent 파라미터명
  ragValueToArg?: (v: unknown) => string | number
}> = [
  {
    field: "genres",
    label: "장르",
    ragKey: "genres",
    ragContentField: "genres",
    ragValueToArg: (v) => Array.isArray(v) ? (v as string[]).join(", ") : String(v),
  },
  {
    field: "cast",
    label: "출연진",
    ragKey: "cast",
    ragContentField: "cast",
    ragValueToArg: (v) => Array.isArray(v) ? (v as string[]).slice(0, 10).join(", ") : String(v),
  },
  {
    field: "director",
    label: "감독",
    ragKey: "directors",
    ragContentField: "directors",
    ragValueToArg: (v) => Array.isArray(v) ? (v as string[]).join(", ") : String(v),
  },
  {
    field: "runtime",
    label: "러닝타임",
    ragKey: "runtime",
    ragContentField: "runtime",
    ragValueToArg: (v) => typeof v === "number" ? v : parseInt(String(v), 10),
  },
  {
    field: "country",
    label: "국가",
    ragKey: "country",
    ragContentField: "country",
    ragValueToArg: (v) => String(v),
  },
  {
    field: "production_year",
    label: "제작연도",
    ragKey: "production_year",
    ragContentField: "production_year",
    ragValueToArg: (v) => typeof v === "number" ? v : parseInt(String(v), 10),
  },
  {
    field: "synopsis",
    label: "줄거리",
  },
  {
    field: "synopsis_ko",
    label: "줄거리(한)",
  },
  {
    field: "synopsis_en",
    label: "줄거리(영)",
  },
]


type BoostRow = {
  field: string
  label: string
  isExtra: boolean
  currentValue: string | null
  suggestValue: string | null
  suggestSource: "RAG" | "AI" | null
  ragUpdate?: { contentField: string; arg: string | number }
  aiSaved: boolean
  applied: boolean
  applying: boolean
}

function buildBaseRows(detail: ContentDetail): BoostRow[] {
  return BOOST_STANDARD_FIELDS.map((f) => ({
    field: f.field,
    label: f.label,
    isExtra: false,
    currentValue: currentFieldValue(detail, f.field),
    suggestValue: null,
    suggestSource: null,
    aiSaved: false,
    applied: false,
    applying: false,
  }))
}

function EnrichBoostPanel({ selectedContentId, onRefresh }: { selectedContentId: number | null; onRefresh: () => void }) {
  const [rows, setRows] = useState<BoostRow[]>([])
  const [detail, setDetail] = useState<ContentDetail | null>(null)
  const [ragBusy, setRagBusy] = useState(false)
  const [ragDone, setRagDone] = useState(false)
  const [translateBusy, setTranslateBusy] = useState(false)
  const [translateDone, setTranslateDone] = useState(false)
  const [shortSynopsisBusy, setShortSynopsisBusy] = useState(false)
  const [shortSynopsisDone, setShortSynopsisDone] = useState(false)
  const [wikipediaText, setWikipediaText] = useState<string | null>(null)
  const [wikipediaUrl, setWikipediaUrl] = useState<string | null>(null)
  const [expandWikipedia, setExpandWikipedia] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadDetail = useCallback(async () => {
    if (!selectedContentId) { setDetail(null); setRows([]); return }
    try {
      const d = await metadataApi.getContent(selectedContentId)
      setDetail(d)
      setRows(buildBaseRows(d))
    } catch { setDetail(null) }
  }, [selectedContentId])

  useEffect(() => {
    setRagDone(false); setTranslateDone(false); setShortSynopsisDone(false)
    setWikipediaText(null); setWikipediaUrl(null)
    setError(null)
    void loadDetail()
  }, [loadDetail])

  const runRag = async () => {
    if (!selectedContentId) return
    setRagBusy(true); setError(null)
    try {
      const rag = await pipelineTestApi.referenceExtract(selectedContentId)
      setWikipediaText(rag.wikipedia_text ?? null)
      setWikipediaUrl(rag.wikipedia_url ?? null)
      setRagDone(true)

      const freshDetail = await metadataApi.getContent(selectedContentId)
      setDetail(freshDetail)

      setRows((prev) => {
        const next = prev.map((row) => {
          const fDef = BOOST_STANDARD_FIELDS.find((f) => f.field === row.field)
          if (!fDef?.ragKey) return row
          const val = rag.wikidata_facts[fDef.ragKey]
          if (val === undefined || val === null) return row
          const displayVal = Array.isArray(val) ? (val as string[]).join(", ") : String(val)
          const currentVal = currentFieldValue(freshDetail, row.field)
          const isSame = !!(currentVal && isBoostValueSimilar(row.field, currentVal, displayVal))
          return {
            ...row,
            currentValue: currentVal,
            suggestValue: displayVal,
            suggestSource: "RAG" as const,
            ragUpdate: fDef.ragContentField && fDef.ragValueToArg
              ? { contentField: fDef.ragContentField, arg: fDef.ragValueToArg(val) }
              : undefined,
            applied: isSame,
          }
        })
        return next
      })
    } catch (e) {
      setError(e instanceof Error ? e.message : "RAG 오류")
    } finally {
      setRagBusy(false)
    }
  }

  const runAiTranslate = async () => {
    if (!selectedContentId) return
    setTranslateBusy(true); setError(null)
    try {
      await pipelineTestApi.runAiTask(selectedContentId, "translate_synopsis")
      const freshDetail = await metadataApi.getContent(selectedContentId)
      setDetail(freshDetail)
      setTranslateDone(true)
      const koVal = freshDetail.metadata_record?.synopsis_ko || null
      const enVal = freshDetail.metadata_record?.synopsis_en || null
      setRows((prev) => prev.map((row) => {
        if (row.field === "synopsis_ko" && koVal) return { ...row, currentValue: koVal, suggestValue: koVal, suggestSource: "AI" as const, aiSaved: true }
        if (row.field === "synopsis_en" && enVal) return { ...row, currentValue: enVal, suggestValue: enVal, suggestSource: "AI" as const, aiSaved: true }
        return row
      }))
    } catch (e) {
      setError(e instanceof Error ? e.message : "번역 오류")
    } finally {
      setTranslateBusy(false)
    }
  }

  const runAiSynopsis = async () => {
    if (!selectedContentId) return
    setShortSynopsisBusy(true); setError(null)
    try {
      const r = await pipelineTestApi.runAiTask(selectedContentId, "short_synopsis")
      const freshDetail = await metadataApi.getContent(selectedContentId)
      setDetail(freshDetail)
      setShortSynopsisDone(true)
      const val = r.result_preview ?? freshDetail.metadata_record?.short_synopsis ?? null
      if (val) {
        setRows((prev) => prev.map((row) =>
          row.field === "synopsis"
            ? {
                ...row,
                currentValue: currentFieldValue(freshDetail, "synopsis"),
                suggestValue: val,
                suggestSource: "AI" as const,
                aiSaved: false,
                ragUpdate: { contentField: "synopsis", arg: val },
              }
            : row
        ))
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "축약 오류")
    } finally {
      setShortSynopsisBusy(false)
    }
  }

  const applyRagRow = async (row: BoostRow) => {
    if (!selectedContentId || !row.ragUpdate) return
    setRows((prev) => prev.map((r) => r.field === row.field ? { ...r, applying: true } : r))
    try {
      await metadataApi.updateContent(selectedContentId, {
        [row.ragUpdate.contentField]: row.ragUpdate.arg,
      } as Parameters<typeof metadataApi.updateContent>[1])
      const freshDetail = await metadataApi.getContent(selectedContentId)
      setDetail(freshDetail)
      setRows((prev) => prev.map((r) =>
        r.field === row.field
          ? { ...r, currentValue: currentFieldValue(freshDetail, r.field), applied: true, applying: false }
          : r
      ))
    } catch (e) {
      setError(e instanceof Error ? e.message : "적용 오류")
      setRows((prev) => prev.map((r) => r.field === row.field ? { ...r, applying: false } : r))
    }
  }

  const applyAll = async () => {
    const unapplied = rows.filter((r) => r.suggestSource === "RAG" && !r.applied && r.ragUpdate)
    for (const row of unapplied) {
      await applyRagRow(row)
    }
  }

  if (!selectedContentId) return null

  const standardRows = rows.filter((r) => !r.isExtra)
  const extraRows = rows.filter((r) => r.isExtra)
  const hasUnappliedRag = rows.some((r) => r.suggestSource === "RAG" && !r.applied && r.ragUpdate)

  return (
    <div className="rounded-lg border border-violet-200 dark:border-violet-800/40 bg-violet-50/40 dark:bg-violet-900/10 p-3 space-y-2">
      <p className="text-[11px] font-semibold text-violet-700 dark:text-violet-400 uppercase tracking-wide">STEP 1 — RAG 보완 (status 불변)</p>

      {/* 버튼 영역 */}
      <div className="flex items-center gap-2 flex-wrap">
        <button onClick={() => void runRag()} disabled={ragBusy}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-700 text-white text-xs font-medium disabled:opacity-50 transition-colors">
          {ragBusy ? <RefreshCw className="h-3 w-3 animate-spin" /> : <Search className="h-3 w-3" />}
          RAG 보완
        </button>
        <button onClick={() => void runAiTranslate()} disabled={translateBusy}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium disabled:opacity-50 transition-colors">
          {translateBusy ? <RefreshCw className="h-3 w-3 animate-spin" /> : <Zap className="h-3 w-3" />}
          AI 번역
        </button>
        <button onClick={() => void runAiSynopsis()} disabled={shortSynopsisBusy}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-700 text-white text-xs font-medium disabled:opacity-50 transition-colors">
          {shortSynopsisBusy ? <RefreshCw className="h-3 w-3 animate-spin" /> : <Zap className="h-3 w-3" />}
          AI 축약
        </button>
        <span className="flex gap-1.5 text-[10px]">
          {ragDone && <span className="px-1.5 py-0.5 rounded-full bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300 font-medium">RAG ✓</span>}
          {translateDone && <span className="px-1.5 py-0.5 rounded-full bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300 font-medium">번역 ✓</span>}
          {shortSynopsisDone && <span className="px-1.5 py-0.5 rounded-full bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300 font-medium">축약 ✓</span>}
        </span>
        {error && <span className="text-[10px] text-red-500">{error}</span>}
      </div>

      {/* 전체 필드 테이블 */}
      <div className="rounded border border-border bg-background overflow-hidden">
        <div className="grid grid-cols-[4.5rem_1fr_1fr_4rem] text-[10px] font-semibold text-muted-foreground bg-muted/40 border-b border-border">
          <div className="px-2 py-1">필드</div>
          <div className="px-2 py-1 border-l border-border">현재값</div>
          <div className="px-2 py-1 border-l border-border">보완값(추천)</div>
          <div className="px-2 py-1 border-l border-border text-center">적용</div>
        </div>
        <div>
          {standardRows.map((row) => (
            <div key={row.field} className="grid grid-cols-[4.5rem_1fr_1fr_4rem] items-stretch border-t border-border text-[10px]">
              <div className="flex items-center px-2 py-1.5 font-medium text-muted-foreground">{row.label}</div>
              <div className={`px-2 py-1.5 border-l border-border ${row.currentValue ? "text-foreground" : "text-muted-foreground/50"}`}>
                {row.currentValue ? <span>{row.currentValue}</span> : "(없음)"}
              </div>
              <div className="px-2 py-1.5 border-l border-border">
                {row.suggestValue ? (
                  <span className="text-foreground">
                    {row.suggestValue}
                    {row.suggestSource && (
                      <span className={`ml-1 text-[9px] font-medium px-1 py-0.5 rounded ${row.suggestSource === "RAG" ? "bg-violet-100 text-violet-600 dark:bg-violet-900/40 dark:text-violet-300" : "bg-purple-100 text-purple-600 dark:bg-purple-900/40 dark:text-purple-300"}`}>
                        {row.suggestSource}
                      </span>
                    )}
                  </span>
                ) : (
                  <span className="text-muted-foreground/40">—</span>
                )}
              </div>
              <div className="flex items-center justify-center border-l border-border px-1">
                {row.aiSaved ? (
                  <span className="text-[9px] font-medium text-emerald-600">✓저장됨</span>
                ) : row.applied ? (
                  <span className="text-[9px] font-medium text-emerald-600">✓</span>
                ) : row.ragUpdate ? (
                  <button onClick={() => void applyRagRow(row)} disabled={row.applying}
                    className="text-[10px] px-1.5 py-0.5 rounded bg-violet-600 hover:bg-violet-700 text-white font-medium disabled:opacity-50 transition-colors">
                    {row.applying ? "…" : "적용"}
                  </button>
                ) : null}
              </div>
            </div>
          ))}
        </div>

        {/* 추가 필드 구분선 */}
        {extraRows.length > 0 && (
          <>
            <div className="px-2 py-1 bg-muted/20 border-t border-border text-[10px] text-muted-foreground font-medium">추가 필드</div>
            {extraRows.map((row) => (
              <div key={row.field} className="grid grid-cols-[4.5rem_1fr_1fr_4rem] items-stretch border-t border-border text-[10px]">
                <div className="flex items-center px-2 py-1.5 font-medium text-muted-foreground">{row.label}</div>
                <div className="px-2 py-1.5 border-l border-border text-muted-foreground/50">(없음)</div>
                <div className="px-2 py-1.5 border-l border-border">
                  {row.suggestValue && (
                    <span className="text-foreground line-clamp-2">
                      {row.suggestValue}
                      <span className="ml-1 text-[9px] font-medium px-1 py-0.5 rounded bg-purple-100 text-purple-600 dark:bg-purple-900/40 dark:text-purple-300">AI</span>
                    </span>
                  )}
                </div>
                <div className="flex items-center justify-center border-l border-border px-1">
                  {row.aiSaved && <span className="text-[9px] font-medium text-emerald-600">✓저장됨</span>}
                </div>
              </div>
            ))}
          </>
        )}
      </div>

      {/* 전체 적용 + Wikipedia */}
      <div className="flex items-center gap-3 flex-wrap">
        {hasUnappliedRag && (
          <button onClick={() => void applyAll()}
            className="text-[10px] px-2 py-1 rounded bg-violet-600 hover:bg-violet-700 text-white font-medium transition-colors">
            전체 적용
          </button>
        )}
        {wikipediaText && (
          <button onClick={() => setExpandWikipedia(!expandWikipedia)} className="flex items-center gap-1 text-[10px] text-violet-600 dark:text-violet-400 hover:underline font-medium">
            <span>{expandWikipedia ? "▼" : "▶"}</span> Wikipedia
          </button>
        )}
      </div>

      {expandWikipedia && wikipediaText && (
        <div className="rounded border border-border bg-background p-2 text-[11px] space-y-1">
          <p className="text-foreground leading-relaxed">{wikipediaText}</p>
          {wikipediaUrl && (
            <a href={wikipediaUrl} target="_blank" rel="noreferrer" className="text-[10px] text-violet-500 hover:underline">{wikipediaUrl}</a>
          )}
        </div>
      )}
    </div>
  )
}

// 단계 공용 액션바 — (선택) 주 액션 + 이전단계로 / 다음단계로 / 클린업 (좌=전체, 중=단건 공용)
function StageActionBar({ ids, primary, onDone }: {
  ids: number[]
  primary?: { label: string; icon: ReactNode; className: string; run: (ids: number[]) => Promise<string> }
  onDone: () => void
}) {
  const [primaryBusy, setPrimaryBusy] = useState(false)
  const [revBusy, setRevBusy] = useState(false)
  const [advBusy, setAdvBusy] = useState(false)
  const [cleanBusy, setCleanBusy] = useState(false)
  const [cleanConfirm, setCleanConfirm] = useState(false)
  const [result, setResult] = useState<string | null>(null)
  const n = ids.length

  const handlePrimary = async () => {
    if (!n || !primary) return
    setPrimaryBusy(true); setResult(null)
    try { setResult(await primary.run(ids)) }
    catch (e) { setResult(`오류: ${e instanceof Error ? e.message : "실패"}`) }
    finally { setPrimaryBusy(false) }
  }
  const handleRevert = async () => {
    if (!n) return
    setRevBusy(true); setResult(null)
    try { const r = await pipelineTestApi.revert(ids); setResult(`↩ ${r.reverted}건 이전단계`); onDone() }
    catch (e) { setResult(`오류: ${e instanceof Error ? e.message : "실패"}`) }
    finally { setRevBusy(false) }
  }
  const handleAdvance = async () => {
    if (!n) return
    setAdvBusy(true); setResult(null)
    try { const r = await pipelineTestApi.advance(ids); setResult(`✓ ${r.advanced}건 다음단계`); onDone() }
    catch (e) { setResult(`오류: ${e instanceof Error ? e.message : "실패"}`) }
    finally { setAdvBusy(false) }
  }
  const handleCleanup = async () => {
    if (!n) return
    setCleanBusy(true); setResult(null); setCleanConfirm(false)
    try { const r = await pipelineTestApi.cleanupStage(ids); setResult(`삭제 ${r.deleted}건`); onDone() }
    catch (e) { setResult(`오류: ${e instanceof Error ? e.message : "실패"}`) }
    finally { setCleanBusy(false) }
  }

  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-1.5 flex-wrap">
        {primary && (
          <button onClick={() => void handlePrimary()} disabled={primaryBusy || !n}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-white text-xs font-medium disabled:opacity-50 transition-colors ${primary.className}`}>
            {primaryBusy ? <RefreshCw className="h-3 w-3 animate-spin" /> : primary.icon}
            {primary.label} ({n}건)
          </button>
        )}
        <button onClick={() => void handleRevert()} disabled={revBusy || !n}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-600 text-slate-600 dark:text-slate-400 text-xs font-medium hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50 transition-colors">
          {revBusy ? <RefreshCw className="h-3 w-3 animate-spin" /> : <span>↩</span>}
          이전단계로 ({n}건)
        </button>
        <button onClick={() => void handleAdvance()} disabled={advBusy || !n}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-medium disabled:opacity-50 transition-colors">
          {advBusy ? <RefreshCw className="h-3 w-3 animate-spin" /> : <span>→</span>}
          다음단계로 ({n}건)
        </button>
        {cleanConfirm ? (
          <>
            <span className="text-[11px] text-red-500 font-medium">{n}건 삭제?</span>
            <button onClick={() => void handleCleanup()} className="px-2.5 py-1.5 rounded-lg bg-red-500 hover:bg-red-600 text-white text-[11px] font-medium transition-colors">확인</button>
            <button onClick={() => setCleanConfirm(false)} className="px-2.5 py-1.5 rounded-lg border border-border text-[11px] hover:bg-accent transition-colors">취소</button>
          </>
        ) : (
          <button onClick={() => setCleanConfirm(true)} disabled={cleanBusy || !n}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-red-200 dark:border-red-800/40 text-red-600 dark:text-red-400 text-xs font-medium hover:bg-red-50 dark:hover:bg-red-900/10 disabled:opacity-50 transition-colors">
            {cleanBusy ? <RefreshCw className="h-3 w-3 animate-spin" /> : <Trash2 className="h-3 w-3" />}
            클린업 ({n}건)
          </button>
        )}
      </div>
      {result && <p className={`text-[11px] ${result.startsWith("오류") ? "text-red-500" : "text-muted-foreground"}`}>{result}</p>}
    </div>
  )
}

// S2(Enrich) 3단 콘솔 — 좌(목록+전체버튼) / 중(상세+필드테이블+단건버튼) / 우(추천 요약)
function S2Console({ testContents, testContentsLoading, selectedContentId, onSelect, refreshTestSummary }: {
  testContents: ContentOut[]; testContentsLoading: boolean; selectedContentId: number | null
  onSelect: (id: number) => void; refreshTestSummary: () => void
}) {
  const [detail, setDetail] = useState<ContentDetail | null>(null)
  const [recs, setRecs] = useState<RecommendationsOut | null>(null)
  const [appliedFields, setAppliedFields] = useState<Set<string>>(new Set())

  const refetch = useCallback(async () => {
    if (selectedContentId === null) { setDetail(null); setRecs(null); return }
    try {
      const [c, r] = await Promise.all([
        metadataApi.getContent(selectedContentId),
        metadataApi.getRecommendations(selectedContentId).catch(() => null),
      ])
      setDetail(c); setRecs(r)
    } catch { setDetail(null); setRecs(null) }
  }, [selectedContentId])

  useEffect(() => { setAppliedFields(new Set()); void refetch() }, [refetch])

  const recByField = (f: string): FieldRecommendation | null =>
    recs ? [...recs.auto_fill, ...recs.conflicts].find((x) => x.field === f) ?? null : null

  const allRecs = recs ? [...recs.auto_fill, ...recs.conflicts] : []

  const enrichPrimary = {
    label: "Enrich", icon: <Zap className="h-3 w-3" />, className: "bg-blue-600 hover:bg-blue-700",
    run: async (ids: number[]) => {
      let ok = 0
      for (const id of ids) { try { await metadataApi.triggerEnrich(id); ok++ } catch { /* skip */ } }
      void refetch(); refreshTestSummary()
      return `Enrich ${ok}/${ids.length}건 완료`
    },
  }

  return (
    <>
      {/* 좌 — Enrich (외부 메타보강) */}
      <div className="col-span-1">
        <div className="rounded-lg border border-amber-200 dark:border-amber-700/50 bg-background overflow-hidden">
          <div className="px-4 py-2.5 border-b border-amber-200 dark:border-amber-700/50 bg-amber-50/50 dark:bg-amber-900/10">
            <span className="text-xs font-semibold text-amber-800 dark:text-amber-300">Enrich (외부 메타보강)</span>
            {testContents.length > 0 && <span className="ml-2 text-xs text-amber-600 dark:text-amber-400">{testContents.length}건</span>}
          </div>
          <div className="p-3 space-y-3">
            <TestContentList contents={testContents} loading={testContentsLoading} selectedId={selectedContentId} onSelect={onSelect} />
            {testContents.length > 0 && (
              <StageActionBar ids={testContents.map((c) => c.id)} primary={enrichPrimary} onDone={refreshTestSummary} />
            )}
          </div>
        </div>
      </div>

      {/* 중 — 콘텐츠 상세 + 필드 테이블 */}
      <div className="col-span-1">
        <div className="rounded-lg border border-amber-200 dark:border-amber-700/50 bg-background overflow-hidden">
          <div className="px-4 py-2.5 border-b border-amber-200 dark:border-amber-700/50 bg-amber-50/50 dark:bg-amber-900/10">
            <span className="text-xs font-semibold text-amber-800 dark:text-amber-300">콘텐츠 상세</span>
            {selectedContentId && <span className="ml-2 text-xs text-amber-600 dark:text-amber-400">#{selectedContentId}</span>}
          </div>
          <div className="p-3 space-y-3">
            <SelectedContentMeta contentId={selectedContentId} />
            {selectedContentId !== null && (
              <>
                <div className="rounded border border-border bg-background overflow-hidden">
                  <div className="grid grid-cols-[4.5rem_1fr_1fr_4rem] text-[10px] font-semibold text-muted-foreground bg-muted/40 border-b border-border">
                    <div className="px-2 py-1">필드</div>
                    <div className="px-2 py-1 border-l border-border">현재값</div>
                    <div className="px-2 py-1 border-l border-border">Enrich</div>
                    <div className="px-2 py-1 border-l border-border text-center">적용</div>
                  </div>
                  <div>
                    {ALL_ENRICH_FIELDS.map((f) => (
                      <EnrichFieldRow key={f} field={f} rec={recByField(f)} contentId={selectedContentId}
                        currentValue={currentFieldValue(detail, f)}
                        applied={appliedFields.has(f)}
                        onApplied={(field) => { setAppliedFields((s) => new Set(s).add(field)); void refetch() }} />
                    ))}
                  </div>
                </div>
                <StageActionBar ids={[selectedContentId]} primary={enrichPrimary} onDone={refreshTestSummary} />
              </>
            )}
          </div>
        </div>
      </div>

      {/* 우 — 추천 요약 */}
      <div className="col-span-1">
        <div className="rounded-lg border border-amber-200 dark:border-amber-700/50 bg-background overflow-hidden">
          <div className="px-4 py-2.5 border-b border-amber-200 dark:border-amber-700/50 bg-amber-50/50 dark:bg-amber-900/10">
            <span className="text-xs font-semibold text-amber-800 dark:text-amber-300">추천 요약</span>
          </div>
          <div className="p-3 space-y-3">
            {selectedContentId === null ? (
              <p className="text-xs text-muted-foreground text-center py-4">콘텐츠를 선택하면 추천 요약이 표시됩니다</p>
            ) : (
              <>
                <div>
                  <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">보완 필요 필드</p>
                  {recs && recs.missing_fields.length === 0
                    ? <p className="text-xs text-emerald-600">✓ 보완 필요 필드 없음</p>
                    : <div className="flex flex-wrap gap-1.5">{recs?.missing_fields.map((f) => { const done = !!recByField(f); return <span key={f} className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${done ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400" : "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"}`}>{ENRICH_FIELD_LABELS[f] ?? f} {done ? "✓" : ""}</span> })}</div>
                  }
                </div>
                <div>
                  <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">추천 ({allRecs.length})</p>
                  {allRecs.length === 0 ? (
                    <p className="text-xs text-muted-foreground">추천 없음 — Enrich 실행 후 갱신됩니다</p>
                  ) : (
                    <div className="space-y-2">
                      {allRecs.map((r) => {
                        const best = r.ai_synthesis ?? r.recommendations[0] ?? null
                        return (
                          <div key={r.field} className="rounded border border-border bg-muted/20 px-2.5 py-1.5">
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-xs font-medium">{ENRICH_FIELD_LABELS[r.field] ?? r.field}</span>
                              <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${r.status === "conflict" ? "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400" : "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400"}`}>{r.status === "conflict" ? "충돌" : "자동"}</span>
                            </div>
                            {best && (
                              <div className="mt-1 text-[11px] text-muted-foreground">
                                <span className="text-foreground">{best.value}</span>
                                <span className="ml-1.5 text-[10px] uppercase">{best.source_type}{r.ai_synthesis ? " · AI" : ""}</span>
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </>
  )
}

// S3(AI처리) 3단 콘솔 — 좌(목록+전체버튼) / 중(상세+RAG/번역/축약 테이블+단건버튼) / 우(AI 결과 요약)
function S3Console({ testContents, testContentsLoading, selectedContentId, onSelect, refreshTestSummary }: {
  testContents: ContentOut[]; testContentsLoading: boolean; selectedContentId: number | null
  onSelect: (id: number) => void; refreshTestSummary: () => void
}) {
  const [aiResults, setAiResults] = useState<ContentAIResult[]>([])

  const refetch = useCallback(async () => {
    if (selectedContentId === null) { setAiResults([]); return }
    try { setAiResults(await metadataApi.getAiResults(selectedContentId)) }
    catch { setAiResults([]) }
  }, [selectedContentId])

  useEffect(() => { void refetch() }, [refetch])

  const aiPrimary = {
    label: "AI처리", icon: <Zap className="h-3 w-3" />, className: "bg-purple-600 hover:bg-purple-700",
    run: async (ids: number[]) => {
      const r = await metadataApi.bulkProcessAi({ ids })
      void refetch(); refreshTestSummary()
      return `AI처리 ${r.ids_accepted}건 접수${r.ids_rejected ? ` (거부 ${r.ids_rejected})` : ""}`
    },
  }

  return (
    <>
      {/* 좌 — AI처리 (LLM 태스크) */}
      <div className="col-span-1">
        <div className="rounded-lg border border-amber-200 dark:border-amber-700/50 bg-background overflow-hidden">
          <div className="px-4 py-2.5 border-b border-amber-200 dark:border-amber-700/50 bg-amber-50/50 dark:bg-amber-900/10">
            <span className="text-xs font-semibold text-amber-800 dark:text-amber-300">AI처리 (LLM 태스크)</span>
            {testContents.length > 0 && <span className="ml-2 text-xs text-amber-600 dark:text-amber-400">{testContents.length}건</span>}
          </div>
          <div className="p-3 space-y-3">
            <TestContentList contents={testContents} loading={testContentsLoading} selectedId={selectedContentId} onSelect={onSelect} />
            {testContents.length > 0 && (
              <StageActionBar ids={testContents.map((c) => c.id)} primary={aiPrimary} onDone={refreshTestSummary} />
            )}
          </div>
        </div>
      </div>

      {/* 중 — 콘텐츠 상세 + RAG/번역/축약 테이블 */}
      <div className="col-span-1">
        <div className="rounded-lg border border-amber-200 dark:border-amber-700/50 bg-background overflow-hidden">
          <div className="px-4 py-2.5 border-b border-amber-200 dark:border-amber-700/50 bg-amber-50/50 dark:bg-amber-900/10">
            <span className="text-xs font-semibold text-amber-800 dark:text-amber-300">콘텐츠 상세</span>
            {selectedContentId && <span className="ml-2 text-xs text-amber-600 dark:text-amber-400">#{selectedContentId}</span>}
          </div>
          <div className="p-3 space-y-3">
            <SelectedContentMeta contentId={selectedContentId} />
            {selectedContentId !== null && (
              <>
                <EnrichBoostPanel selectedContentId={selectedContentId} onRefresh={() => { void refetch(); refreshTestSummary() }} />
                <StageActionBar ids={[selectedContentId]} primary={aiPrimary} onDone={refreshTestSummary} />
              </>
            )}
          </div>
        </div>
      </div>

      {/* 우 — AI 결과 요약 */}
      <div className="col-span-1">
        <div className="rounded-lg border border-amber-200 dark:border-amber-700/50 bg-background overflow-hidden">
          <div className="px-4 py-2.5 border-b border-amber-200 dark:border-amber-700/50 bg-amber-50/50 dark:bg-amber-900/10">
            <span className="text-xs font-semibold text-amber-800 dark:text-amber-300">AI 결과 요약</span>
            {aiResults.length > 0 && <span className="ml-2 text-xs text-amber-600 dark:text-amber-400">{aiResults.length}건</span>}
          </div>
          <div className="p-3 space-y-2">
            {selectedContentId === null ? (
              <p className="text-xs text-muted-foreground text-center py-4">콘텐츠를 선택하면 AI 결과가 표시됩니다</p>
            ) : aiResults.length === 0 ? (
              <p className="text-xs text-muted-foreground">AI 결과 없음 — AI처리 실행 후 갱신됩니다</p>
            ) : (
              aiResults.map((r) => (
                <div key={r.id} className="rounded border border-border bg-muted/20 px-2.5 py-1.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-medium">{r.task_type}</span>
                    <div className="flex items-center gap-1.5 shrink-0">
                      {r.is_final && <span className="text-[10px] px-1.5 py-0.5 rounded-full font-medium bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">final</span>}
                      {r.quality_score !== null && <span className="text-[10px] text-muted-foreground">{r.quality_score}점</span>}
                    </div>
                  </div>
                  <div className="mt-0.5 flex items-center gap-1.5">
                    <span className="text-[10px] uppercase text-muted-foreground">{r.engine}</span>
                    <span className="text-[10px] text-muted-foreground">{new Date(r.processed_at).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })}</span>
                  </div>
                  {r.error_message && <div className="mt-0.5 text-[10px] text-red-500 truncate">{r.error_message}</div>}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </>
  )
}

function ProgressLog({ contentId }: { contentId: number | null }) {
  const [events, setEvents] = useState<PipelineEventLog[]>([])
  const [loading, setLoading] = useState(false)

  const fetchEvents = useCallback(async () => {
    setLoading(true)
    try {
      const r = await pipelineTestApi.events(contentId ?? undefined, 20)
      setEvents(r)
    } catch { setEvents([]) } finally { setLoading(false) }
  }, [contentId])

  useEffect(() => {
    fetchEvents()
    const id = setInterval(fetchEvents, 10000)
    return () => clearInterval(id)
  }, [fetchEvents])

  const eventColor = (type: string) => {
    if (type === "completed" || type === "advanced") return "text-green-600 dark:text-green-400"
    if (type === "failed") return "text-red-600 dark:text-red-400"
    if (type === "entered") return "text-blue-600 dark:text-blue-400"
    return "text-muted-foreground"
  }

  return (
    <div className="rounded-lg border border-border bg-background overflow-hidden">
      <div className="px-3 py-2 bg-muted/40 flex items-center justify-between">
        <span className="text-xs font-semibold text-muted-foreground">
          진행 이벤트 로그{contentId ? ` (#${contentId})` : " (전체)"}
        </span>
        <button onClick={fetchEvents} disabled={loading} className="p-1 rounded hover:bg-accent transition-colors">
          <RefreshCw className={`h-3 w-3 text-muted-foreground ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>
      {events.length === 0 ? (
        <div className="px-3 py-4 text-center text-xs text-muted-foreground">이벤트 없음</div>
      ) : (
        <div className="divide-y divide-border max-h-52 overflow-y-auto">
          {events.map((e) => (
            <div key={e.id} className="px-3 py-2 flex items-start gap-2">
              <div className="shrink-0 text-[10px] text-muted-foreground w-10 pt-0.5">{e.stage.replace("stage_", "S")}</div>
              <div className="flex-1 min-w-0">
                <span className={`text-xs font-medium ${eventColor(e.event_type)}`}>{e.event_type}</span>
                {e.source && <span className="text-[10px] text-muted-foreground ml-1.5">{e.source}</span>}
                {e.error_text && <div className="text-[10px] text-red-500 truncate">{e.error_text}</div>}
              </div>
              <div className="shrink-0 text-[10px] text-muted-foreground">
                {new Date(e.started_at).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── 검수 인라인 필드 편집 테이블 ─────────────────────────────

const REVIEW_EDIT_FIELDS: Array<{
  field: string
  label: string
  contentField: string
  getValue: (c: ContentDetail) => string
  numeric?: boolean
  multiline?: boolean
}> = [
  {
    field: "title",
    label: "제목",
    contentField: "title",
    getValue: (c) => c.title ?? "",
  },
  {
    field: "genres",
    label: "장르",
    contentField: "genres",
    getValue: (c) => c.genres.map((g) => g.genre.name_ko).join(", "),
  },
  {
    field: "cast",
    label: "출연진",
    contentField: "cast",
    getValue: (c) => c.credits.filter((cr) => /actor|cast|주연|출연/i.test(cr.role)).map((cr) => cr.person.name_ko).join(", "),
  },
  {
    field: "directors",
    label: "감독",
    contentField: "directors",
    getValue: (c) => c.credits.filter((cr) => /director|감독|연출/i.test(cr.role)).map((cr) => cr.person.name_ko).join(", "),
  },
  {
    field: "runtime",
    label: "러닝타임(분)",
    contentField: "runtime",
    getValue: (c) => c.runtime_minutes ? String(c.runtime_minutes) : "",
    numeric: true,
  },
  {
    field: "country",
    label: "국가",
    contentField: "country",
    getValue: (c) => c.country ?? "",
  },
  {
    field: "production_year",
    label: "제작연도",
    contentField: "production_year",
    getValue: (c) => c.production_year ? String(c.production_year) : "",
    numeric: true,
  },
  {
    field: "synopsis",
    label: "줄거리",
    contentField: "synopsis",
    // manual edit → cp_synopsis; cp_synopsis must precede ai_synopsis so edits are visible
    getValue: (c) => c.metadata_record?.final_synopsis || c.metadata_record?.cp_synopsis || c.metadata_record?.ai_synopsis || "",
    multiline: true,
  },
]

function ReviewFieldTable({ selectedContentId, onApplied }: { selectedContentId: number | null; onApplied?: () => void }) {
  const [detail, setDetail] = useState<ContentDetail | null>(null)
  const [editingField, setEditingField] = useState<string | null>(null)
  const [editValue, setEditValue] = useState("")
  const [applying, setApplying] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadDetail = useCallback(async () => {
    if (!selectedContentId) { setDetail(null); return }
    try { setDetail(await metadataApi.getContent(selectedContentId)) } catch { setDetail(null) }
  }, [selectedContentId])

  useEffect(() => { setEditingField(null); setError(null); void loadDetail() }, [loadDetail])

  const startEdit = (field: typeof REVIEW_EDIT_FIELDS[number], currentVal: string) => {
    setEditingField(field.field)
    setEditValue(currentVal)
    setError(null)
  }

  const cancelEdit = () => { setEditingField(null); setError(null) }

  const applyEdit = async () => {
    if (!selectedContentId || !editingField) return
    const fieldDef = REVIEW_EDIT_FIELDS.find((f) => f.field === editingField)
    if (!fieldDef) return
    if (fieldDef.numeric && editValue.trim() === "") return

    setApplying(true); setError(null)
    try {
      const rawVal = fieldDef.numeric ? parseInt(editValue.trim(), 10) : editValue.trim()
      await metadataApi.updateContent(selectedContentId, { [fieldDef.contentField]: rawVal } as Parameters<typeof metadataApi.updateContent>[1])
      const freshDetail = await metadataApi.getContent(selectedContentId)
      setDetail(freshDetail)
      setEditingField(null)
      onApplied?.()
    } catch (e) {
      setError(e instanceof Error ? e.message : "적용 오류")
    } finally {
      setApplying(false)
    }
  }

  if (!selectedContentId || !detail) return null

  return (
    <div className="rounded-lg border border-orange-200 dark:border-orange-800/40 bg-orange-50/40 dark:bg-orange-900/10 p-3 space-y-2">
      <p className="text-[11px] font-semibold text-orange-700 dark:text-orange-400 uppercase tracking-wide">필드 편집 — #{selectedContentId} {detail.title}</p>
      {error && <p className="text-[10px] text-red-500">{error}</p>}
      <div className="rounded border border-border bg-background overflow-hidden">
        <div className="grid grid-cols-[5rem_1fr_5rem] text-[10px] font-semibold text-muted-foreground bg-muted/40 border-b border-border">
          <div className="px-2 py-1">필드</div>
          <div className="px-2 py-1 border-l border-border">현재값</div>
          <div className="px-2 py-1 border-l border-border text-center">적용</div>
        </div>
        {REVIEW_EDIT_FIELDS.map((fDef) => {
          const currentVal = fDef.getValue(detail)
          const isEditing = editingField === fDef.field
          return (
            <div key={fDef.field} className="grid grid-cols-[5rem_1fr_5rem] items-stretch border-t border-border text-[10px]">
              <div className="flex items-center px-2 py-1.5 font-medium text-muted-foreground shrink-0">{fDef.label}</div>
              <div
                className={`px-2 py-1.5 border-l border-border cursor-pointer ${isEditing ? "bg-accent/30" : "hover:bg-accent/20"}`}
                onClick={() => !isEditing && startEdit(fDef, currentVal)}
              >
                {isEditing ? (
                  fDef.multiline ? (
                    <textarea
                      autoFocus
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      rows={4}
                      className="w-full text-[10px] bg-transparent border-none outline-none resize-none text-foreground"
                      onClick={(e) => e.stopPropagation()}
                    />
                  ) : (
                    <input
                      autoFocus
                      type={fDef.numeric ? "number" : "text"}
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      className="w-full text-[10px] bg-transparent border-none outline-none text-foreground"
                      onClick={(e) => e.stopPropagation()}
                    />
                  )
                ) : (
                  <span className={currentVal ? "text-foreground" : "text-muted-foreground/40 italic"}>
                    {currentVal || "(없음 — 클릭하여 입력)"}
                  </span>
                )}
              </div>
              <div className="flex flex-col items-center justify-center gap-1 border-l border-border px-1 py-1">
                {isEditing ? (
                  <>
                    <button
                      onClick={() => void applyEdit()}
                      disabled={applying || (!!fDef.numeric && editValue.trim() === "")}
                      className="text-[9px] px-1.5 py-0.5 rounded bg-orange-600 hover:bg-orange-700 text-white font-medium disabled:opacity-50 w-full text-center"
                    >
                      {applying ? "…" : "적용"}
                    </button>
                    <button
                      onClick={cancelEdit}
                      className="text-[9px] px-1.5 py-0.5 rounded border border-border text-muted-foreground hover:bg-accent w-full text-center"
                    >
                      취소
                    </button>
                  </>
                ) : (
                  <button
                    onClick={() => startEdit(fDef, currentVal)}
                    className="text-[9px] px-1.5 py-0.5 rounded border border-border text-muted-foreground hover:bg-accent"
                  >
                    편집
                  </button>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function RejectedPanel({ onRefresh, selectedContentId, stageContents }: { onRefresh: () => void; selectedContentId: number | null; stageContents: ContentOut[] }) {
  const [contentStatus, setContentStatus] = useState<ContentStatus | null>(null)
  const [acting, setActing] = useState(false)
  const [resultMsg, setResultMsg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [title, setTitle] = useState("")

  const fetchContent = useCallback(async () => {
    if (!selectedContentId) { setTitle(""); setContentStatus(null); return }
    try {
      const c = await metadataApi.getContent(selectedContentId)
      setTitle(c.title)
      setContentStatus(c.status as ContentStatus)
    } catch { setContentStatus(null) }
  }, [selectedContentId])

  useEffect(() => { void fetchContent() }, [fetchContent])

  const handleReReview = async () => {
    if (!selectedContentId) return
    setActing(true); setResultMsg(null); setError(null)
    try {
      const r = await pipelineTestApi.reReview([selectedContentId])
      setResultMsg(`↻ #${selectedContentId} 검수 단계로 복귀 (${r.processed}건)`)
      onRefresh()
      await fetchContent()
    } catch (e) { setError(e instanceof Error ? e.message : "재검수 실패") }
    finally { setActing(false) }
  }

  const isRejected = contentStatus === "rejected"

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold">✕ 반려/실패</h3>
          {selectedContentId
            ? <p className="text-xs text-muted-foreground mt-0.5">#{selectedContentId} {title && <span className="font-medium text-foreground">{title}</span>}</p>
            : <p className="text-xs text-muted-foreground mt-0.5">좌측 목록에서 반려 콘텐츠를 선택하세요</p>
          }
        </div>
        {contentStatus && (
          <span className="text-[11px] px-2 py-0.5 rounded-full font-medium bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">
            {STATUS_LABEL[contentStatus] ?? contentStatus}
          </span>
        )}
      </div>

      {/* 필드 수정 — 재검수 전 메타 보강 */}
      <ReviewFieldTable selectedContentId={selectedContentId} onApplied={fetchContent} />

      {error && (
        <div className="text-xs text-red-600 dark:text-red-400 px-3 py-2 rounded-lg border border-red-200 dark:border-red-800/40 bg-red-50 dark:bg-red-900/10">{error}</div>
      )}
      {resultMsg && (
        <div className="rounded-lg border border-green-200 dark:border-green-800/40 bg-green-50 dark:bg-green-900/10 px-3 py-2.5">
          <div className="text-sm font-medium text-green-700 dark:text-green-400">{resultMsg}</div>
        </div>
      )}

      <button
        onClick={() => void handleReReview()}
        disabled={!selectedContentId || !isRejected || acting}
        className="flex items-center gap-1.5 px-4 py-2 rounded-lg border border-amber-200 dark:border-amber-800/40 text-amber-700 dark:text-amber-400 text-sm font-medium hover:bg-amber-50 dark:hover:bg-amber-900/10 disabled:opacity-50 transition-colors"
      >
        {acting ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
        재검수 (검수 단계로 복귀)
      </button>
      <StageControlBar stageContents={stageContents} onDone={onRefresh} />
    </div>
  )
}

function BulkApproveButton({ stageContents, onRefresh, setResultMsg, setError }: {
  stageContents: ContentOut[]; onRefresh: () => void
  setResultMsg: (m: string | null) => void; setError: (e: string | null) => void
}) {
  const [busy, setBusy] = useState(false)
  const approvableIds = stageContents.filter((c) => c.status !== "rejected").map((c) => c.id)
  if (!approvableIds.length) return null
  const handleBulkApprove = async () => {
    setBusy(true); setResultMsg(null); setError(null)
    try {
      const r = await pipelineTestApi.approve(approvableIds)
      setResultMsg(`✓ 전체 ${r.processed}건 승인됨`)
      onRefresh()
    } catch (e) { setError(e instanceof Error ? e.message : "전체 승인 실패") }
    finally { setBusy(false) }
  }
  return (
    <button
      onClick={() => void handleBulkApprove()}
      disabled={busy}
      className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-green-700 hover:bg-green-800 text-white text-sm font-medium disabled:opacity-50 transition-colors"
    >
      {busy ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle className="h-3.5 w-3.5" />}
      전체 {approvableIds.length}건 승인
    </button>
  )
}

// S4(검수) 중앙 단건 — 승인 / 반려 / 재검수
function S4ReviewActionBar({ id, status, onDone }: { id: number; status: ContentStatus | null; onDone: () => void }) {
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<string | null>(null)

  const act = async (fn: (ids: number[]) => Promise<ReviewActionResponse>, msg: string) => {
    setBusy(true); setResult(null)
    try { await fn([id]); setResult(msg); onDone() }
    catch (e) { setResult(`오류: ${e instanceof Error ? e.message : "실패"}`) }
    finally { setBusy(false) }
  }

  const isRejected = status === "rejected"

  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-1.5 flex-wrap">
        <button onClick={() => void act(pipelineTestApi.approve, "✓ 승인됨")} disabled={busy || isRejected}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-green-600 hover:bg-green-700 text-white text-xs font-medium disabled:opacity-50 transition-colors">
          {busy ? <RefreshCw className="h-3 w-3 animate-spin" /> : <CheckCircle className="h-3 w-3" />}
          승인 (1건)
        </button>
        <button onClick={() => void act(pipelineTestApi.reject, "✗ 반려됨")} disabled={busy || isRejected}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-red-200 dark:border-red-800/40 text-red-600 dark:text-red-400 text-xs font-medium hover:bg-red-50 dark:hover:bg-red-900/10 disabled:opacity-50 transition-colors">
          반려 (1건)
        </button>
        <button onClick={() => void act(pipelineTestApi.reReview, "↻ 재검수 복귀")} disabled={busy || !isRejected}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-amber-200 dark:border-amber-800/40 text-amber-600 dark:text-amber-400 text-xs font-medium hover:bg-amber-50 dark:hover:bg-amber-900/10 disabled:opacity-50 transition-colors">
          재검수 (1건)
        </button>
      </div>
      {result && <p className={`text-[11px] ${result.startsWith("오류") ? "text-red-500" : "text-muted-foreground"}`}>{result}</p>}
    </div>
  )
}

// S4(검수) 3단 콘솔 — 좌(목록+전체승인+이전/다음/클린업) / 중(상세+필드편집+단건결정) / 우(WebSearch)
function S4Console({ testContents, testContentsLoading, selectedContentId, onSelect, refreshTestSummary }: {
  testContents: ContentOut[]; testContentsLoading: boolean; selectedContentId: number | null
  onSelect: (id: number) => void; refreshTestSummary: () => void
}) {
  const [contentStatus, setContentStatus] = useState<ContentStatus | null>(null)
  const [reviewTitle, setReviewTitle] = useState("")
  const [useWebsearch, setUseWebsearch] = useState(false)
  const [policyBusy, setPolicyBusy] = useState(false)
  const [bulkResult, setBulkResult] = useState<string | null>(null)

  useEffect(() => { metadataApi.getEnrichPolicy().then((p) => setUseWebsearch(p.use_websearch)).catch(() => {}) }, [])

  const fetchStatus = useCallback(async () => {
    if (!selectedContentId) { setContentStatus(null); setReviewTitle(""); return }
    try {
      const c = await metadataApi.getContent(selectedContentId)
      setContentStatus(c.status as ContentStatus)
      setReviewTitle(c.title)
    } catch { setContentStatus(null) }
  }, [selectedContentId])

  useEffect(() => { void fetchStatus() }, [fetchStatus])

  const toggleWebsearch = async () => {
    setPolicyBusy(true)
    try { const p = await metadataApi.patchEnrichPolicy({ use_websearch: !useWebsearch }); setUseWebsearch(p.use_websearch) }
    catch { /* ignore */ } finally { setPolicyBusy(false) }
  }

  const isRejected = contentStatus === "rejected"
  const isApproved = contentStatus === "approved"

  return (
    <>
      {/* 좌 — 검수 목록 + 전체 승인 + 단계 이동 */}
      <div className="col-span-1">
        <div className="rounded-lg border border-amber-200 dark:border-amber-700/50 bg-background overflow-hidden">
          <div className="px-4 py-2.5 border-b border-amber-200 dark:border-amber-700/50 bg-amber-50/50 dark:bg-amber-900/10">
            <span className="text-xs font-semibold text-amber-800 dark:text-amber-300">검수</span>
            {testContents.length > 0 && <span className="ml-2 text-xs text-amber-600 dark:text-amber-400">{testContents.length}건</span>}
          </div>
          <div className="p-3 space-y-3">
            <TestContentList contents={testContents} loading={testContentsLoading} selectedId={selectedContentId} onSelect={onSelect} />
            {testContents.length > 0 && (
              <div className="space-y-2">
                {/* 전체 승인 버튼 */}
                <BulkApproveButton
                  stageContents={testContents}
                  onRefresh={refreshTestSummary}
                  setResultMsg={setBulkResult}
                  setError={() => {}}
                />
                {bulkResult && <p className="text-[11px] text-muted-foreground">{bulkResult}</p>}
                {/* 이전/다음/클린업 */}
                <StageActionBar ids={testContents.map((c) => c.id)} onDone={refreshTestSummary} />
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 중 — 콘텐츠 상세 + 필드 편집 + 단건 결정 */}
      <div className="col-span-1">
        <div className="rounded-lg border border-amber-200 dark:border-amber-700/50 bg-background overflow-hidden">
          <div className="px-4 py-2.5 border-b border-amber-200 dark:border-amber-700/50 bg-amber-50/50 dark:bg-amber-900/10 flex items-center gap-2">
            <span className="text-xs font-semibold text-amber-800 dark:text-amber-300">콘텐츠 상세</span>
            {selectedContentId && <span className="text-xs text-amber-600 dark:text-amber-400">#{selectedContentId}</span>}
            {contentStatus && (
              <span className={`ml-auto text-[11px] px-1.5 py-0.5 rounded-full font-medium ${
                isRejected ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                : isApproved ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                : "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400"
              }`}>{STATUS_LABEL[contentStatus] ?? contentStatus}</span>
            )}
          </div>
          <div className="p-3 space-y-3">
            {selectedContentId === null ? (
              <p className="text-xs text-muted-foreground text-center py-4">콘텐츠를 선택하면 상세 및 필드 편집이 표시됩니다</p>
            ) : (
              <>
                <SelectedContentMeta contentId={selectedContentId} />
                <ReviewFieldTable selectedContentId={selectedContentId} onApplied={fetchStatus} />
                <S4ReviewActionBar id={selectedContentId} status={contentStatus} onDone={() => { void fetchStatus(); refreshTestSummary() }} />
              </>
            )}
          </div>
        </div>
      </div>

      {/* 우 — WebSearch */}
      <div className="col-span-1">
        <div className="rounded-lg border border-amber-200 dark:border-amber-700/50 bg-background overflow-hidden">
          <div className="px-4 py-2.5 border-b border-amber-200 dark:border-amber-700/50 bg-amber-50/50 dark:bg-amber-900/10 flex items-center justify-between">
            <span className="text-xs font-semibold text-amber-800 dark:text-amber-300">WebSearch</span>
            <label className="flex items-center gap-1.5 cursor-pointer">
              <span className="text-[10px] text-muted-foreground">정책</span>
              <button onClick={() => void toggleWebsearch()} disabled={policyBusy}
                className={`relative inline-flex h-4 w-7 items-center rounded-full transition-colors ${useWebsearch ? "bg-violet-600" : "bg-slate-300 dark:bg-slate-600"}`}>
                <span className={`inline-block h-3 w-3 transform rounded-full bg-white transition-transform ${useWebsearch ? "translate-x-3.5" : "translate-x-0.5"}`} />
              </button>
              <span className={`text-[10px] font-medium ${useWebsearch ? "text-violet-600" : "text-muted-foreground"}`}>{useWebsearch ? "ON" : "OFF"}</span>
            </label>
          </div>
          <div className="p-3">
            {!useWebsearch ? (
              <p className="text-xs text-muted-foreground">WebSearch 정책이 OFF — 위 토글로 활성화 후 검색하세요.</p>
            ) : (
              <InlineWebSearch key={selectedContentId ?? 0} defaultQuery={reviewTitle} />
            )}
          </div>
        </div>
      </div>
    </>
  )
}

function TestReviewPanel({ onRefresh, selectedContentId, stageContents }: { onRefresh: () => void; selectedContentId: number | null; stageContents: ContentOut[] }) {
  const [contentStatus, setContentStatus] = useState<ContentStatus | null>(null)
  const [acting, setActing] = useState(false)
  const [resultMsg, setResultMsg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showWebSearch, setShowWebSearch] = useState(false)
  const [useWebsearch, setUseWebsearch] = useState(false)
  const [policyBusy, setPolicyBusy] = useState(false)
  const [reviewTitle, setReviewTitle] = useState("")

  useEffect(() => { metadataApi.getEnrichPolicy().then((p) => setUseWebsearch(p.use_websearch)).catch(() => {}) }, [])

  const fetchContent = useCallback(async () => {
    if (!selectedContentId) { setReviewTitle(""); setContentStatus(null); return }
    try {
      const c = await metadataApi.getContent(selectedContentId)
      setReviewTitle(c.title)
      setContentStatus(c.status as ContentStatus)
    } catch { setContentStatus(null) }
  }, [selectedContentId])

  useEffect(() => { void fetchContent() }, [fetchContent])

  const toggleWebsearch = async () => {
    setPolicyBusy(true)
    try { const p = await metadataApi.patchEnrichPolicy({ use_websearch: !useWebsearch }); setUseWebsearch(p.use_websearch) }
    catch { /* ignore */ } finally { setPolicyBusy(false) }
  }

  const runAction = async (
    action: (ids: number[]) => Promise<ReviewActionResponse>,
    successMsg: (r: ReviewActionResponse) => string
  ) => {
    if (!selectedContentId) return
    setActing(true); setResultMsg(null); setError(null)
    try {
      const r = await action([selectedContentId])
      setResultMsg(successMsg(r))
      onRefresh()
      await fetchContent()
    } catch (e) { setError(e instanceof Error ? e.message : "처리 실패") }
    finally { setActing(false) }
  }

  const isRejected = contentStatus === "rejected"
  const canAct = !!selectedContentId && !acting

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold">④ 검수</h3>
          {selectedContentId
            ? <p className="text-xs text-muted-foreground mt-0.5">#{selectedContentId} {reviewTitle && <span className="font-medium text-foreground">{reviewTitle}</span>}</p>
            : <p className="text-xs text-muted-foreground mt-0.5">좌측 목록에서 검수할 콘텐츠를 선택하세요</p>
          }
        </div>
        {contentStatus && (
          <span className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${
            isRejected ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
            : contentStatus === "approved" ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
            : "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400"
          }`}>{STATUS_LABEL[contentStatus] ?? contentStatus}</span>
        )}
      </div>

      {/* 필드 편집 테이블 */}
      <ReviewFieldTable selectedContentId={selectedContentId} onApplied={fetchContent} />

      {error && (
        <div className="text-xs text-red-600 dark:text-red-400 px-3 py-2 rounded-lg border border-red-200 dark:border-red-800/40 bg-red-50 dark:bg-red-900/10">{error}</div>
      )}
      {resultMsg && (
        <div className="rounded-lg border border-green-200 dark:border-green-800/40 bg-green-50 dark:bg-green-900/10 px-3 py-2.5">
          <div className="text-sm font-medium text-green-700 dark:text-green-400">{resultMsg}</div>
        </div>
      )}

      {/* 검수 결정 3액션 + 전체 승인 */}
      <div className="flex items-center gap-2 flex-wrap">
        <button
          onClick={() => void runAction(pipelineTestApi.approve, (r) => `✓ #${selectedContentId} 승인됨 (${r.processed}건)`)}
          disabled={!canAct || isRejected}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-green-600 hover:bg-green-700 text-white text-sm font-medium disabled:opacity-50 transition-colors"
        >
          {acting ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle className="h-3.5 w-3.5" />}
          승인
        </button>
        <button
          onClick={() => void runAction(pipelineTestApi.reject, (r) => `✗ #${selectedContentId} 반려됨 (${r.processed}건)`)}
          disabled={!canAct || isRejected}
          className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-red-200 dark:border-red-800/40 text-red-600 dark:text-red-400 text-sm hover:bg-red-50 dark:hover:bg-red-900/10 disabled:opacity-50 transition-colors"
        >
          반려
        </button>
        <button
          onClick={() => void runAction(pipelineTestApi.reReview, (r) => `↻ #${selectedContentId} 재검수 복귀 (${r.processed}건)`)}
          disabled={!canAct || !isRejected}
          className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-amber-200 dark:border-amber-800/40 text-amber-600 dark:text-amber-400 text-sm hover:bg-amber-50 dark:hover:bg-amber-900/10 disabled:opacity-50 transition-colors"
        >
          재검수
        </button>
        {stageContents.length >= 2 && (
          <BulkApproveButton stageContents={stageContents} onRefresh={onRefresh} setResultMsg={setResultMsg} setError={setError} />
        )}
      </div>

      {/* WebSearch — 검수 단계에서 추가 보완 검색 */}
      <div className="rounded-lg border border-violet-200 dark:border-violet-800/40 bg-violet-50/40 dark:bg-violet-900/10 p-3 space-y-2">
        <div className="flex items-center justify-between gap-2">
          <p className="text-[11px] font-semibold text-violet-700 dark:text-violet-400 uppercase tracking-wide">WebSearch — 추가 보완 검색</p>
          <label className="flex items-center gap-1.5 cursor-pointer shrink-0">
            <span className="text-[10px] text-muted-foreground">WebSearch 정책</span>
            <button onClick={() => void toggleWebsearch()} disabled={policyBusy}
              className={`relative inline-flex h-4 w-7 items-center rounded-full transition-colors ${useWebsearch ? "bg-violet-600" : "bg-slate-300 dark:bg-slate-600"}`}>
              <span className={`inline-block h-3 w-3 transform rounded-full bg-white transition-transform ${useWebsearch ? "translate-x-3.5" : "translate-x-0.5"}`} />
            </button>
            <span className={`text-[10px] font-medium ${useWebsearch ? "text-violet-600" : "text-muted-foreground"}`}>{useWebsearch ? "ON" : "OFF"}</span>
          </label>
        </div>
        {!useWebsearch
          ? <p className="text-xs text-muted-foreground">WebSearch 정책이 OFF — 위 토글로 활성화 후 검색하세요.</p>
          : <>
            <button onClick={() => setShowWebSearch((v) => !v)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${showWebSearch ? "bg-violet-100 border-violet-300 text-violet-700 dark:bg-violet-900/30 dark:border-violet-600 dark:text-violet-400" : "border-violet-300 dark:border-violet-700 text-violet-700 dark:text-violet-400 hover:bg-violet-100"}`}>
              <Search className="h-3 w-3" /> WebSearch {showWebSearch ? "닫기" : "열기"}
            </button>
            {showWebSearch && <InlineWebSearch defaultQuery={reviewTitle} />}
          </>
        }
      </div>
      <StageAdvanceBar ids={selectedContentId ? [selectedContentId] : []} fromStatus="AI처리" toStatus="검수" onDone={() => { onRefresh(); void fetchContent() }} />
      <StageControlBar stageContents={stageContents} onDone={onRefresh} />
    </div>
  )
}

// S5(승인) 콘솔 — 목록+검색+페이징+체크박스+승인시각+이전단계로
function ApprovedStagePanel({ stageContents, onRefresh }: { stageContents: ContentOut[]; onRefresh: () => void }) {
  const [search, setSearch] = useState("")
  const [checked, setChecked] = useState<Set<number>>(new Set())
  const [page, setPage] = useState(1)
  const [revertBusy, setRevertBusy] = useState(false)
  const [revertResult, setRevertResult] = useState<string | null>(null)
  const PAGE_SIZE = 10

  // search/page 초기화 when stageContents changes
  useEffect(() => { setPage(1) }, [stageContents])
  useEffect(() => { setChecked(new Set()) }, [stageContents])

  const filtered = stageContents.filter((c) =>
    !search.trim() || c.title.toLowerCase().includes(search.trim().toLowerCase()) || String(c.id).includes(search.trim())
  )
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const paginated = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  const allPageChecked = paginated.length > 0 && paginated.every((c) => checked.has(c.id))
  const toggleAll = () => {
    if (allPageChecked) setChecked((s) => { const n = new Set(s); paginated.forEach((c) => n.delete(c.id)); return n })
    else setChecked((s) => { const n = new Set(s); paginated.forEach((c) => n.add(c.id)); return n })
  }
  const toggleOne = (id: number) => setChecked((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n })

  const handleRevert = async () => {
    const ids = [...checked]
    if (!ids.length) return
    setRevertBusy(true); setRevertResult(null)
    try {
      const r = await pipelineTestApi.revert(ids)
      setRevertResult(`↩ ${r.reverted}건 검수 단계로 복귀`)
      setChecked(new Set())
      onRefresh()
    } catch (e) { setRevertResult(`오류: ${e instanceof Error ? e.message : "실패"}`) }
    finally { setRevertBusy(false) }
  }

  const fmtApproved = (dateStr: string) =>
    new Date(dateStr).toLocaleString("ko-KR", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })

  return (
    <div className="space-y-3">
      {/* 헤더 + 검색 */}
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground pointer-events-none" />
          <input
            type="text" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1) }}
            placeholder="제목 또는 ID 검색"
            className="w-full pl-7 pr-2.5 py-1.5 text-xs rounded-lg border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary/30"
          />
        </div>
        <span className="text-xs text-muted-foreground shrink-0">{filtered.length}건</span>
      </div>

      {/* 목록 테이블 */}
      {filtered.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border p-6 text-center text-xs text-muted-foreground">
          {search ? "검색 결과 없음" : "승인된 콘텐츠 없음"}
        </div>
      ) : (
        <div className="rounded-lg border border-border bg-background overflow-hidden">
          {/* 테이블 헤더 */}
          <div className="grid grid-cols-[1.5rem_3rem_1fr_4.5rem_4rem] text-[10px] font-semibold text-muted-foreground bg-muted/40 border-b border-border px-3 py-1.5 gap-2">
            <div><input type="checkbox" checked={allPageChecked} onChange={toggleAll} className="h-3 w-3 rounded border-border" /></div>
            <div>ID</div>
            <div>제목</div>
            <div>승인 시각</div>
            <div>유형</div>
          </div>
          <div className="divide-y divide-border max-h-[400px] overflow-y-auto">
            {paginated.map((c) => (
              <div key={c.id}
                onClick={() => toggleOne(c.id)}
                className={`grid grid-cols-[1.5rem_3rem_1fr_4.5rem_4rem] items-center px-3 py-2 gap-2 text-xs cursor-pointer transition-colors ${checked.has(c.id) ? "bg-green-50 dark:bg-green-900/10" : "hover:bg-accent"}`}>
                <div onClick={(e) => e.stopPropagation()}>
                  <input type="checkbox" checked={checked.has(c.id)} onChange={() => toggleOne(c.id)} className="h-3 w-3 rounded border-border" />
                </div>
                <span className="text-muted-foreground">#{c.id}</span>
                <span className="font-medium truncate">{c.title}</span>
                <span className="text-muted-foreground text-[10px]">{fmtApproved(c.created_at)}</span>
                <span className="text-[10px] text-muted-foreground">{TYPE_LABEL[c.content_type] ?? c.content_type}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 페이징 */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-1">
          <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}
            className="px-2 py-1 text-xs rounded border border-border hover:bg-accent disabled:opacity-40 transition-colors">‹</button>
          {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
            <button key={p} onClick={() => setPage(p)}
              className={`px-2 py-1 text-xs rounded border transition-colors ${p === page ? "bg-primary text-primary-foreground border-primary" : "border-border hover:bg-accent"}`}>{p}</button>
          ))}
          <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page === totalPages}
            className="px-2 py-1 text-xs rounded border border-border hover:bg-accent disabled:opacity-40 transition-colors">›</button>
        </div>
      )}

      {/* 이전단계로 + 클린업 */}
      <div className="flex items-center gap-2 flex-wrap">
        <button onClick={() => void handleRevert()} disabled={revertBusy || checked.size === 0}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-amber-200 dark:border-amber-700/40 text-amber-700 dark:text-amber-400 text-xs font-medium hover:bg-amber-50 dark:hover:bg-amber-900/10 disabled:opacity-50 transition-colors">
          {revertBusy ? <RefreshCw className="h-3 w-3 animate-spin" /> : <span>↩</span>}
          이전단계로 ({checked.size}건)
        </button>
        <CleanupButton ids={[...checked]} onDone={() => { setChecked(new Set()); onRefresh() }} />
        {revertResult && <p className={`text-[11px] ${revertResult.startsWith("오류") ? "text-red-500" : "text-muted-foreground"}`}>{revertResult}</p>}
      </div>
    </div>
  )
}

// S5 클린업 버튼 (confirm 패턴)
function CleanupButton({ ids, onDone }: { ids: number[]; onDone: () => void }) {
  const [confirm, setConfirm] = useState(false)
  const [busy, setBusy] = useState(false)
  if (!ids.length) return null
  const handle = async () => {
    setBusy(true); setConfirm(false)
    try { await pipelineTestApi.cleanupStage(ids); onDone() }
    catch { /* ignore */ } finally { setBusy(false) }
  }
  return confirm ? (
    <>
      <span className="text-[11px] text-red-500 font-medium">{ids.length}건 삭제?</span>
      <button onClick={() => void handle()} className="px-2.5 py-1.5 rounded-lg bg-red-500 hover:bg-red-600 text-white text-[11px] font-medium transition-colors">확인</button>
      <button onClick={() => setConfirm(false)} className="px-2.5 py-1.5 rounded-lg border border-border text-[11px] hover:bg-accent transition-colors">취소</button>
    </>
  ) : (
    <button onClick={() => setConfirm(true)} disabled={busy}
      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-red-200 dark:border-red-800/40 text-red-600 dark:text-red-400 text-xs font-medium hover:bg-red-50 dark:hover:bg-red-900/10 disabled:opacity-50 transition-colors">
      {busy ? <RefreshCw className="h-3 w-3 animate-spin" /> : <Trash2 className="h-3 w-3" />}
      클린업 ({ids.length}건)
    </button>
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
  stage, name, count, colorClass, active, onClick, autoOn, onToggleAuto, autoBusy, showAuto = true,
}: {
  stage: number; name: string; count: number; colorClass: string; active: boolean; onClick: () => void
  autoOn: boolean; onToggleAuto: () => void; autoBusy: boolean; showAuto?: boolean
}) {
  const badgeLabel = stage === 6 ? "✕" : `S${stage}`
  return (
    <div onClick={onClick} role="button" tabIndex={0}
      className={`flex-1 min-w-[88px] cursor-pointer rounded-xl border-2 p-3 text-center transition-all ${active ? "border-primary bg-primary/5" : "border-border bg-card hover:bg-accent"}`}>
      <div className={`text-xs font-bold text-white ${colorClass} rounded px-1.5 py-0.5 inline-block mb-1.5`}>{badgeLabel}</div>
      <div className="text-xs font-medium text-foreground">{name}</div>
      <div className="text-xl font-bold mt-0.5">{count}</div>
      {showAuto && (
        <span role="switch" aria-checked={autoOn}
          onClick={(e) => { e.stopPropagation(); if (!autoBusy) onToggleAuto() }}
          className={`mt-1.5 inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-semibold transition-colors cursor-pointer ${autoOn ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400" : "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400"} ${autoBusy ? "opacity-50" : ""}`}>
          <span className={`h-1.5 w-1.5 rounded-full ${autoOn ? "bg-green-500" : "bg-slate-400"}`} />
          AUTO {autoOn ? "ON" : "OFF"}
        </span>
      )}
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
  const selectedContentIdRef = useRef<number | null>(null)
  useEffect(() => { selectedContentIdRef.current = selectedContentId }, [selectedContentId])

  const [stageAuto, setStageAuto] = useState<StageAutoPolicy>({ s1_auto: false, s2_auto: false, s3_auto: false, s4_auto: false, s5_auto: false, s6_auto: false })
  const [stageAutoBusy, setStageAutoBusy] = useState(false)

  useEffect(() => { metadataApi.getStageAutoPolicy().then(setStageAuto).catch(() => {}) }, [])

  const toggleStageAuto = useCallback(async (stage: number, next: boolean) => {
    const key = `s${stage}_auto` as keyof StageAutoPolicy
    setStageAutoBusy(true)
    try { const updated = await metadataApi.patchStageAutoPolicy({ [key]: next }); setStageAuto(updated) }
    catch { /* ignore */ } finally { setStageAutoBusy(false) }
  }, [])

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
      // CP 무관 전체 조회. 단계 선택 시 해당 bucket 필터, 미선택 시 전체 표시.
      const r = await metadataApi.listContents({ size: 100 })
      const filtered = activeStage !== null
        ? r.items.filter((c) => contentBucket(c) === activeStage)
        : r.items
      setTestContents(filtered)
      if (filtered.length === 0 || (selectedContentIdRef.current !== null && !filtered.some((c) => c.id === selectedContentIdRef.current))) {
        setSelectedContentId(null)
      }
    } catch {
      setTestContents([])
      setSelectedContentId(null)
    } finally {
      setTestContentsLoading(false)
    }
  }, [activeStage])

  const handleSelectContent = useCallback((id: number) => {
    setSelectedContentId(id)
  }, [])

  // S1 AUTO ON: testContents 변경 시 S1에 콘텐츠가 있으면 자동 advance
  const s1AutoBusyRef = useRef(false)
  useEffect(() => {
    if (!stageAuto.s1_auto || activeStage !== 1 || testContents.length === 0) return
    if (s1AutoBusyRef.current) return
    s1AutoBusyRef.current = true
    const ids = testContents.map((c) => c.id)
    pipelineTestApi.advance(ids)
      .then(() => refreshTestSummary())
      .catch(() => {})
      .finally(() => { s1AutoBusyRef.current = false })
  // testContents가 바뀔 때만 — stageAuto/activeStage는 조건 필터
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [testContents])

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

      {/* Pipeline Test Console (dev only — NEXT_PUBLIC_ENABLE_PIPELINE_TEST=true) */}
      {ENABLE_TEST && (
        <div className="rounded-xl border border-amber-200 dark:border-amber-800/40 bg-amber-50 dark:bg-amber-900/10">
          <div className="px-5 py-4 border-b border-amber-200 dark:border-amber-800/40 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FlaskConical className="h-4 w-4 text-amber-600" />
              <h2 className="font-semibold text-amber-800 dark:text-amber-300">Pipeline Console</h2>
              <span className="text-xs px-2 py-0.5 rounded-full bg-amber-200 dark:bg-amber-800/40 text-amber-700 dark:text-amber-400 font-medium">
                dev
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-amber-600 dark:text-amber-500">
                {testSummary && testSummary.total > 0 ? `시드 ${testSummary.total}건` : "시드 없음"}
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
                  count={testSummary?.by_stage?.[String(s.stage)] ?? 0}
                  colorClass={s.colorClass}
                  active={activeStage === s.stage}
                  onClick={() => setActiveStage(activeStage === s.stage ? null : s.stage)}
                  autoOn={stageAuto[`s${s.stage}_auto` as keyof StageAutoPolicy]}
                  onToggleAuto={() => toggleStageAuto(s.stage, !stageAuto[`s${s.stage}_auto` as keyof StageAutoPolicy])}
                  autoBusy={stageAutoBusy}
                  showAuto={s.stage !== 6}
                />
              ))}
            </div>

            {/* S1·S2: 3단 카드, S3~6: 2분할 (좌 목록 / 우 단계패널) */}
            <div className={`grid gap-4 items-start ${activeStage === 6 ? "grid-cols-5" : "grid-cols-3"}`}>
              {/* S1 — 3단 (좌 생성 / 중 목록 / 우 상세) */}
              {activeStage === 1 && (
                <>
                  {/* 좌 — 콘텐츠 등록 */}
                  <div className="col-span-1">
                    <div className="rounded-lg border border-amber-200 dark:border-amber-700/50 bg-background overflow-hidden">
                      <div className="px-4 py-2.5 border-b border-amber-200 dark:border-amber-700/50 bg-amber-50/50 dark:bg-amber-900/10">
                        <span className="text-xs font-semibold text-amber-800 dark:text-amber-300">콘텐츠 등록</span>
                      </div>
                      <div className="p-4">
                        <CreationTabsPanel summary={testSummary} onRefresh={refreshTestSummary} selectedContentId={selectedContentId} stageContents={testContents} />
                      </div>
                    </div>
                  </div>

                  {/* 중 — 콘텐츠 목록 */}
                  <div className="col-span-1">
                    <div className="rounded-lg border border-amber-200 dark:border-amber-700/50 bg-background overflow-hidden">
                      <div className="px-4 py-2.5 border-b border-amber-200 dark:border-amber-700/50 bg-amber-50/50 dark:bg-amber-900/10">
                        <span className="text-xs font-semibold text-amber-800 dark:text-amber-300">콘텐츠 목록</span>
                        {testContents.length > 0 && (
                          <span className="ml-2 text-xs text-amber-600 dark:text-amber-400">{testContents.length}건</span>
                        )}
                      </div>
                      <div className="p-3 space-y-3">
                        <TestContentList
                          contents={testContents}
                          loading={testContentsLoading}
                          selectedId={selectedContentId}
                          onSelect={handleSelectContent}
                        />
                        {testContents.length > 0 && (
                          <S1BulkActionBar
                            stageContents={testContents}
                            activeStage={activeStage}
                            onDone={refreshTestSummary}
                          />
                        )}
                      </div>
                    </div>
                  </div>

                  {/* 우 — 콘텐츠 상세 (콘텐츠 없으면 숨김) */}
                  {testContents.length > 0 && (
                    <div className="col-span-1">
                      <div className="rounded-lg border border-amber-200 dark:border-amber-700/50 bg-background overflow-hidden">
                        <div className="px-4 py-2.5 border-b border-amber-200 dark:border-amber-700/50 bg-amber-50/50 dark:bg-amber-900/10">
                          <span className="text-xs font-semibold text-amber-800 dark:text-amber-300">콘텐츠 상세</span>
                          {selectedContentId && (
                            <span className="ml-2 text-xs text-amber-600 dark:text-amber-400">#{selectedContentId}</span>
                          )}
                        </div>
                        <div className="p-3 space-y-3">
                          <SelectedContentMeta contentId={selectedContentId} />
                          {selectedContentId !== null && (
                            <S1BulkActionBar
                              stageContents={testContents.filter((c) => c.id === selectedContentId)}
                              activeStage={activeStage}
                              onDone={refreshTestSummary}
                              onDeleted={() => { setSelectedContentId(null); void refreshTestSummary() }}
                            />
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </>
              )}

              {/* S2 — Enrich 3단 콘솔 */}
              {activeStage === 2 && (
                <S2Console
                  testContents={testContents}
                  testContentsLoading={testContentsLoading}
                  selectedContentId={selectedContentId}
                  onSelect={handleSelectContent}
                  refreshTestSummary={refreshTestSummary}
                />
              )}

              {/* S3 — AI처리 3단 콘솔 */}
              {activeStage === 3 && (
                <S3Console
                  testContents={testContents}
                  testContentsLoading={testContentsLoading}
                  selectedContentId={selectedContentId}
                  onSelect={handleSelectContent}
                  refreshTestSummary={refreshTestSummary}
                />
              )}

              {/* S4 — 검수 3단 콘솔 */}
              {activeStage === 4 && (
                <S4Console
                  testContents={testContents}
                  testContentsLoading={testContentsLoading}
                  selectedContentId={selectedContentId}
                  onSelect={handleSelectContent}
                  refreshTestSummary={refreshTestSummary}
                />
              )}

              {/* S5 — 승인 전체 패널 (단독 col-span-3) */}
              {activeStage === 5 && (
                <div className="col-span-3">
                  <div className="rounded-lg border border-amber-200 dark:border-amber-700/50 bg-background overflow-hidden">
                    <div className="px-4 py-2.5 border-b border-amber-200 dark:border-amber-700/50 bg-amber-50/50 dark:bg-amber-900/10">
                      <span className="text-xs font-semibold text-amber-800 dark:text-amber-300">승인</span>
                      {testContents.length > 0 && <span className="ml-2 text-xs text-amber-600 dark:text-amber-400">{testContents.length}건</span>}
                    </div>
                    <div className="p-4">
                      <ApprovedStagePanel stageContents={testContents} onRefresh={refreshTestSummary} />
                    </div>
                  </div>
                </div>
              )}

              {/* S6 — 2분할 (좌 목록+메타+버튼 / 우 반려 패널) */}
              {activeStage === 6 && (
                <>
                  <div className="col-span-2 space-y-3">
                    <TestContentList
                      contents={testContents}
                      loading={testContentsLoading}
                      selectedId={selectedContentId}
                      onSelect={handleSelectContent}
                    />
                    <StageBulkBar stageContents={testContents} activeStage={activeStage} onDone={refreshTestSummary} />
                    <SelectedContentMeta contentId={selectedContentId} />
                    <SingleAdvanceDeleteBar
                      contentId={selectedContentId}
                      activeStage={activeStage}
                      onDone={refreshTestSummary}
                      onDeleted={() => { setSelectedContentId(null); void refreshTestSummary() }}
                    />
                  </div>
                  <div className="col-span-3">
                    <div className="rounded-lg border border-amber-200 dark:border-amber-700/50 bg-background p-4">
                      <RejectedPanel onRefresh={refreshTestSummary} selectedContentId={selectedContentId} stageContents={testContents} />
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ADR-006: 파이프라인 보드 (마스터-디테일) */}
      <PipelineBoard />

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

    </div>
  )
}
