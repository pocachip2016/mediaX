import type { AiReviewQueueRow } from "./api"

export type BulkGuardResult =
  | { allowed: true }
  | { allowed: false; violatingIds: number[] }

export function checkBulkApplyGuard(rows: AiReviewQueueRow[]): BulkGuardResult {
  if (rows.length === 0) return { allowed: false, violatingIds: [] }
  const violating = rows.filter(
    r =>
      r.metadata_status !== "clean" ||
      r.poster_status !== "poster_ok" ||
      r.risk_level !== "low"
  )
  if (violating.length === 0) return { allowed: true }
  return { allowed: false, violatingIds: violating.map(r => r.content_id) }
}
