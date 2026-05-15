"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { ArrowLeft, Info } from "lucide-react"
import { ContentForm, type ContentFormData } from "@/components/contents/ContentForm"
import { metadataApi } from "@/lib/api"

export default function EditContentPage() {
  const { id } = useParams<{ id: string }>()
  const contentId = Number(id)

  const [initialData, setInitialData] = useState<Partial<ContentFormData> | null>(null)
  const [title, setTitle] = useState("")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      try {
        const content = await metadataApi.getContent(contentId)
        setTitle(content.title)

        // credits → cast/directors 문자열로 변환
        const cast = content.credits
          ?.filter((c: { role: string }) => c.role === "actor")
          .map((c: { person: { name_ko: string } }) => c.person.name_ko)
          .join(", ") ?? ""
        const directors = content.credits
          ?.filter((c: { role: string }) => c.role === "director")
          .map((c: { person: { name_ko: string } }) => c.person.name_ko)
          .join(", ") ?? ""

        // genres → 문자열로 변환
        const genres = content.genres
          ?.map((g: { genre: { name_ko: string } }) => g.genre?.name_ko)
          .filter(Boolean)
          .join(", ") ?? ""

        const meta = content.metadata_record
        setInitialData({
          title: content.title,
          content_type: content.content_type,
          cp_name: content.cp_name ?? "",
          production_year: content.production_year ?? undefined,
          synopsis: meta?.cp_synopsis ?? meta?.ai_synopsis ?? "",
          cast,
          directors,
          genres,
          country: content.country ?? "",
          runtime: content.runtime_minutes ?? undefined,
          poster_url: content.poster_url ?? "",
        })
      } catch {
        setError("콘텐츠를 불러오지 못했습니다")
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [contentId])

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <div className="flex items-center gap-3 mb-6">
        <Link href={`/programming/contents/${id}`} className="p-1.5 rounded-lg hover:bg-accent transition-colors">
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div>
          <h1 className="text-xl font-bold">콘텐츠 수정</h1>
          <p className="text-sm text-muted-foreground truncate max-w-xs">{title || `#${id}`}</p>
        </div>
      </div>

      {/* 안내 메시지 */}
      <div className="mb-6 px-4 py-3 rounded-lg bg-blue-50 border border-blue-200 flex items-start gap-2">
        <Info className="h-4 w-4 text-blue-600 mt-0.5 shrink-0" />
        <p className="text-sm text-blue-700">
          수정 내용은 <strong>manual(최우선)</strong> 소스로 저장됩니다.
          TMDB·KOBIS 자동 동기화보다 우선 적용됩니다.
        </p>
      </div>

      {loading && (
        <div className="text-center py-16 text-muted-foreground text-sm">불러오는 중...</div>
      )}
      {error && (
        <div className="text-center py-16 text-destructive text-sm">{error}</div>
      )}
      {initialData && !loading && (
        <ContentForm contentId={contentId} initialData={initialData} />
      )}
    </div>
  )
}
