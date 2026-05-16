/**
 * WebSearch Monitoring API client
 * Phase D monitoring endpoints
 */

export interface ProviderQuota {
  provider: string
  daily_limit: number
  used_today: number
  remaining: number
  percent_used: number
  exhausted_until?: string | null
}

export interface QuotaStats {
  as_of: string
  providers: ProviderQuota[]
}

export interface CacheStats {
  period_days: number
  total_queries: number
  cache_hits: number
  cache_misses: number
  hit_rate: number
  by_provider: Array<{
    provider: string
    hits: number
    misses: number
  }>
}

export interface RecentCall {
  timestamp: string
  provider: string
  query_preview: string
  cache_hit: boolean
  status: 'success' | 'error'
}

export interface RecentCalls {
  total: number
  limit: number
  calls: RecentCall[]
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api'

export const webSearchApi = {
  async getQuota(): Promise<QuotaStats> {
    const res = await fetch(`${API_BASE}/meta-core/web-search/quota`)
    if (!res.ok) throw new Error('Failed to fetch quota stats')
    return res.json()
  },

  async getCacheStats(days: number = 7): Promise<CacheStats> {
    const res = await fetch(`${API_BASE}/meta-core/web-search/cache-stats?days=${days}`)
    if (!res.ok) throw new Error('Failed to fetch cache stats')
    return res.json()
  },

  async getRecent(limit: number = 50): Promise<RecentCalls> {
    const res = await fetch(`${API_BASE}/meta-core/web-search/recent?limit=${limit}`)
    if (!res.ok) throw new Error('Failed to fetch recent calls')
    return res.json()
  },
}
