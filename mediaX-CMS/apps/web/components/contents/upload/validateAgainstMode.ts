export type TemplateMode = "movie" | "series" | null

interface PreviewRow {
  [key: string]: string
}

export interface ValidationResult {
  modeMismatch: boolean
  mismatchReasons: string[]
  rowOk: boolean[]
  rowErrors: string[][]
}

export function validateAgainstMode(
  headers: string[],
  rows: PreviewRow[],
  mode: TemplateMode,
): ValidationResult {
  const empty: ValidationResult = {
    modeMismatch: false,
    mismatchReasons: [],
    rowOk: rows.map(() => true),
    rowErrors: rows.map(() => []),
  }
  if (!mode) return empty

  const mismatchReasons: string[] = []

  if (mode === "series" && !headers.includes("series_title")) {
    mismatchReasons.push(
      "series_title 컬럼이 없습니다. Movie 템플릿을 Series 모드로 업로드 중일 수 있습니다.",
    )
  }
  if (mode === "movie" && headers.includes("series_title")) {
    mismatchReasons.push(
      "series_title 컬럼이 감지됩니다. Series 템플릿을 Movie 모드로 업로드 중일 수 있습니다.",
    )
  }

  if (mismatchReasons.length > 0) {
    return { modeMismatch: true, mismatchReasons, rowOk: [], rowErrors: [] }
  }

  const rowOk: boolean[] = []
  const rowErrors: string[][] = []

  for (const row of rows) {
    const errors: string[] = []
    if (mode === "series") {
      if (!row["series_title"]) errors.push("series_title 필수")
      const ct = row["content_type"] ?? ""
      if (ct === "season" && !row["season_number"]) {
        errors.push("season_number 필수 (season 행)")
      }
      if (ct === "episode") {
        if (!row["season_number"]) errors.push("season_number 필수 (episode 행)")
        if (!row["episode_number"]) errors.push("episode_number 필수 (episode 행)")
      }
    }
    rowOk.push(errors.length === 0)
    rowErrors.push(errors)
  }

  return { modeMismatch: false, mismatchReasons: [], rowOk, rowErrors }
}
