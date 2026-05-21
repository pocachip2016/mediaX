import type { FieldRecommendation, RecommendationsOut } from "@/lib/api"

export type FieldKind = "confirmed" | "auto" | "conflict" | "missing"

// 값 normalize — 구분자(/ , | ·) 통일 + trim + lowercase
export function tokenize(s: string): Set<string> {
  return new Set(
    s.split(/[\/,|·]/)
      .map((x) => x.trim().toLowerCase())
      .filter(Boolean)
  )
}

export function isSimilar(a: string | null | undefined, b: string | null | undefined): boolean {
  if (a == null || b == null) return false
  const sa = tokenize(String(a))
  const sb = tokenize(String(b))
  if (sa.size === 0 || sb.size === 0) return false
  if (sa.size !== sb.size) return false
  for (const x of sa) if (!sb.has(x)) return false
  return true
}

// rec의 top value가 현재값과 유사한지 (개별 적용 불필요 판단용)
export function isRecSimilarToCurrent(rec: FieldRecommendation, currentValue: string | null | undefined): boolean {
  const top = rec.ai_synthesis ?? rec.recommendations[0]
  if (!top) return false
  return isSimilar(top.value, currentValue)
}

export function classifyField(rec: FieldRecommendation | null): FieldKind {
  if (rec === null) return "missing"
  if (rec.status === "conflict") return "conflict"
  if (
    rec.status === "auto" &&
    rec.recommendations.length >= 2 &&
    Math.min(...rec.recommendations.map((r) => r.confidence)) >= 0.9
  ) {
    return "confirmed"
  }
  return "auto"
}

export function reasonSummary(rec: FieldRecommendation): string {
  const kind = classifyField(rec)
  if (kind === "confirmed") {
    const sources = rec.recommendations.map((r) => r.source_type.toUpperCase()).join("+")
    const minConf = Math.min(...rec.recommendations.map((r) => r.confidence))
    return `${sources} 일치 ${minConf.toFixed(2)}`
  }
  if (kind === "conflict") {
    return `소스 충돌 — ${rec.recommendations.length}개 소스 불일치`
  }
  const top = rec.recommendations[0]
  if (top) return `${top.source_type.toUpperCase()} ${top.confidence.toFixed(2)}`
  return "추천 없음"
}

export function avgConfidence(recs: FieldRecommendation[]): number {
  const all = recs.flatMap((r) => r.recommendations.map((s) => s.confidence))
  if (all.length === 0) return 0
  return all.reduce((a, b) => a + b, 0) / all.length
}

export function summarizeByKind(
  recommendations: RecommendationsOut,
  appliedFields: Set<string>,
  currentValuesByField?: Record<string, string | null | undefined>
): { confirmed: string[]; auto: string[]; conflict: string[]; missing: string[] } {
  const confirmed: string[] = []
  const auto: string[] = []
  const conflict: string[] = []

  const similar = (rec: FieldRecommendation) =>
    currentValuesByField ? isRecSimilarToCurrent(rec, currentValuesByField[rec.field]) : false

  for (const rec of recommendations.auto_fill) {
    if (appliedFields.has(rec.field) || similar(rec)) { confirmed.push(rec.field); continue }
    const kind = classifyField(rec)
    if (kind === "confirmed") confirmed.push(rec.field)
    else auto.push(rec.field)
  }
  for (const rec of recommendations.conflicts) {
    if (appliedFields.has(rec.field) || similar(rec)) { confirmed.push(rec.field); continue }
    conflict.push(rec.field)
  }

  return { confirmed, auto, conflict, missing: [...recommendations.missing_fields] }
}

export function getReturnPath(
  searchParams: { get(name: string): string | null }
): "list" | "review" | "edit" {
  const r = searchParams.get("return")
  if (r === "review" || r === "edit") return r
  return "list"
}

export function getReturnHref(returnPath: "list" | "review" | "edit", contentId?: number): { label: string; href: string } {
  if (returnPath === "review") return { label: "← Review Queue로", href: "/programming/contents/review" }
  if (returnPath === "edit" && contentId) return { label: "← 편집으로", href: `/programming/contents/${contentId}/edit` }
  return { label: "← 콘텐츠 목록으로", href: "/programming/contents" }
}
