"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import {
  Activity, CheckCircle, Clock, XCircle, TrendingUp, Plus, RefreshCw,
  Eye, Upload, GitBranch, AlertCircle, ChevronDown, ChevronUp,
} from "lucide-react"
import { metadataApi, serviceReadinessApi, type DashboardStats, type ContentOut, type PipelineStatus, type ServiceReadinessStats } from "@/lib/api"

const STATUS_LABEL: Record<string, string> = {
  waiting: "대기",
  processing: "처리중",
  staging: "검토대기",
  review: "검수대기",
  approved: "등록완료",
  rejected: "반려",
}

const STATUS_COLOR: Record<string, string> = {
  waiting: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
  processing: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
  staging: "bg-violet-100 text-violet-800 dark:bg-violet-900/30 dark:text-violet-300",
  review: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300",
  approved: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
  rejected: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
}

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

function ScoreBadge({ score }: { score: number | null }) {
  if (score === null) return <span className="text-muted-foreground text-xs">-</span>
  const color = score >= 90 ? "text-green-600" : score >= 70 ? "text-yellow-600" : "text-red-500"
  return <span className={`font-semibold text-sm ${color}`}>{score.toFixed(0)}점</span>
}

const MOCK_STATS: DashboardStats = {
  total_today: 247,
  auto_registered: 189,
  review_pending: 41,
  rejected: 17,
  avg_quality_score: 83.4,
  score_distribution: { "90+": 189, "70-89": 41, "~70": 17 },
  cp_stats: [
    { cp_name: "CJ ENM", count: 52 },
    { cp_name: "JTBC스튜디오", count: 43 },
    { cp_name: "NEW", count: 38 },
    { cp_name: "롯데엔터테인먼트", count: 31 },
    { cp_name: "쇼박스", count: 27 },
  ],
}

const MOCK_RECENT: ContentOut[] = [
  { id: 1, title: "기생충", original_title: "Parasite", content_type: "movie", status: "approved", cp_name: "CJ ENM", production_year: 2019, runtime_minutes: 132, created_at: new Date().toISOString(), quality_score: 96 },
  { id: 2, title: "오징어 게임 시즌2", original_title: null, content_type: "series", status: "review", cp_name: "JTBC스튜디오", production_year: 2024, runtime_minutes: null, created_at: new Date().toISOString(), quality_score: 78 },
  { id: 3, title: "범죄도시4", original_title: null, content_type: "movie", status: "approved", cp_name: "NEW", production_year: 2024, runtime_minutes: 109, created_at: new Date().toISOString(), quality_score: 91 },
  { id: 4, title: "미확인 다큐멘터리", original_title: null, content_type: "movie", status: "review", cp_name: "롯데엔터테인먼트", production_year: 2024, runtime_minutes: 90, created_at: new Date().toISOString(), quality_score: 65 },
  { id: 5, title: "서울의 봄", original_title: null, content_type: "movie", status: "approved", cp_name: "쇼박스", production_year: 2023, runtime_minutes: 141, created_at: new Date().toISOString(), quality_score: 94 },
]

const MOCK_READINESS: ServiceReadinessStats = {
  total: 247,
  text_completed: 189,
  image_completed: 156,
  video_completed: 142,
  all_completed: 137,
}

export default function MetadataDashboardPage() {
  const router = useRouter()
  const [stats, setStats] = useState<DashboardStats>(MOCK_STATS)
  const [pipeline, setPipeline] = useState<PipelineStatus>(MOCK_PIPELINE)
  const [recent, setRecent] = useState<ContentOut[]>(MOCK_RECENT)
  const [readiness, setReadiness] = useState<ServiceReadinessStats>(MOCK_READINESS)
  const [loading, setLoading] = useState(false)
  const [isPipelineOpen, setIsPipelineOpen] = useState(true)
  const [isRecentOpen, setIsRecentOpen] = useState(false)

  const fetchData = async () => {
    setLoading(true)
    try {
      const [s, r, p, rd] = await Promise.all([
        metadataApi.getDashboard(),
        metadataApi.listContents({ size: 10 }),
        metadataApi.getPipelineStatus(),
        serviceReadinessApi.get(),
      ])
      setStats(s)
      setRecent(r.items)
      setPipeline(p)
      setReadiness(rd)
    } catch {
      // API 미연결 시 Mock 유지
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [])

  return (
    <div className="space-y-5">
      {/* ── 헤더 ─────────────────────────────────────────────── */}
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold">메타데이터 대시보드</h1>
          <p className="text-muted-foreground text-sm mt-0.5">콘텐츠 서비스 준비 현황</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={fetchData}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border text-sm hover:bg-accent transition-colors"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            새로고침
          </button>
          <Link
            href="/programming/metadata/staging"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-violet-200 dark:border-violet-800/40 bg-violet-50 dark:bg-violet-900/10 text-violet-700 dark:text-violet-300 text-sm hover:opacity-80 transition-opacity"
          >
            <Eye className="h-3.5 w-3.5" />
            검토 대기
            <span className="ml-0.5 font-bold">{pipeline.staging_count}</span>
          </Link>
          <Link
            href="/programming/metadata/queue"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-orange-200 dark:border-orange-800/40 bg-orange-50 dark:bg-orange-900/10 text-orange-700 dark:text-orange-300 text-sm hover:opacity-80 transition-opacity"
          >
            <Clock className="h-3.5 w-3.5" />
            검수 큐
            <span className="ml-0.5 font-bold">{pipeline.review_count}</span>
          </Link>
          <Link
            href="/programming/metadata/create"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-sm hover:bg-primary/90 transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            메타 생성
          </Link>
        </div>
      </div>

      {/* ── 서비스 준비 현황 (핵심 KPI) ─────────────────────── */}
      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <div className="px-5 py-3.5 border-b border-border flex items-center justify-between">
          <h2 className="font-semibold text-sm">서비스 준비 현황</h2>
          <span className="text-xs text-muted-foreground">글자메타 + 이미지메타 + 영상메타 모두 완료 시 서비스 준비 완료</span>
        </div>
        <div className="p-4 grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            {
              label: "글자메타",
              value: readiness.text_completed,
              href: "/programming/metadata/text",
              color: "text-blue-600",
              bg: "bg-blue-50 dark:bg-blue-900/20",
              border: "border-blue-200 dark:border-blue-800",
              sub: `AI 처리중 ${pipeline.processing_count} / 검수대기 ${pipeline.review_count}`,
            },
            {
              label: "이미지메타",
              value: readiness.image_completed,
              href: "/programming/metadata/image",
              color: "text-violet-600",
              bg: "bg-violet-50 dark:bg-violet-900/20",
              border: "border-violet-200 dark:border-violet-800",
              sub: "TMDB 자동 수집",
            },
            {
              label: "영상메타",
              value: readiness.video_completed,
              href: "/programming/metadata/video",
              color: "text-orange-600",
              bg: "bg-orange-50 dark:bg-orange-900/20",
              border: "border-orange-200 dark:border-orange-800",
              sub: "인제스트 연동",
            },
            {
              label: "서비스 준비 완료",
              value: readiness.all_completed,
              href: undefined,
              color: "text-green-600",
              bg: "bg-green-50 dark:bg-green-900/20",
              border: "border-green-200 dark:border-green-800",
              sub: "3가지 메타 모두 완료",
            },
          ].map(({ label, value, href, color, bg, border, sub }) => {
            const pct = readiness.total > 0 ? Math.round((value / readiness.total) * 100) : 0
            const card = (
              <div className={`rounded-xl border p-4 space-y-2 ${bg} ${border} hover:opacity-80 transition-opacity`}>
                <div className={`text-xs font-medium ${color}`}>{label}</div>
                <div className={`text-2xl font-bold ${color}`}>{value.toLocaleString()}</div>
                <div className="h-1.5 rounded-full bg-white/50 dark:bg-white/10 overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${color.replace("text-", "bg-")}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <div className={`text-xs ${color} opacity-80`}>{pct}% / {readiness.total}건</div>
                  <div className={`text-xs ${color} opacity-60`}>{sub}</div>
                </div>
              </div>
            )
            return href
              ? <Link key={label} href={href}>{card}</Link>
              : <div key={label}>{card}</div>
          })}
        </div>
      </div>

      {/* ── 품질 점수 + CP사별 수신량 (2-col) ──────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* 품질 점수 분포 */}
        <div className="rounded-xl border border-border bg-card p-5 space-y-4">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-primary" />
            <h2 className="font-semibold">품질 점수 분포</h2>
          </div>
          <div className="text-3xl font-bold">{stats.avg_quality_score}<span className="text-base text-muted-foreground font-normal ml-1">점 평균</span></div>
          <div className="space-y-2">
            {[
              { label: "90점 이상 (자동 등록)", key: "90+", color: "bg-green-500" },
              { label: "70~89점 (검수 대기)", key: "70-89", color: "bg-yellow-500" },
              { label: "70점 미만 (반려)", key: "~70", color: "bg-red-500" },
            ].map(({ label, key, color }) => {
              const count = stats.score_distribution[key] ?? 0
              const pct = stats.total_today ? Math.round((count / stats.total_today) * 100) : 0
              return (
                <div key={key} className="space-y-1">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">{label}</span>
                    <span className="font-medium">{count}건 ({pct}%)</span>
                  </div>
                  <div className="h-2 rounded-full bg-muted overflow-hidden">
                    <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${pct}%` }} />
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* CP사별 수신량 */}
        <div className="rounded-xl border border-border bg-card p-5 space-y-4">
          <h2 className="font-semibold">CP사별 수신량</h2>
          <div className="space-y-2">
            {stats.cp_stats.map((cp) => {
              const max = stats.cp_stats[0]?.count ?? 1
              const pct = Math.round((cp.count / max) * 100)
              return (
                <div key={cp.cp_name} className="space-y-1">
                  <div className="flex justify-between text-sm">
                    <span>{cp.cp_name}</span>
                    <span className="text-muted-foreground">{cp.count}건</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                    <div className="h-full bg-primary rounded-full" style={{ width: `${pct}%` }} />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* ── AI 파이프라인 현황 (접기 가능) ────────────────── */}
      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <button
          onClick={() => setIsPipelineOpen(!isPipelineOpen)}
          className="w-full px-5 py-3.5 flex items-center justify-between hover:bg-accent/30 transition-colors"
        >
          <div className="flex items-center gap-2">
            <GitBranch className="h-4 w-4 text-primary" />
            <span className="font-semibold text-sm">AI 파이프라인 현황</span>
            {pipeline.failed_enrichment_count > 0 && (
              <span className="flex items-center gap-1 text-xs text-red-500 bg-red-50 dark:bg-red-900/20 px-2 py-0.5 rounded-full">
                <AlertCircle className="h-3 w-3" />
                실패 {pipeline.failed_enrichment_count}건
              </span>
            )}
          </div>
          {isPipelineOpen
            ? <ChevronUp className="h-4 w-4 text-muted-foreground" />
            : <ChevronDown className="h-4 w-4 text-muted-foreground" />
          }
        </button>
        {isPipelineOpen && (
          <div className="px-5 pb-4 space-y-3 border-t border-border">
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2 pt-4">
              <PipelineCard label="수신 대기" value={pipeline.waiting_count} color="yellow" icon={<Activity className="h-3.5 w-3.5" />} />
              <PipelineCard label="처리 중" value={pipeline.processing_count} color="blue" icon={<RefreshCw className="h-3.5 w-3.5" />} />
              <PipelineCard label="검토 대기" value={pipeline.staging_count} color="violet" icon={<Eye className="h-3.5 w-3.5" />} href="/programming/metadata/staging" />
              <PipelineCard label="검수 대기" value={pipeline.review_count} color="orange" icon={<Clock className="h-3.5 w-3.5" />} href="/programming/metadata/queue" />
              <PipelineCard label="등록 완료" value={pipeline.approved_count} color="green" icon={<CheckCircle className="h-3.5 w-3.5" />} />
              <PipelineCard label="실패/반려" value={pipeline.rejected_count + pipeline.failed_enrichment_count} color="red" icon={<XCircle className="h-3.5 w-3.5" />} />
            </div>
            <div className="flex items-center justify-between text-xs text-muted-foreground pt-1">
              <span>{pipeline.tasks_description}</span>
              <span>마지막 이메일 폴링: {pipeline.last_email_poll ? new Date(pipeline.last_email_poll).toLocaleString("ko-KR") : "—"}</span>
            </div>
          </div>
        )}
      </div>

      {/* ── 최근 처리 콘텐츠 (기본 접힌 상태) ──────────────── */}
      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <button
          onClick={() => setIsRecentOpen(!isRecentOpen)}
          className="w-full px-5 py-3.5 flex items-center justify-between hover:bg-accent/30 transition-colors"
        >
          <span className="font-semibold text-sm">최근 처리 콘텐츠</span>
          {isRecentOpen
            ? <ChevronUp className="h-4 w-4 text-muted-foreground" />
            : <ChevronDown className="h-4 w-4 text-muted-foreground" />
          }
        </button>
        {isRecentOpen && (
          <div className="border-t border-border overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/50">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-muted-foreground">제목</th>
                  <th className="text-left px-4 py-3 font-medium text-muted-foreground">CP사</th>
                  <th className="text-left px-4 py-3 font-medium text-muted-foreground">연도</th>
                  <th className="text-left px-4 py-3 font-medium text-muted-foreground">상태</th>
                  <th className="text-left px-4 py-3 font-medium text-muted-foreground">품질</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {recent.map((c) => (
                  <tr
                    key={c.id}
                    className="hover:bg-muted/30 transition-colors cursor-pointer"
                    onClick={() => router.push(`/programming/contents/${c.id}`)}
                  >
                    <td className="px-4 py-3">
                      <div className="font-medium">{c.title}</div>
                      {c.original_title && <div className="text-xs text-muted-foreground">{c.original_title}</div>}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">{c.cp_name ?? "-"}</td>
                    <td className="px-4 py-3 text-muted-foreground">{c.production_year ?? "-"}</td>
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLOR[c.status]}`}>
                        {STATUS_LABEL[c.status]}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <ScoreBadge score={c.quality_score} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

const PIPELINE_COLOR_MAP: Record<string, string> = {
  yellow: "bg-yellow-50 dark:bg-yellow-900/10 border-yellow-200 dark:border-yellow-800/30 text-yellow-600 dark:text-yellow-400",
  blue: "bg-blue-50 dark:bg-blue-900/10 border-blue-200 dark:border-blue-800/30 text-blue-600 dark:text-blue-400",
  violet: "bg-violet-50 dark:bg-violet-900/10 border-violet-200 dark:border-violet-800/30 text-violet-600 dark:text-violet-400",
  orange: "bg-orange-50 dark:bg-orange-900/10 border-orange-200 dark:border-orange-800/30 text-orange-600 dark:text-orange-400",
  green: "bg-green-50 dark:bg-green-900/10 border-green-200 dark:border-green-800/30 text-green-600 dark:text-green-400",
  red: "bg-red-50 dark:bg-red-900/10 border-red-200 dark:border-red-800/30 text-red-600 dark:text-red-400",
}

function PipelineCard({ label, value, color, icon, href }: {
  label: string; value: number; color: string; icon: React.ReactNode; href?: string
}) {
  const cls = PIPELINE_COLOR_MAP[color] ?? ""
  const inner = (
    <div className={`rounded-xl border p-3 space-y-1 hover:opacity-80 transition-opacity ${cls}`}>
      <div className="flex items-center gap-1.5">
        {icon}
        <span className="text-xs font-medium">{label}</span>
      </div>
      <div className="text-2xl font-bold">{value.toLocaleString()}</div>
    </div>
  )
  return href ? <Link href={href}>{inner}</Link> : inner
}
