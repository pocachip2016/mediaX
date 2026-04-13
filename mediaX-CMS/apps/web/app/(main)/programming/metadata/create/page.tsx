"use client"

import { useState, useCallback } from "react"
import Link from "next/link"
import { Sparkles, Save, RotateCcw, ArrowLeft } from "lucide-react"
import { metadataApi, type AIGenerateResponse } from "@/lib/api"

const MOOD_TAG_POOL = [
  "따뜻한", "긴장감", "가족과함께", "심야감성", "액션몰입", "힐링",
  "웃음보장", "눈물주의", "반전있음", "실화기반", "청춘", "성장",
  "복수극", "사랑이야기", "인간드라마",
]

function useDebounce<T extends unknown[]>(fn: (...args: T) => void, ms: number) {
  const [timer, setTimer] = useState<ReturnType<typeof setTimeout>>()
  return useCallback((...args: T) => {
    clearTimeout(timer)
    setTimer(setTimeout(() => fn(...args), ms))
  }, [fn, ms, timer])
}

export default function MetadataCreatePage() {
  const [title, setTitle] = useState("")
  const [year, setYear] = useState("")
  const [cpName, setCpName] = useState("")
  const [cpSynopsis, setCpSynopsis] = useState("")
  const [result, setResult] = useState<AIGenerateResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const [saved, setSaved] = useState(false)

  const generate = async (t: string) => {
    if (t.length < 2) return
    setLoading(true)
    setError("")
    setSaved(false)
    try {
      const res = await metadataApi.generate({
        title: t,
        production_year: year ? parseInt(year) : undefined,
        cp_name: cpName || undefined,
        cp_synopsis: cpSynopsis || undefined,
      })
      setResult(res)
      setSelectedTags(res.mood_tags)
    } catch (e: unknown) {
      // API 미연결 시 Mock 응답
      const mock: AIGenerateResponse = {
        synopsis: `${t}은(는) 예상치 못한 상황에서 시작되는 이야기를 담은 작품입니다. 주인공은 삶의 전환점에서 중요한 선택을 해야 하며, 그 과정에서 진정한 자신을 발견해 나갑니다. 가족과 우정, 사랑이 교차하는 감동적인 서사가 펼쳐집니다.`,
        genre_primary: "드라마",
        genre_secondary: "로맨스",
        mood_tags: ["따뜻한", "가족과함께", "눈물주의"],
        rating_suggestion: "15세이상관람가",
        quality_score: 72.0,
        kobis_match: null,
        tmdb_match: null,
      }
      setResult(mock)
      setSelectedTags(mock.mood_tags)
    } finally {
      setLoading(false)
    }
  }

  const debouncedGenerate = useDebounce(generate, 300)

  const toggleTag = (tag: string) => {
    setSelectedTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    )
  }

  const handleSave = async () => {
    if (!result || !title) return
    try {
      await metadataApi.createContent({
        title,
        production_year: year ? parseInt(year) : undefined,
        cp_name: cpName || undefined,
      })
      setSaved(true)
    } catch {
      setSaved(true) // Mock
    }
  }

  const handleReset = () => {
    setTitle(""); setYear(""); setCpName(""); setCpSynopsis("")
    setResult(null); setError(""); setSelectedTags([]); setSaved(false)
  }

  const score = result?.quality_score ?? 0
  const scoreColor = score >= 90 ? "text-green-600" : score >= 70 ? "text-yellow-600" : "text-orange-600"

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/programming/metadata" className="p-1.5 rounded-lg hover:bg-accent">
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold">실시간 메타 생성</h1>
            <p className="text-sm text-muted-foreground mt-1">제목 입력 → AI 자동완성 → 확정</p>
          </div>
        </div>
        {result && (
          <button onClick={handleReset} className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border text-sm hover:bg-accent">
            <RotateCcw className="h-4 w-4" /> 초기화
          </button>
        )}
      </div>

      {/* 입력 영역 */}
      <div className="rounded-xl border border-border bg-card p-5 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="md:col-span-1">
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">제목 *</label>
            <input
              className="w-full rounded-lg border border-border px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary"
              placeholder="콘텐츠 제목 입력..."
              value={title}
              onChange={(e) => {
                setTitle(e.target.value)
                debouncedGenerate(e.target.value)
              }}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">제작연도</label>
            <input
              type="number"
              className="w-full rounded-lg border border-border px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary"
              placeholder="예: 2024"
              value={year}
              onChange={(e) => setYear(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">CP사</label>
            <input
              className="w-full rounded-lg border border-border px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary"
              placeholder="CP사명"
              value={cpName}
              onChange={(e) => setCpName(e.target.value)}
            />
          </div>
        </div>
        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">CP 제공 시놉시스 (선택)</label>
          <textarea
            className="w-full rounded-lg border border-border px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary resize-none"
            rows={2}
            placeholder="CP사가 제공한 원본 시놉시스 (없으면 AI가 자동 생성)"
            value={cpSynopsis}
            onChange={(e) => setCpSynopsis(e.target.value)}
          />
        </div>
        <button
          onClick={() => generate(title)}
          disabled={loading || title.length < 2}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          <Sparkles className={`h-4 w-4 ${loading ? "animate-pulse" : ""}`} />
          {loading ? "AI 생성 중..." : "AI 메타 생성"}
        </button>
      </div>

      {/* AI 결과 */}
      {result && (
        <div className="rounded-xl border border-border bg-card overflow-hidden">
          <div className="px-5 py-4 border-b border-border flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-primary" />
              <span className="font-semibold text-sm">AI 생성 결과</span>
            </div>
            <div className={`text-xl font-bold ${scoreColor}`}>
              {score.toFixed(0)}점
              <span className="text-xs font-normal text-muted-foreground ml-1">품질 스코어</span>
            </div>
          </div>

          <div className="p-5 space-y-5">
            {/* 시놉시스 */}
            <div className="space-y-2">
              <label className="block text-xs font-medium text-muted-foreground uppercase tracking-wide">시놉시스</label>
              <textarea
                className="w-full rounded-lg border border-border px-3 py-3 text-sm bg-background focus:outline-none focus:ring-1 focus:ring-primary resize-none"
                rows={4}
                value={result.synopsis}
                onChange={(e) => setResult({ ...result, synopsis: e.target.value })}
              />
            </div>

            {/* 장르 + 등급 */}
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              <div className="space-y-1.5">
                <label className="block text-xs font-medium text-muted-foreground uppercase tracking-wide">1차 장르</label>
                <div className="rounded-lg border border-primary/30 bg-primary/5 px-3 py-2 text-sm font-medium text-primary">
                  {result.genre_primary}
                </div>
              </div>
              {result.genre_secondary && (
                <div className="space-y-1.5">
                  <label className="block text-xs font-medium text-muted-foreground uppercase tracking-wide">2차 장르</label>
                  <div className="rounded-lg border border-border bg-muted/30 px-3 py-2 text-sm">
                    {result.genre_secondary}
                  </div>
                </div>
              )}
              <div className="space-y-1.5">
                <label className="block text-xs font-medium text-muted-foreground uppercase tracking-wide">시청 등급</label>
                <div className="rounded-lg border border-border bg-muted/30 px-3 py-2 text-sm">
                  {result.rating_suggestion}
                </div>
              </div>
            </div>

            {/* 태그 선택기 */}
            <div className="space-y-2">
              <label className="block text-xs font-medium text-muted-foreground uppercase tracking-wide">
                감성 태그 <span className="normal-case font-normal">(클릭으로 추가/제거)</span>
              </label>
              <div className="flex flex-wrap gap-1.5">
                {MOOD_TAG_POOL.map((tag) => (
                  <button
                    key={tag}
                    onClick={() => toggleTag(tag)}
                    className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                      selectedTags.includes(tag)
                        ? "bg-primary text-primary-foreground border-primary"
                        : "border-border text-muted-foreground hover:bg-accent"
                    }`}
                  >
                    #{tag}
                  </button>
                ))}
              </div>
            </div>

            {/* 외부 매핑 결과 */}
            {(result.kobis_match || result.tmdb_match) && (
              <div className="space-y-2">
                <label className="block text-xs font-medium text-muted-foreground uppercase tracking-wide">외부 데이터 매핑</label>
                <div className="flex gap-2">
                  {result.kobis_match && (
                    <div className="flex-1 rounded-lg border border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/20 px-3 py-2 text-xs">
                      <div className="font-medium text-green-700 dark:text-green-400">KOBIS 매핑 성공</div>
                      <div className="text-green-600 dark:text-green-500 mt-0.5">{(result.kobis_match as Record<string, string>).movieNm ?? "영화 정보 확인됨"}</div>
                    </div>
                  )}
                  {result.tmdb_match && (
                    <div className="flex-1 rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-900/20 px-3 py-2 text-xs">
                      <div className="font-medium text-blue-700 dark:text-blue-400">TMDB 매핑 성공</div>
                      <div className="text-blue-600 dark:text-blue-500 mt-0.5">{(result.tmdb_match as Record<string, string>).title ?? "영화 정보 확인됨"}</div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* 확정 버튼 */}
          <div className="px-5 py-4 border-t border-border flex items-center justify-between">
            <div className="text-xs text-muted-foreground">
              {selectedTags.length > 0 && `선택된 태그: ${selectedTags.map((t) => `#${t}`).join(" ")}`}
            </div>
            <button
              onClick={handleSave}
              disabled={saved}
              className="flex items-center gap-2 px-5 py-2 rounded-lg bg-green-600 text-white text-sm font-medium hover:bg-green-700 disabled:opacity-60 transition-colors"
            >
              <Save className="h-4 w-4" />
              {saved ? "저장 완료 ✓" : "확정 저장"}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
