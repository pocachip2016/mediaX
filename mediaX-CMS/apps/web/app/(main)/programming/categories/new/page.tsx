"use client"

import { Suspense, useState } from "react"
import { useSearchParams, useRouter } from "next/navigation"
import Link from "next/link"
import { ArrowLeft, Hand, RefreshCw } from "lucide-react"
import { distributionApi } from "@/lib/api"
import { AiWizard } from "./_wizard"
import { ExternalImport } from "./_external"

// ── 상수 ──────────────────────────────────────────────────────

const PLATFORM_OPTIONS = ["ott", "iptv", "mobile", "web"]
const CATEGORY_TYPE_OPTIONS = [
  "recommendation",
  "ranking",
  "genre",
  "mood",
  "new_release",
  "event",
]

// ── 수동 생성 폼 ───────────────────────────────────────────────

function ManualCreateForm() {
  const router = useRouter()
  const [name, setName]                 = useState("")
  const [headlineCopy, setHeadlineCopy] = useState("")
  const [subCopy, setSubCopy]           = useState("")
  const [platform, setPlatform]         = useState("ott")
  const [categoryType, setCategoryType] = useState("recommendation")
  const [isActive, setIsActive]         = useState(true)
  const [isDraft, setIsDraft]           = useState(false)
  const [submitting, setSubmitting]     = useState(false)
  const [error, setError]               = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) {
      setError("이름은 필수입니다.")
      return
    }
    setError(null)
    setSubmitting(true)
    try {
      const created = await distributionApi.createCategory({
        name: name.trim(),
        headline_copy: headlineCopy.trim() || null,
        sub_copy: subCopy.trim() || null,
        platform,
        category_type: categoryType,
        source_mode: "manual",
        is_active: isActive,
        is_draft: isDraft,
        position: 0,
      })
      router.push(`/programming/categories/${created.id}`)
    } catch (err) {
      console.error("[manual-create] API 실패", err)
      setError("저장 중 오류가 발생했습니다. 다시 시도해주세요.")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="max-w-xl mx-auto">
      <Link
        href="/programming/categories"
        className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground mb-6 transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        큐레이션 목록
      </Link>

      <div className="flex items-center gap-3 mb-6">
        <div className="p-2 rounded-lg bg-muted">
          <Hand className="h-5 w-5 text-muted-foreground" />
        </div>
        <div>
          <h1 className="text-xl font-semibold">새 큐레이션 — 수동 묶기</h1>
          <p className="text-xs text-muted-foreground mt-0.5">기본 정보를 입력 후 콘텐츠를 묶어보세요.</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border bg-card p-6 shadow-sm">
        {/* 이름 */}
        <div className="space-y-1.5">
          <label className="text-sm font-medium">
            이름 <span className="text-destructive">*</span>
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="예: 주말 영화 추천"
            className="w-full px-3 py-2 border rounded-lg bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
        </div>

        {/* 헤드라인 카피 */}
        <div className="space-y-1.5">
          <label className="text-sm font-medium">헤드라인 카피</label>
          <input
            type="text"
            value={headlineCopy}
            onChange={(e) => setHeadlineCopy(e.target.value)}
            placeholder="예: 퇴근 후 90분의 위로"
            className="w-full px-3 py-2 border rounded-lg bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
        </div>

        {/* 보조 카피 */}
        <div className="space-y-1.5">
          <label className="text-sm font-medium">보조 카피</label>
          <input
            type="text"
            value={subCopy}
            onChange={(e) => setSubCopy(e.target.value)}
            placeholder="예: 오늘 저녁을 채울 딱 맞는 영화"
            className="w-full px-3 py-2 border rounded-lg bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
        </div>

        {/* 플랫폼 + 유형 */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label className="text-sm font-medium">
              플랫폼 <span className="text-destructive">*</span>
            </label>
            <select
              value={platform}
              onChange={(e) => setPlatform(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
            >
              {PLATFORM_OPTIONS.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">
              유형 <span className="text-destructive">*</span>
            </label>
            <select
              value={categoryType}
              onChange={(e) => setCategoryType(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
            >
              {CATEGORY_TYPE_OPTIONS.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
        </div>

        {/* 활성 / 임시저장 */}
        <div className="flex items-center gap-6">
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
              className="rounded"
            />
            활성
          </label>
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={isDraft}
              onChange={(e) => setIsDraft(e.target.checked)}
              className="rounded"
            />
            임시저장
          </label>
        </div>

        {/* 에러 */}
        {error && (
          <p className="text-sm text-destructive">{error}</p>
        )}

        {/* 버튼 */}
        <div className="flex justify-end gap-3 pt-2">
          <Link
            href="/programming/categories"
            className="px-4 py-2 rounded-lg border bg-background text-sm hover:bg-accent transition-colors"
          >
            취소
          </Link>
          <button
            type="submit"
            disabled={submitting}
            className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
          >
            {submitting ? "저장 중..." : "만들기"}
          </button>
        </div>
      </form>
    </div>
  )
}

// ── 진입 컴포넌트 ──────────────────────────────────────────────

function NewCategoryContent() {
  const params = useSearchParams()
  const mode = params.get("mode") ?? "manual"

  if (mode === "manual") return <ManualCreateForm />
  if (mode === "ai") return <AiWizard />
  if (mode === "external") return <ExternalImport />
  return <ManualCreateForm />
}

function PageLoading() {
  return (
    <div className="flex items-center justify-center min-h-[40vh] text-muted-foreground">
      <RefreshCw className="h-5 w-5 animate-spin mr-2" />
      불러오는 중...
    </div>
  )
}

export default function NewCategoryPage() {
  return (
    <Suspense fallback={<PageLoading />}>
      <NewCategoryContent />
    </Suspense>
  )
}
