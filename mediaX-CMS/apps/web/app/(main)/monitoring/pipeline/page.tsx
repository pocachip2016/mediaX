"use client"

import { useEffect, useState, useCallback } from "react"
import { RefreshCw, CheckCircle, AlertCircle, Clock, Mail, Search, GitMerge, Database } from "lucide-react"
import { metadataApi, type PipelineStatus } from "@/lib/api"

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

// ── 컴포넌트 ─────────────────────────────────────────────

function StatusDot({ status }: { status: "ok" | "warning" | "error" }) {
  return (
    <span className={`inline-block w-2 h-2 rounded-full ${
      status === "ok" ? "bg-green-500" : status === "warning" ? "bg-yellow-500" : "bg-red-500"
    }`} />
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

  const handleRetry = async (item: FailedItem) => {
    setRetrying((prev) => new Set(prev).add(item.id))
    try {
      await metadataApi.triggerEnrich(item.id)
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
    </div>
  )
}
