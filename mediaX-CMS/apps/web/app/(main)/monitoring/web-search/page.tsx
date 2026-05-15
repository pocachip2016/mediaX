'use client'

import { useEffect, useState } from 'react'
import { webSearchApi, type QuotaStats, type CacheStats, type RecentCalls } from '@/lib/webSearchApi'

export default function WebSearchMonitoringPage() {
  const [quotaStats, setQuotaStats] = useState<QuotaStats | null>(null)
  const [cacheStats, setCacheStats] = useState<CacheStats | null>(null)
  const [recentCalls, setRecentCalls] = useState<RecentCalls | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchData = async () => {
    try {
      setLoading(true)
      setError(null)
      const [quota, cache, recent] = await Promise.all([
        webSearchApi.getQuota(),
        webSearchApi.getCacheStats(7),
        webSearchApi.getRecent(50),
      ])
      setQuotaStats(quota)
      setCacheStats(cache)
      setRecentCalls(recent)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load monitoring data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 30000) // 30초 자동 새로고침
    return () => clearInterval(interval)
  }, [])

  if (loading) return <div className="p-8">로딩 중...</div>
  if (error) return <div className="p-8 text-red-600">오류: {error}</div>

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-6">WebSearch 모니터링</h1>

      {/* Provider Quota Cards */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold mb-4">Provider 쿼터 현황</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {quotaStats?.providers.map((provider) => (
            <div
              key={provider.provider}
              className="border rounded-lg p-4 bg-white shadow"
            >
              <div className="font-semibold text-lg capitalize mb-2">
                {provider.provider}
              </div>
              <div className="text-sm text-gray-600 mb-3">
                <div>한도: {provider.daily_limit}</div>
                <div>사용: {provider.used_today}</div>
                <div>남음: {provider.remaining}</div>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className={`h-2 rounded-full transition-all ${
                    provider.percent_used > 90 ? 'bg-red-500' : 'bg-green-500'
                  }`}
                  style={{ width: `${provider.percent_used}%` }}
                />
              </div>
              <div className="text-xs text-gray-500 mt-1">
                {provider.percent_used.toFixed(1)}% 사용 중
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Cache Stats Table */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold mb-4">캐시 통계 (7일)</h2>
        {cacheStats && (
          <div className="border rounded-lg overflow-hidden bg-white shadow">
            <table className="w-full text-sm">
              <tbody>
                <tr className="border-b">
                  <td className="p-3 font-semibold">총 쿼리</td>
                  <td className="p-3">{cacheStats.total_queries}</td>
                </tr>
                <tr className="border-b">
                  <td className="p-3 font-semibold">캐시 히트</td>
                  <td className="p-3">{cacheStats.cache_hits}</td>
                </tr>
                <tr className="border-b">
                  <td className="p-3 font-semibold">캐시 미스</td>
                  <td className="p-3">{cacheStats.cache_misses}</td>
                </tr>
                <tr>
                  <td className="p-3 font-semibold">히트율</td>
                  <td className="p-3 text-green-600 font-semibold">
                    {(cacheStats.hit_rate * 100).toFixed(1)}%
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Recent Calls */}
      <div>
        <h2 className="text-lg font-semibold mb-4">최근 호출 (최대 50건)</h2>
        {recentCalls && recentCalls.calls.length > 0 ? (
          <div className="border rounded-lg overflow-hidden bg-white shadow">
            <table className="w-full text-sm">
              <thead className="bg-gray-100 border-b">
                <tr>
                  <th className="p-3 text-left">시간</th>
                  <th className="p-3 text-left">Provider</th>
                  <th className="p-3 text-left">쿼리</th>
                  <th className="p-3 text-left">캐시</th>
                  <th className="p-3 text-left">상태</th>
                </tr>
              </thead>
              <tbody>
                {recentCalls.calls.slice(0, 20).map((call, idx) => (
                  <tr key={idx} className="border-b hover:bg-gray-50">
                    <td className="p-3 text-xs text-gray-500">
                      {new Date(call.timestamp).toLocaleString('ko-KR')}
                    </td>
                    <td className="p-3 capitalize">{call.provider}</td>
                    <td className="p-3 text-gray-600 truncate max-w-xs">
                      {call.query_preview}
                    </td>
                    <td className="p-3">
                      {call.cache_hit ? (
                        <span className="bg-green-100 text-green-800 px-2 py-1 rounded text-xs">
                          Hit
                        </span>
                      ) : (
                        <span className="bg-gray-100 text-gray-800 px-2 py-1 rounded text-xs">
                          Miss
                        </span>
                      )}
                    </td>
                    <td className="p-3">
                      {call.status === 'success' ? (
                        <span className="text-green-600">✓</span>
                      ) : (
                        <span className="text-red-600">✗</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-gray-500 p-4">호출 기록이 없습니다</div>
        )}
      </div>

      <div className="mt-4 text-xs text-gray-500">
        마지막 업데이트: {quotaStats?.as_of ? new Date(quotaStats.as_of).toLocaleString('ko-KR') : '—'}
      </div>
    </div>
  )
}
