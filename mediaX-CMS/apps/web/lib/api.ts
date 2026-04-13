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

export type ContentStatus = "waiting" | "processing" | "staging" | "review" | "approved" | "rejected"
export type ContentType = "movie" | "series" | "season" | "episode"

export interface ContentOut {
  id: number
  title: string
  original_title: string | null
  content_type: ContentType
  status: ContentStatus
  cp_name: string | null
  production_year: number | null
  runtime_minutes: number | null
  country?: string | null
  created_at: string
  quality_score: number | null
}

export interface MetadataOut {
  id: number
  content_id: number
  cp_synopsis: string | null
  cp_genre: string | null
  cp_tags: string[] | null
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

// ── Staging 타입 ───────────────────────────────────────────

export interface ExternalSourceOut {
  id: number
  source_type: string
  external_id: string | null
  fetched_at: string | null
}

export interface StagingItem {
  content: ContentOut
  metadata: MetadataOut | null
  diff: Record<string, { cp: string | null; ai: string | null }>
  external_sources: ExternalSourceOut[]
  children: StagingItem[]
}

export interface PaginatedStagingItems {
  items: StagingItem[]
  total: number
  page: number
  size: number
}

export interface BulkActionRequest {
  content_ids: number[]
  reviewer: string
}

// ── 파이프라인 타입 ────────────────────────────────────────

export interface PipelineStatus {
  waiting_count: number
  processing_count: number
  staging_count: number
  review_count: number
  approved_count: number
  rejected_count: number
  failed_enrichment_count: number
  avg_quality_score: number
  last_email_poll: string | null
  tasks_description: string
}

// ── 배치 업로드 타입 ──────────────────────────────────────

export interface BatchJobOut {
  id: number
  job_name: string
  cp_name: string | null
  status: string
  file_name: string | null
  total_count: number
  success_count: number
  failed_count: number
  created_by: string | null
  created_at: string
  finished_at: string | null
}

// ── API 함수 ──────────────────────────────────────────────

export const metadataApi = {
  getDashboard: () =>
    request<DashboardStats>("/api/programming/metadata/dashboard"),

  listContents: (params?: {
    status?: ContentStatus
    cp_name?: string
    title?: string
    content_type?: ContentType
    production_year?: number
    page?: number
    size?: number
  }) => {
    const q = new URLSearchParams()
    if (params?.status) q.set("status", params.status)
    if (params?.cp_name) q.set("cp_name", params.cp_name)
    if (params?.title) q.set("title", params.title)
    if (params?.content_type) q.set("content_type", params.content_type)
    if (params?.production_year) q.set("production_year", String(params.production_year))
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

  // ── Staging 대기풀 ────────────────────────────────────
  getStaging: (params?: { content_type?: string; page?: number; size?: number }) => {
    const q = new URLSearchParams()
    if (params?.content_type) q.set("content_type", params.content_type)
    if (params?.page) q.set("page", String(params.page))
    if (params?.size) q.set("size", String(params.size))
    return request<PaginatedStagingItems>(`/api/programming/metadata/staging?${q}`)
  },

  bulkApprove: (data: BulkActionRequest) =>
    request<{ approved: number; ids: number[] }>("/api/programming/metadata/staging/bulk-approve", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  bulkReject: (data: BulkActionRequest) =>
    request<{ rejected: number; ids: number[] }>("/api/programming/metadata/staging/bulk-reject", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  triggerEnrich: (id: number) =>
    request<{ task_id: string }>(`/api/programming/metadata/contents/${id}/enrich`, { method: "POST" }),

  getHierarchy: (id: number) =>
    request<StagingItem>(`/api/programming/metadata/contents/${id}/hierarchy`),

  // ── 파이프라인 현황 ───────────────────────────────────
  getPipelineStatus: () =>
    request<PipelineStatus>("/api/programming/metadata/pipeline/status"),

  // ── 배치 업로드 ──────────────────────────────────────
  uploadBatch: (formData: FormData) => {
    const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
    return fetch(`${BASE_URL}/api/programming/metadata/upload/batch`, {
      method: "POST",
      body: formData,
    }).then(async (res) => {
      if (!res.ok) {
        const detail = await res.text()
        throw new Error(`API upload/batch → ${res.status}: ${detail}`)
      }
      return res.json() as Promise<BatchJobOut>
    })
  },

  getBatchJob: (jobId: number) =>
    request<BatchJobOut>(`/api/programming/metadata/upload/batch/${jobId}`),
}

// ── 타입: 메타 3분류 ──────────────────────────────────────────

export interface TextMetaOut {
  id: number
  title: string
  content_type: ContentType
  cp_name: string | null
  production_year: number | null
  season_number: number | null
  episode_number: number | null
  parent_id: number | null
  synopsis: string | null
  genre_primary: string | null
  genre_secondary: string | null
  mood_tags: string[] | null
  rating_suggestion: string | null
  text_meta_completed: boolean
  episode_completed_count: number
  episode_total_count: number
  children: TextMetaOut[]
}

export interface ContentImageOut {
  id: number
  content_id: number
  image_type: string
  url: string
  width: number | null
  height: number | null
  alt_text: string | null
  source: string | null
}

export interface ImageMetaOut {
  id: number
  title: string
  content_type: ContentType
  cp_name: string | null
  production_year: number | null
  images: ContentImageOut[]
  has_poster: boolean
  has_thumbnail: boolean
  has_stillcut: boolean
  has_banner: boolean
  has_logo: boolean
  image_meta_completed: boolean
}

export interface VideoMetaOut {
  id: number
  title: string
  content_type: ContentType
  cp_name: string | null
  production_year: number | null
  video_resolution: string | null
  video_format: string | null
  codec_video: string | null
  codec_audio: string | null
  video_bitrate_kbps: number | null
  video_duration_seconds: number | null
  subtitle_languages: string[] | null
  drm_type: string | null
  preview_clip_url: string | null
  video_meta_completed: boolean
}

export interface ServiceReadinessStats {
  total: number
  text_completed: number
  image_completed: number
  video_completed: number
  all_completed: number
}

interface PaginatedTextMeta { items: TextMetaOut[]; total: number; page: number; size: number }
interface PaginatedImageMeta { items: ImageMetaOut[]; total: number; page: number; size: number }
interface PaginatedVideoMeta { items: VideoMetaOut[]; total: number; page: number; size: number }

// ── textMetaApi ───────────────────────────────────────────────

export const textMetaApi = {
  list: (params?: { completed?: boolean; content_type?: string; page?: number; size?: number }) => {
    const q = new URLSearchParams()
    if (params?.completed !== undefined) q.set("completed", String(params.completed))
    if (params?.content_type) q.set("content_type", params.content_type)
    if (params?.page) q.set("page", String(params.page))
    if (params?.size) q.set("size", String(params.size))
    return request<PaginatedTextMeta>(`/api/programming/metadata/text?${q}`)
  },

  get: (id: number) =>
    request<TextMetaOut>(`/api/programming/metadata/text/${id}`),

  update: (id: number, data: { synopsis?: string; genre_primary?: string; mood_tags?: string[]; rating_suggestion?: string; completed: boolean }) =>
    request<TextMetaOut>(`/api/programming/metadata/text/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  bulkComplete: (content_ids: number[]) =>
    request<{ updated: number }>("/api/programming/metadata/text/bulk-complete", {
      method: "POST",
      body: JSON.stringify({ content_ids }),
    }),
}

// ── imageMetaApi ──────────────────────────────────────────────

export const imageMetaApi = {
  list: (params?: { completed?: boolean; page?: number; size?: number }) => {
    const q = new URLSearchParams()
    if (params?.completed !== undefined) q.set("completed", String(params.completed))
    if (params?.page) q.set("page", String(params.page))
    if (params?.size) q.set("size", String(params.size))
    return request<PaginatedImageMeta>(`/api/programming/metadata/image?${q}`)
  },

  get: (id: number) =>
    request<ImageMetaOut>(`/api/programming/metadata/image/${id}`),
}

// ── videoMetaApi ──────────────────────────────────────────────

export const videoMetaApi = {
  list: (params?: { completed?: boolean; page?: number; size?: number }) => {
    const q = new URLSearchParams()
    if (params?.completed !== undefined) q.set("completed", String(params.completed))
    if (params?.page) q.set("page", String(params.page))
    if (params?.size) q.set("size", String(params.size))
    return request<PaginatedVideoMeta>(`/api/programming/metadata/video?${q}`)
  },

  get: (id: number) =>
    request<VideoMetaOut>(`/api/programming/metadata/video/${id}`),

  update: (id: number, data: {
    video_resolution?: string; video_format?: string; codec_video?: string; codec_audio?: string;
    video_bitrate_kbps?: number; video_duration_seconds?: number; subtitle_languages?: string[];
    drm_type?: string; preview_clip_url?: string; completed: boolean
  }) =>
    request<VideoMetaOut>(`/api/programming/metadata/video/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  bulkComplete: (content_ids: number[]) =>
    request<{ updated: number }>("/api/programming/metadata/video/bulk-complete", {
      method: "POST",
      body: JSON.stringify({ content_ids }),
    }),
}

// ── serviceReadinessApi ───────────────────────────────────────

export const serviceReadinessApi = {
  get: () => request<ServiceReadinessStats>("/api/programming/metadata/service-readiness"),
}
