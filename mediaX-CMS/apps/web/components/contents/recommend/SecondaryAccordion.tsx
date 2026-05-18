"use client"

import { useState } from "react"
import { ChevronRight, Users, Link2, Bot } from "lucide-react"
import { cn } from "@workspace/ui/lib/utils"
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from "@workspace/ui/components/collapsible"
import type { ContentDetail, ContentCreditOut } from "@/lib/api"

const CAST_ROLES = new Set(["actor", "cast", "주연", "출연", "조연", "단역", "특별출연", "카메오"])
const DIRECTOR_ROLES = new Set(["director", "감독", "연출"])

interface Props {
  content: ContentDetail
}

interface SectionProps {
  icon: typeof Users
  title: string
  count: number | null
  defaultOpen?: boolean
  children: React.ReactNode
}

function Section({ icon: Icon, title, count, defaultOpen = false, children }: SectionProps) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger className="w-full flex items-center gap-2 px-4 py-3 hover:bg-slate-50 transition-colors">
        <ChevronRight
          className={cn("h-4 w-4 text-slate-400 transition-transform", open && "rotate-90")}
        />
        <Icon className="h-4 w-4 text-slate-500" />
        <span className="text-sm font-medium text-slate-700">{title}</span>
        {count !== null && (
          <span className="text-xs text-slate-400">({count})</span>
        )}
      </CollapsibleTrigger>
      <CollapsibleContent className="px-4 pb-4 text-sm text-slate-600">
        {children}
      </CollapsibleContent>
    </Collapsible>
  )
}

function EmptyMessage() {
  return <p className="text-xs text-slate-400 py-2">표시할 정보가 없습니다.</p>
}

function CreditsSection({ credits }: { credits: ContentCreditOut[] }) {
  const directors = credits.filter((c) => DIRECTOR_ROLES.has(c.role.toLowerCase()))
  const cast = credits
    .filter((c) => CAST_ROLES.has(c.role.toLowerCase()))
    .sort((a, b) => (a.cast_order ?? 9999) - (b.cast_order ?? 9999))
  const others = credits.filter(
    (c) => !DIRECTOR_ROLES.has(c.role.toLowerCase()) && !CAST_ROLES.has(c.role.toLowerCase())
  )

  if (credits.length === 0) return <EmptyMessage />

  return (
    <div className="pt-1 space-y-3">
      {directors.length > 0 && (
        <div>
          <div className="text-xs font-medium text-slate-500 mb-1">감독 · 연출</div>
          <ul className="space-y-0.5 pl-2">
            {directors.map((c) => (
              <li key={c.id} className="text-sm">
                {c.person.name_ko}
                {c.person.name_en && <span className="text-slate-400 ml-1">({c.person.name_en})</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
      {cast.length > 0 && (
        <div>
          <div className="text-xs font-medium text-slate-500 mb-1">출연진</div>
          <ul className="space-y-0.5 pl-2">
            {cast.map((c) => (
              <li key={c.id} className="text-sm">
                <span className="text-slate-700">{c.person.name_ko}</span>
                {c.character_name && (
                  <span className="text-slate-500"> — {c.character_name} 역</span>
                )}
                {c.cast_order !== null && (
                  <span className="text-xs text-slate-400 ml-2">#{c.cast_order}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
      {others.length > 0 && (
        <div>
          <div className="text-xs font-medium text-slate-500 mb-1">기타</div>
          <ul className="space-y-0.5 pl-2">
            {others.map((c) => (
              <li key={c.id} className="text-sm">
                {c.person.name_ko}
                <span className="text-xs text-slate-400 ml-2">({c.role})</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function ExternalSourcesSection({ sources }: { sources: ContentDetail["external_sources"] }) {
  if (sources.length === 0) return <EmptyMessage />
  return (
    <div className="pt-1">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-slate-500 border-b border-slate-200">
            <th className="text-left py-2 font-medium">소스</th>
            <th className="text-left py-2 font-medium">External ID</th>
            <th className="text-left py-2 font-medium">연동 시각</th>
          </tr>
        </thead>
        <tbody>
          {sources.map((s) => (
            <tr key={s.id} className="border-b border-slate-100 last:border-b-0">
              <td className="py-1.5 uppercase font-medium text-slate-700">{s.source_type}</td>
              <td className="py-1.5 text-slate-600">{s.external_id ?? "—"}</td>
              <td className="py-1.5 text-slate-500 text-xs">
                {s.fetched_at ? new Date(s.fetched_at).toLocaleString("ko-KR") : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function AIHistorySection({ meta }: { meta: ContentDetail["metadata_record"] }) {
  if (!meta) return <EmptyMessage />
  const hasAnyAI =
    meta.ai_synopsis ||
    meta.ai_genre_primary ||
    meta.ai_genre_secondary ||
    (meta.ai_mood_tags && meta.ai_mood_tags.length > 0) ||
    meta.ai_rating_suggestion ||
    meta.ai_processed_at
  if (!hasAnyAI) return <EmptyMessage />

  return (
    <div className="pt-1 space-y-3">
      <div className="flex gap-4 text-xs">
        <div>
          <span className="text-slate-500">처리 시각: </span>
          <span className="text-slate-700">
            {meta.ai_processed_at ? new Date(meta.ai_processed_at).toLocaleString("ko-KR") : "—"}
          </span>
        </div>
        <div>
          <span className="text-slate-500">품질 점수: </span>
          <span className="text-slate-700 font-medium">
            {meta.quality_score ? meta.quality_score.toFixed(1) : "—"}
          </span>
        </div>
      </div>

      {meta.ai_synopsis && (
        <div>
          <div className="text-xs font-medium text-slate-500 mb-1">AI 시놉시스</div>
          <p className="text-sm text-slate-600 leading-relaxed whitespace-pre-wrap">
            {meta.ai_synopsis}
          </p>
        </div>
      )}

      {(meta.ai_genre_primary || meta.ai_genre_secondary) && (
        <div>
          <div className="text-xs font-medium text-slate-500 mb-1">AI 장르</div>
          <div className="text-sm text-slate-600">
            {meta.ai_genre_primary}
            {meta.ai_genre_secondary && (
              <span className="text-slate-400 ml-2">· {meta.ai_genre_secondary}</span>
            )}
          </div>
        </div>
      )}

      {meta.ai_mood_tags && meta.ai_mood_tags.length > 0 && (
        <div>
          <div className="text-xs font-medium text-slate-500 mb-1">AI 무드 태그</div>
          <div className="flex flex-wrap gap-1.5">
            {meta.ai_mood_tags.map((tag, i) => (
              <span
                key={i}
                className="px-2 py-0.5 text-xs rounded bg-slate-100 text-slate-600"
              >
                {tag}
              </span>
            ))}
          </div>
        </div>
      )}

      {meta.ai_rating_suggestion && (
        <div>
          <div className="text-xs font-medium text-slate-500 mb-1">추천 등급</div>
          <div className="text-sm text-slate-600">{meta.ai_rating_suggestion}</div>
        </div>
      )}

      {meta.score_breakdown && Object.keys(meta.score_breakdown).length > 0 && (
        <div>
          <div className="text-xs font-medium text-slate-500 mb-1">스코어 분해</div>
          <ul className="text-xs text-slate-600 space-y-0.5 pl-2">
            {Object.entries(meta.score_breakdown).map(([k, v]) => (
              <li key={k}>
                <span className="text-slate-500">{k}:</span> {v}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

export function SecondaryAccordion({ content }: Props) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 divide-y divide-slate-200">
      <Section icon={Users} title="출연진·제작진" count={content.credits.length}>
        <CreditsSection credits={content.credits} />
      </Section>
      <Section icon={Link2} title="외부 소스" count={content.external_sources.length}>
        <ExternalSourcesSection sources={content.external_sources} />
      </Section>
      <Section icon={Bot} title="AI 처리 이력" count={null}>
        <AIHistorySection meta={content.metadata_record} />
      </Section>
    </div>
  )
}
