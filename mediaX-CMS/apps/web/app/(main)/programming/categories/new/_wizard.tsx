"use client"

import { useCallback, useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import Link from "next/link"
import {
  ArrowLeft, ArrowRight, Sparkles, RefreshCw, Check, X, Save, Star,
} from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import {
  distributionApi,
  type OttSectionCardOut,
  type CopyCandidateOut,
  type ContentMatchCandidateOut,
} from "@/lib/api"

// ── 옵션 상수 (value=영문 SSOT / label=한글) ──────────────────────

const GENRE_OPTIONS = [
  "드라마", "코미디", "액션", "로맨스", "스릴러", "공포",
  "SF", "판타지", "애니메이션", "다큐멘터리", "범죄", "전쟁",
]

const MOOD_OPTIONS = [
  "따뜻한", "가벼운", "긴장감", "감동", "신나는", "잔잔한", "어두운", "유쾌한",
]

const TARGET_OPTIONS: { value: string; label: string }[] = [
  { value: "all", label: "전체" },
  { value: "teens", label: "10대" },
  { value: "20s", label: "20대" },
  { value: "30s_adults", label: "30대 성인" },
  { value: "40s_plus", label: "40대 이상" },
  { value: "family", label: "가족" },
]

const OCCASION_OPTIONS: { value: string; label: string }[] = [
  { value: "any", label: "무관" },
  { value: "weekday_evening", label: "평일 저녁" },
  { value: "weekend", label: "주말" },
  { value: "late_night", label: "심야" },
  { value: "holiday", label: "휴일" },
]

const CHANNEL_LABEL: Record<string, string> = {
  ott_watcha: "WATCHA",
  ott_netflix: "NETFLIX",
  ott_wave: "WAVVE",
  ott_tving: "TVING",
}

const STEPS = [
  { step: 1, label: "테마 특징" },
  { step: 2, label: "외부 참고" },
  { step: 3, label: "카피·콘텐츠" },
]

const MAX_IMPLEMENTED_STEP = 3  // 4단(카피/콘텐츠)을 3단 워크벤치로 병합

const SCORE_DIMENSIONS: { key: string; label: string; weight: number }[] = [
  { key: "genre", label: "장르 일치", weight: 0.30 },
  { key: "mood", label: "무드 매칭", weight: 0.15 },
  { key: "runtime", label: "런타임", weight: 0.20 },
  { key: "era", label: "시대", weight: 0.10 },
  { key: "external", label: "외부 참고", weight: 0.15 },
  { key: "keywords", label: "키워드", weight: 0.10 },
]

// ── Draft 모델 ────────────────────────────────────────────────

interface ThemeFeatures {
  genres: string[]
  moods: string[]
  runtime_min: number | null
  runtime_max: number | null
  era_from: number | null
  era_to: number | null
  target: string
  occasion: string
  free_keywords: string[]
}

export interface WizardDraft {
  name: string
  theme_features: ThemeFeatures
  selected_sections: OttSectionCardOut[]
  headline_copy: string | null
  sub_copy: string | null
  selected_content_ids: number[]
}

const DRAFT_KEY = "curation-ai-draft"

const emptyDraft = (): WizardDraft => ({
  name: "",
  theme_features: {
    genres: [],
    moods: [],
    runtime_min: null,
    runtime_max: null,
    era_from: null,
    era_to: null,
    target: "all",
    occasion: "any",
    free_keywords: [],
  },
  selected_sections: [],
  headline_copy: null,
  sub_copy: null,
  selected_content_ids: [],
})

// sessionStorage 자동 저장 훅
function useDraft(): [WizardDraft, (patch: Partial<WizardDraft>) => void, () => void] {
  const [draft, setDraft] = useState<WizardDraft>(emptyDraft)

  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(DRAFT_KEY)
      if (raw) setDraft({ ...emptyDraft(), ...JSON.parse(raw) })
    } catch {
      // 손상된 캐시는 무시하고 빈 draft 유지
    }
  }, [])

  const update = useCallback((patch: Partial<WizardDraft>) => {
    setDraft((prev) => {
      const next = { ...prev, ...patch }
      try {
        sessionStorage.setItem(DRAFT_KEY, JSON.stringify(next))
      } catch {
        // 저장 실패는 무시 (메모리 상태는 유지)
      }
      return next
    })
  }, [])

  const reset = useCallback(() => {
    try {
      sessionStorage.removeItem(DRAFT_KEY)
    } catch {
      // 무시
    }
    setDraft(emptyDraft())
  }, [])

  return [draft, update, reset]
}

// ── 칩 멀티셀렉트 ──────────────────────────────────────────────

function ChipMultiSelect({
  options, selected, onToggle,
}: {
  options: string[]
  selected: string[]
  onToggle: (value: string) => void
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((opt) => {
        const active = selected.includes(opt)
        return (
          <button
            key={opt}
            type="button"
            onClick={() => onToggle(opt)}
            className={cn(
              "inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium border transition-colors",
              active
                ? "bg-violet-100 text-violet-700 border-violet-300 dark:bg-violet-900 dark:text-violet-200 dark:border-violet-700"
                : "bg-background text-muted-foreground border-border hover:bg-accent"
            )}
          >
            {active && <Check className="h-3 w-3" />}
            {opt}
          </button>
        )
      })}
    </div>
  )
}

// ── 키워드 태그 입력 ──────────────────────────────────────────

function KeywordTagInput({
  keywords, onAdd, onRemove,
}: {
  keywords: string[]
  onAdd: (kw: string) => void
  onRemove: (kw: string) => void
}) {
  const [value, setValue] = useState("")

  const commit = () => {
    const kw = value.trim()
    if (kw && !keywords.includes(kw)) onAdd(kw)
    setValue("")
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      {keywords.map((kw) => (
        <span
          key={kw}
          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs bg-muted text-foreground"
        >
          {kw}
          <button
            type="button"
            onClick={() => onRemove(kw)}
            className="hover:text-destructive transition-colors"
          >
            <X className="h-3 w-3" />
          </button>
        </span>
      ))}
      <div className="relative">
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") { e.preventDefault(); commit() }
          }}
          onBlur={commit}
          placeholder="+ 키워드 입력"
          className="w-32 pl-3 pr-2 py-1 border rounded-full bg-background text-xs focus:outline-none focus:ring-2 focus:ring-primary/30"
        />
      </div>
    </div>
  )
}

// ── 범위 입력 ─────────────────────────────────────────────────

function RangeInput({
  minValue, maxValue, onMin, onMax, placeholderMin, placeholderMax,
}: {
  minValue: number | null
  maxValue: number | null
  onMin: (v: number | null) => void
  onMax: (v: number | null) => void
  placeholderMin: string
  placeholderMax: string
}) {
  const parse = (s: string): number | null => {
    if (s.trim() === "") return null
    const n = Number(s)
    return Number.isFinite(n) ? n : null
  }
  const inputCls =
    "w-full px-3 py-2 border rounded-lg bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
  return (
    <div className="flex items-center gap-2">
      <input
        type="number"
        value={minValue ?? ""}
        onChange={(e) => onMin(parse(e.target.value))}
        placeholder={placeholderMin}
        className={inputCls}
      />
      <span className="text-muted-foreground shrink-0">~</span>
      <input
        type="number"
        value={maxValue ?? ""}
        onChange={(e) => onMax(parse(e.target.value))}
        placeholder={placeholderMax}
        className={inputCls}
      />
    </div>
  )
}

// ── Step 1 — 테마 특징 ────────────────────────────────────────

function Step1Features({
  draft, update,
}: {
  draft: WizardDraft
  update: (patch: Partial<WizardDraft>) => void
}) {
  const tf = draft.theme_features

  const patchFeatures = (patch: Partial<ThemeFeatures>) =>
    update({ theme_features: { ...tf, ...patch } })

  const toggleInList = (key: "genres" | "moods", value: string) => {
    const list = tf[key]
    patchFeatures({
      [key]: list.includes(value)
        ? list.filter((v) => v !== value)
        : [...list, value],
    } as Partial<ThemeFeatures>)
  }

  return (
    <div className="rounded-xl border bg-card p-6 shadow-sm space-y-6">
      <div className="space-y-1.5">
        <label className="text-sm font-medium">이름</label>
        <input
          type="text"
          value={draft.name}
          onChange={(e) => update({ name: e.target.value })}
          placeholder="예: 주말 영화 추천 (저장 시 카피 후보로도 활용)"
          className="w-full px-3 py-2 border rounded-lg bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
        />
      </div>

      <div className="space-y-2">
        <label className="text-sm font-medium">장르 <span className="text-xs text-muted-foreground font-normal">(복수 선택)</span></label>
        <ChipMultiSelect
          options={GENRE_OPTIONS}
          selected={tf.genres}
          onToggle={(v) => toggleInList("genres", v)}
        />
      </div>

      <div className="space-y-2">
        <label className="text-sm font-medium">무드 <span className="text-xs text-muted-foreground font-normal">(복수 선택)</span></label>
        <ChipMultiSelect
          options={MOOD_OPTIONS}
          selected={tf.moods}
          onToggle={(v) => toggleInList("moods", v)}
        />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
        <div className="space-y-1.5">
          <label className="text-sm font-medium">런타임 (분)</label>
          <RangeInput
            minValue={tf.runtime_min}
            maxValue={tf.runtime_max}
            onMin={(v) => patchFeatures({ runtime_min: v })}
            onMax={(v) => patchFeatures({ runtime_max: v })}
            placeholderMin="최소"
            placeholderMax="최대"
          />
        </div>
        <div className="space-y-1.5">
          <label className="text-sm font-medium">시대 (년도)</label>
          <RangeInput
            minValue={tf.era_from}
            maxValue={tf.era_to}
            onMin={(v) => patchFeatures({ era_from: v })}
            onMax={(v) => patchFeatures({ era_to: v })}
            placeholderMin="from"
            placeholderMax="to"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
        <div className="space-y-1.5">
          <label className="text-sm font-medium">타겟</label>
          <select
            value={tf.target}
            onChange={(e) => patchFeatures({ target: e.target.value })}
            className="w-full px-3 py-2 border rounded-lg bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
          >
            {TARGET_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        <div className="space-y-1.5">
          <label className="text-sm font-medium">상황</label>
          <select
            value={tf.occasion}
            onChange={(e) => patchFeatures({ occasion: e.target.value })}
            className="w-full px-3 py-2 border rounded-lg bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
          >
            {OCCASION_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
      </div>

      <div className="space-y-2">
        <label className="text-sm font-medium">자유 키워드</label>
        <KeywordTagInput
          keywords={tf.free_keywords}
          onAdd={(kw) => patchFeatures({ free_keywords: [...tf.free_keywords, kw] })}
          onRemove={(kw) => patchFeatures({ free_keywords: tf.free_keywords.filter((k) => k !== kw) })}
        />
      </div>
    </div>
  )
}

// ── Step 2 — 외부 참고 ────────────────────────────────────────

const MOCK_SECTIONS: OttSectionCardOut[] = [
  {
    section_id: "ott_watcha:top",
    name: "이번 주 TOP10",
    category_type: "ranking",
    channel: "ott_watcha",
    item_count: 10,
    items: [
      { title: "파묘", rank: 1, production_year: 2024, external_id: null },
      { title: "서울의 봄", rank: 2, production_year: 2023, external_id: null },
      { title: "범죄도시4", rank: 3, production_year: 2024, external_id: null },
    ],
  },
  {
    section_id: "ott_netflix:new",
    name: "신작 영화",
    category_type: "new_release",
    channel: "ott_netflix",
    item_count: 8,
    items: [
      { title: "댓글부대", rank: 1, production_year: 2024, external_id: null },
      { title: "시민덕희", rank: 2, production_year: 2024, external_id: null },
    ],
  },
]

function OttSectionCard({
  section, selected, onToggle,
}: {
  section: OttSectionCardOut
  selected: boolean
  onToggle: () => void
}) {
  const preview = section.items.slice(0, 2)
  const rest = section.item_count - preview.length
  return (
    <button
      type="button"
      onClick={onToggle}
      className={cn(
        "text-left rounded-xl border p-4 shadow-sm transition-all flex flex-col gap-2",
        selected
          ? "border-violet-400 bg-violet-50 dark:bg-violet-950/40 dark:border-violet-600 ring-1 ring-violet-300 dark:ring-violet-700"
          : "bg-card hover:border-violet-300 dark:hover:border-violet-700 hover:shadow-md"
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="font-semibold text-sm leading-snug">{section.name}</span>
        <span
          className={cn(
            "shrink-0 h-5 w-5 rounded flex items-center justify-center border transition-colors",
            selected
              ? "bg-violet-600 border-violet-600 text-white"
              : "border-border text-transparent"
          )}
        >
          <Check className="h-3.5 w-3.5" />
        </span>
      </div>
      <div className="flex items-center gap-2 text-xs">
        <span className="px-1.5 py-0.5 rounded bg-muted font-medium text-muted-foreground">
          {CHANNEL_LABEL[section.channel] ?? section.channel}
        </span>
        <span className="text-muted-foreground">{section.category_type}</span>
        <span className="text-muted-foreground">· {section.item_count}개 작품</span>
      </div>
      <ul className="text-xs text-muted-foreground space-y-0.5">
        {preview.map((it) => (
          <li key={`${it.rank}-${it.title}`} className="truncate">· {it.title}</li>
        ))}
        {rest > 0 && <li className="italic">· 외 {rest}건</li>}
      </ul>
    </button>
  )
}

function Step2ExternalRefs({
  draft, update,
}: {
  draft: WizardDraft
  update: (patch: Partial<WizardDraft>) => void
}) {
  const [sections, setSections] = useState<OttSectionCardOut[]>([])
  const [loading, setLoading] = useState(true)
  const [usedMock, setUsedMock] = useState(false)

  const fetchRefs = useCallback(async () => {
    setLoading(true)
    try {
      const res = await distributionApi.getExternalReferences()
      setSections(res.sections)
      setUsedMock(false)
    } catch (err) {
      console.error("[wizard-step2] external-references 실패 → Mock 폴백", err)
      setSections(MOCK_SECTIONS)
      setUsedMock(true)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchRefs() }, [fetchRefs])

  const selectedIds = new Set(draft.selected_sections.map((s) => s.section_id))

  const toggle = (section: OttSectionCardOut) => {
    update({
      selected_sections: selectedIds.has(section.section_id)
        ? draft.selected_sections.filter((s) => s.section_id !== section.section_id)
        : [...draft.selected_sections, section],
    })
  }

  return (
    <div className="rounded-xl border bg-card p-6 shadow-sm space-y-4">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          유사 외부 큐레이션을 선택하면 섹션명·작품이 다음 단계의 카피·콘텐츠 후보에 반영됩니다.
          {usedMock && <span className="ml-1 text-amber-600 dark:text-amber-400">(샘플 데이터)</span>}
        </p>
        <button
          type="button"
          onClick={fetchRefs}
          disabled={loading}
          className="shrink-0 flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border bg-background text-xs hover:bg-accent transition-colors"
        >
          <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
          새로고침
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16 text-muted-foreground">
          <RefreshCw className="h-5 w-5 animate-spin mr-2" />
          외부 큐레이션을 불러오는 중...
        </div>
      ) : sections.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center text-muted-foreground">
          <p className="text-sm">참고할 외부 큐레이션이 없습니다.</p>
          <p className="text-xs mt-1">건너뛰고 다음 단계로 진행할 수 있습니다.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {sections.map((section) => (
            <OttSectionCard
              key={section.section_id}
              section={section}
              selected={selectedIds.has(section.section_id)}
              onToggle={() => toggle(section)}
            />
          ))}
        </div>
      )}

      {draft.selected_sections.length > 0 && (
        <p className="text-xs text-muted-foreground border-t pt-3">
          선택됨: {draft.selected_sections.length}개 —{" "}
          {draft.selected_sections.map((s) => `"${s.name}"`).join(", ")}
        </p>
      )}
    </div>
  )
}

// ── Stepper ───────────────────────────────────────────────────

function Stepper({ current }: { current: number }) {
  return (
    <div className="flex items-center">
      {STEPS.map((s, idx) => {
        const done = s.step < current
        const active = s.step === current
        const pending = s.step > MAX_IMPLEMENTED_STEP
        return (
          <div key={s.step} className="flex items-center flex-1 last:flex-none">
            <div className="flex flex-col items-center gap-1">
              <span
                className={cn(
                  "h-7 w-7 rounded-full flex items-center justify-center text-xs font-semibold border-2 transition-colors",
                  active
                    ? "bg-violet-600 border-violet-600 text-white"
                    : done
                    ? "bg-violet-100 border-violet-400 text-violet-700 dark:bg-violet-900 dark:text-violet-200"
                    : "bg-background border-border text-muted-foreground"
                )}
              >
                {done ? <Check className="h-3.5 w-3.5" /> : s.step}
              </span>
              <span
                className={cn(
                  "text-[11px] whitespace-nowrap",
                  active ? "font-medium text-foreground" : "text-muted-foreground",
                  pending && "opacity-50"
                )}
              >
                {s.label}
                {pending && " ·"}
              </span>
            </div>
            {idx < STEPS.length - 1 && (
              <div
                className={cn(
                  "h-0.5 flex-1 mx-2 -mt-4 rounded",
                  s.step < current ? "bg-violet-400" : "bg-border"
                )}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}

// ── ScoreBar (추천 근거 막대) ──────────────────────────────────

function ScoreBar({ label, value, weight }: { label: string; value: number; weight: number }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-mono text-[11px]">
          {value.toFixed(2)}{" "}
          <span className="text-muted-foreground">({weight.toFixed(2)})</span>
        </span>
      </div>
      <div className="h-1.5 rounded-full bg-muted overflow-hidden">
        <div
          className="h-full rounded-full bg-violet-500 transition-all"
          style={{ width: `${Math.round(Math.max(0, Math.min(1, value)) * 100)}%` }}
        />
      </div>
    </div>
  )
}

// ── Step 3 워크벤치 (카피 | 콘텐츠 | 근거) ─────────────────────

interface Step3Props {
  draft: WizardDraft
  update: (patch: Partial<WizardDraft>) => void
  onBack: () => void
  onSaved: (categoryId: number) => void
}

function Step3Workbench({ draft, update, onBack, onSaved }: Step3Props) {
  const [copies, setCopies]           = useState<CopyCandidateOut[]>([])
  const [copyEngine, setCopyEngine]   = useState<string | null>(null)
  const [copyLoading, setCopyLoading] = useState(true)
  const [matches, setMatches]         = useState<ContentMatchCandidateOut[]>([])
  const [matchLoading, setMatchLoading] = useState(true)

  // 선택된 카피: 인덱스(후보) | "manual"
  const [copyChoice, setCopyChoice]   = useState<number | "manual">(0)
  const [manualHeadline, setManualHeadline] = useState(draft.headline_copy ?? "")
  const [manualSub, setManualSub]     = useState(draft.sub_copy ?? "")

  const [selectedIds, setSelectedIds] = useState<Set<number>>(
    new Set(draft.selected_content_ids)
  )
  const [focusId, setFocusId]         = useState<number | null>(null)

  const [platform, setPlatform]       = useState("ott")
  const [name, setName]               = useState(draft.name)
  const [saving, setSaving]           = useState(false)
  const [error, setError]             = useState<string | null>(null)

  // 외부 참고에서 resolve된 content_id (Step 8 영속 데이터)
  const externalContentIds = draft.selected_sections
    .flatMap((s) => s.items)
    .map((i) => i.content_id)
    .filter((id): id is number => typeof id === "number")

  const sectionNames = draft.selected_sections.map((s) => s.name)
  const tfRecord = draft.theme_features as unknown as Record<string, unknown>

  // 카피 후보 로드
  useEffect(() => {
    let cancelled = false
    setCopyLoading(true)
    distributionApi
      .proposeCopy({ theme_features: tfRecord, selected_section_names: sectionNames })
      .then((res) => {
        if (cancelled) return
        setCopies(res.candidates)
        setCopyEngine(res.engine_used)
      })
      .catch((err) => {
        console.error("[wizard-step3] propose-copy 실패", err)
        if (!cancelled) setCopies([])
      })
      .finally(() => { if (!cancelled) setCopyLoading(false) })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 콘텐츠 매칭 로드
  useEffect(() => {
    let cancelled = false
    setMatchLoading(true)
    distributionApi
      .matchContents({
        theme_features: tfRecord,
        external_content_ids: externalContentIds,
        limit: 20,
      })
      .then((res) => {
        if (cancelled) return
        setMatches(res.items)
        // 기본 선택: draft에 없으면 상위 10건
        if (draft.selected_content_ids.length === 0 && res.items.length > 0) {
          const top = res.items.slice(0, 10).map((m) => m.content_id)
          setSelectedIds(new Set(top))
          update({ selected_content_ids: top })
        }
        setFocusId(res.items[0]?.content_id ?? null)
      })
      .catch((err) => {
        console.error("[wizard-step3] match-contents 실패", err)
        if (!cancelled) setMatches([])
      })
      .finally(() => { if (!cancelled) setMatchLoading(false) })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const chooseCopy = (choice: number | "manual") => {
    setCopyChoice(choice)
    if (choice === "manual") {
      update({ headline_copy: manualHeadline || null, sub_copy: manualSub || null })
    } else {
      const c = copies[choice]
      if (c) update({ headline_copy: c.headline_copy, sub_copy: c.sub_copy })
    }
  }

  const toggleContent = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      update({ selected_content_ids: [...next] })
      return next
    })
  }

  const focused = matches.find((m) => m.content_id === focusId) ?? null

  const resolvedCopy = (): { headline: string | null; sub: string | null } => {
    if (copyChoice === "manual") return { headline: manualHeadline || null, sub: manualSub || null }
    const c = copies[copyChoice]
    return { headline: c?.headline_copy ?? null, sub: c?.sub_copy ?? null }
  }

  const handleSave = async () => {
    if (!name.trim()) { setError("이름을 입력해 주세요."); return }
    if (selectedIds.size === 0) { setError("콘텐츠를 1개 이상 선택해 주세요."); return }
    setError(null)
    setSaving(true)
    const { headline, sub } = resolvedCopy()
    try {
      const created = await distributionApi.createCategory({
        name: name.trim(),
        platform,
        category_type: "recommendation",
        source_mode: "ai_proposed",
        headline_copy: headline,
        sub_copy: sub,
        theme_features: tfRecord,
        is_active: true,
        is_draft: false,
      })
      // 선택된 콘텐츠를 match 순서대로 rank 부여해 추가
      const orderedIds = matches
        .map((m) => m.content_id)
        .filter((id) => selectedIds.has(id))
      let rank = 1
      for (const cid of orderedIds) {
        await distributionApi.addItem(created.id, { content_id: cid, rank: rank++ })
      }
      onSaved(created.id)
    } catch (err) {
      console.error("[wizard-step3] 저장 실패", err)
      setError("저장 중 오류가 발생했습니다. 다시 시도해 주세요.")
      setSaving(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 lg:grid-cols-[240px_1fr_340px] gap-4 items-start">
        {/* 좌 — 카피 후보 */}
        <div className="rounded-xl border bg-card shadow-sm">
          <div className="px-4 py-3 border-b">
            <h2 className="text-sm font-semibold">카피 후보</h2>
            {copyEngine && (
              <p className="text-[10px] text-muted-foreground mt-0.5">엔진: {copyEngine}</p>
            )}
          </div>
          <div className="p-3 space-y-2">
            {copyLoading ? (
              <div className="flex items-center justify-center py-8 text-muted-foreground text-xs">
                <RefreshCw className="h-4 w-4 animate-spin mr-1.5" /> 카피 생성 중...
              </div>
            ) : copies.length === 0 ? (
              <p className="text-xs text-muted-foreground py-2">자동 카피 후보가 없습니다. 직접 입력해 주세요.</p>
            ) : (
              copies.map((c, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => chooseCopy(idx)}
                  className={cn(
                    "w-full text-left rounded-lg border p-3 transition-colors",
                    copyChoice === idx
                      ? "border-violet-400 bg-violet-50 dark:bg-violet-950/40 ring-1 ring-violet-300"
                      : "hover:border-violet-300"
                  )}
                >
                  <div className="flex items-start gap-2">
                    <span className={cn(
                      "shrink-0 mt-0.5 h-3.5 w-3.5 rounded-full border-2",
                      copyChoice === idx ? "border-violet-600 bg-violet-600" : "border-border"
                    )} />
                    <div className="min-w-0">
                      <p className="text-sm font-medium leading-snug">{c.headline_copy}</p>
                      {c.sub_copy && <p className="text-xs text-muted-foreground mt-0.5">{c.sub_copy}</p>}
                      <span className="inline-block mt-1.5 text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground uppercase">
                        {c.source === "external_imported" ? "외부" : "AI"}
                      </span>
                    </div>
                  </div>
                </button>
              ))
            )}

            {/* 직접 입력 */}
            <div className={cn(
              "rounded-lg border p-3 space-y-2 transition-colors",
              copyChoice === "manual" ? "border-violet-400 bg-violet-50 dark:bg-violet-950/40 ring-1 ring-violet-300" : ""
            )}>
              <button
                type="button"
                onClick={() => chooseCopy("manual")}
                className="flex items-center gap-2 text-xs font-medium"
              >
                <span className={cn(
                  "h-3.5 w-3.5 rounded-full border-2",
                  copyChoice === "manual" ? "border-violet-600 bg-violet-600" : "border-border"
                )} />
                직접 입력
              </button>
              <input
                type="text"
                value={manualHeadline}
                onChange={(e) => { setManualHeadline(e.target.value); if (copyChoice === "manual") update({ headline_copy: e.target.value || null }) }}
                onFocus={() => chooseCopy("manual")}
                placeholder="헤드라인 카피"
                className="w-full px-2.5 py-1.5 border rounded-md bg-background text-xs focus:outline-none focus:ring-2 focus:ring-primary/30"
              />
              <input
                type="text"
                value={manualSub}
                onChange={(e) => { setManualSub(e.target.value); if (copyChoice === "manual") update({ sub_copy: e.target.value || null }) }}
                onFocus={() => chooseCopy("manual")}
                placeholder="보조 카피 (선택)"
                className="w-full px-2.5 py-1.5 border rounded-md bg-background text-xs focus:outline-none focus:ring-2 focus:ring-primary/30"
              />
            </div>
          </div>
        </div>

        {/* 중 — 매칭 콘텐츠 */}
        <div className="rounded-xl border bg-card shadow-sm">
          <div className="px-4 py-3 border-b flex items-center justify-between">
            <h2 className="text-sm font-semibold">
              매칭 콘텐츠
              <span className="ml-2 text-xs text-muted-foreground font-normal">
                ({matches.length})
              </span>
            </h2>
            <span className="text-xs text-muted-foreground">선택 {selectedIds.size}개</span>
          </div>
          <div className="p-2 max-h-[480px] overflow-y-auto">
            {matchLoading ? (
              <div className="flex items-center justify-center py-16 text-muted-foreground text-xs">
                <RefreshCw className="h-4 w-4 animate-spin mr-1.5" /> 콘텐츠 매칭 중...
              </div>
            ) : matches.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center text-muted-foreground">
                <p className="text-sm">매칭된 콘텐츠가 없습니다.</p>
                <button onClick={onBack} className="text-xs text-violet-600 hover:underline mt-1">
                  외부 참고·테마 조건 완화하기
                </button>
              </div>
            ) : (
              <ul className="divide-y">
                {matches.map((m) => {
                  const checked = selectedIds.has(m.content_id)
                  const isFocus = focusId === m.content_id
                  return (
                    <li
                      key={m.content_id}
                      onClick={() => setFocusId(m.content_id)}
                      className={cn(
                        "flex items-center gap-2.5 px-2 py-2 cursor-pointer transition-colors rounded-md",
                        isFocus ? "bg-violet-50 dark:bg-violet-950/30" : "hover:bg-accent/40"
                      )}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleContent(m.content_id)}
                        onClick={(e) => e.stopPropagation()}
                        className="rounded shrink-0"
                      />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm truncate">{m.title}</p>
                        <p className="text-xs text-muted-foreground">
                          {m.content_type} · {m.production_year ?? "-"}
                        </p>
                      </div>
                      <span className="shrink-0 text-xs font-mono text-violet-600 dark:text-violet-400">
                        {m.score.toFixed(2)}
                      </span>
                    </li>
                  )
                })}
              </ul>
            )}
          </div>
        </div>

        {/* 우 — 추천 근거 */}
        <div className="rounded-xl border bg-card shadow-sm">
          <div className="px-4 py-3 border-b">
            <h2 className="text-sm font-semibold">AI 추천 근거</h2>
          </div>
          <div className="p-4">
            {!focused ? (
              <p className="text-xs text-muted-foreground py-8 text-center">
                콘텐츠를 선택하면 추천 근거가 표시됩니다.
              </p>
            ) : (
              <div className="space-y-3">
                <p className="text-sm font-medium">{focused.title}</p>
                <div className="space-y-2.5">
                  {SCORE_DIMENSIONS.map((d) => (
                    <ScoreBar
                      key={d.key}
                      label={d.label}
                      value={focused.score_breakdown[d.key] ?? 0}
                      weight={d.weight}
                    />
                  ))}
                </div>
                <div className="border-t pt-3 flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">최종 점수</span>
                  <span className="font-semibold text-sm">{focused.score.toFixed(2)}</span>
                </div>
                <div className="flex gap-0.5">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <Star
                      key={i}
                      className={cn(
                        "h-4 w-4",
                        i < Math.round(focused.score * 5)
                          ? "fill-violet-500 text-violet-500"
                          : "text-muted"
                      )}
                    />
                  ))}
                </div>
                <button
                  type="button"
                  onClick={() => toggleContent(focused.content_id)}
                  className={cn(
                    "w-full mt-1 py-2 rounded-lg text-xs font-medium transition-colors",
                    selectedIds.has(focused.content_id)
                      ? "bg-violet-100 text-violet-700 dark:bg-violet-900 dark:text-violet-200"
                      : "bg-primary text-primary-foreground hover:bg-primary/90"
                  )}
                >
                  {selectedIds.has(focused.content_id) ? "✓ 선택됨 — 해제" : "+ 선택"}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* SaveBar */}
      <div className="rounded-xl border bg-card shadow-sm p-4 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={onBack}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg border bg-background text-sm hover:bg-accent transition-colors"
        >
          <ArrowLeft className="h-4 w-4" /> 이전
        </button>

        <select
          value={platform}
          onChange={(e) => setPlatform(e.target.value)}
          className="px-3 py-2 border rounded-lg bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
        >
          {["ott", "iptv", "mobile", "web"].map((p) => <option key={p} value={p}>{p}</option>)}
        </select>

        <input
          type="text"
          value={name}
          onChange={(e) => { setName(e.target.value); update({ name: e.target.value }) }}
          placeholder="큐레이션 이름 *"
          className="flex-1 min-w-[160px] px-3 py-2 border rounded-lg bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
        />

        {error && <span className="text-xs text-destructive w-full sm:w-auto">{error}</span>}

        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          <Save className="h-4 w-4" />
          {saving ? "저장 중..." : "저장"}
        </button>
      </div>
    </div>
  )
}

// ── AiWizard (진입) ───────────────────────────────────────────

export function AiWizard() {
  const router = useRouter()
  const params = useSearchParams()
  const [draft, update, reset] = useDraft()

  const rawStep = Number(params.get("step") ?? "1")
  const step = Math.min(Math.max(Number.isFinite(rawStep) ? rawStep : 1, 1), MAX_IMPLEMENTED_STEP)

  const goStep = (n: number) => {
    router.replace(`/programming/categories/new?mode=ai&step=${n}`)
  }

  const handleCancel = () => {
    if (confirm("작성 중인 내용을 버리고 목록으로 돌아갈까요?")) {
      reset()
      router.push("/programming/categories")
    }
  }

  const handleSaved = (categoryId: number) => {
    reset()
    router.push(`/programming/categories/${categoryId}`)
  }

  return (
    <div className={cn("mx-auto", step === 3 ? "max-w-[1400px]" : "max-w-3xl")}>
      <Link
        href="/programming/categories"
        className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground mb-6 transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        AI 큐레이션
      </Link>

      <div className="flex items-center gap-3 mb-6">
        <div className="p-2 rounded-lg bg-violet-100 dark:bg-violet-900">
          <Sparkles className="h-5 w-5 text-violet-600 dark:text-violet-300" />
        </div>
        <div>
          <h1 className="text-xl font-semibold">새 큐레이션 — AI 제안</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            테마 특징을 설정하면 AI가 카피와 콘텐츠를 제안합니다.
          </p>
        </div>
      </div>

      <div className="mb-6">
        <Stepper current={step} />
      </div>

      {step === 1 && <Step1Features draft={draft} update={update} />}
      {step === 2 && <Step2ExternalRefs draft={draft} update={update} />}
      {step === 3 && (
        <Step3Workbench
          draft={draft}
          update={update}
          onBack={() => goStep(2)}
          onSaved={handleSaved}
        />
      )}

      {/* Step 1·2 네비 푸터 (Step 3은 자체 SaveBar) */}
      {step < 3 && (
        <div className="flex items-center justify-between mt-6">
          <button
            type="button"
            onClick={step === 1 ? handleCancel : () => goStep(step - 1)}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg border bg-background text-sm hover:bg-accent transition-colors"
          >
            {step === 1 ? "취소" : <><ArrowLeft className="h-4 w-4" />이전</>}
          </button>
          <button
            type="button"
            onClick={() => goStep(step + 1)}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            다음
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  )
}
