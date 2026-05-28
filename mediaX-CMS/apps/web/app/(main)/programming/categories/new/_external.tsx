"use client"

import { useCallback, useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { ArrowLeft, Globe, Check, RefreshCw, Save } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import {
  distributionApi,
  type OttSectionCardOut,
} from "@/lib/api"

// ── 상수 ──────────────────────────────────────────────────────

const PLATFORM_OPTIONS = ["ott", "iptv", "mobile", "web"]

const CHANNEL_LABEL: Record<string, string> = {
  ott_watcha: "WATCHA",
  ott_netflix: "NETFLIX",
  ott_wave: "WAVVE",
  ott_tving: "TVING",
}

// content_id 일부 채운 데모 목 — Beat 미실행 시 UI 확인용
const MOCK_SECTIONS: OttSectionCardOut[] = [
  {
    section_id: "ott_watcha:top",
    name: "이번 주 TOP10",
    category_type: "ranking",
    channel: "ott_watcha",
    item_count: 4,
    items: [
      { title: "파묘", rank: 1, production_year: 2024, external_id: null, content_id: 1 },
      { title: "서울의 봄", rank: 2, production_year: 2023, external_id: null, content_id: 2 },
      { title: "범죄도시4", rank: 3, production_year: 2024, external_id: null, content_id: 3 },
      { title: "미매칭 작품", rank: 4, production_year: 2024, external_id: null, content_id: null },
    ],
  },
  {
    section_id: "ott_netflix:new",
    name: "신작 영화",
    category_type: "new_release",
    channel: "ott_netflix",
    item_count: 3,
    items: [
      { title: "댓글부대", rank: 1, production_year: 2024, external_id: null, content_id: 4 },
      { title: "시민덕희", rank: 2, production_year: 2024, external_id: null, content_id: 5 },
      { title: "미매칭", rank: 3, production_year: 2024, external_id: null, content_id: null },
    ],
  },
]

// ── 섹션 카드 ──────────────────────────────────────────────────

function SectionCard({
  section,
  selected,
  onSelect,
}: {
  section: OttSectionCardOut
  selected: boolean
  onSelect: () => void
}) {
  const matchedCount = section.items.filter((i) => typeof i.content_id === "number").length
  const preview = section.items.slice(0, 3)
  const rest = section.item_count - preview.length

  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "text-left rounded-xl border p-4 shadow-sm transition-all flex flex-col gap-2 w-full",
        selected
          ? "border-blue-400 bg-blue-50 dark:bg-blue-950/40 dark:border-blue-600 ring-1 ring-blue-300 dark:ring-blue-700"
          : "bg-card hover:border-blue-300 dark:hover:border-blue-700 hover:shadow-md"
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="font-semibold text-sm leading-snug">{section.name}</span>
        <span
          className={cn(
            "shrink-0 h-5 w-5 rounded flex items-center justify-center border transition-colors",
            selected
              ? "bg-blue-600 border-blue-600 text-white"
              : "border-border text-transparent"
          )}
        >
          <Check className="h-3.5 w-3.5" />
        </span>
      </div>
      <div className="flex items-center gap-2 text-xs flex-wrap">
        <span className="px-1.5 py-0.5 rounded bg-muted font-medium text-muted-foreground">
          {CHANNEL_LABEL[section.channel] ?? section.channel}
        </span>
        <span className="text-muted-foreground">{section.category_type}</span>
        <span
          className={cn(
            "font-medium",
            matchedCount > 0 ? "text-green-600 dark:text-green-400" : "text-muted-foreground"
          )}
        >
          매칭 {matchedCount}/{section.item_count}
        </span>
      </div>
      <ul className="text-xs text-muted-foreground space-y-0.5">
        {preview.map((it) => (
          <li key={`${it.rank}-${it.title}`} className="flex items-center gap-1 truncate">
            {typeof it.content_id === "number" ? (
              <Check className="h-3 w-3 text-green-500 shrink-0" />
            ) : (
              <span className="h-3 w-3 shrink-0 inline-block" />
            )}
            <span className="truncate">{it.title}</span>
          </li>
        ))}
        {rest > 0 && <li className="italic">· 외 {rest}건</li>}
      </ul>
    </button>
  )
}

// ── 확인 패널 ──────────────────────────────────────────────────

function ConfirmPanel({
  section,
  onImported,
}: {
  section: OttSectionCardOut
  onImported: (categoryId: number) => void
}) {
  const [name, setName]           = useState(section.name)
  const [platform, setPlatform]   = useState("ott")
  const [importing, setImporting] = useState(false)
  const [error, setError]         = useState<string | null>(null)

  // 섹션 바뀌면 이름·에러 리셋
  useEffect(() => {
    setName(section.name)
    setError(null)
  }, [section.section_id]) // eslint-disable-line react-hooks/exhaustive-deps

  const matchedItems = section.items.filter((i) => typeof i.content_id === "number")
  const skippedCount = section.item_count - matchedItems.length

  const handleImport = async () => {
    if (!name.trim()) { setError("이름을 입력해 주세요."); return }
    if (matchedItems.length === 0) { setError("가져올 매칭 콘텐츠가 없습니다."); return }
    setError(null)
    setImporting(true)
    try {
      const created = await distributionApi.createCategory({
        name: name.trim(),
        platform,
        category_type: section.category_type,
        source_mode: "external_imported",
        headline_copy: section.name,
        reference_external_id: section.section_id,
        is_active: true,
        is_draft: false,
      })
      let rank = 1
      for (const it of section.items) {
        if (typeof it.content_id === "number") {
          await distributionApi.addItem(created.id, { content_id: it.content_id, rank: rank++ })
        }
      }
      onImported(created.id)
    } catch (err) {
      console.error("[external-import] 저장 실패", err)
      setError("저장 중 오류가 발생했습니다. 다시 시도해주세요.")
      setImporting(false)
    }
  }

  return (
    <div className="rounded-xl border bg-card shadow-sm sticky top-4">
      <div className="px-5 py-4 border-b">
        <h2 className="text-sm font-semibold">가져오기 확인</h2>
        <p className="text-xs text-muted-foreground mt-0.5">섹션 정보를 확인하고 큐레이션을 만드세요.</p>
      </div>
      <div className="p-5 space-y-4">
        {/* 이름 */}
        <div className="space-y-1.5">
          <label className="text-xs font-medium">이름</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full px-3 py-2 border rounded-lg bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
        </div>

        {/* 플랫폼 */}
        <div className="space-y-1.5">
          <label className="text-xs font-medium">플랫폼</label>
          <select
            value={platform}
            onChange={(e) => setPlatform(e.target.value)}
            className="w-full px-3 py-2 border rounded-lg bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
          >
            {PLATFORM_OPTIONS.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>

        {/* 헤드라인 카피 (읽기 전용) */}
        <div className="space-y-1.5">
          <label className="text-xs font-medium">헤드라인 카피</label>
          <div className="px-3 py-2 border rounded-lg bg-muted/30 text-sm text-muted-foreground">
            {section.name}
          </div>
          <p className="text-[11px] text-muted-foreground">섹션명이 카피로 사용됩니다.</p>
        </div>

        {/* 매칭 아이템 목록 */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label className="text-xs font-medium">
              콘텐츠{" "}
              <span className="text-green-600 dark:text-green-400 font-semibold">
                {matchedItems.length}건
              </span>{" "}
              가져오기
            </label>
            {skippedCount > 0 && (
              <span className="text-[11px] text-muted-foreground">미매칭 {skippedCount}건 스킵</span>
            )}
          </div>
          <div className="rounded-lg border divide-y max-h-[200px] overflow-y-auto">
            {matchedItems.length === 0 ? (
              <p className="text-xs text-muted-foreground text-center py-4">매칭된 콘텐츠가 없습니다.</p>
            ) : (
              matchedItems.map((it) => (
                <div key={it.rank} className="flex items-center gap-2 px-3 py-2 text-xs">
                  <span className="text-muted-foreground w-4 shrink-0 text-right">{it.rank}.</span>
                  <span className="flex-1 truncate">{it.title}</span>
                  <Check className="h-3.5 w-3.5 text-green-500 shrink-0" />
                </div>
              ))
            )}
          </div>
        </div>

        {/* 에러 */}
        {error && <p className="text-xs text-destructive">{error}</p>}

        {/* 가져오기 버튼 */}
        <button
          type="button"
          onClick={handleImport}
          disabled={importing || matchedItems.length === 0}
          className="w-full flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          <Save className="h-4 w-4" />
          {importing ? "가져오는 중..." : "가져오기"}
        </button>
      </div>
    </div>
  )
}

// ── ExternalImport (진입) ──────────────────────────────────────

export function ExternalImport() {
  const router = useRouter()
  const [sections, setSections] = useState<OttSectionCardOut[]>([])
  const [loading, setLoading]   = useState(true)
  const [usedMock, setUsedMock] = useState(false)
  const [selected, setSelected] = useState<OttSectionCardOut | null>(null)

  const fetchSections = useCallback(async () => {
    setLoading(true)
    try {
      const res = await distributionApi.getExternalReferences()
      setSections(res.sections)
      setUsedMock(false)
    } catch (err) {
      console.error("[external-import] external-references 실패 → Mock 폴백", err)
      setSections(MOCK_SECTIONS)
      setUsedMock(true)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchSections() }, [fetchSections])

  const handleImported = (categoryId: number) => {
    router.push(`/programming/categories/${categoryId}`)
  }

  return (
    <div className="mx-auto max-w-[1200px]">
      <Link
        href="/programming/categories"
        className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground mb-6 transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        큐레이션 목록
      </Link>

      <div className="flex items-center gap-3 mb-6">
        <div className="p-2 rounded-lg bg-blue-100 dark:bg-blue-900">
          <Globe className="h-5 w-5 text-blue-600 dark:text-blue-300" />
        </div>
        <div>
          <h1 className="text-xl font-semibold">새 큐레이션 — 외부 참고</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            OTT 큐레이션 섹션을 선택해 콘텐츠를 빠르게 가져옵니다.
            {usedMock && (
              <span className="ml-1 text-amber-600 dark:text-amber-400">(샘플 데이터)</span>
            )}
          </p>
        </div>
        <button
          type="button"
          onClick={fetchSections}
          disabled={loading}
          className="ml-auto flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border bg-background text-xs hover:bg-accent transition-colors"
        >
          <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
          새로고침
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center min-h-[40vh] text-muted-foreground">
          <RefreshCw className="h-5 w-5 animate-spin mr-2" />
          외부 큐레이션을 불러오는 중...
        </div>
      ) : sections.length === 0 ? (
        <div className="flex flex-col items-center justify-center min-h-[40vh] text-center text-muted-foreground gap-3">
          <Globe className="h-8 w-8 opacity-30" />
          <p className="text-sm">불러올 외부 큐레이션이 없습니다.</p>
          <p className="text-xs">Beat 백필이 실행된 후 섹션이 표시됩니다.</p>
          <Link
            href="/programming/categories"
            className="text-xs text-blue-600 hover:underline flex items-center gap-1"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            큐레이션 목록으로 돌아가기
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_340px] gap-6 items-start">
          {/* 좌 — 섹션 카드 그리드 */}
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              가져올 섹션을 선택하면 오른쪽에 확인 패널이 표시됩니다.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
              {sections.map((section) => (
                <SectionCard
                  key={section.section_id}
                  section={section}
                  selected={selected?.section_id === section.section_id}
                  onSelect={() => setSelected(section)}
                />
              ))}
            </div>
          </div>

          {/* 우 — 확인 패널 */}
          <div>
            {selected ? (
              <ConfirmPanel section={selected} onImported={handleImported} />
            ) : (
              <div className="rounded-xl border bg-card shadow-sm p-8 text-center text-muted-foreground sticky top-4">
                <Globe className="h-8 w-8 mx-auto mb-3 opacity-30" />
                <p className="text-sm">
                  섹션을 선택하면<br />여기에 상세가 표시됩니다.
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
