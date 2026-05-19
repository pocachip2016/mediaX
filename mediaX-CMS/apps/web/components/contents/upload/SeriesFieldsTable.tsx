"use client"

import { useState } from "react"

const FIELD_DESCRIPTIONS_SERIES = [
  { field: "series_title", required: "필수" as const, desc: "그룹 키 — 같은 시리즈는 같은 값" },
  { field: "content_type", required: "필수" as const, desc: "series / season / episode 중 하나" },
  { field: "cp_name", required: "필수" as const, desc: "CP사명" },
  { field: "season_number", required: "조건부" as const, desc: "season · episode 행일 때 필수" },
  { field: "episode_number", required: "조건부" as const, desc: "episode 행일 때 필수" },
  { field: "title", required: "선택" as const, desc: "노드 제목 (생략 시 자동)" },
  { field: "production_year", required: "선택" as const, desc: "제작년도 — 비우면 series에서 상속" },
  { field: "synopsis", required: "선택" as const, desc: "줄거리 — 비우면 series에서 상속" },
  { field: "genres", required: "선택" as const, desc: "장르 — 비우면 series에서 상속" },
  { field: "poster_url", required: "선택" as const, desc: "포스터 URL — 비우면 series에서 상속" },
  { field: "country", required: "선택" as const, desc: "제작국가" },
  { field: "cast", required: "선택" as const, desc: "출연진 (쉼표 구분)" },
  { field: "directors", required: "선택" as const, desc: "감독 (쉼표 구분)" },
  { field: "rating_age", required: "선택" as const, desc: "시청등급" },
  { field: "runtime", required: "선택" as const, desc: "런타임 (분) — episode에만 의미있음" },
]

const INITIAL_COUNT = 5

export function SeriesFieldsTable() {
  const [expanded, setExpanded] = useState(false)
  const visible = expanded ? FIELD_DESCRIPTIONS_SERIES : FIELD_DESCRIPTIONS_SERIES.slice(0, INITIAL_COUNT)
  const remaining = FIELD_DESCRIPTIONS_SERIES.length - INITIAL_COUNT

  return (
    <div className="space-y-3">
      <div className="rounded-lg bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 p-3 space-y-1 text-xs text-blue-800 dark:text-blue-200">
        <p>💡 <strong>series_title</strong> 으로 그룹핑됨 — 같은 시리즈는 같은 값</p>
        <p>💡 행 패턴: season_number·episode_number 모두 비움 → <strong>series</strong> 노드 / season_number만 → <strong>season</strong> 노드 / 둘 다 채움 → <strong>episode</strong> 노드</p>
        <p>💡 synopsis·genres·poster_url 등을 비워두면 series → season → episode 로 자동 상속</p>
      </div>
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-border">
            <th className="py-2 text-left font-medium text-muted-foreground">필드명</th>
            <th className="py-2 text-left font-medium text-muted-foreground w-20">필수</th>
            <th className="py-2 text-left font-medium text-muted-foreground">설명</th>
          </tr>
        </thead>
        <tbody>
          {visible.map(f => (
            <tr key={f.field} className="border-b border-border last:border-0">
              <td className="py-2 font-mono text-primary">{f.field}</td>
              <td className="py-2">
                {f.required === "필수" ? (
                  <span className="text-destructive font-medium">필수</span>
                ) : f.required === "조건부" ? (
                  <span className="text-amber-600 font-medium">조건부</span>
                ) : (
                  <span className="text-muted-foreground">선택</span>
                )}
              </td>
              <td className="py-2 text-muted-foreground">{f.desc}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {!expanded && (
        <button
          type="button"
          onClick={() => setExpanded(true)}
          className="text-xs text-primary hover:underline"
        >
          {remaining}개 더 보기 ▼
        </button>
      )}
    </div>
  )
}
