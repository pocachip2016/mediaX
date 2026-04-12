"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Activity, CheckCircle, Clock, XCircle, TrendingUp, Plus, RefreshCw } from "lucide-react"
import { metadataApi, type DashboardStats, type ContentOut } from "@/lib/api"

const STATUS_LABEL: Record<string, string> = {
  waiting: "대기",
  processing: "처리중",
  review: "검수대기",
  approved: "등록완료",
  rejected: "반려",
}

const STATUS_COLOR: Record<string, string> = {
  waiting: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
  processing: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
  review: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300",
  approved: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
  rejected: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
}

function ScoreBadge({ score }: { score: number | null }) {
  if (score === null) return <span className="text-muted-foreground text-xs">-</span>
  const color = score >= 90 ? "text-green-600" : score >= 70 ? "text-yellow-600" : "text-red-500"
  return <span className={`font-semibold text-sm ${color}`}>{score.toFixed(0)}점</span>
}

// Mock 데이터 (API 연결 전)
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

export default function MetadataDashboardPage() {
  const [stats, setStats] = useState<DashboardStats>(MOCK_STATS)
  const [recent, setRecent] = useState<ContentOut[]>(MOCK_RECENT)
  const [loading, setLoading] = useState(false)

  const fetchData = async () => {
    setLoading(true)
    try {
      const [s, r] = await Promise.all([
        metadataApi.getDashboard(),
        metadataApi.listContents({ size: 10 }),
      ])
      setStats(s)
      setRecent(r.items)
    } catch {
      // API 미연결 시 Mock 유지
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [])

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">메타데이터 대시보드</h1>
          <p className="text-muted-foreground text-sm mt-1">AI 메타데이터 처리 현황</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={fetchData}
            className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border text-sm hover:bg-accent transition-colors"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            새로고침
          </button>
          <Link
            href="/programming/metadata/create"
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-primary text-primary-foreground text-sm hover:bg-primary/90 transition-colors"
          >
            <Plus className="h-4 w-4" />
            메타 생성
          </Link>
        </div>
      </div>

      {/* 통계 카드 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard icon={<Activity className="h-5 w-5 text-blue-500" />} label="오늘 수신" value={stats.total_today} sub="총 건수" />
        <StatCard icon={<CheckCircle className="h-5 w-5 text-green-500" />} label="자동 등록" value={stats.auto_registered} sub={`${((stats.auto_registered / stats.total_today) * 100).toFixed(0)}%`} />
        <StatCard icon={<Clock className="h-5 w-5 text-orange-500" />} label="검수 대기" value={stats.review_pending} sub="70~89점" href="/programming/metadata/queue" />
        <StatCard icon={<XCircle className="h-5 w-5 text-red-500" />} label="반려" value={stats.rejected} sub="70점 미만" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 점수 분포 */}
        <div className="col-span-1 rounded-xl border border-border bg-card p-5 space-y-4">
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

        {/* CP사별 통계 */}
        <div className="col-span-1 rounded-xl border border-border bg-card p-5 space-y-4">
          <h2 className="font-semibold">CP사별 수신량</h2>
          <div className="space-y-2">
            {stats.cp_stats.map((cp, i) => {
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

        {/* 빠른 액션 */}
        <div className="col-span-1 rounded-xl border border-border bg-card p-5 space-y-3">
          <h2 className="font-semibold">빠른 이동</h2>
          <div className="space-y-2">
            <Link href="/programming/metadata/queue" className="flex items-center justify-between p-3 rounded-lg border border-border hover:bg-accent transition-colors">
              <div>
                <div className="text-sm font-medium">검수 큐</div>
                <div className="text-xs text-muted-foreground">담당자 리뷰 대기 {stats.review_pending}건</div>
              </div>
              <span className="text-xs bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300 px-2 py-0.5 rounded-full font-medium">{stats.review_pending}</span>
            </Link>
            <Link href="/programming/metadata/create" className="flex items-center justify-between p-3 rounded-lg border border-border hover:bg-accent transition-colors">
              <div>
                <div className="text-sm font-medium">실시간 메타 생성</div>
                <div className="text-xs text-muted-foreground">제목 입력 → AI 자동완성</div>
              </div>
              <Plus className="h-4 w-4 text-muted-foreground" />
            </Link>
          </div>
        </div>
      </div>

      {/* 최근 처리 콘텐츠 */}
      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <div className="px-5 py-4 border-b border-border">
          <h2 className="font-semibold">최근 처리 콘텐츠</h2>
        </div>
        <div className="overflow-x-auto">
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
                <tr key={c.id} className="hover:bg-muted/30 transition-colors">
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
      </div>
    </div>
  )
}

function StatCard({ icon, label, value, sub, href }: {
  icon: React.ReactNode; label: string; value: number; sub: string; href?: string
}) {
  const inner = (
    <div className="rounded-xl border border-border bg-card p-5 space-y-2 hover:bg-accent/50 transition-colors">
      <div className="flex items-center gap-2">
        {icon}
        <span className="text-sm text-muted-foreground">{label}</span>
      </div>
      <div className="text-3xl font-bold">{value.toLocaleString()}</div>
      <div className="text-xs text-muted-foreground">{sub}</div>
    </div>
  )
  return href ? <Link href={href}>{inner}</Link> : inner
}
