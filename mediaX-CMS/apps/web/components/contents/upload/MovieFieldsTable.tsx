"use client"

import { useState } from "react"

const FIELD_DESCRIPTIONS_MOVIE = [
  { field: "title", required: "필수" as const, desc: "영화 제목" },
  { field: "content_type", required: "필수" as const, desc: "고정값 movie" },
  { field: "cp_name", required: "필수" as const, desc: "CP사명" },
  { field: "production_year", required: "선택" as const, desc: "제작년도 (숫자)" },
  { field: "runtime", required: "선택" as const, desc: "런타임 (분, 양수)" },
  { field: "synopsis", required: "선택" as const, desc: "줄거리" },
  { field: "cast", required: "선택" as const, desc: "출연진 (쉼표 구분)" },
  { field: "directors", required: "선택" as const, desc: "감독 (쉼표 구분)" },
  { field: "genres", required: "선택" as const, desc: "장르 (쉼표 구분)" },
  { field: "country", required: "선택" as const, desc: "제작국가" },
  { field: "rating_age", required: "선택" as const, desc: "시청등급" },
  { field: "poster_url", required: "선택" as const, desc: "포스터 이미지 URL" },
]

const INITIAL_COUNT = 4

export function MovieFieldsTable() {
  const [expanded, setExpanded] = useState(false)
  const visible = expanded ? FIELD_DESCRIPTIONS_MOVIE : FIELD_DESCRIPTIONS_MOVIE.slice(0, INITIAL_COUNT)
  const remaining = FIELD_DESCRIPTIONS_MOVIE.length - INITIAL_COUNT

  return (
    <div>
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-border">
            <th className="py-2 text-left font-medium text-muted-foreground">필드명</th>
            <th className="py-2 text-left font-medium text-muted-foreground w-16">필수</th>
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
          className="mt-2 text-xs text-primary hover:underline"
        >
          {remaining}개 더 보기 ▼
        </button>
      )}
    </div>
  )
}
