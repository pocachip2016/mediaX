"use client"

interface ThreeColumnShellProps {
  poster: React.ReactNode
  /** edit 모드: alignedFields 사용 → 2컬럼(poster+fieldRows) */
  alignedFields?: React.ReactNode
  /** review 모드: current+right 사용 → 3컬럼 */
  current?: React.ReactNode
  right?: React.ReactNode
  footer?: React.ReactNode
}

export function ThreeColumnShell({ poster, alignedFields, current, right, footer }: ThreeColumnShellProps) {
  return (
    <div className="p-6 max-w-[1600px] mx-auto space-y-4">
      {alignedFields != null ? (
        <div className="grid grid-cols-[200px_1fr] gap-4 items-start">
          <div>{poster}</div>
          <div>{alignedFields}</div>
        </div>
      ) : (
        <div className="grid grid-cols-[200px_1fr_1fr] gap-4 items-start">
          <div>{poster}</div>
          <div>{current}</div>
          <div>{right}</div>
        </div>
      )}
      {footer && <div>{footer}</div>}
    </div>
  )
}
