/**
 * API 클라이언트 — FastAPI 백엔드 통신
 * Base URL: NEXT_PUBLIC_API_URL (기본 http://localhost:8000)
 */

export const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

export function resolvePosterUrl(url: string | null | undefined): string | null {
  if (!url) return null
  if (url.startsWith("http")) return url
  return `${BASE}${url}`
}

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

export type ContentStatus = "raw" | "enriched" | "ai" | "review" | "approved" | "rejected"
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
  poster_url?: string | null
  parent_id?: number | null
  season_number?: number | null
  episode_number?: number | null
  current_stage?: string | null   // 위치(stage) SSOT — 두 축(위치/완료) 중 위치
}

export interface MetadataOut {
  id: number
  content_id: number
  cp_synopsis: string | null
  cp_genre: string | null
  cp_tags: string[] | null
  ai_synopsis: string | null
  short_synopsis: string | null
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
  synopsis_ko: string | null
  synopsis_en: string | null
  total_seasons: number | null
  total_episodes: number | null
  first_air_date: string | null
  last_air_date: string | null
  air_status: string | null
  networks: string[] | null
}

export interface PersonOut {
  id: number
  name_ko: string
  name_en: string | null
  tmdb_person_id: number | null
}

export interface ContentCreditOut {
  id: number
  person: PersonOut
  role: string
  character_name: string | null
  cast_order: number | null
  source: string | null
}

export interface GenreOut {
  id: number
  code: string
  name_ko: string
}

export interface ContentGenreOut {
  genre: GenreOut
  is_primary: boolean
  source: string | null
}

export interface ContentDetail extends ContentOut {
  metadata_record: MetadataOut | null
  genres: ContentGenreOut[]
  credits: ContentCreditOut[]
  external_sources: ExternalSourceOut[]
  inherited_meta?: Record<string, unknown> | null
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
  inherited_meta?: Record<string, unknown> | null
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

// ── dev-ui-api-wiring 타입 (18개 신규 엔드포인트) ─────────────

// Bulk Actions (5개)
export interface BulkActionConsolidatedRequest {
  ids: number[]
  reason?: string
  filter_query?: Record<string, unknown>
}

export interface BulkActionResponse {
  job_id: string
  ids_accepted: number
  ids_rejected: number
  errors?: string[]
}

export interface JobStatusOut {
  id: number
  status: string
  action_type: string
  target_count: number
  completed_count: number
  failed_count: number
  progress_percent: number
  created_at: string
  started_at?: string | null
  completed_at?: string | null
  errors?: string[]
}

export interface UndoActionRequest {
  action_id: string
}

export interface UndoActionOut {
  id: number
  status: string
  reverted_count: number
}

// Content Detail (3개 추가 + PromoteAIResultOut)
export interface PromoteAIResultOut {
  id: number
  is_final: boolean
}

export interface ChangeLogItem {
  field: string
  old_value?: unknown
  new_value?: unknown
  changed_by?: string
  changed_at: string
}

export interface ContentChangelogOut {
  changes: ChangeLogItem[]
}

// Content Add Flow (4개)
export interface EnrichPreviewRequest {
  fields?: string[]
}

export interface EnrichPreviewOut {
  enriched_fields: Record<string, unknown>
  external_sources: ExternalSourceItem[]
  errors?: string[]
}

export interface BatchPreviewOut {
  valid_count: number
  missing_count: number
  error_count: number
  duplicate_count: number
  estimated_cost: string
  estimated_duration_seconds: number
}

export interface SourceResult {
  title: string
  year?: number
  source: string
  match_percent: number
  director?: string
  metadata: Record<string, unknown>
}

export interface SourceSearchOut {
  results: SourceResult[]
  errors?: string[]
}

export interface CreateFromSourcesRequest {
  source_id: number
  selected_fields: string[]
  cp_name: string
}

export interface CreateFromSourcesOut {
  id: number
  title: string
  status: string
}

// ── 메타 보강 추천 타입 ───────────────────────────────────

export interface SourceFieldRec {
  source_type: string
  source_id: number
  value: string
  confidence: number
}

export interface FieldRecommendation {
  field: string
  status: "auto" | "conflict"
  recommendations: SourceFieldRec[]
  ai_synthesis: SourceFieldRec | null
}

export interface RecommendationsOut {
  content_id: number
  missing_fields: string[]
  auto_fill: FieldRecommendation[]
  conflicts: FieldRecommendation[]
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

  // 수동 필드 값 적용 — manual source 머지 후 resolve. WebSearch로 찾은 값 직접 입력용.
  updateContent: (id: number, data: {
    title?: string; synopsis?: string; cast?: string; directors?: string; genres?: string;
    country?: string; runtime?: number; rating_age?: string; poster_url?: string; production_year?: number
  }) =>
    request<ContentDetail>(`/api/programming/metadata/contents/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
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
  uploadBatch: (formData: FormData, autoProcess?: boolean) => {
    const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
    const url = new URL(`${BASE_URL}/api/programming/metadata/upload/batch`)
    if (autoProcess !== undefined) url.searchParams.set("auto_process", String(autoProcess))
    return fetch(url.toString(), {
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

  // ── AI Review Queue ───────────────────────────────────────
  getAiReviewQueue: (params?: {
    status?: string
    input_type?: string
    metadata_status?: string
    poster_status?: string
    risk_level?: string
    include_dam?: boolean
    page?: number
    size?: number
  }) => {
    const q = new URLSearchParams()
    if (params?.status) q.set("status", params.status)
    if (params?.input_type) q.set("input_type", params.input_type)
    if (params?.metadata_status) q.set("metadata_status", params.metadata_status)
    if (params?.poster_status) q.set("poster_status", params.poster_status)
    if (params?.risk_level) q.set("risk_level", params.risk_level)
    if (params?.include_dam != null) q.set("include_dam", String(params.include_dam))
    if (params?.page) q.set("page", String(params.page))
    if (params?.size) q.set("size", String(params.size))
    return request<PaginatedAiReviewQueue>(`/api/programming/metadata/ai-review-queue?${q}`)
  },

  // ── dev-ui-api-wiring: 18개 신규 함수 ─────────────────────

  // Bulk Actions (5개)
  bulkReprocess: (data: BulkActionConsolidatedRequest) =>
    request<BulkActionResponse>("/api/programming/metadata/bulk/reprocess", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  bulkEnrich: (data: BulkActionConsolidatedRequest) =>
    request<BulkActionResponse>("/api/programming/metadata/bulk/enrich", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  bulkProcess: (data: BulkActionConsolidatedRequest) =>
    request<BulkActionResponse>("/api/programming/metadata/bulk/process", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  bulkRecall: (data: BulkActionConsolidatedRequest) =>
    request<BulkActionResponse>("/api/programming/metadata/bulk/recall", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  bulkProcessAi: (data: BulkActionConsolidatedRequest) =>
    request<BulkActionResponse>("/api/programming/metadata/test/pipeline/process-ai", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  bulkDelete: (data: BulkActionConsolidatedRequest) =>
    request<BulkActionResponse>("/api/programming/metadata/bulk", {
      method: "DELETE",
      body: JSON.stringify(data),
    }),

  // Job (3개)
  getJobStatus: (jobId: string | number) =>
    request<JobStatusOut>(`/api/programming/metadata/contents/jobs/${jobId}`),

  bulkUndo: (data: UndoActionRequest) =>
    request<UndoActionOut>("/api/programming/metadata/bulk/undo", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  retryFailedJob: (jobId: string | number) =>
    request<BulkActionResponse>(
      `/api/programming/metadata/contents/jobs/${jobId}/retry-failed`,
      {
        method: "POST",
      }
    ),

  // Content Detail (6개)
  promoteAIResult: (contentId: number, resultId: number) =>
    request<PromoteAIResultOut>(
      `/api/programming/metadata/contents/${contentId}/ai-results/${resultId}/promote`,
      {
        method: "POST",
      }
    ),

  getAiResults: (contentId: number) =>
    request<ContentAIResult[]>(
      `/api/programming/metadata/contents/${contentId}/ai-results`
    ),

  partialReprocess: (contentId: number, fields?: string[]) =>
    request<JobStatusOut>(`/api/programming/metadata/contents/${contentId}/process`, {
      method: "POST",
      body: JSON.stringify({ fields }),
    }),

  applyExternalFields: (
    contentId: number,
    sourceId: number,
    fields?: string[]
  ) =>
    request<unknown>(
      `/api/programming/metadata/contents/${contentId}/external/${sourceId}/apply-fields`,
      {
        method: "POST",
        body: JSON.stringify({ fields }),
      }
    ),

  getChangelog: (contentId: number) =>
    request<ContentChangelogOut>(
      `/api/programming/metadata/contents/${contentId}/changelog`
    ),

  lockFields: (contentId: number, fields: string[], reason?: string) =>
    request<unknown>(`/api/programming/metadata/contents/${contentId}/lock`, {
      method: "POST",
      body: JSON.stringify({ fields, reason }),
    }),

  requestPreviewClip: (contentId: number) =>
    request<unknown>(
      `/api/programming/metadata/contents/${contentId}/preview-clip`,
      {
        method: "POST",
      }
    ),

  // Content Add Flow (4개)
  enrichPreview: (contentId: number, data: EnrichPreviewRequest) =>
    request<EnrichPreviewOut>(`/api/programming/metadata/contents/${contentId}/enrich`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  batchPreviewCsv: (formData: FormData) => {
    const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
    return fetch(`${BASE_URL}/api/programming/metadata/upload/batch?dry_run=true`, {
      method: "POST",
      body: formData,
    }).then(async (res) => {
      if (!res.ok) {
        const detail = await res.text()
        throw new Error(`API upload/batch (dry_run) → ${res.status}: ${detail}`)
      }
      return res.json() as Promise<BatchPreviewOut>
    })
  },

  sourcesSearch: (query: string, sources?: string[]) => {
    const params = new URLSearchParams()
    params.append("query", query)
    if (sources?.length) {
      params.append("sources", sources.join(","))
    }
    return request<SourceSearchOut>(
      `/api/programming/metadata/sources/search?${params.toString()}`
    )
  },

  createFromSources: (data: CreateFromSourcesRequest) =>
    request<CreateFromSourcesOut>("/api/programming/metadata/contents/from_sources", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getDamAssets: (contentId: number) =>
    request<DamAssetsOut>(`/api/meta-core/contents/${contentId}/dam-assets`),

  getRecommendations: (contentId: number) =>
    request<RecommendationsOut>(
      `/api/programming/metadata/contents/${contentId}/recommendations`
    ),

  getTimeline: (id: number) =>
    request<ContentTimeline>(`/api/programming/metadata/contents/${id}/timeline`),

  getTimelineV2: (id: number) =>
    request<ContentTimelineV2>(`/api/programming/metadata/contents/${id}/timeline`),

  getAiTaskSettings: () =>
    request<AiTaskSetting[]>("/api/programming/metadata/ai-tasks/settings"),

  patchAiTaskSetting: (taskName: string, enabled: boolean) =>
    request<AiTaskSetting>(
      `/api/programming/metadata/ai-tasks/settings/${taskName}?enabled=${enabled}`,
      { method: "PATCH" }
    ),

  getEnrichPolicy: () =>
    request<EnrichPolicy>("/api/programming/metadata/ai-tasks/enrich-policy"),
  patchEnrichPolicy: (body: Partial<EnrichPolicy>) =>
    request<EnrichPolicy>("/api/programming/metadata/ai-tasks/enrich-policy", {
      method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    }),
  getStageAutoPolicy: () =>
    request<StageAutoPolicy>("/api/programming/metadata/ai-tasks/stage-auto-policy"),
  patchStageAutoPolicy: (body: Partial<StageAutoPolicy>) =>
    request<StageAutoPolicy>("/api/programming/metadata/ai-tasks/stage-auto-policy", {
      method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    }),
  websearchQuery: (query: string, num = 6) =>
    request<WebSearchResultItem[]>("/api/programming/metadata/ai-tasks/websearch-query", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query, num }),
    }),
}

export interface WebSearchResultItem { title: string; url: string; domain: string; snippet: string; provider: string }

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
  text_rate: number
  image_rate: number
  video_rate: number
  all_rate: number
}

export interface TextMetaSuggestion {
  source: "tmdb" | "kobis" | "ai"
  synopsis: string | null
  genre_primary: string | null
  genre_secondary: string | null
  mood_tags: string[] | null
  rating_suggestion: string | null
}

export interface ImageSuggestion {
  source: string
  image_type: string
  url: string
  width: number | null
  height: number | null
}

export interface ImageMetaSuggestions {
  content_id: number
  suggestions: ImageSuggestion[]
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

  suggest: (id: number) =>
    request<TextMetaSuggestion>(`/api/programming/metadata/text/${id}/suggest`),
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

  bulkComplete: (content_ids: number[]) =>
    request<{ updated: number }>("/api/programming/metadata/image/bulk-complete", {
      method: "POST",
      body: JSON.stringify({ content_ids }),
    }),

  suggest: (id: number) =>
    request<ImageMetaSuggestions>(`/api/programming/metadata/image/${id}/suggest`),

  uploadUrl: (
    contentId: number,
    data: { image_type: string; url: string; width?: number; height?: number; source?: string }
  ) => {
    const form = new FormData()
    form.append("image_type", data.image_type)
    form.append("url", data.url)
    if (data.width != null) form.append("width", String(data.width))
    if (data.height != null) form.append("height", String(data.height))
    form.append("source", data.source ?? "manual")
    const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
    return fetch(`${BASE_URL}/api/programming/metadata/image/${contentId}/upload`, {
      method: "POST",
      body: form,
    }).then(async (res) => {
      if (!res.ok) throw new Error(`image upload → ${res.status}: ${await res.text()}`)
      return res.json() as Promise<ImageMetaOut>
    })
  },
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

// ── tmdbApi ──────────────────────────────────────────────────

export interface TmdbSyncedItem {
  content_id: number
  title: string
  original_title: string | null
  content_type: string
  status: ContentStatus
  production_year: number | null
  cp_name: string | null
  tmdb_id: string
  poster_url: string | null
  match_confidence: number | null
  matched_at: string | null
  quality_score: number | null
}

export interface PaginatedTmdbItems {
  items: TmdbSyncedItem[]
  total: number
  page: number
  size: number
}

export const tmdbApi = {
  list: (params?: { content_type?: string; search?: string; page?: number; size?: number }) => {
    const q = new URLSearchParams()
    if (params?.content_type) q.set("content_type", params.content_type)
    if (params?.search) q.set("search", params.search)
    if (params?.page) q.set("page", String(params.page))
    if (params?.size) q.set("size", String(params.size))
    return request<PaginatedTmdbItems>(`/api/programming/metadata/tmdb?${q}`)
  },
}

// ── tmdbCacheApi ─────────────────────────────────────────

export interface TmdbCacheDailyPoint {
  date: string
  movies: number
  tv: number
  errors: number
}

export interface TmdbCacheStats {
  total_movies: number
  total_tv: number
  total_persons: number
  last_24h_movies_added: number
  last_24h_tv_added: number
  last_24h_errors: number
  last_7d_daily: TmdbCacheDailyPoint[]
  oldest_movie_year: number | null
  newest_movie_year: number | null
  last_run_at: string | null
  last_run_status: string | null
}

export interface TmdbSyncLogItem {
  id: number
  run_id: string
  source: string
  target_year: number | null
  target_date: string | null
  status: string
  started_at: string
  finished_at: string | null
  pages_fetched: number
  items_fetched: number
  items_inserted: number
  items_updated: number
  items_unchanged: number
  errors: number
}

export interface PaginatedSyncLog {
  items: TmdbSyncLogItem[]
  total: number
  page: number
  size: number
}

export interface TmdbCacheRecentItem {
  id: number
  title: string
  original_title: string | null
  release_date: string | null
  first_air_date: string | null
  popularity: number | null
  vote_average: number | null
  poster_url: string | null
  kind: "movie" | "tv"
  fetched_at: string
}

export interface PaginatedTmdbCache {
  items: TmdbCacheRecentItem[]
  total: number
  page: number
}

export const tmdbCacheApi = {
  getStats: () =>
    request<TmdbCacheStats>("/api/programming/metadata/tmdb-cache/stats"),

  getSyncLog: (params?: { source?: string; status?: string; page?: number; size?: number }) => {
    const q = new URLSearchParams()
    if (params?.source) q.set("source", params.source)
    if (params?.status) q.set("status", params.status)
    if (params?.page) q.set("page", String(params.page))
    if (params?.size) q.set("size", String(params.size))
    return request<PaginatedSyncLog>(`/api/programming/metadata/tmdb-cache/sync-log?${q}`)
  },

  getRecent: (params?: { kind?: string; limit?: number }) => {
    const q = new URLSearchParams()
    if (params?.kind) q.set("kind", params.kind)
    if (params?.limit) q.set("limit", String(params.limit))
    return request<TmdbCacheRecentItem[]>(`/api/programming/metadata/tmdb-cache/recent?${q}`)
  },

  search: (params?: { title?: string; kind?: string; page?: number; size?: number }) => {
    const q = new URLSearchParams()
    if (params?.title) q.set("title", params.title)
    if (params?.kind) q.set("kind", params.kind)
    if (params?.page) q.set("page", String(params.page))
    if (params?.size) q.set("size", String(params.size))
    return request<PaginatedTmdbCache>(`/api/programming/metadata/tmdb-cache/search?${q}`)
  },
}

// ── 외부 소스 (KOBIS / KMDB) ──────────────────────────────

export interface ExternalSourceDailyPoint {
  date: string
  count: number
  errors: number
}

export interface ExternalSourceStats {
  total_synced: number
  last_run_at: string | null
  last_run_status: string | null
  last_7d_daily: ExternalSourceDailyPoint[]
}

export interface ExternalSourceItem {
  id: number
  content_id: number | null
  source_type: string
  external_id: string | null
  title_on_source: string | null
  match_confidence: number | null
  matched_at: string | null
  created_at: string
}

export interface PaginatedExternalItems {
  items: ExternalSourceItem[]
  total: number
  page: number
  size: number
}

export interface MappedExternalItem {
  content_id: number
  title: string
  original_title: string | null
  content_type: string
  status: ContentStatus
  production_year: number | null
  cp_name: string | null
  external_id: string
  poster_url: string | null
  match_confidence: number | null
  matched_at: string | null
  quality_score: number | null
}

export interface PaginatedMappedItems {
  items: MappedExternalItem[]
  total: number
  page: number
  size: number
}

export interface KmdbCacheItem {
  docid: string
  title: string
  title_eng: string | null
  prod_year: number | null
  genre: string | null
  nation: string | null
  poster_url: string | null
  first_fetched_at: string
  last_fetched_at: string
}

export interface PaginatedKmdbCache {
  items: KmdbCacheItem[]
  total: number
  page: number
}

export interface DamAssetItem {
  asset_id: number
  filename: string
  folder_path?: string
  confidence?: number
  method?: string
  status?: string
  thumbnail_url: string
}

export interface DamAssetsOut {
  content_id: number
  assets: DamAssetItem[]
  dam_available: boolean
}

function makeExternalApi(source: "kobis" | "kmdb") {
  const base = `/api/programming/metadata/${source}`
  return {
    getStats: () => request<ExternalSourceStats>(`${base}/stats`),

    getSyncLog: (params?: { status?: string; page?: number; size?: number }) => {
      const q = new URLSearchParams()
      if (params?.status) q.set("status", params.status)
      if (params?.page) q.set("page", String(params.page))
      if (params?.size) q.set("size", String(params.size))
      return request<PaginatedSyncLog>(`${base}/sync-log?${q}`)
    },

    search: (params?: { title?: string; page?: number; size?: number }) => {
      const q = new URLSearchParams()
      if (params?.title) q.set("title", params.title)
      if (params?.page) q.set("page", String(params.page))
      if (params?.size) q.set("size", String(params.size))
      return request<PaginatedExternalItems>(`${base}/search?${q}`)
    },

    listContents: (params?: { title?: string; content_type?: string; page?: number; size?: number }) => {
      const q = new URLSearchParams()
      if (params?.title)        q.set("title",        params.title)
      if (params?.content_type) q.set("content_type", params.content_type)
      if (params?.page)         q.set("page",         String(params.page))
      if (params?.size)         q.set("size",         String(params.size))
      return request<PaginatedMappedItems>(`${base}/contents?${q}`)
    },
  }
}

export interface KobisCacheItem {
  movie_cd: string
  title: string
  title_en: string | null
  open_dt: string | null
  prdt_year: number | null
  rep_genre_nm: string | null
  rep_nation_nm: string | null
  first_fetched_at: string
  last_fetched_at: string
}

export interface PaginatedKobisCache {
  items: KobisCacheItem[]
  total: number
  page: number
}

export const kobisApi = {
  ...makeExternalApi("kobis"),
  getCache: (params?: { title?: string; year?: number; page?: number; size?: number }) => {
    const q = new URLSearchParams()
    if (params?.title) q.set("title", params.title)
    if (params?.year)  q.set("year",  String(params.year))
    if (params?.page)  q.set("page",  String(params.page))
    if (params?.size)  q.set("size",  String(params.size))
    return request<PaginatedKobisCache>(`/api/programming/metadata/kobis/cache?${q}`)
  },
}
export const kmdbApi = {
  ...makeExternalApi("kmdb"),
  getCache: (params?: { title?: string; year?: number; page?: number; size?: number }) => {
    const q = new URLSearchParams()
    if (params?.title) q.set("title", params.title)
    if (params?.year)  q.set("year",  String(params.year))
    if (params?.page)  q.set("page",  String(params.page))
    if (params?.size)  q.set("size",  String(params.size))
    return request<PaginatedKmdbCache>(`/api/programming/metadata/kmdb/cache?${q}`)
  },
}

// ── 포스터 추천 ────────────────────────────────────────────────────────────────

export interface PosterCandidateOut {
  id: number
  url: string
  source: string
  is_primary: boolean
  width?: number
  height?: number
}

export interface PosterRecommendResponse {
  content_id: number
  candidates: PosterCandidateOut[]
  added: number
}

export interface PosterSelectRequest {
  image_id: number
}

// ── AI Review Queue 타입 ──────────────────────────────────

export type AiReviewQueueRow = {
  content_id: number
  title: string
  content_type: string
  input_type: "bulk" | "manual" | "existing"
  content_status: string
  metadata_status: "missing" | "conflict" | "enhancement" | "clean"
  poster_status: "poster_ok" | "needs_selection" | "dam_match_found" | "external_only" | "no_candidate"
  dam_match_count: number
  risk_level: "low" | "medium" | "high"
  confidence: number
  updated_at: string
}

export type AiReviewQueueSummary = {
  total: number
  missing: number
  conflict: number
  needs_poster: number
  dam_match: number
  high_risk: number
}

export type PaginatedAiReviewQueue = {
  items: AiReviewQueueRow[]
  summary: AiReviewQueueSummary
  total: number
  page: number
  size: number
}

const _posterBase = (contentId: number) =>
  `/api/programming/metadata/contents/${contentId}`

export const posterRecommendApi = {
  recommend: (contentId: number) =>
    request<PosterRecommendResponse>(`${_posterBase(contentId)}/recommend-posters`, {
      method: "POST",
    }),

  getCandidates: (contentId: number) =>
    request<PosterCandidateOut[]>(`${_posterBase(contentId)}/poster-candidates`),

  selectPrimary: (contentId: number, imageId: number) =>
    request<PosterCandidateOut[]>(`${_posterBase(contentId)}/poster/select`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image_id: imageId } satisfies PosterSelectRequest),
    }),
}

// ── DAM API ───────────────────────────────────────────────

export const damApi = {
  getAssetsByContent: (contentId: number) =>
    request<DamAssetsOut>(`/api/meta-core/contents/${contentId}/dam-assets`),
}

// ── Pipeline Test Console API (dev only) ─────────────────

export interface PipelineTestSeedResult {
  movie_complete: number
  movie_incomplete: number
  series_complete: number
  series_incomplete: number
  conflict: number
  total_root: number
  skipped_in_pipeline: number
  skipped_registered: number
}

export interface PipelineTestCleanup {
  deleted: number
  dry_run: boolean
}

export interface PipelineTestStageSummary {
  by_status: Record<string, number>
  by_stage: Record<string, number>   // 위치(bucket) 기준 — 카드 카운트용
  by_type: Record<string, number>
  total: number
  last_seeded_at: string | null
}

export interface TimelineStage {
  stage: number
  name: string
  at: string | null
  status: "done" | "active" | "pending"
  detail: Record<string, unknown>
}

export interface ContentTimeline {
  content_id: number
  title: string
  content_type: string
  current_status: string
  stages: TimelineStage[]
}

// ── ContentTimelineV2 (ADR-006 9-stage) ──────────────────────

export interface StageSourceOut {
  source: string
  result: "ok" | "hit" | "miss" | "error" | "skipped"
  latency_ms: number | null
  detail: Record<string, unknown> | null
}

export interface StageOut {
  stage: string
  status: "done" | "active" | "pending"
  at: string | null
  duration_ms: number | null
  sources: StageSourceOut[]
}

export interface ContentTimelineV2 extends ContentTimeline {
  current_stage: string | null
  intake_channel: string | null
  pipeline_stages: StageOut[]
}

// ── 파이프라인 보드 타입 (ADR-006) ────────────────────────────

export interface ChannelStats {
  count: number
  last_at: string | null
  status: "ok" | "stale"
}

export interface StageSourceProgress {
  source: string
  result: "ok" | "hit" | "miss" | "error" | "pending"
  latency_ms: number | null
}

export interface StageContentItem {
  id: number
  title: string
  entered_at: string | null
  seconds_in_stage: number | null
  sources: StageSourceProgress[]
}

export interface StageCount {
  count: number
  total_published?: number | null
  top_contents: StageContentItem[]
  avg_seconds?: number | null
  error_count: number
}

export interface GateInfo {
  mode: "manual" | "auto"
  pending: number
}

export interface AlertInfo {
  failed_queue: number
  rejected_archive: number
  enrichment_blocked: number
}

export interface PipelineBoardResponse {
  channels_24h: Record<string, ChannelStats>
  stages: Record<string, StageCount>
  gates: Record<string, GateInfo>
  alerts: AlertInfo
}

export interface StageEventOut {
  id: number
  content_id: number
  stage: string
  event_type: string
  source: string | null
  started_at: string
  actor: string
  latency_ms: number | null
  error_text: string | null
}

export interface PaginatedStageEvents {
  items: StageEventOut[]
  next_cursor: number | null
  total: number
}

export interface GateAdvanceRequest {
  content_ids?: number[]
  simulate?: boolean
  if_match?: number | null
}

export interface GateAdvanceResponse {
  advanced: number
  skipped: number
  failed: number
  next_stage: string
  events: unknown[]
}

export interface AiTaskSetting {
  task_name: string
  enabled: boolean
  updated_at?: string
}

export interface ContentAIResult {
  id: number
  content_id: number
  engine: string
  task_type: string
  result_json: Record<string, unknown> | null
  quality_score: number | null
  is_final: boolean
  error_message: string | null
  input_hash: string | null
  processed_at: string
}

export const pipelineApi = {
  getBoard: () =>
    request<PipelineBoardResponse>("/api/pipeline/board"),

  getEvents: (params?: { since?: number; limit?: number; stage?: string; source?: string; event_type?: string }) => {
    const q = new URLSearchParams()
    if (params?.since) q.set("since", String(params.since))
    if (params?.limit) q.set("limit", String(params.limit))
    if (params?.stage) q.set("stage", params.stage)
    if (params?.source) q.set("source", params.source)
    if (params?.event_type) q.set("event_type", params.event_type)
    return request<PaginatedStageEvents>(`/api/pipeline/events?${q}`)
  },

  advanceGate: (gateId: string, req: GateAdvanceRequest) =>
    request<GateAdvanceResponse>(`/api/pipeline/gate/${gateId}/advance`, {
      method: "POST",
      body: JSON.stringify(req),
    }),

  toggleGateMode: (gateId: string, mode: "manual" | "auto") =>
    request<{ gate_id: string; mode: "manual" | "auto" }>(`/api/pipeline/gate/${gateId}/mode`, {
      method: "POST",
      body: JSON.stringify({ mode }),
    }),
}

const _PT_TOKEN = process.env.NEXT_PUBLIC_PIPELINE_TEST_TOKEN ?? ""

function requestTest<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(_PT_TOKEN ? { "X-Pipeline-Test-Token": _PT_TOKEN } : {}),
  }
  const { headers: _h, ...rest } = init ?? {}
  return fetch(`${BASE}${path}`, { headers, ...rest }).then(async (res) => {
    if (!res.ok) {
      const detail = await res.text()
      throw new Error(`Test API ${path} → ${res.status}: ${detail}`)
    }
    return res.json() as Promise<T>
  })
}

export interface PipelineEventLog {
  id: number
  content_id: number
  stage: string
  event_type: string
  source: string | null
  started_at: string
  ended_at: string | null
  latency_ms: number | null
  error_text: string | null
  actor: string
}

// ADR-009 response types
export interface AdvanceResponse { advanced: number; skipped: number; results: Record<number, string> }
export interface ReviewActionResponse { processed: number; skipped: number; results: Record<number, string> }
export interface EnrichSourceResponse { content_id: number; source: string; candidates_upserted: number; suggestions_created: number; sources_hit: string[]; sources_skipped: string[]; status_unchanged: string }
export interface AiTaskResponse { content_id: number; task_name: string; status: string; engine: string | null; result_preview: string | null; status_unchanged: string }
export interface EnrichAutofillResponse { content_id: number; enriched_sources: string[]; filled_fields: string[]; skipped_fields: string[]; status_unchanged: string }
export interface AiAutofillResponse { content_id: number; rag_sources: string[]; ai_tasks: Record<string, string>; filled_fields: string[]; skipped_fields: string[]; status_unchanged: string }
export interface EnrichPolicy { use_cache_db: boolean; confidence_threshold: number; use_websearch: boolean }
export interface StageAutoPolicy {
  s1_auto: boolean; s2_auto: boolean; s3_auto: boolean
  s4_auto: boolean; s5_auto: boolean; s6_auto: boolean
  s4_quality_threshold: number
  // ADR-010 워커 제어
  auto_tick_enabled?: boolean
  batch_size?: number
  ai_concurrency?: number
  ai_visibility_timeout?: number
}

export interface AutoBucketStatus {
  pending: number
  in_flight: number
  held: number
  skipped: number
}

export interface AutoWorkerStatus {
  tick_enabled: boolean
  s1_auto: boolean; s2_auto: boolean; s3_auto: boolean; s4_auto: boolean
  buckets: Record<string, AutoBucketStatus>
}

export interface AutoLogEvent {
  id: number
  content_id: number
  title: string
  stage: string | null
  event_type: string | null
  actor: string
  at: string | null
}
export interface ReferenceExtractResponse {
  content_id: number; title_used: string; year_used: number | null
  wikidata_facts: Record<string, unknown>; wikidata_url: string | null
  wikipedia_text: string | null; wikipedia_url: string | null; wikipedia_lang: string | null
  sources_hit: string[]; sources_skipped: string[]
}

export interface RevertResponse {
  reverted: number
  skipped: number
  results: Record<number, string>
}

export const pipelineTestApi = {
  seed: () =>
    requestTest<PipelineTestSeedResult>("/api/test/pipeline/seed", { method: "POST" }),
  cleanup: (dry_run = false) =>
    requestTest<PipelineTestCleanup>(
      `/api/test/pipeline/cleanup?dry_run=${dry_run}`,
      { method: "POST" }
    ),
  cleanupStage: (ids: number[], dry_run = false) =>
    requestTest<PipelineTestCleanup>(
      `/api/test/pipeline/cleanup-stage?dry_run=${dry_run}`,
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ids }) }
    ),
  revert: (ids: number[]) =>
    requestTest<RevertResponse>("/api/test/pipeline/revert", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ids }),
    }),
  summary: () =>
    requestTest<PipelineTestStageSummary>("/api/test/pipeline/summary"),
  events: (content_id?: number, limit = 30) => {
    const q = new URLSearchParams()
    if (content_id) q.set("content_id", String(content_id))
    q.set("limit", String(limit))
    return requestTest<PipelineEventLog[]>(`/api/test/pipeline/events?${q}`)
  },
  advance: (ids: number[]) =>
    requestTest<AdvanceResponse>("/api/test/pipeline/advance", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ids }),
    }),
  enrichSource: (content_id: number, source: "tmdb" | "kmdb") =>
    requestTest<EnrichSourceResponse>("/api/test/pipeline/enrich-source", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content_id, source }),
    }),
  runAiTask: (content_id: number, task_name: string) =>
    requestTest<AiTaskResponse>("/api/test/pipeline/run-ai-task", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content_id, task_name }),
    }),
  enrichAutofill: (content_id: number) =>
    requestTest<EnrichAutofillResponse>("/api/test/pipeline/enrich-autofill", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content_id }),
    }),
  aiAutofill: (content_id: number) =>
    requestTest<AiAutofillResponse>("/api/test/pipeline/ai-autofill", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content_id }),
    }),
  listAiTasks: () =>
    requestTest<{ tasks: string[] }>("/api/test/pipeline/ai-tasks"),
  referenceExtract: (content_id: number) =>
    requestTest<ReferenceExtractResponse>("/api/test/pipeline/reference-extract", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content_id }),
    }),
  approve: (ids: number[]) =>
    requestTest<ReviewActionResponse>("/api/test/pipeline/approve", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ids }),
    }),
  reject: (ids: number[]) =>
    requestTest<ReviewActionResponse>("/api/test/pipeline/reject", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ids }),
    }),
  reReview: (ids: number[]) =>
    requestTest<ReviewActionResponse>("/api/test/pipeline/re-review", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ids }),
    }),
  resumeAuto: (ids: number[]) =>
    requestTest<{ resumed: number; results: Record<number, string> }>("/api/test/pipeline/resume-auto", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ids }),
    }),
  autoStatus: () =>
    requestTest<AutoWorkerStatus>("/api/test/pipeline/auto-status"),
  autoLog: (limit = 20) =>
    requestTest<{ events: AutoLogEvent[] }>(`/api/test/pipeline/auto-log?limit=${limit}`),
}

// ── Distribution / Curation ───────────────────────────────

export interface ServiceCategoryOut {
  id: number
  name: string
  category_type: string
  platform: string
  position: number
  is_active: boolean
  headline_copy: string | null
  sub_copy: string | null
  theme_features: Record<string, unknown> | null
  source_mode: string        // "manual" | "ai_proposed" | "external_imported"
  reference_external_id: string | null
  is_draft: boolean
  created_at: string | null
  updated_at: string | null
}

export interface ServiceCategoryItemOut {
  id: number
  category_id: number
  content_id: number
  content_title: string | null
  rank: number
  score: number | null
  added_at: string | null
}

export interface ServiceCategoryWithItemsOut extends ServiceCategoryOut {
  items: ServiceCategoryItemOut[]
}

export interface ServiceCategoryCreate {
  name: string
  category_type: string
  platform: string
  position?: number
  is_active?: boolean
  headline_copy?: string | null
  sub_copy?: string | null
  theme_features?: Record<string, unknown> | null
  source_mode?: string
  reference_external_id?: string | null
  is_draft?: boolean
}

export interface ServiceCategoryUpdate {
  name?: string
  category_type?: string
  platform?: string
  position?: number
  is_active?: boolean
  headline_copy?: string | null
  sub_copy?: string | null
  theme_features?: Record<string, unknown> | null
  source_mode?: string
  reference_external_id?: string | null
  is_draft?: boolean
}

export interface ServiceCategoryItemCreate {
  content_id: number
  rank: number
  score?: number | null
}

// 큐레이션 워크벤치 — 외부 OTT 참고 (Step 7·8)
export interface OttItemOut {
  title: string
  rank: number
  production_year: number | null
  external_id: string | null
  content_id?: number | null  // 영속 데이터 읽을 때 ott/matcher resolve 결과 (Step 8)
}

export interface OttSectionCardOut {
  section_id: string
  name: string
  category_type: string
  channel: string
  item_count: number
  items: OttItemOut[]
}

export interface ExternalReferencesResponse {
  sections: OttSectionCardOut[]
  total_sections: number
}

// 큐레이션 워크벤치 — AI 위저드 Step 3·4 (Step 9)
export interface CopyCandidateOut {
  rank: number
  headline_copy: string
  sub_copy: string | null
  source: string  // "ai_proposed" | "external_imported"
  reasoning: string | null
}

export interface ProposeCopyResponse {
  candidates: CopyCandidateOut[]
  engine_used: string | null
}

export interface ContentMatchCandidateOut {
  content_id: number
  title: string
  content_type: string
  production_year: number | null
  runtime_minutes: number | null
  score: number
  score_breakdown: Record<string, number>
}

export interface MatchContentsResponse {
  items: ContentMatchCandidateOut[]
  total: number
  theme_features: Record<string, unknown>
}

export const distributionApi = {
  getCategories: (params?: { platform?: string; is_active?: boolean }) => {
    const q = new URLSearchParams()
    if (params?.platform) q.set("platform", params.platform)
    if (params?.is_active != null) q.set("is_active", String(params.is_active))
    const qs = q.toString()
    return request<ServiceCategoryOut[]>(`/api/distribution/categories${qs ? `?${qs}` : ""}`)
  },

  createCategory: (data: ServiceCategoryCreate) =>
    request<ServiceCategoryOut>("/api/distribution/categories", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getCategory: (id: number) =>
    request<ServiceCategoryWithItemsOut>(`/api/distribution/categories/${id}`),

  updateCategory: (id: number, data: ServiceCategoryUpdate) =>
    request<ServiceCategoryOut>(`/api/distribution/categories/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  deleteCategory: (id: number) =>
    request<void>(`/api/distribution/categories/${id}`, { method: "DELETE" }),

  addItem: (categoryId: number, data: ServiceCategoryItemCreate) =>
    request<ServiceCategoryItemOut>(`/api/distribution/categories/${categoryId}/items`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  removeItem: (categoryId: number, itemId: number) =>
    request<void>(`/api/distribution/categories/${categoryId}/items/${itemId}`, {
      method: "DELETE",
    }),

  reorderItems: (categoryId: number, items: { id: number; rank: number }[]) =>
    request<void>(`/api/distribution/categories/${categoryId}/items/reorder`, {
      method: "POST",
      body: JSON.stringify({ items }),
    }),

  getExternalReferences: (channel?: string) => {
    const qs = channel ? `?channel=${encodeURIComponent(channel)}` : ""
    return request<ExternalReferencesResponse>(
      `/api/distribution/curations/external-references${qs}`
    )
  },

  proposeCopy: (data: {
    theme_features: Record<string, unknown>
    selected_section_names?: string[]
    limit?: number
  }) =>
    request<ProposeCopyResponse>("/api/distribution/curations/propose-copy", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  matchContents: (data: {
    theme_features: Record<string, unknown>
    external_titles?: string[]
    external_content_ids?: number[]
    limit?: number
  }) =>
    request<MatchContentsResponse>("/api/distribution/curations/match-contents", {
      method: "POST",
      body: JSON.stringify(data),
    }),
}

// ── 카탈로그 카테고리 트리 (1.2.1) ───────────────────────────────────────────

export interface CategorySet {
  id: number
  name: string
  description: string | null
  category_count: number
  created_at: string | null
  updated_at: string | null
}

export interface CategoryNode {
  id: number
  name: string
  slug: string | null
  depth: number
  sort_order: number
  is_active: boolean
  parent_id: number | null
  created_at: string | null
  updated_at: string | null
  children: CategoryNode[]
  content_count?: number
}

export interface CategoryCreateRequest {
  name: string
  parent_id?: number | null
  sort_order?: number | null
  slug?: string | null
}

export interface CategoryUpdateRequest {
  name?: string
  slug?: string | null
  is_active?: boolean
  sort_order?: number
}

export interface BulkCategoryNode {
  name: string
  children?: BulkCategoryNode[]
}

export interface BulkCategoryResult {
  created: number
  skipped: number
  tree: CategoryNode[]
}

export type Quality = "SD" | "HD" | "FHD" | "UHD_4K"
export type PurchaseType = "single" | "series_episode" | "season_package" | "est_single" | "est_season"

export type PriceMatrix = Record<PurchaseType, Record<Quality, number>>

export interface PricingOut {
  id: number
  content_id: number
  quality: Quality
  purchase_type: PurchaseType
  price: number
  currency: string
  is_active: boolean
  created_at: string | null
  updated_at: string | null
}

export interface PriceChangeLog {
  id: number
  content_id: number
  quality: Quality
  purchase_type: PurchaseType
  old_price: number | null
  new_price: number
  changed_by: string | null
  reason: string | null
  batch_id: string | null
  created_at: string | null
}

export interface HoldbackPolicy {
  id: number
  cp_name: string
  window_no: number
  name: string
  offset_days_start: number
  offset_days_end: number | null
  price_rule: string
  is_active: boolean
  created_at: string | null
  updated_at: string | null
}

export interface HoldbackSchedule {
  id: number
  content_id: number
  window_no: number
  start_date: string
  end_date: string | null
  price_id: number | null
  source_policy_id: number | null
  status: string
  created_at: string | null
  updated_at: string | null
}

export const catalogApi = {
  getTree: (opts?: { root_id?: number; counts?: boolean }) => {
    const qs = new URLSearchParams()
    if (opts?.root_id != null) qs.set("root_id", String(opts.root_id))
    if (opts?.counts) qs.set("counts", "true")
    const q = qs.toString()
    return request<CategoryNode[]>(
      `/api/programming/catalog/categories/tree${q ? `?${q}` : ""}`
    )
  },

  createCategory: (data: CategoryCreateRequest) =>
    request<CategoryNode>("/api/programming/catalog/categories", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateCategory: (id: number, data: CategoryUpdateRequest) =>
    request<CategoryNode>(`/api/programming/catalog/categories/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  moveCategory: (id: number, data: { new_parent_id: number | null; new_sort_order?: number | null }) =>
    request<CategoryNode>(`/api/programming/catalog/categories/${id}/move`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  bulkCreate: (data: { nodes: BulkCategoryNode[]; parent_id?: number | null }) =>
    request<BulkCategoryResult>("/api/programming/catalog/categories/bulk", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  deleteCategory: (id: number, cascade = false) =>
    request<void>(
      `/api/programming/catalog/categories/${id}${cascade ? "?cascade=true" : ""}`,
      { method: "DELETE" }
    ),

  // ── 카테고리 세트 ────────────────────────────────────────────────────────────

  listSets: () =>
    request<CategorySet[]>("/api/programming/catalog/sets"),

  commitSet: (data: { name: string; description?: string }) =>
    request<CategorySet>("/api/programming/catalog/sets", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateSet: (id: number, data: { name?: string; description?: string }) =>
    request<CategorySet>(`/api/programming/catalog/sets/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  deleteSet: (id: number) =>
    request<void>(`/api/programming/catalog/sets/${id}`, { method: "DELETE" }),

  loadSet: (id: number) =>
    request<{ cleared: number; loaded: number }>(`/api/programming/catalog/sets/${id}/load`, {
      method: "POST",
    }),

  clearDraft: () =>
    request<{ cleared: number }>("/api/programming/catalog/sets/clear-draft", {
      method: "POST",
    }),

  getSetTree: (setId: number) =>
    request<CategoryNode[]>(`/api/programming/catalog/sets/${setId}/tree`),

  // ── 가격 정책 ──────────────────────────────────────────────────────────────

  getPriceMatrix: (contentId: number) =>
    request<PriceMatrix>(`/api/programming/catalog/contents/${contentId}/pricing`),

  setPrice: (contentId: number, data: {
    quality: Quality; purchase_type: PurchaseType; price: number
    changed_by?: string; reason?: string
  }) =>
    request<PricingOut>(`/api/programming/catalog/contents/${contentId}/pricing`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  bulkUpdatePricing: (data: {
    items: Array<{ content_id: number; quality: Quality; purchase_type: PurchaseType; price: number }>
    changed_by?: string; reason?: string
  }) =>
    request<PricingOut[]>("/api/programming/catalog/pricing/bulk", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  listPriceChanges: (contentId: number, limit = 50) =>
    request<PriceChangeLog[]>(
      `/api/programming/catalog/contents/${contentId}/price-changes?limit=${limit}`
    ),

  deletePrice: (contentId: number, quality: Quality, purchaseType: PurchaseType) =>
    request<void>(
      `/api/programming/catalog/contents/${contentId}/pricing?quality=${quality}&purchase_type=${purchaseType}`,
      { method: "DELETE" }
    ),

  // ── 홀드백 ────────────────────────────────────────────────────────────────

  listHoldbackPolicies: (cpName?: string) => {
    const qs = cpName ? `?cp_name=${encodeURIComponent(cpName)}` : ""
    return request<HoldbackPolicy[]>(`/api/programming/catalog/holdback/policies${qs}`)
  },

  upsertHoldbackPolicy: (data: {
    cp_name: string; window_no: number; name: string
    offset_days_start: number; offset_days_end?: number | null
    price_rule: string; is_active?: boolean
  }) =>
    request<HoldbackPolicy>("/api/programming/catalog/holdback/policies", {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  deleteHoldbackPolicy: (policyId: number) =>
    request<void>(`/api/programming/catalog/holdback/policies/${policyId}`, {
      method: "DELETE",
    }),

  applyHoldback: (contentId: number, baseDate: string) =>
    request<HoldbackSchedule[]>(
      `/api/programming/catalog/contents/${contentId}/holdback/apply`,
      { method: "POST", body: JSON.stringify({ base_date: baseDate }) }
    ),

  listHoldbackSchedules: (contentId: number) =>
    request<HoldbackSchedule[]>(`/api/programming/catalog/contents/${contentId}/holdback`),

  activateWindow: (
    contentId: number,
    windowNo: number,
    data: { quality?: Quality; purchase_type?: PurchaseType; price?: number; changed_by?: string }
  ) =>
    request<HoldbackSchedule>(
      `/api/programming/catalog/contents/${contentId}/holdback/${windowNo}/activate`,
      { method: "POST", body: JSON.stringify(data) }
    ),

  holdbackCalendar: (start: string, end: string) =>
    request<HoldbackSchedule[]>(
      `/api/programming/catalog/holdback/calendar?start=${start}&end=${end}`
    ),
}
