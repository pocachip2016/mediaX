"use client"

import { useState, useMemo } from "react"
import { Search, Check, X, RotateCcw, Eye, ChevronDown, Film, Tv } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"

interface Content {
  id: number
  title: string
  original_title?: string
  content_type: "movie" | "series"
  status: "waiting" | "processing" | "staging" | "review" | "approved" | "rejected"
  cp_name: string
  production_year?: number
  quality_score?: number
  created_at: string
  enrichment?: {
    ai_fields: number
    sources: string[]
    confidence?: "high" | "medium" | "low"
  }
}

const MOCK_DATA: Content[] = [
  {
    id: 1,
    title: "기생충",
    original_title: "Parasite",
    content_type: "movie",
    status: "review",
    cp_name: "CJ ENM",
    production_year: 2019,
    quality_score: 87,
    created_at: "2026-05-13T09:15:00",
    enrichment: { ai_fields: 3, sources: ["TMDB", "AI"], confidence: "high" },
  },
  {
    id: 2,
    title: "부산행",
    original_title: "Train to Busan",
    content_type: "movie",
    status: "review",
    cp_name: "Next Entertainment",
    production_year: 2016,
    quality_score: 82,
    created_at: "2026-05-13T09:20:00",
    enrichment: { ai_fields: 5, sources: ["TMDB", "KOBIS"], confidence: "high" },
  },
  {
    id: 3,
    title: "미나리",
    original_title: "Minari",
    content_type: "movie",
    status: "staging",
    cp_name: "A24",
    production_year: 2020,
    quality_score: 94,
    created_at: "2026-05-13T10:00:00",
    enrichment: { ai_fields: 2, sources: ["TMDB", "KOBIS"], confidence: "high" },
  },
  {
    id: 4,
    title: "헤어질 결심",
    original_title: "Decision to Leave",
    content_type: "movie",
    status: "staging",
    cp_name: "CJ ENM",
    production_year: 2022,
    quality_score: 91,
    created_at: "2026-05-13T10:30:00",
    enrichment: { ai_fields: 1, sources: ["TMDB"], confidence: "high" },
  },
  {
    id: 5,
    title: "오징어 게임",
    content_type: "series",
    status: "approved",
    cp_name: "Netflix",
    production_year: 2021,
    quality_score: 96,
    created_at: "2026-05-12T14:00:00",
    enrichment: { ai_fields: 0, sources: ["TMDB"], confidence: "high" },
  },
  {
    id: 6,
    title: "무빙",
    original_title: "Moving",
    content_type: "series",
    status: "processing",
    cp_name: "Disney+",
    production_year: 2023,
    quality_score: undefined,
    created_at: "2026-05-13T08:00:00",
    enrichment: { ai_fields: 2, sources: ["AI"], confidence: "medium" },
  },
  {
    id: 7,
    title: "듣보잡 컬트 영화",
    content_type: "movie",
    status: "review",
    cp_name: "Watcha",
    production_year: undefined,
    quality_score: 54,
    created_at: "2026-05-13T11:00:00",
    enrichment: { ai_fields: 1, sources: ["AI"], confidence: "low" },
  },
]

const STATUS_LABEL: Record<Content["status"], string> = {
  waiting: "대기",
  processing: "처리중",
  staging: "자동검토",
  review: "검수",
  approved: "승인됨",
  rejected: "반려됨",
}

const STATUS_CLASS: Record<Content["status"], string> = {
  waiting: "bg-slate-100 text-slate-700",
  processing: "bg-blue-100 text-blue-700",
  staging: "bg-violet-100 text-violet-700",
  review: "bg-amber-100 text-amber-700",
  approved: "bg-green-100 text-green-700",
  rejected: "bg-red-100 text-red-700",
}

function StatusBadge({ status }: { status: Content["status"] }) {
  return (
    <span className={cn("inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium", STATUS_CLASS[status])}>
      {status === "processing" && <div className="h-1.5 w-1.5 rounded-full bg-blue-400 animate-pulse" />}
      {STATUS_LABEL[status]}
    </span>
  )
}

function EnrichmentBadge({ enrichment }: { enrichment?: Content["enrichment"] }) {
  if (!enrichment) return null
  const colors =
    enrichment.confidence === "high"
      ? "bg-green-50 text-green-700"
      : enrichment.confidence === "medium"
        ? "bg-yellow-50 text-yellow-700"
        : "bg-red-50 text-red-700"

  return (
    <span className={cn("inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs", colors)}>
      ✨ AI{enrichment.ai_fields > 0 ? ` ${enrichment.ai_fields}` : ""}
      {enrichment.sources.length > 0 && <span>🔗 {enrichment.sources.join("•")}</span>}
    </span>
  )
}

export default function PrototypeListPage() {
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const [statusFilter, setStatusFilter] = useState<Content["status"] | "all">("all")
  const [searchQuery, setSearchQuery] = useState("")
  const [cpFilter, setCpFilter] = useState<string | "all">("all")

  const filteredData = useMemo(() => {
    return MOCK_DATA.filter((item) => {
      const matchStatus = statusFilter === "all" || item.status === statusFilter
      const matchSearch = item.title.toLowerCase().includes(searchQuery.toLowerCase()) || item.cp_name.toLowerCase().includes(searchQuery.toLowerCase())
      const matchCp = cpFilter === "all" || item.cp_name === cpFilter
      return matchStatus && matchSearch && matchCp
    })
  }, [statusFilter, searchQuery, cpFilter])

  const uniqueCps = useMemo(() => {
    return [...new Set(MOCK_DATA.map((item) => item.cp_name))].sort()
  }, [])

  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = { all: MOCK_DATA.length }
    MOCK_DATA.forEach((item) => {
      counts[item.status] = (counts[item.status] || 0) + 1
    })
    return counts
  }, [])

  const toggleAll = () => {
    if (selectedIds.length === filteredData.length) {
      setSelectedIds([])
    } else {
      setSelectedIds(filteredData.map((item) => item.id))
    }
  }

  const toggleRow = (id: number) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  const canApprove = selectedIds.length > 0 && selectedIds.every((id) => {
    const item = MOCK_DATA.find((x) => x.id === id)
    return item && ["staging", "review"].includes(item.status)
  })

  const canReject = selectedIds.length > 0 && selectedIds.every((id) => {
    const item = MOCK_DATA.find((x) => x.id === id)
    return item && ["staging", "review"].includes(item.status)
  })

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-slate-900">콘텐츠 목록</h1>
        <p className="text-sm text-slate-500 mt-1">AI 자동 채움 + 검수 workflow 프로토타입</p>
      </div>

      {/* Sticky Selection Bar */}
      {selectedIds.length > 0 && (
        <div className="sticky top-0 z-40 mb-4 bg-blue-50 border border-blue-200 rounded-lg p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              checked={selectedIds.length === filteredData.length}
              onChange={toggleAll}
              className="h-4 w-4 cursor-pointer"
            />
            <span className="text-sm font-medium text-slate-700">
              {selectedIds.length}개 선택
              {filteredData.length > selectedIds.length && ` · 현재 페이지 ${selectedIds.length}/${filteredData.length}`}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              disabled={!canApprove}
              className={cn(
                "inline-flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                canApprove ? "bg-green-100 text-green-700 hover:bg-green-200 cursor-pointer" : "bg-gray-100 text-gray-400 cursor-not-allowed",
              )}
            >
              <Check className="h-4 w-4" />
              승인 ({selectedIds.length})
            </button>

            <button
              disabled={!canReject}
              className={cn(
                "inline-flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                canReject ? "bg-red-100 text-red-700 hover:bg-red-200 cursor-pointer" : "bg-gray-100 text-gray-400 cursor-not-allowed",
              )}
            >
              <X className="h-4 w-4" />
              반려 ({selectedIds.length})
            </button>

            <button className="inline-flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium bg-orange-100 text-orange-700 hover:bg-orange-200 cursor-pointer transition-colors">
              <RotateCcw className="h-4 w-4" />
              AI 재처리
            </button>

            <button
              onClick={() => setSelectedIds([])}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium bg-slate-100 text-slate-700 hover:bg-slate-200 cursor-pointer transition-colors"
            >
              ✕ 해제
            </button>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="bg-white rounded-lg border border-slate-200 p-4 mb-4">
        {/* Status Tabs */}
        <div className="flex gap-2 mb-4 pb-4 border-b border-slate-200 overflow-x-auto">
          {(["all", "processing", "staging", "review", "approved", "rejected"] as const).map((status) => (
            <button
              key={status}
              onClick={() => setStatusFilter(status)}
              className={cn(
                "px-3 py-1.5 rounded-full text-sm font-medium whitespace-nowrap transition-colors",
                statusFilter === status
                  ? "bg-slate-900 text-white"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200",
              )}
            >
              {status === "all" ? "전체" : STATUS_LABEL[status as Content["status"]]}
              <span className="ml-1.5 text-xs opacity-70">
                {statusCounts[status as string] || 0}
              </span>
            </button>
          ))}
        </div>

        {/* Search & Filters */}
        <div className="flex gap-3">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input
              type="text"
              placeholder="제목, CP사 검색..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <select
            value={cpFilter}
            onChange={(e) => setCpFilter(e.target.value)}
            className="px-3 py-2 rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">CP: 전체</option>
            {uniqueCps.map((cp) => (
              <option key={cp} value={cp}>
                {cp}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <table className="w-full">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              <th className="w-8 px-4 py-3">
                <input
                  type="checkbox"
                  checked={selectedIds.length === filteredData.length && filteredData.length > 0}
                  onChange={toggleAll}
                  className="h-4 w-4 cursor-pointer"
                />
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600">제목</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600">CP</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600">상태</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600">품질</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600">Enrichment</th>
              <th className="px-4 py-3 text-right text-xs font-semibold text-slate-600">액션</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200">
            {filteredData.map((item) => (
              <tr key={item.id} className={cn("hover:bg-slate-50 transition-colors", selectedIds.includes(item.id) && "bg-blue-50")}>
                <td className="px-4 py-3">
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(item.id)}
                    onChange={() => toggleRow(item.id)}
                    className="h-4 w-4 cursor-pointer"
                  />
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    {item.content_type === "movie" ? <Film className="h-4 w-4 text-blue-600" /> : <Tv className="h-4 w-4 text-violet-600" />}
                    <div>
                      <div className="font-medium text-slate-900">{item.title}</div>
                      {item.original_title && <div className="text-xs text-slate-500">{item.original_title}</div>}
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3 text-sm text-slate-700">{item.cp_name}</td>
                <td className="px-4 py-3">
                  <StatusBadge status={item.status} />
                </td>
                <td className="px-4 py-3 text-sm font-medium">
                  {item.quality_score ? (
                    <span className={cn("px-2 py-1 rounded", item.quality_score >= 90 ? "bg-green-100 text-green-700" : item.quality_score >= 70 ? "bg-amber-100 text-amber-700" : "bg-red-100 text-red-700")}>
                      {item.quality_score}
                    </span>
                  ) : (
                    <span className="text-slate-400">-</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <EnrichmentBadge enrichment={item.enrichment} />
                </td>
                <td className="px-4 py-3 text-right">
                  <button className="inline-flex items-center gap-1 px-2 py-1 rounded text-sm font-medium bg-blue-100 text-blue-700 hover:bg-blue-200">
                    <Eye className="h-4 w-4" />
                    상세
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {filteredData.length === 0 && (
        <div className="text-center py-8 text-slate-500">
          <p>해당하는 콘텐츠가 없습니다.</p>
        </div>
      )}

      {/* Pagination */}
      <div className="mt-4 flex items-center justify-between">
        <p className="text-sm text-slate-600">
          총 {filteredData.length}개 · 현재 {filteredData.length}개 표시
        </p>
        <div className="flex gap-2">
          <button className="px-3 py-2 rounded-lg border border-slate-200 hover:bg-slate-50 disabled:opacity-50">
            <ChevronDown className="h-4 w-4 rotate-90" />
          </button>
          <button className="px-3 py-2 rounded-lg border border-slate-200 hover:bg-slate-50">
            <ChevronDown className="h-4 w-4 -rotate-90" />
          </button>
        </div>
      </div>
    </div>
  )
}
