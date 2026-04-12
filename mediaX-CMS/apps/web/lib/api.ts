/**
 * API 클라이언트 — FastAPI 백엔드 통신
 * Base URL: NEXT_PUBLIC_API_URL (기본 http://localhost:8000)
 */

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(`API ${path} → ${res.status}: ${detail}`)
  }
  return res.json() as Promise<T>
}

// ── 타입 ──────────────────────────────────────────────────

export type ContentStatus = "waiting" | "processing" | "review" | "approved" | "rejected"
export type ContentType = "movie" | "series" | "episode"

export interface ContentOut {
  id: number
  title: string
  original_title: string | null
  content_type: ContentType
  status: ContentStatus
  cp_name: string | null
  production_year: number | null
  runtime_minutes: number | null
  created_at: string
  quality_score: number | null
}

export interface MetadataOut {
  id: number
  content_id: number
  cp_synopsis: string | null
  cp_genre: string | null
  ai_synopsis: string | null
  ai_genre_primary: string | null
  ai_genre_secondary: string | null
  ai_mood_tags: string[] | null
  ai_rating_suggestion: string | null
  final_synopsis: string | null
  final_genre: string | null
  final_tags: string[] | null
  quality_score: number
  score_breakdown: Record<string, number> | null
  ai_processed_at: string | null
  reviewed_at: string | null
}

export interface ContentDetail extends ContentOut {
  metadata_record: MetadataOut | null
}

export interface PaginatedContents {
  items: ContentOut[]
  total: number
  page: number
  size: number
}

export interface DashboardStats {
  total_today: number
  auto_registered: number
  review_pending: number
  rejected: number
  avg_quality_score: number
  score_distribution: Record<string, number>
  cp_stats: { cp_name: string; count: number }[]
}

export interface AIGenerateResponse {
  synopsis: string
  genre_primary: string
  genre_secondary: string | null
  mood_tags: string[]
  rating_suggestion: string
  quality_score: number
  kobis_match: Record<string, unknown> | null
  tmdb_match: Record<string, unknown> | null
}

// ── API 함수 ──────────────────────────────────────────────

export const metadataApi = {
  getDashboard: () =>
    request<DashboardStats>("/api/programming/metadata/dashboard"),

  listContents: (params?: { status?: ContentStatus; cp_name?: string; page?: number; size?: number }) => {
    const q = new URLSearchParams()
    if (params?.status) q.set("status", params.status)
    if (params?.cp_name) q.set("cp_name", params.cp_name)
    if (params?.page) q.set("page", String(params.page))
    if (params?.size) q.set("size", String(params.size))
    return request<PaginatedContents>(`/api/programming/metadata/contents?${q}`)
  },

  getContent: (id: number) =>
    request<ContentDetail>(`/api/programming/metadata/contents/${id}`),

  createContent: (data: { title: string; content_type?: ContentType; cp_name?: string; production_year?: number }) =>
    request<ContentOut>("/api/programming/metadata/contents", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  triggerProcess: (id: number) =>
    request<{ task_id: string }>(`/api/programming/metadata/contents/${id}/process`, { method: "POST" }),

  getQueue: (params?: { page?: number; size?: number }) => {
    const q = new URLSearchParams()
    if (params?.page) q.set("page", String(params.page))
    if (params?.size) q.set("size", String(params.size))
    return request<PaginatedContents>(`/api/programming/metadata/queue?${q}`)
  },

  reviewAction: (
    id: number,
    action: { action: "approve" | "reject" | "modify"; reviewer: string; final_synopsis?: string; final_genre?: string; final_tags?: string[] }
  ) =>
    request<ContentOut>(`/api/programming/metadata/queue/${id}/action`, {
      method: "POST",
      body: JSON.stringify(action),
    }),

  generate: (data: { title: string; production_year?: number; cp_name?: string; cp_synopsis?: string }) =>
    request<AIGenerateResponse>("/api/programming/metadata/generate", {
      method: "POST",
      body: JSON.stringify(data),
    }),
}
